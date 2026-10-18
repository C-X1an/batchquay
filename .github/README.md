# CI scope
Workflows are authored but have not run remotely in this handoff. Core CI is intentionally not the full release gate; pretrained execution is manual to avoid repeated model downloads on untrusted PRs. Workflows receive contents:read only and do not use repository secrets or pull_request_target. Checkout is pinned to a verified complete upstream commit.

Missing release work: resolved transitive hash lock/license inventory, online security scan results, durable retained CI evidence/artifact handling, fresh dependency reproduction, independent review and complete reference-host benchmarks. Do not add a passing badge before a real run. Do not give an untrusted PR elevated access or execute it on a credential-bearing self-hosted runner.
