# Public execution evidence

Start with the [criterion index](../criterion_status.json), [evidence index](../evidence_index.json) and [measured assessment](current-assessment/REPORT.md). The indexes identify the exact source/release identity, current receipt directories and original independent assessment. They are the navigation authority; directory names alone do not establish current eligibility.

Each indexed command bundle retains its sealed record, source/release manifests, captured output and semantic artifacts. The benchmark includes all warmups, repetitions and native command/JSON/stderr companions. The current assessment also retains nested clean-environment and mutation command details. Read [verification and reproducibility](../../VERIFICATION_REPORT.md) for commands, prerequisites and the distinction between core checks and release approval.

The [Certifi remediation](certifi-remediation/remediation.json) retains the actual advisory failure, verified patched-wheel digest and before/after reports. Expected mutation failures remain inside their indexed PASS -> expected FAIL -> PASS campaign.

Superseded duplicate execution sets and the obsolete author observation manifest are archived outside this public tree. Their previously published history remains intact. Raw private paths, orchestration logs, account diagnostics, model weights, virtual environments and build products are outside the public export.

Receipt hashes are local integrity bindings, not signatures or independent attestation. Current source, output bytes, all locked criteria and genuine separate review must pass `make release-verify` before full experimental-release eligibility is claimed.
