# Contributing to BatchQuay

Thank you for helping make inference behavior easier to inspect. This is a deliberately small systems experiment: changes should improve **correctness, clarity or evidence**, not add infrastructure for its own sake.

## Before opening a change

Read the [README](README.md), [architecture](ARCHITECTURE.md), [API contract](API_SPEC.md), [locked acceptance criteria](ACCEPTANCE_SPEC.md) and relevant [ADRs](docs/adr/001-cpu-original-core.md). For substantive scope/interface changes, explain the requirement, simpler alternative and removal test. Do not turn the trusted single-host core into an unreviewed service.

## Run the checks

```bash
make bootstrap
make build
make verify
```

For numerical or lifetime-sensitive changes, additionally run `make differential`, `make sanitize lint` in a supported Linux environment, and the relevant integration tests. Python-reference logic must remain separately expressed from the native code. A correction should include a regression that fails against the original defect.

## Evidence and acceptance discipline

- Check integrity using `python3 scripts/check_integrity.py` before integration.
- Record important commands through `python3 scripts/evidence.py run NAME -- COMMAND...` and preserve real failures and output hashes.
- Do not weaken, delete, skip or silently rewrite locked acceptance behavior. A genuine mistake requires a documented, reviewed exception.
- For critical invariants, use selected isolated **PASS → expected FAIL → PASS** negative controls where appropriate.
- Do not present a mocked result as native integration, or synthetic observations as pretrained-model results.

## Keep the public tree public-safe

Contribute original source, useful tests, reproducible synthetic fixtures, documentation and reviewed evidence only. **Never commit credentials, model weights, personal data, internal prompts, employer materials, private handoffs or raw agent conversations.** Check [third-party notices](THIRD_PARTY_NOTICES.md) for licensing.

For sensitive findings, follow the private-reporting instructions in [SECURITY.md](SECURITY.md); do not post exploit details or secrets in public issues.

---

See the [documentation guide](docs/README.md) for the quickest map of contracts, tests and limitations.
