# Private orchestration and public inspectability

## Context and drivers
Public reviewers need code/tests/evidence, not a resume or private agent transcript.

## Options
Publish everything; publish source without tests; trust Markdown claims.

## Decision
Separate private handoff from the public tree; publish bounded synthetic receipts and source identities.

## Consequences
Useful tests remain public; sensitive research and raw account diagnostics do not.

## Risks
Source hashes are not third-party attestation and logs require content review.

## Revisit when
Revisit artifact storage as evidence volume grows, preserving reproducibility and attribution.
