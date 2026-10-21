# CI verification scope

The core workflow executes native, numerical, process, evidence-integrity, benchmark-regression, sanitizer, static-analysis and selected mutation checks. It also provisions a fresh committed checkout with a new hash-locked core dependency environment. Its artifact retains actual outputs, including failures, and excludes model weights.

The [source-bound evidence index](../verification/evidence_index.json) links completed CI observations and their retained original artifacts. Read that evidence for actual run status. Core CI is one part of full release verification; real pinned-checkpoint conformance, deterministic conversion, the complete reference dependency environment, browser checks, full benchmark measurements, advisory/license scans and independent approval have separate evidence requirements. `make release-verify` enforces the complete criterion map and final publication audit.

Pretrained execution is a manual workflow to avoid repeated model downloads on untrusted pull requests. Workflows use `contents: read`, pinned action commits, no repository secrets and no `pull_request_target`. Do not give an untrusted pull request elevated access or run it on a credential-bearing self-hosted runner.

The repository landing page is the [root README](../README.md). This CI guide uses a distinct filename so it does not take precedence over that introduction.
