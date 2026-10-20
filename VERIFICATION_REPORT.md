# Verification status — 2026-10-20

Final committed-source release evidence is being collected. Real pinned-checkpoint conformance and repeated conversion have passed locally. Separate read-only reviews preceded integration fixes and later challenged evidence validation and benchmark accounting; their findings and follow-up remain part of the release work. The earlier missing-dependency/DNS/scanner failures are retained, not relabelled as success.

The current benchmark measures four paired synthetic workloads with warmups, five repetitions, exact greedy-output parity, native high-water RSS and KV payload counters captured before reclamation. Native resource regression reproduces the three-page transient previously hidden by round-end sampling. Release regression tests reject an actually executed replacement make recipe, altered artifacts, false parity, inconsistent timing, missing warmups and duplicated repetitions.

Current release status: **NOT READY** until fresh committed reproduction, supported-Linux gates, current public receipts, complete-candidate audit and final independent review all pass. The material below is preserved historical author evidence for its stated source; its counts, blocked status and same-host reproduction are not current-source approval.

---

# Verification report

Research date: 2026-10-19, Asia/Singapore. Actual command timestamps are UTC in receipts (the initial author runs occurred on 2026-10-18 UTC / 2026-10-19 Singapore). No independently executed Codex or remote CI result is claimed.

## Source and environment
Checked code/contracts source SHA-256: `8fa2a6c5e66eea460b2619c984c2be02e2f7edec239515a0ae82d2019daa846b`.
Initial verified Git commit: `9c773daeabf4be83e14992ce365e9bd4022a9fda`. Later publication-only documentation/evidence commits do not change this explicitly defined code/contracts hash; do not mistake it for a full-tree or final-HEAD verification claim.

Linux 6.18.55 x86_64, GCC 14.2, Clang 17, CMake 3.31.6, Python 3.13.5. Actual local numerical/reference-conversion packages: NumPy 2.3.5, Torch 2.10.0+cpu, Safetensors 0.7.0. Transformers/tokenizers absent. Recommended current pins in requirements files are a different, not-yet-provisioned target environment.

## Executed successfully
33 named native/Python checks across the core and synthetic-conversion suites. Numerical evidence compared 100 seeded sequences of lengths 1..32 across three model configurations, and contiguous, paged and recomputed execution. 176,934 logit values were compared against a separately expressed dense full-prefix oracle. Maximum absolute difference: **2.9268134849047556e-7**; RMS difference: **4.329997188272048e-8**. Limits were 3e-5 and 3e-6 respectively.

Real child-process checks covered interleaved-vs-isolated output, capacity denial, cancellation/stale generation, malformed commands, damaged model files and process kill/restart. Native tests covered page ownership, epochs, clearing/reuse, reclamation including injected forward failure, bounded prefill and decode grants.

Clang AddressSanitizer/UndefinedBehaviorSanitizer checks and static analysis passed for their recorded finite scope. Two selected temporary mutations (ownership check removal and attention scaling error) established baseline PASS -> expected semantic FAIL -> restored PASS in isolated source trees. This is not a global mutation coverage number.

The real demo produced admission, denial, cancellation, completion and zero final reservations/pages. Browser QA loaded its owned HTML with `set_content`, checked first keyboard focus, desktop/mobile overflow and embedded resources, and captured actual screenshots. Filesystem URL navigation was restricted by the author environment; no browser-security setting was disabled.

A **fresh committed source checkout passed on the same host and installed dependencies**. This is deliberately narrower than the required fresh dependency installation/reproduction gate.

## Actual small benchmark, including the unfavorable result
All variants processed the same 64-position tiny synthetic workload. One warmup per variant, then five fresh-process repetitions per variant with rotated order; output values matched exactly. Process wall time includes loading and JSON output. Raw observations: [benchmark JSON](verification/published/observations/benchmark.json).

|Variant|Median ms|Min ms|Max ms|
|---|---:|---:|---:|
|contiguous|4.383|3.893|5.582|
|paged|5.474|5.118|5.777|
|serial-recompute|29.519|27.008|29.790|

Paged execution was slower than contiguous execution in this tiny measurement. The result does not establish a universal regression or advantage. CPU affinity was not pinned, the host was shared, the model was synthetic and only one workload was measured. RSS, serving TTFT, p99 latency, energy and production capacity were NOT MEASURED. Full reference-host evaluation remains PARTIAL.

## Failed, blocked and interrupted work
Actual model-download attempt failed with temporary DNS resolution failure. Actual real-model target failed because Transformers was not installed. Actual online-security target refused to proceed without gitleaks/pip-audit. Their nonzero command receipts are retained; no success was substituted. Pinned real-model execution and deterministic real-model conversion remain BLOCKED.

Two author-side bundled command invocations were interrupted before complete receipts for their next command were written. Those incomplete attempt directories are not published as PASS evidence. Static analysis and clean-checkout verification were rerun individually and completed with their own receipts. The cause of the outer interruptions is not established as a product defect or a passed run. Earlier compiler/style and analyzer findings were corrected and rerun, not suppressed.

No independent-agent review, fresh dependency installation, resolved-transitive hash lock, full-history secret/advisory scan, complete license inventory, hosted CI, public repository creation or service deployment has been established.

## Reproduce and interpret
See README.md for commands and TEST_MATRIX.md for criterion mapping. Receipts include actual command arrays, exits, timestamp/duration, tool versions, Git metadata and source/stdout/stderr hashes. `python3 scripts/evidence.py verify verification/published/core` verifies the current defined source and recorded output bytes. A changed output or source manifest is rejected. Hashes are local byte bindings, not independent attestation against someone who controls the source and all records.

The overall product release gate is intentionally FAIL: 19 locally passing criteria, 2 FAIL, 3 BLOCKED, and independent verification NOT RUN. `make verify` does not override `make release-verify`.
