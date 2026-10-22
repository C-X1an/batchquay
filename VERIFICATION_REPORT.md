# Verification and reproducibility

The [criterion index](verification/criterion_status.json) records the assessed source commit, source and release hashes, all 24 locked criteria, and the exact independent review artifact. The [evidence index](verification/evidence_index.json) identifies its actual command receipts. Check those bindings before treating a result as evidence for a different checkout.

The [measured assessment](verification/published/current-assessment/REPORT.md) contains the source-bound conformance results and all six synthetic benchmark workloads. Its [machine-readable measurements](verification/published/current-assessment/measurements.json), [host environment](verification/published/current-assessment/host-environment.json) and [CI observation](verification/published/current-assessment/ci-observation.json) explain the execution scope. The indexed benchmark bundle retains every warmup, repetition and native companion file, including unfavorable timings.

## Run the gates

Use GCC, GNU Make, CMake, Ninja, Git and Python 3.12 on a supported host. Install the [hash-locked core dependencies](requirements-core.lock) in a fresh virtual environment. The Windows reference lock and browser lock support the separate pretrained and browser gates; see [operations](OPERATIONS.md) and [third-party notices](THIRD_PARTY_NOTICES.md).

```sh
make bootstrap
make verify
make conversion-test
make sanitize lint
make mutation
make benchmark
make clean-verify
make security-online
make real-model
make release-verify
```

`make verify` checks the core build, native and Python tests, numerical oracle, process behavior, evidence integrity, bounded export policy and actual native demo. Linux Clang is required for sanitizer checks. Conversion and real-model execution require the reference environment and the pinned checkpoint; synthetic oracle success does not establish pretrained-model conformance.

`make release-verify` additionally checks all criterion-specific command and semantic contracts, exact current source and release bindings, the genuine independent assessment, and the complete current publication candidate plus Git history. It requires Gitleaks on PATH. It fails when any required evidence is missing, stale or invalid. The [test matrix](TEST_MATRIX.md), [acceptance contract](ACCEPTANCE_SPEC.md) and [benchmark method](BENCHMARKS.md) define the required behavior.

## Inspect a receipt

Find a bundle's `receipt` path in the evidence index, then run:

```sh
python3 scripts/evidence.py verify verification/published/BUNDLE_FROM_INDEX
```

The bundle includes the actual command, exit status, environment, source/release manifests, captured output and named semantic artifacts. Published streams disclose any local-path and line-ending transformation; original streams remain separate. Hashes bind the retained bytes locally. They are not signatures or third-party attestation.

The live [Core verification workflow](https://github.com/C-X1an/batchquay/actions/workflows/core.yml) runs the core, sanitizers, static analysis, selected semantic mutations and a fresh committed checkout with new hash-locked core dependencies. The README badge follows real push runs on `main`; it does not replace full release verification.

## Failures and public scope

[Run 39745310021](https://github.com/C-X1an/batchquay/actions/runs/39745310021) failed after the presentation update introduced four SVGs outside the export allowlist. The evidence test exposed that refusal. The policy explicitly permits those four reviewed assets while preserving unknown-path, symlink, generated/private-file and secret checks. The failing run remains available as a failure; later results must be read from their own runs.

The public tree retains source, build and reproduction tools, tests, contracts, documentation, demo, licenses and one indexed evidence set. Superseded duplicate bundles and the obsolete author observation manifest were archived before removal from the current tree. Existing Git history is preserved. The [Certifi remediation](verification/published/certifi-remediation/remediation.json) keeps the actual advisory finding and before/after results visible.

The measured runtime is experimental, single-host and CPU-only. Synthetic workload latency is distinct from pretrained throughput or language quality. No GPU, fused GEMM, HTTP inference deployment, production capacity, universal speed advantage or security certification is claimed; see [limitations](LIMITATIONS.md).
