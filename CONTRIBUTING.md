# Contributing
Discuss substantive scope/interface changes against PRD.md, API_SPEC.md and the existing ADRs. Keep the single-host core coherent. Avoid introducing a service, database or dependency without a concrete requirement and removal test.

Use the Make targets in README.md. Build with the strict existing warnings; run tests, differential checks and sanitizer/static analysis for numerical or lifetime changes. Keep a separate oracle expression. Every bug fix needs a failing regression; critical invariants benefit from a targeted temporary mutation. Do not weaken or delete locked acceptance behavior to fit an implementation.

Run `python3 scripts/check_integrity.py` before integration. Capture important commands through `python3 scripts/evidence.py run NAME -- COMMAND...`. Never edit a generated receipt to claim a test ran. Add stricter cases, preserve failures, distinguish mocks from real-process integration, and retain limitations. Acceptance corrections require an explicit exception with evidence and review, not regenerating the lock hash.

Only public source, useful tests, bounded synthetic examples, documentation, licenses and reviewed reproducibility evidence belong in this tree. Never add model weights, personal data, credentials, private handoffs, raw agent conversations or employer material. Report sensitive issues using SECURITY.md, not public proof-of-exploit material containing secrets.
