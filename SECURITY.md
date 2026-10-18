# Security policy and supported boundary

BatchQuay is experimental. No version has an independent security certification. It is a local, trusted-host numerical/runtime experiment, not an Internet service or hostile-code sandbox.

Do not process sensitive real user prompts in the demo. Do not enable remote code or deserialize pickle checkpoints. Do not run untrusted model preparation code with credentials. No model APIs, tools, prompt-based permissions or outbound telemetry exist in the core.

Request isolation means checked cache ownership, generation and lifecycle. It does not hide memory from the process owner, prevent CPU timing channels, protect core dumps, or make generated text safe for downstream tools. Read THREAT_MODEL.md and LIMITATIONS.md before extending the boundary.

Use private GitHub vulnerability reporting if enabled on the eventual repository. If unavailable, open a minimal issue asking for a private reporting channel without exploit details or secrets. No response-time SLA is claimed. Maintainers must triage reports, reproduce in a disposable environment, add a regression test and publish an evidence-backed fix notice. Do not publicize an unverified exploit claim.

CI for untrusted pull requests uses read-only permissions and no secrets; never run PR code through pull_request_target. Model weights and downloaded tools stay outside version control. Public releases include reviewed source, tests, synthetic fixtures, notices and curated evidence, not the research resume or private agent files.
