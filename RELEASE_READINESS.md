# Release readiness

The authoritative current state is [verification/criterion_status.json](verification/criterion_status.json). Its overall field and hashed independent assessment determine readiness; this document defines the gate and does not independently assert READY or NOT READY.

All 24 locked criteria require current-source integration receipts, exact command/tool bindings, retained semantic artifacts, a fresh hash-locked reproduction, supported-Linux sanitizer evidence and independent final approval. Static-analyzer evidence and actual remote CI are retained separately in the evidence index. Historical receipts remain available with their original source scope.

The terminal-replay exception requires a hashed independent acceptance of its exact bytes. An accepted exception does not approve unrelated release work. `make verify` is the core gate only. `make release-verify` checks criterion evidence and the final independent report, then freshly audits every current export file and all referenced history through the publication commit. Its last audit stays outside Git to avoid a self-hash loop.

Public stream capture discloses local-path/LF transformations and preserves original hashes. Raw originals are checked for locally retained receipts; published Git bundles intentionally omit private local originals. Semantic outputs and companion files are snapshotted so later producer runs cannot alter earlier receipts. Public CI archives retain their nonpersonal originals.
