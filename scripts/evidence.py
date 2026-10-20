"""Capture and verify source-bound local execution receipts.

Version 2 receipts hash the record, streams, source manifest, release-scope
manifest, and explicitly named semantic artifacts. These are local mutable hash
bindings, not signatures or external attestation.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import time
import uuid
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRS = ("src", "tests", "tools", "scripts")
SOURCE_FILES = (
    "CMakeLists.txt", "Makefile", "requirements.txt", "requirements-reference.txt", "requirements-core.lock",
    "requirements-reference-windows-cp312.lock", "requirements-browser.lock", "API_SPEC.md", "ACCEPTANCE_SPEC.md",
    "PRD.md", "ARCHITECTURE.md", "THREAT_MODEL.md", "SECURITY.md",
    "TEST_SPEC_EXCEPTION_TERMINAL_REPLAY.md", "verification/acceptance.json",
    "verification/acceptance.lock.json", "verification/phase_plan.json",
    "verification/phase_plan.sha256", "verification/receipt.schema.json",
    "verification/criterion_evidence_map.json", "verification/criterion_status.schema.json",
    "models/manifest.json",
)
RELEASE_SCOPE_EXCLUDES = (
    "verification/published/",
    "verification/criterion_status.json",
    "verification/evidence_index.json",
)
HEX = set("0123456789abcdef")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _identity(data: dict[str, str]) -> str:
    return sha(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())


def identity(data: dict[str, str]) -> str:
    """Backwards-compatible public name used by other verification code."""
    return _identity(data)


def _safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("path must be a non-empty string")
    path = Path(value)
    if path.is_absolute() or path.drive or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    return path


def _has_symlink_component(root: Path, path: Path) -> bool:
    """Check the lexical path before resolve() erases symlink information."""
    root = root.absolute()
    path = path.absolute()
    relative = path.relative_to(root)
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def _inside(root: Path, path: Path) -> Path:
    try:
        symlinked = _has_symlink_component(root, path)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {path}") from exc
    if symlinked:
        raise ValueError(f"symlink path is not allowed: {path}")
    resolved_root = root.resolve()
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {path}") from exc
    if not resolved.is_file():
        raise ValueError(f"artifact must be a regular non-symlink file: {path}")
    return resolved


def _directory_inside(root: Path, path: Path) -> Path:
    try:
        symlinked = _has_symlink_component(root, path)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {path}") from exc
    if symlinked:
        raise ValueError(f"symlink path is not allowed: {path}")
    resolved_root = root.resolve()
    resolved = path.resolve(strict=True)
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {path}") from exc
    if not resolved.is_dir():
        raise ValueError(f"receipt must be a repository-contained directory: {path}")
    return resolved


def manifest(root: Path = ROOT) -> dict[str, str]:
    files = [root / item for item in SOURCE_FILES if (root / item).is_file()]
    for directory in SOURCE_DIRS:
        base = root / directory
        if not base.is_dir():
            continue
        files.extend(
            path for path in base.rglob("*")
            if path.is_file() and not path.is_symlink()
            and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".plist")
        )
    return {
        path.relative_to(root).as_posix(): sha(path.read_bytes())
        for path in sorted(set(files))
    }


def _git_output(args: list[str], root: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=15,
        encoding="utf-8", errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def release_manifest(root: Path = ROOT) -> dict[str, str]:
    """Hash tracked public files except the deliberately mutable evidence envelope.

    Source, public docs, workflows, licenses, dependency locks, and release tooling
    are included. Published receipts and their indexes are excluded to avoid a
    receipt/commit self-reference loop. The record also binds the Git commit/tree.
    """
    listed = _git_output(["ls-files", "-z"], root)
    if listed == "UNAVAILABLE":
        raise ValueError("Git tracked-file inventory unavailable")
    result: dict[str, str] = {}
    for raw in listed.split("\x00"):
        if not raw:
            continue
        rel = Path(raw).as_posix()
        if rel in RELEASE_SCOPE_EXCLUDES or any(rel.startswith(p) for p in RELEASE_SCOPE_EXCLUDES):
            continue
        path = root / _safe_relative(rel)
        _inside(root, path)
        result[rel] = sha(path.read_bytes())
    return dict(sorted(result.items()))


def command_info(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace",
        )
        return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def _artifact_rows(artifacts: dict[str, Path] | None) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    errors: list[str] = []
    for label, supplied in sorted((artifacts or {}).items()):
        if not label.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"invalid artifact label: {label!r}")
        path = supplied if supplied.is_absolute() else ROOT / supplied
        try:
            resolved = _inside(ROOT, path)
            rel = resolved.relative_to(ROOT.resolve()).as_posix()
            payload = resolved.read_bytes()
            rows.append({"label": label, "path": rel, "bytes": len(payload), "sha256": sha(payload)})
        except (OSError, ValueError) as exc:
            errors.append(f"{label}: {exc}")
    return rows, errors


def _write_json(path: Path, value: object) -> None:
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def public_stream(payload: bytes) -> bytes:
    """Replace only known absolute local path prefixes; retain raw bytes locally.

    This does not remove diagnostics or change verdicts. Commands remain exact;
    use relative command arguments for receipts intended for public export.
    """
    import sys
    prefixes = [(ROOT, '<public-repo>'), (ROOT.parent, '<project-workspace>'),
                (Path(sys.prefix), '<python-environment>'), (Path(sys.base_prefix), '<python-base>'),
                (Path.home(), '<user-home>')]
    if os.environ.get('BQ_TEMP_BASE'):
        prefixes.append((Path(os.environ['BQ_TEMP_BASE']), '<project-temp>'))
    substitutions = {}
    for path, replacement in prefixes:
        raw = str(path)
        for spelling in (raw, raw.replace('\\', '/'), json.dumps(raw, ensure_ascii=False)[1:-1]):
            substitutions[spelling.encode('utf-8')] = replacement.encode('ascii')
    for original, replacement in sorted(substitutions.items(), key=lambda item: len(item[0]), reverse=True):
        payload = payload.replace(original, replacement)
    return payload.replace(b'\r\n', b'\n')


def _bundle(out: Path, artifact_rows: Iterable[dict]) -> None:
    files = {
        name: sha((out / name).read_bytes())
        for name in ("record.json", "source_manifest.json", "release_manifest.json", "stdout.txt", "stderr.txt")
    }
    for row in artifact_rows:
        files[f"artifact:{row['label']}:{row['path']}"] = row["sha256"]
    _write_json(out / "bundle_manifest.json", {"schema_version": 1, "files": files})


def run(
    name: str,
    command: list[str],
    timeout: int = 180,
    artifacts: dict[str, Path] | None = None,
    evidence_class: str = "integration",
) -> Path:
    if not name.replace("-", "").replace("_", "").isalnum() or not command:
        raise ValueError("invalid evidence request")
    if evidence_class not in {"integration", "unit_fixture"}:
        raise ValueError("unsupported evidence class")
    out = ROOT / ".local-runs" / "evidence" / f"{name}-{uuid.uuid4().hex[:12]}"
    out.mkdir(parents=True, exist_ok=False)
    sources = manifest()
    release_sources = release_manifest()
    _write_json(out / "source_manifest.json", sources)
    _write_json(out / "release_manifest.json", release_sources)
    commit = _git_output(["rev-parse", "HEAD"])
    tree = _git_output(["rev-parse", "HEAD^{tree}"])
    dirty = _git_output(["status", "--porcelain", "--untracked-files=normal"])
    versions = {
        tool: command_info([tool, "--version"]).split("\n")[0]
        for tool in ("c++", "clang++", "cmake", "git")
    }
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    clock = time.perf_counter_ns()
    timed_out = False
    try:
        child_env = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
        for variable in ('MAKEFLAGS', 'GNUMAKEFLAGS', 'MAKEFILES'):
            child_env.pop(variable, None)
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, timeout=timeout,
            env=child_env,
        )
        code, stdout, stderr = result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        code, stdout, stderr = 124, exc.stdout or b"", exc.stderr or b""
        timed_out = True
    except OSError as exc:
        code, stdout, stderr = 127, b"", str(exc).encode()
    elapsed = (time.perf_counter_ns() - clock) / 1e9
    # Raw streams never leave the ignored local evidence directory. Public
    # streams and their hashes explicitly describe the path-only transform.
    (out / "raw.stdout.txt").write_bytes(stdout)
    (out / "raw.stderr.txt").write_bytes(stderr)
    raw_stdout_sha256, raw_stderr_sha256 = sha(stdout), sha(stderr)
    stdout, stderr = public_stream(stdout), public_stream(stderr)
    (out / "stdout.txt").write_bytes(stdout)
    (out / "stderr.txt").write_bytes(stderr)
    artifact_rows, artifact_errors = _artifact_rows(artifacts)
    info = {
        "schema_version": 2,
        "name": name,
        "category": name,
        "command": command,
        "cwd": "public repository root",
        "started_utc": start,
        "ended_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": elapsed,
        "exit_code": code,
        "timed_out": timed_out,
        "status": "PASS" if code == 0 and not timed_out else "FAIL",
        "evidence_class": evidence_class,
        "git_commit": commit,
        "git_tree": tree,
        "git_dirty": None if dirty == "UNAVAILABLE" else bool(dirty),
        "runtime_versions": versions,
        "stdout_file": "stdout.txt",
        "stderr_file": "stderr.txt",
        "source_manifest_file": "source_manifest.json",
        "release_manifest_file": "release_manifest.json",
        "source_sha256": _identity(sources),
        "release_sha256": _identity(release_sources),
        "stdout_sha256": sha(stdout),
        "stderr_sha256": sha(stderr),
        "artifacts": artifact_rows,
        "artifact_errors": artifact_errors,
        "environment": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "python_executable": Path(sys_executable()).name,
            "machine": platform.machine(),
            "stream_transform": "known-absolute-local-path-prefixes-v1 plus LF line endings; raw streams retained locally, not published",
            "raw_stdout_sha256": raw_stdout_sha256,
            "raw_stderr_sha256": raw_stderr_sha256,
        },
        "scope": "local mutable hash binding; no external attestation, independent review, or hosted-CI claim",
    }
    _write_json(out / "record.json", info)
    _bundle(out, artifact_rows)
    return out


def sys_executable() -> str:
    import sys
    return sys.executable


def _is_hex64(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX


def _is_git_oid(value: object) -> bool:
    return isinstance(value, str) and len(value) in (40, 64) and set(value) <= HEX


def _validate_record(info: object) -> dict:
    if not isinstance(info, dict):
        raise ValueError("record must be an object")
    required = {
        "schema_version": int, "name": str, "category": str, "command": list,
        "cwd": str,
        "started_utc": str, "ended_utc": str, "duration_seconds": (int, float),
        "exit_code": int, "timed_out": bool, "status": str, "evidence_class": str,
        "git_commit": str, "git_tree": str, "git_dirty": (bool, type(None)),
        "runtime_versions": dict, "stdout_file": str, "stderr_file": str,
        "source_manifest_file": str, "release_manifest_file": str,
        "source_sha256": str, "release_sha256": str, "stdout_sha256": str,
        "stderr_sha256": str, "environment": dict, "scope": str, "artifacts": list,
        "artifact_errors": list,
    }
    for key, expected in required.items():
        if key not in info or not isinstance(info[key], expected) or (
            (expected is int or key == "duration_seconds") and isinstance(info[key], bool)
        ):
            raise ValueError(f"invalid or missing record field: {key}")
    if info["schema_version"] != 2:
        raise ValueError("release receipts require schema_version 2")
    if set(info) != set(required):
        raise ValueError("record contains unexpected fields")
    if info["cwd"] != "public repository root":
        raise ValueError("invalid receipt working directory")
    for key, value in (("name", info["name"]), ("category", info["category"])):
        if not value or not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError(f"invalid record field: {key}")
    if not info["command"] or not all(isinstance(x, str) and x for x in info["command"]):
        raise ValueError("command must contain non-empty strings")
    if info["status"] not in {"PASS", "FAIL"} or info["evidence_class"] not in {"integration", "unit_fixture"}:
        raise ValueError("invalid status or evidence class")
    if info["status"] == "PASS" and (info["exit_code"] != 0 or info["timed_out"]):
        raise ValueError("PASS receipt has nonzero exit or timeout")
    if info["status"] == "FAIL" and info["exit_code"] == 0 and not info["timed_out"]:
        raise ValueError("FAIL receipt has successful execution fields")
    for key in ("source_sha256", "release_sha256", "stdout_sha256", "stderr_sha256"):
        if not _is_hex64(info[key]):
            raise ValueError(f"invalid digest field: {key}")
    if info["git_commit"] != "UNAVAILABLE" and not _is_git_oid(info["git_commit"]):
        raise ValueError("invalid git_commit")
    if info["git_tree"] != "UNAVAILABLE" and not _is_git_oid(info["git_tree"]):
        raise ValueError("invalid git_tree")
    expected_files = {
        "stdout_file": "stdout.txt", "stderr_file": "stderr.txt",
        "source_manifest_file": "source_manifest.json",
        "release_manifest_file": "release_manifest.json",
    }
    for key, expected in expected_files.items():
        if info[key] != expected:
            raise ValueError(f"unsafe record filename: {key}")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in info["runtime_versions"].items()):
        raise ValueError("invalid runtime_versions")
    if not all(isinstance(item, str) for item in info["artifact_errors"]):
        raise ValueError("invalid artifact_errors")
    timestamps: dict[str, dt.datetime] = {}
    for key in ("started_utc", "ended_utc"):
        try:
            parsed = dt.datetime.fromisoformat(info[key])
        except ValueError as exc:
            raise ValueError(f"invalid timestamp: {key}") from exc
        if parsed.tzinfo is None:
            raise ValueError(f"timestamp lacks timezone: {key}")
        timestamps[key] = parsed
    if timestamps["ended_utc"] < timestamps["started_utc"]:
        raise ValueError("receipt ends before it starts")
    if info["duration_seconds"] < 0:
        raise ValueError("negative duration")
    return info


def _load_object(path: Path, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid {label}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _validate_hash_manifest(value: dict, label: str) -> None:
    for rel, digest in value.items():
        _safe_relative(rel)
        if not _is_hex64(digest):
            raise ValueError(f"invalid {label} digest: {rel}")


def _verify_v1(receipt: Path, info: dict, current: bool, release_scope: bool) -> dict:
    """Verify legacy bytes for historical inspection, never for release use."""
    if current or release_scope:
        raise ValueError("schema_version 1 receipts are historical only")
    required = {
        "schema_version", "name", "command", "started_utc", "ended_utc",
        "duration_seconds", "exit_code", "timed_out", "git_commit", "git_dirty",
        "category", "stdout_file", "stderr_file", "status", "source_sha256",
        "stdout_sha256", "stderr_sha256", "environment", "scope",
    }
    if not required <= set(info) or info.get("schema_version") != 1:
        raise ValueError("invalid historical receipt schema")
    if info.get("git_commit") != "UNAVAILABLE" and not _is_git_oid(info.get("git_commit")):
        raise ValueError("invalid historical git_commit")
    for key in ("source_sha256", "stdout_sha256", "stderr_sha256"):
        if not _is_hex64(info.get(key)):
            raise ValueError(f"invalid historical digest field: {key}")
    if info.get("stdout_file") != "stdout.txt" or info.get("stderr_file") != "stderr.txt":
        raise ValueError("unsafe historical stream filename")
    sources = _load_object(_inside(receipt, receipt / "source_manifest.json"), "source manifest")
    _validate_hash_manifest(sources, "source manifest")
    if _identity(sources) != info["source_sha256"]:
        raise ValueError("source manifest changed")
    for stream in ("stdout", "stderr"):
        payload = _inside(receipt, receipt / f"{stream}.txt").read_bytes()
        if sha(payload) != info[f"{stream}_sha256"]:
            raise ValueError(f"{stream} payload changed")
    if info.get("status") == "PASS" and (info.get("exit_code") != 0 or info.get("timed_out") is not False):
        raise ValueError("historical PASS receipt has nonzero exit or timeout")
    return info


def verify(path: Path, current: bool = True, release_scope: bool = False) -> dict:
    candidate = path if path.is_absolute() else ROOT / path
    receipt = _directory_inside(ROOT, candidate)
    record_path = _inside(receipt, receipt / "record.json")
    raw_info = _load_object(record_path, "record")
    if raw_info.get("schema_version") == 1:
        return _verify_v1(receipt, raw_info, current, release_scope)
    info = _validate_record(raw_info)
    bundle = _load_object(_inside(receipt, receipt / "bundle_manifest.json"), "bundle manifest")
    if bundle.get("schema_version") != 1 or not isinstance(bundle.get("files"), dict):
        raise ValueError("invalid bundle manifest schema")
    bundle_files = bundle["files"]
    fixed = {
        "record.json", "source_manifest.json", "release_manifest.json", "stdout.txt", "stderr.txt"
    }
    expected_bundle = set(fixed)
    for row in info["artifacts"]:
        if isinstance(row, dict) and isinstance(row.get("label"), str) and isinstance(row.get("path"), str):
            expected_bundle.add(f"artifact:{row['label']}:{row['path']}")
    if set(bundle_files) != expected_bundle:
        raise ValueError("bundle manifest members do not match record")
    for name in fixed:
        member = _inside(receipt, receipt / name)
        if not _is_hex64(bundle_files[name]) or sha(member.read_bytes()) != bundle_files[name]:
            raise ValueError(f"bundle member changed: {name}")
    sources = _load_object(_inside(receipt, receipt / "source_manifest.json"), "source manifest")
    releases = _load_object(_inside(receipt, receipt / "release_manifest.json"), "release manifest")
    _validate_hash_manifest(sources, "source manifest")
    _validate_hash_manifest(releases, "release manifest")
    if _identity(sources) != info["source_sha256"]:
        raise ValueError("source manifest changed")
    if _identity(releases) != info["release_sha256"]:
        raise ValueError("release manifest changed")
    for stream in ("stdout", "stderr"):
        if info.get(f"{stream}_file") != f"{stream}.txt":
            raise ValueError(f"unsafe {stream} filename")
        payload = _inside(receipt, receipt / f"{stream}.txt").read_bytes()
        if sha(payload) != info[f"{stream}_sha256"]:
            raise ValueError(f"{stream} payload changed")
    labels: set[str] = set()
    for row in info["artifacts"]:
        if not isinstance(row, dict) or set(row) != {"label", "path", "bytes", "sha256"}:
            raise ValueError("invalid artifact record")
        label, rel = row["label"], row["path"]
        if (
            not isinstance(label, str) or not label.replace("-", "").replace("_", "").isalnum()
            or label in labels or not isinstance(rel, str)
            or not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool) or row["bytes"] < 0
            or not _is_hex64(row["sha256"])
        ):
            raise ValueError("invalid or duplicate artifact label")
        labels.add(label)
        artifact = ROOT / _safe_relative(rel)
        resolved = _inside(ROOT, artifact)
        payload = resolved.read_bytes()
        key = f"artifact:{label}:{rel}"
        if len(payload) != row["bytes"] or sha(payload) != row["sha256"]:
            raise ValueError(f"artifact changed: {label}")
        if bundle_files.get(key) != row["sha256"] or not _is_hex64(bundle_files.get(key)):
            raise ValueError(f"artifact bundle binding changed: {label}")
    if current and _identity(manifest()) != info["source_sha256"]:
        raise ValueError("receipt belongs to a different source state")
    if release_scope and _identity(release_manifest()) != info["release_sha256"]:
        raise ValueError("receipt belongs to a different release scope")
    return info


def _parse_artifacts(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("artifact must be LABEL=REPOSITORY_RELATIVE_PATH")
        label, raw = value.split("=", 1)
        if label in result:
            raise ValueError(f"duplicate artifact label: {label}")
        result[label] = _safe_relative(raw)
    return result


def publish(path: Path, name: str | None = None) -> Path:
    """Relocate a verified execution bundle without changing execution facts.

    The original record hash is disclosed. Raw local streams, weights, build
    products and arbitrary sibling files are never copied to the public tree.
    """
    import copy
    info = verify(path, current=True, release_scope=True)
    if info['evidence_class'] != 'integration' or info['status'] != 'PASS':
        raise ValueError('only successful integration receipts can enter the release envelope')
    original = path if path.is_absolute() else ROOT/path
    name = name or original.name
    if not name.replace('-', '').replace('_', '').isalnum():
        raise ValueError('invalid publication directory name')
    out = ROOT/'verification/published'/name
    if out.exists():
        raise ValueError('publication target already exists; historical evidence is never overwritten')
    out.mkdir(parents=True)
    published = copy.deepcopy(info)
    published['environment']['published_from_record_sha256'] = sha((original/'record.json').read_bytes())
    published['environment']['publication_transform'] = 'artifact paths relocated; all stream and artifact bytes unchanged; raw local streams excluded'
    artifacts = []
    labels = set()
    def retain(label: str, source: Path, filename: str) -> None:
        if label in labels:
            return
        if Path(filename).name != filename or source.suffix.lower() not in {'.json','.txt','.html','.png','.jpg','.jpeg'}:
            raise ValueError('unsupported public artifact')
        source = _inside(ROOT, source)
        data = source.read_bytes()
        destination = out/'artifacts'/filename
        destination.parent.mkdir(exist_ok=True)
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('artifact filename collision')
        destination.write_bytes(data)
        artifacts.append(dict(label=label,path=destination.relative_to(ROOT).as_posix(),bytes=len(data),sha256=sha(data)))
        labels.add(label)
    for row in info['artifacts']:
        source = _inside(ROOT, ROOT/_safe_relative(row['path']))
        retain(row['label'], source, row['label']+source.suffix)
        if row['label'] == 'benchmark-result':
            value = json.loads(source.read_bytes())
            for index, measurement in enumerate(value['warmup_rows']+value['rows']):
                for stream in ('stdout','stderr','command'):
                    filename = measurement[f'raw_{stream}_file']
                    child = _inside(ROOT, source.parent/_safe_relative(filename))
                    if sha(child.read_bytes()) != measurement[f'{stream}_sha256']:
                        raise ValueError('native benchmark artifact changed before publication')
                    retain(f'benchmark-{stream}-{index:03}', child, filename)
        elif row['label'] == 'browser-result':
            for view in ('desktop','mobile'):
                retain('browser-'+view, source.parent/(view+'.png'),view+'.png')
        elif row['label'] == 'demo-trace':
            retain('demo-report',source.parent/'report.html','report.html')
    published['artifacts'] = artifacts
    for filename in ('stdout.txt','stderr.txt','source_manifest.json','release_manifest.json'):
        (out/filename).write_bytes(_inside(original,original/filename).read_bytes())
    _write_json(out/'record.json',published)
    _bundle(out,artifacts)
    verify(out,current=True,release_scope=True)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    runner = sub.add_parser("run")
    runner.add_argument("name")
    runner.add_argument("--timeout", type=int, default=180)
    runner.add_argument("--artifact", action="append", default=[])
    runner.add_argument("--evidence-class", choices=("integration", "unit_fixture"), default="integration")
    runner.add_argument("command", nargs=argparse.REMAINDER)
    verifier = sub.add_parser("verify")
    verifier.add_argument("path", type=Path)
    verifier.add_argument("--historical", action="store_true")
    verifier.add_argument("--release-scope", action="store_true")
    publisher = sub.add_parser('publish')
    publisher.add_argument('path',type=Path)
    publisher.add_argument('--name')
    args = parser.parse_args()
    if args.operation == "run":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        path = run(args.name, command, args.timeout, _parse_artifacts(args.artifact), args.evidence_class)
        info = verify(path)
        print(json.dumps({"path": str(path.relative_to(ROOT)), **info}, indent=2))
        raise SystemExit(info["exit_code"])
    if args.operation == 'publish':
        print(publish(args.path,args.name).relative_to(ROOT).as_posix())
        return
    print(json.dumps(verify(args.path, not args.historical, args.release_scope), indent=2))


if __name__ == "__main__":
    main()
