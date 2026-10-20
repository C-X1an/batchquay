"""Fail-closed full-release evidence verification.

The evidence hashes checked here are local integrity bindings, not signatures or
third-party attestation. Release eligibility additionally requires an actual
source-bound independent-review artifact and criterion-specific semantic data.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from scripts import evidence
from scripts.execution import MAKE_PROGRAMS, PYTHON_PROGRAMS, RECIPE_VARIABLES, valid_assignment

ROOT = Path(__file__).resolve().parents[1]
STATUS = Path("verification/criterion_status.json")
MAPPING = Path("verification/criterion_evidence_map.json")
ACCEPTANCE = Path("verification/acceptance.json")
EXCEPTION = Path("TEST_SPEC_EXCEPTION_TERMINAL_REPLAY.md")
EVIDENCE_PREFIX = "verification/published/"
ENVELOPE_PATHS = {"verification/criterion_status.json", "verification/evidence_index.json"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


@dataclass(frozen=True)
class ReceiptView:
    path: str
    directory: Path
    record: dict
    output: str
    artifacts: dict[str, Path]


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _json(path: Path, expected: type = dict):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON: {path}") from exc
    if not isinstance(value, expected):
        raise ValueError(f"unexpected JSON type: {path}")
    return value


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=15,
        encoding="utf-8", errors="replace",
    )
    if result.returncode:
        raise ValueError(f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant], cwd=root,
        capture_output=True, timeout=15,
    )
    return result.returncode == 0


def _changed_paths(root: Path) -> set[str]:
    changed: set[str] = set()
    commands = (
        ("diff", "--name-only", "--no-renames"),
        ("diff", "--cached", "--name-only", "--no-renames"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    for command in commands:
        output = _git(root, *command)
        changed.update(Path(line).as_posix() for line in output.splitlines() if line)
    return changed


def _allowed_envelope(path: str) -> bool:
    return path in ENVELOPE_PATHS or path.startswith(EVIDENCE_PREFIX)


def _safe_public_file(root: Path, raw: str, prefix: str | None = None) -> Path:
    relative = evidence._safe_relative(raw)
    normalized = relative.as_posix()
    if prefix is not None and not normalized.startswith(prefix):
        raise ValueError(f"path is outside required {prefix} envelope: {raw}")
    return evidence._inside(root, root / relative)


def _make_command(command: list[str], target: str) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    if executable not in MAKE_PROGRAMS:
        return False
    if len(command) < 2 or command[-1] != target:
        return False
    # Reject alternate recipes, eval/dry-run switches and Make substitutions.
    seen: set[str] = set()
    for item in command[1:-1]:
        if '=' not in item:
            return False
        name, value = item.split('=', 1)
        if name in seen:
            return False
        seen.add(name)
        if not valid_assignment(name,value):
            return False
    return seen == RECIPE_VARIABLES


def _module_command(command: list[str], module: str) -> bool:
    if not command:
        return False
    executable = Path(command[0]).name.lower()
    if executable not in PYTHON_PROGRAMS:
        return False
    if len(command) < 3 or command[1:3] != ['-m', module]:
        return False
    rest = command[3:]
    if len(rest) % 2:
        return False
    seen: set[str] = set()
    for flag, value in zip(rest[::2], rest[1::2]):
        if flag not in {'--directory', '--executable'} or flag in seen or not value:
            return False
        seen.add(flag)
    return True


def command_matches(command: list[str], specification: dict) -> bool:
    """Match the fixed command contract without executing a shell string."""
    if not isinstance(command, list) or not all(isinstance(item, str) and item for item in command):
        return False
    if specification.get("kind") == "make":
        return _make_command(command, specification.get("target", ""))
    if specification.get("kind") == "python-module":
        return _module_command(command, specification.get("module", ""))
    return False


def contract_errors(
    record: dict,
    requirement: dict,
    commands: dict,
    output: str,
    artifact_labels: set[str],
) -> list[str]:
    """Pure criterion/receipt matching used by the gate and regression tests."""
    errors: list[str] = []
    category = requirement.get("category")
    if record.get("schema_version") != 2:
        errors.append("schema_version 2 required")
    if record.get("evidence_class") != "integration":
        errors.append("unit_fixture/historical evidence is not release-eligible")
    if record.get("category") != category:
        errors.append(f"expected category {category!r}")
    specification = commands.get(category)
    if not isinstance(specification, dict) or not command_matches(record.get("command", []), specification):
        errors.append(f"command does not match {category!r} contract")
    for marker in requirement.get("markers", []):
        if not isinstance(marker, str) or marker not in output:
            errors.append(f"missing output marker {marker!r}")
    for label in requirement.get("artifacts", []):
        if label not in artifact_labels:
            errors.append(f"missing semantic artifact {label!r}")
    return errors


def _json_objects(text: str):
    decoder = json.JSONDecoder()
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield value


def _numerical_summary(views: list[ReceiptView]) -> dict | None:
    for view in views:
        for value in _json_objects(view.output):
            if {"max_absolute_error", "rms_error", "sequences", "variants"} <= set(value):
                return value
    return None


def _artifact_json(view: ReceiptView, label: str):
    path = view.artifacts.get(label)
    if path is None:
        raise ValueError(f"missing artifact {label}")
    return _json(path, (dict, list))


def _view_for_label(views: list[ReceiptView], label: str) -> ReceiptView:
    matches = [view for view in views if label in view.artifacts]
    if len(matches) != 1:
        raise ValueError(f"artifact {label} must occur exactly once")
    return matches[0]


def _finite_number(value, minimum: float = 0.0) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= minimum


def _validate_tiny(views: list[ReceiptView], cache_equivalence: bool) -> None:
    summary = _numerical_summary(views)
    if summary is None:
        raise ValueError("missing machine-readable tiny numerical summary")
    if not _finite_number(summary.get("max_absolute_error")) or summary["max_absolute_error"] > 3e-5:
        raise ValueError("tiny max-absolute tolerance not established")
    if not _finite_number(summary.get("rms_error")) or summary["rms_error"] > 3e-6:
        raise ValueError("tiny RMS tolerance not established")
    if cache_equivalence and (summary.get("sequences", 0) < 100 or summary.get("variants", 0) < 3):
        raise ValueError("100-sequence/three-variant property evidence missing")


def _validate_real_model(views: list[ReceiptView], root: Path) -> None:
    value = _artifact_json(_view_for_label(views, "pretrained-result"), "pretrained-result")
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise ValueError("pretrained artifact is not PASS")
    model = _json(root / "models/manifest.json")
    if value.get("revision") != model.get("revision"):
        raise ValueError("pretrained revision is not the locked revision")
    rows = value.get("rows")
    if not isinstance(rows, list) or len(rows) != 20:
        raise ValueError("pretrained artifact must contain exactly 20 cases")
    positions = 0
    confident = 0
    rng = random.Random(20261019)
    for index, row in enumerate(rows):
        expected_length = 1 + (index * 7) % 32
        expected_tokens = [rng.randrange(49152) for _ in range(expected_length)]
        if not isinstance(row, dict) or row.get("case") != index:
            raise ValueError("pretrained case identities are incomplete")
        tokens = row.get("tokens")
        if tokens != expected_tokens or not all(isinstance(x, int) and not isinstance(x, bool) for x in tokens):
            raise ValueError("pretrained fixed token sequence is invalid")
        if not _finite_number(row.get("max_abs")) or row["max_abs"] > 0.01:
            raise ValueError("pretrained maximum tolerance exceeded")
        if not _finite_number(row.get("mean_abs")) or row["mean_abs"] > 0.001:
            raise ValueError("pretrained mean tolerance exceeded")
        if row.get("confident_top1_matches") is not True:
            raise ValueError("confident top-1 equality failed")
        count = row.get("confident_positions")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0 or count > len(tokens):
            raise ValueError("invalid confident-position count")
        positions += len(tokens)
        confident += count
    if positions != 326 or confident < 1:
        raise ValueError("pretrained position coverage is incomplete")
    conversion = value.get("conversion")
    if not isinstance(conversion, dict) or not SHA256_RE.fullmatch(str(conversion.get("output_sha256", ""))):
        raise ValueError("converted-model digest missing")
    provenance = conversion.get("source_provenance")
    if not isinstance(provenance, dict) or provenance.get("repository") != model.get("repository") or provenance.get("revision") != model.get("revision"):
        raise ValueError("converted-model provenance mismatch")
    if conversion.get("source_weight_sha256") != model.get("expected_weight_sha256"):
        raise ValueError("converted-model source digest mismatch")
    repeated: list[str] = []
    if isinstance(value.get("conversion_hashes"), list):
        repeated = value["conversion_hashes"]
    elif isinstance(value.get("conversions"), list):
        repeated = [item.get("output_sha256") for item in value["conversions"] if isinstance(item, dict)]
    elif isinstance(conversion.get("repeat_output_sha256"), str):
        repeated = [conversion.get("output_sha256"), conversion.get("repeat_output_sha256")]
    if len(repeated) < 2 or not all(SHA256_RE.fullmatch(str(item)) for item in repeated) or len(set(repeated)) != 1:
        raise ValueError("two identical deterministic conversion hashes are required")


def _validate_trace(views: list[ReceiptView], source_sha256: str) -> None:
    core = _view_for_label(views, "demo-trace")
    trace = _artifact_json(core, "demo-trace")
    if not isinstance(trace, dict) or trace.get("source_sha256") != source_sha256:
        raise ValueError("demo trace is not bound to current source")
    rows = trace.get("trace")
    if not isinstance(rows, list) or not rows:
        raise ValueError("demo trace is empty")
    events: list[str] = []
    def collect(value) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("event"), str):
                events.append(value["event"])
            for nested in value.values():
                collect(nested)
        elif isinstance(value, list):
            for nested in value:
                collect(nested)
    collect(rows)
    if not {"accepted", "error", "cancelled", "finished"} <= set(events):
        raise ValueError("demo trace lacks success, denial, cancellation, or completion")
    if "test_report_escapes_untrusted_strings" not in core.output:
        raise ValueError("malicious-string escaping test evidence missing")
    browser = _artifact_json(_view_for_label(views, "browser-result"), "browser-result")
    if not isinstance(browser, dict) or browser.get("status") != "PASS" or "keyboard" not in str(browser.get("mode", "")).lower():
        raise ValueError("real browser keyboard result missing")
    report_path = core.artifacts.get('demo-report')
    if (report_path is None or browser.get('source_sha256') != source_sha256
        or browser.get('html_sha256') != _sha(report_path.read_bytes())):
        raise ValueError('browser did not inspect this exact current-source report')
    view_rows = browser.get("views")
    if not isinstance(view_rows, list):
        raise ValueError("browser view results missing")
    by_name = {row.get("view"): row for row in view_rows if isinstance(row, dict)}
    for name in ("desktop", "mobile"):
        row = by_name.get(name)
        if not row or row.get("horizontal_overflow") is not False or row.get("first_focus") != "#trace":
            raise ValueError(f"browser {name} layout/keyboard evidence failed")


def _validate_clean(views: list[ReceiptView], bindings: dict[str, str]) -> None:
    value = _artifact_json(_view_for_label(views, "clean-result"), "clean-result")
    if not isinstance(value, dict) or value.get("status") != "PASS":
        raise ValueError("clean reproduction did not pass")
    for key in ("source_sha256", "release_sha256", "git_commit", "git_tree"):
        if value.get(key) != bindings[key]:
            raise ValueError(f"clean reproduction {key} mismatch")
    for key in ("fresh_checkout", "fresh_dependency_environment", "hash_locked_dependencies"):
        if value.get(key) is not True:
            raise ValueError(f"clean reproduction lacks {key}")
    if not SHA256_RE.fullmatch(str(value.get("dependency_lock_sha256", ""))):
        raise ValueError("fresh dependency lock digest missing")
    steps = value.get("steps")
    required = {"dependency-install", "build", "tests", "demo"}
    if not isinstance(steps, list):
        raise ValueError("clean reproduction steps missing")
    passed = {item.get("name") for item in steps if isinstance(item, dict) and item.get("exit_code") == 0}
    if not required <= passed:
        raise ValueError("clean reproduction omitted install/build/tests/demo")


def _validate_sanitizers(views: list[ReceiptView]) -> None:
    view = views[0]
    os_name = str(view.record.get("environment", {}).get("os", ""))
    compiler = str(view.record.get("runtime_versions", {}).get("clang++", ""))
    if "linux" not in os_name.lower() or not compiler or compiler == "UNAVAILABLE":
        raise ValueError("supported Linux Clang sanitizer scope not established")
    forbidden = ("ERROR: AddressSanitizer", "runtime error:", "UndefinedBehaviorSanitizer")
    if any(marker in view.output for marker in forbidden):
        raise ValueError("sanitizer diagnostic found in retained output")


def _validate_mutation(views: list[ReceiptView]) -> None:
    value = _artifact_json(_view_for_label(views, "mutation-result"), "mutation-result")
    if not isinstance(value, dict) or value.get("sequence") != "PASS -> expected FAIL -> PASS":
        raise ValueError("mutation PASS -> semantic FAIL -> PASS sequence missing")
    mutations = value.get("selected_mutations")
    if not isinstance(mutations, list) or len(mutations) < 2:
        raise ValueError("selected critical mutations missing")
    for item in mutations:
        verdict = str(item.get("verdict", "")) if isinstance(item, dict) else ""
        if not isinstance(item, dict) or not isinstance(item.get("exit_code"), int) or item["exit_code"] == 0:
            raise ValueError("mutation did not produce a failing check")
        if item.get("failure_kind") != "semantic" and "EXPECTED_TEST_FAILURE" not in verdict:
            raise ValueError("mutation failure is not identified as semantic")


def _validate_benchmark(views: list[ReceiptView], source_sha256: str, root: Path = ROOT) -> None:
    from scripts.benchmark_evidence import validate
    view = _view_for_label(views, "benchmark-result")
    validate(_artifact_json(view, "benchmark-result"), view.artifacts["benchmark-result"].parent, root, source_sha256)


def _no_findings(value) -> bool:
    if isinstance(value, list):
        return not value
    if not isinstance(value, dict) or value.get("status") != "PASS":
        return False
    findings = value.get("findings", value.get("vulnerabilities", value.get("unresolved", [])))
    if findings:
        return False
    dependencies = value.get("dependencies")
    if isinstance(dependencies, list):
        dependencies = dependencies + value.get('browser_dependencies', [])
        return all(isinstance(item, dict) and not item.get("vulns", item.get("vulnerabilities", [])) and not item.get('skip_reason') for item in dependencies)
    return True


def _validate_public_audit(views: list[ReceiptView], bindings: dict[str, str]) -> None:
    history = _artifact_json(_view_for_label(views, "history-scan"), "history-scan")
    if not isinstance(history, dict) or history.get("status") != "PASS" or history.get("full_history") is not True:
        raise ValueError("full-history scan evidence missing")
    if history.get("git_commit") != bindings["git_commit"] or history.get("findings"):
        raise ValueError("history scan is stale or has findings")
    for label in ("gitleaks-report", "advisory-report"):
        value = _artifact_json(_view_for_label(views, label), label)
        if not _no_findings(value):
            raise ValueError(f"{label} is incomplete or has findings")
    licenses = _artifact_json(_view_for_label(views, "license-inventory"), "license-inventory")
    if not isinstance(licenses, dict) or licenses.get("status") != "PASS" or licenses.get("unresolved"):
        raise ValueError("license inventory is incomplete")
    packages = licenses.get("packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("license inventory has no resolved packages")
    if any(not isinstance(item, dict) or item.get("approved") is not True for item in packages):
        raise ValueError("license inventory contains an unapproved package")


def _validate_review(root: Path, status: dict, bindings: dict[str, str]) -> None:
    reference = status.get("independent_review")
    if not isinstance(reference, dict) or set(reference) != {"artifact", "sha256"}:
        raise ValueError("hashed independent-review artifact is required")
    path = _safe_public_file(root, reference.get("artifact", ""), EVIDENCE_PREFIX)
    payload = path.read_bytes()
    if not SHA256_RE.fullmatch(str(reference.get("sha256", ""))) or _sha(payload) != reference["sha256"]:
        raise ValueError("independent-review artifact digest mismatch")
    try:
        review = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError("independent-review artifact is not JSON") from exc
    if not isinstance(review, dict) or review.get("schema_version") != 1:
        raise ValueError("independent-review artifact schema mismatch")
    if review.get("review_type") != "independent-final" or review.get("execution_mode") != "separate-read-only-session":
        raise ValueError("review is not an independent final read-only assessment")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("reviewer identity/role missing")
    for key in ("source_sha256", "release_sha256", "git_commit", "git_tree"):
        if review.get(key) != bindings[key]:
            raise ValueError(f"independent review {key} mismatch")
    if review.get("disposition") != "APPROVED":
        raise ValueError("independent review disposition is not APPROVED")
    exception = review.get("exception")
    exception_path = _safe_public_file(root, EXCEPTION.as_posix())
    if (
        not isinstance(exception, dict) or exception.get("path") != EXCEPTION.as_posix()
        or exception.get("sha256") != _sha(exception_path.read_bytes())
        or exception.get("disposition") != "ACCEPTED"
    ):
        raise ValueError("terminal-replay exception lacks independent acceptance")
    findings = review.get("findings")
    if not isinstance(findings, list) or any(
        not isinstance(item, dict) or item.get("status") not in {"CLOSED", "ACCEPTED"}
        for item in findings
    ):
        raise ValueError("independent review has unresolved findings")
    scope = review.get("scope")
    if not isinstance(scope, list) or not {"source", "acceptance", "evidence", "release-scope"} <= set(scope):
        raise ValueError("independent review scope is incomplete")
    try:
        completed = dt.datetime.fromisoformat(review.get("completed_utc", ""))
    except (TypeError, ValueError) as exc:
        raise ValueError("independent review completion time missing") from exc
    if completed.tzinfo is None:
        raise ValueError("independent review completion time lacks timezone")


def _load_receipt(root: Path, raw: str, bindings: dict[str, str]) -> ReceiptView:
    if not isinstance(raw, str):
        raise ValueError("receipt path must be a string")
    relative = evidence._safe_relative(raw)
    normalized = relative.as_posix()
    if not normalized.startswith(EVIDENCE_PREFIX) or "/" in normalized[len(EVIDENCE_PREFIX):]:
        raise ValueError("release receipts must be direct directories under verification/published")
    directory = root / relative
    record = evidence.verify(directory, current=True, release_scope=True)
    if record.get("schema_version") != 2:
        raise ValueError("schema_version 1 receipts are historical only")
    if record.get("evidence_class") != "integration":
        raise ValueError("unit_fixture receipts are never release-eligible")
    if record.get("status") != "PASS" or record.get("exit_code") != 0 or record.get("timed_out") is not False:
        raise ValueError("receipt is not a successful non-timeout execution")
    if record.get("artifact_errors"):
        raise ValueError("receipt recorded artifact capture errors")
    if record.get("git_dirty") is not False:
        raise ValueError("release receipt was captured from a dirty source tree")
    for key in ("source_sha256", "release_sha256", "git_commit", "git_tree"):
        if record.get(key) != bindings[key]:
            raise ValueError(f"stale receipt {key}")
    artifacts: dict[str, Path] = {}
    for row in record.get("artifacts", []):
        path = _safe_public_file(root, row["path"], EVIDENCE_PREFIX)
        artifacts[row["label"]] = path
    stdout = evidence._inside(directory, directory / "stdout.txt").read_text(encoding="utf-8", errors="replace")
    stderr = evidence._inside(directory, directory / "stderr.txt").read_text(encoding="utf-8", errors="replace")
    return ReceiptView(normalized, directory, record, stdout + "\n" + stderr, artifacts)


def _semantic_check(semantic: str, views: list[ReceiptView], root: Path, bindings: dict[str, str]) -> None:
    if semantic == "tiny-numerics":
        _validate_tiny(views, False)
    elif semantic == "cache-equivalence":
        _validate_tiny(views, True)
    elif semantic in {"real-model", "model-convert"}:
        _validate_real_model(views, root)
    elif semantic == "inspector":
        _validate_trace(views, bindings["source_sha256"])
    elif semantic == "fresh-reproduction":
        _validate_clean(views, bindings)
    elif semantic == "sanitizers":
        _validate_sanitizers(views)
    elif semantic == "public-audit":
        _validate_public_audit(views, bindings)
    elif semantic in {"benchmark", "batching"}:
        _validate_benchmark(views, bindings["source_sha256"], root)
    elif semantic == "mutation":
        _validate_mutation(views)


def _status_shape_errors(status: dict, acceptance: dict[str, dict], mapping: dict) -> list[str]:
    errors: list[str] = []
    required_top = {
        "schema_version", "source_sha256", "release_sha256", "git_commit", "git_tree",
        "criteria", "independent_review", "overall", "as_of", "remote_publication",
    }
    if set(status) != required_top or status.get("schema_version") != 2:
        errors.append("criterion status must match schema_version 2 (bare review Booleans are invalid)")
    criteria = status.get("criteria")
    expected_ids = set(acceptance)
    mapped_ids = set(mapping.get("criteria", {}))
    if expected_ids != {f"AC-{number:03d}" for number in range(1, 25)} or mapped_ids != expected_ids:
        errors.append("locked acceptance IDs and fixed evidence map do not match all 24 criteria")
    if not isinstance(criteria, dict) or set(criteria) != expected_ids:
        errors.append("criterion status does not contain exactly the locked 24 criteria")
        return errors
    entry_keys = {"status", "requirement", "label", "receipts", "scope"}
    for criterion in sorted(expected_ids):
        entry = criteria[criterion]
        contract = acceptance[criterion]
        evidence_contract = mapping["criteria"].get(criterion, {})
        if not isinstance(entry, dict) or set(entry) != entry_keys:
            errors.append(f"{criterion}: invalid status entry schema")
            continue
        if entry.get("status") != "PASS":
            errors.append(f"{criterion}: {entry.get('status', 'NOT_RUN')}")
        if entry.get("requirement") != contract.get("requirement") or entry.get("label") != contract.get("label"):
            errors.append(f"{criterion}: requirement/label differs from locked acceptance")
        receipts = entry.get("receipts")
        required_receipts = evidence_contract.get("receipts")
        if (
            not isinstance(receipts, list) or not receipts or len(receipts) != len(set(receipts))
            or not isinstance(required_receipts, list) or len(receipts) != len(required_receipts)
        ):
            errors.append(f"{criterion}: receipt count/uniqueness does not match fixed evidence map")
        if not isinstance(entry.get("scope"), str) or not entry["scope"].strip():
            errors.append(f"{criterion}: evidence scope missing")
    if status.get("overall") != "RELEASE_READY":
        errors.append("overall status is not RELEASE_READY")
    if status.get("remote_publication") != "VERIFIED":
        errors.append("actual public publication/remote verification is not VERIFIED")
    try:
        dt.date.fromisoformat(status.get("as_of", ""))
    except (TypeError, ValueError):
        errors.append("status as_of is not an ISO date")
    return errors


def verify_release(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        status = _json(root / STATUS)
        mapping = _json(root / MAPPING)
        acceptance_list = _json(root / ACCEPTANCE, list)
        acceptance = {item["id"]: item for item in acceptance_list if isinstance(item, dict) and isinstance(item.get("id"), str)}
    except (ValueError, KeyError) as exc:
        return [str(exc)]
    errors.extend(_status_shape_errors(status, acceptance, mapping))
    try:
        source_sha256 = evidence.identity(evidence.manifest(root))
        release_sha256 = evidence.identity(evidence.release_manifest(root))
        current_head = _git(root, "rev-parse", "HEAD")
        source_commit = status.get("git_commit", "")
        source_tree = status.get("git_tree", "")
        if (
            not GIT_OID_RE.fullmatch(current_head)
            or not GIT_OID_RE.fullmatch(str(source_commit))
            or not GIT_OID_RE.fullmatch(str(source_tree))
        ):
            raise ValueError("unsupported Git object ID format")
        actual_source_tree = _git(root, "rev-parse", f"{source_commit}^{{tree}}")
        if actual_source_tree != source_tree:
            raise ValueError("criterion index Git tree does not belong to its source commit")
        if not _git_is_ancestor(root, source_commit, current_head):
            raise ValueError("criterion index source commit is not an ancestor of current HEAD")
        bindings = {
            "source_sha256": source_sha256, "release_sha256": release_sha256,
            # This is the clean source-baseline commit shared by receipts. Current
            # HEAD may be a descendant containing only the excluded evidence
            # envelope; exact current source/release hashes are still mandatory.
            "git_commit": source_commit, "git_tree": source_tree,
        }
        for key, value in (("source_sha256", source_sha256), ("release_sha256", release_sha256)):
            if status.get(key) != value:
                errors.append(f"criterion index {key} is stale")
        disallowed = sorted(path for path in _changed_paths(root) if not _allowed_envelope(path))
        if disallowed:
            errors.append("source/release tree is dirty outside the evidence envelope: " + ", ".join(disallowed))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        errors.append(f"release-scope binding failed: {exc}")
        return errors
    cache: dict[str, ReceiptView] = {}
    criteria = status.get("criteria") if isinstance(status.get("criteria"), dict) else {}
    commands = mapping.get("commands") if isinstance(mapping.get("commands"), dict) else {}
    for criterion in sorted(acceptance):
        entry = criteria.get(criterion)
        fixed = mapping.get("criteria", {}).get(criterion)
        if not isinstance(entry, dict) or not isinstance(fixed, dict):
            continue
        raw_paths = entry.get("receipts")
        requirements = fixed.get("receipts")
        if not isinstance(raw_paths, list) or not isinstance(requirements, list):
            continue
        views: list[ReceiptView] = []
        for raw in raw_paths:
            try:
                if raw not in cache:
                    cache[raw] = _load_receipt(root, raw, bindings)
                views.append(cache[raw])
            except (OSError, ValueError, KeyError) as exc:
                errors.append(f"{criterion}: receipt {raw!r}: {exc}")
        if len(views) != len(raw_paths):
            continue
        unused = list(views)
        for requirement in requirements:
            candidates: list[tuple[ReceiptView, list[str]]] = []
            for view in unused:
                problems = contract_errors(view.record, requirement, commands, view.output, set(view.artifacts))
                candidates.append((view, problems))
            matching = next(((view, problems) for view, problems in candidates if not problems), None)
            if matching is None:
                details = "; ".join(f"{view.path}: {', '.join(problems)}" for view, problems in candidates)
                errors.append(f"{criterion}: no receipt satisfies {requirement.get('category')!r}: {details or 'none supplied'}")
            else:
                unused.remove(matching[0])
        if unused:
            errors.append(f"{criterion}: unrelated extra receipt(s): {', '.join(view.path for view in unused)}")
        if any(error.startswith(f"{criterion}:") for error in errors):
            continue
        try:
            _semantic_check(fixed.get("semantic", ""), views, root, bindings)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{criterion}: semantic evidence failed: {exc}")
    try:
        _validate_review(root, status, bindings)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"independent review: {exc}")
    return errors


def main() -> None:
    errors = verify_release()
    if errors:
        raise SystemExit("NOT RELEASE READY\n" + "\n".join(errors))
    # Audit the final candidate rather than trusting the older source-baseline
    # history receipt. This covers extra evidence and descendant history too.
    from scripts.publication_verify import verify_publication
    publication = verify_publication()
    print(json.dumps({"current_publication_audit": publication}, indent=2))
    print("Release evidence gate passed. Hashes are local bindings, not external attestation.")


if __name__ == "__main__":
    main()
