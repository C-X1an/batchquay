# TEST_SPEC_EXCEPTION: terminal request-ID replay

Status: **PENDING INDEPENDENT ACCEPTANCE**. This records a proposed resolution of a pre-existing contract conflict. It does not change the locked acceptance specification, does not declare the exception accepted, and is not release approval.

## Conflict and selected behavior

`API_SPEC.md` permits an owner/request ID to be reused after cancellation or completion, with a new generation. `ARCHITECTURE.md` instead promises a bounded completed-ID ledger that returns an already-terminal result without regenerating output. The implementation follows the API direction: after terminal state is removed, a later `SUBMIT` for the same owner/ID is intentional new work and receives a strictly newer generation.

The selected direction preserves the tested meanings of AC-005, AC-007, AC-020, and AC-021: state is reclaimed once, cancellation acknowledgement remains terminal for that generation, restart changes the session, and incompatible/stale session or generation values are rejected. The original contracts and acceptance locks remain unchanged.

## Explicitly overridden architecture and threat-model statements

This exception, if independently accepted, overrides all of the following statements for version 1:

- The already-terminal cancellation behavior in `ARCHITECTURE.md`: after terminal removal, `CANCEL` returns `E_NOT_FOUND`. If the owner/ID has already been reused, cancellation carrying the old generation returns `E_STALE`. A completed request is not retroactively cancelled.
- The bounded completed-ID ledger promise in `ARCHITECTURE.md`: version 1 retains no completed-result ledger and therefore cannot replay a prior terminal response.
- The bounded-terminal-ledger control listed for TH-015 in `THREAT_MODEL.md`: session and generation binding remain controls, but a ledger is not implemented and must not be claimed as evidence.

## Retry semantics and residual risk

A `SUBMIT` whose response was lost is not distinguishishable from intentional new work after the prior generation becomes terminal. Retrying that `SUBMIT` can therefore regenerate output under a new generation. The runtime does not provide durable or in-memory exactly-once request delivery.

Every client must attribute responses using the complete `(session, owner, request ID, generation)` tuple, retain the accepted generation, and reject events for a different session or generation. Reusing only owner/request ID can confuse output attribution. Already emitted tokens cannot be retracted, and a transport that needs idempotent retries must add its own idempotency key/result store outside this native protocol.

Residual risk remains that a buggy controller drops session/generation metadata and treats regenerated output as the original request. This is a trusted-controller integration risk, not an authentication or durable-delivery guarantee.

## Independent assessment state

A separate read-only source review found the new-generation reuse direction technically defensible and compatible with AC-005/007/020/021, but required the missing overrides and residual risk above to be documented. That review did **not** accept this exception or approve release. Its public-safe disposition is: `CHANGES_REQUIRED pending corrected exception and updated independent assessment`.

Acceptance requires a new, hashed, privacy-safe independent-review artifact that identifies the reviewed source/commit scope and explicitly records `ACCEPTED` or `REJECTED` for this corrected exception. Until then, the status remains pending and the release gate must fail.
