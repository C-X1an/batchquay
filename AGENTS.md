# Contributor contract
Build a bounded, inspectable CPU inference runtime; do not inflate scope or claims.

Canonical order: verification/phase_plan.json (phase structure); ACCEPTANCE_SPEC.md; PRD.md; ARCHITECTURE.md; THREAT_MODEL.md / SECURITY.md; API_SPEC.md; other documentation. Phase and acceptance locks are immutable. Run scripts/check_integrity.py; do not regenerate hashes to hide changes. Record justified deviations and preserve old definitions.

One writer per path. Keep numerical model, cache, scheduler and tests in separate owned work areas. Reviewers are read-only until findings are recorded. Maintain strict C++20 warnings, checked resource arithmetic, RAII, explicit errors, bounded parsers and independent reference calculations. Do not copy implementation logic into an oracle and call it independent.

Commands: `make bootstrap build`; `make fmt` (text hygiene); `make format` (optional clang-format); `make lint` (Clang analyzer); `make typecheck` (compiler/Python syntax, not mypy); `make test`; `make differential`; `make integration`; `make evidence-test fetch-test conversion-test`; `make sanitize mutation security`; `make benchmark demo`; `make clean-verify`; `make security-online`; `make fetch-model real-model`; `make release-verify`. NumPy is needed for differential; Torch/safetensors for conversion; a network-provisioned reference environment for real-model checks.

`make verify` is a core gate, not release approval. Capture meaningful commands with `python3 scripts/evidence.py run NAME -- COMMAND...`; verify receipts and preserve source/output hashes. Never fabricate execution, metrics, screenshots, deployment, users or independent review. Never silently weaken/skip tests or replace integration with mocks. Selected mutations must establish baseline PASS, expected semantic FAIL, restored PASS in disposable trees.

An unavailable external credential or OS permission blocks only its narrow task. Use explicit placeholders outside the runtime, continue independent work, and never pass a mocked path as the real integration. Do not put secrets or private execution/research material into this public tree. Update VERIFICATION_REPORT.md, CLAIMS_EVIDENCE.md and verification/criterion_status.json after meaningful checks. Completion requires all locked criteria and an independent review, not a green subset.
