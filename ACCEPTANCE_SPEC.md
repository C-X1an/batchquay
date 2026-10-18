# Locked acceptance specification

acceptance_spec_locked: true
version: 1.0

Generated before product implementation. Add stricter criteria freely; never weaken these without a documented TEST_SPEC_EXCEPTION with independent assessment and preserved history. Each criterion is a full product gate unless explicitly conditional (optional adapter behavior in AC-014). A kernel-only milestone is not full acceptance.

## AC-001 - FR-001

Precondition: Tiny deterministic model and independent reference.

Input: Fixed token sequence, per-position logits.

Behavior: Run C++ original decoder and full-prefix oracle.

Expected result: All finite logits agree.

Tolerance: max abs <=3e-5 and RMS <=3e-6.

Test level: differential. Evidence type: numerical. Test label: `tiny-numerics`.

## AC-002 - FR-002

Precondition: Same weights; fresh and cached executions.

Input: At least 100 seeded sequences, lengths 1..32.

Behavior: Compare every position, not only generated text.

Expected result: Cached and recomputed logits agree.

Tolerance: AC-001 tolerance.

Test level: property. Evidence type: numerical. Test label: `cache-equivalence`.

## AC-003 - FR-003

Precondition: Allocated page bound to A/generation1.

Input: Read or write using B or stale generation.

Behavior: Validate handle before data access.

Expected result: Typed rejection and unchanged owner state.

Tolerance: zero unauthorized accesses.

Test level: unit/security. Evidence type: ownership. Test label: `cache-owner`.

## AC-004 - SEC-003

Precondition: Page released after nonzero contents.

Input: Reallocate to B and use old A handle.

Behavior: Clear before reuse and reject old handle.

Expected result: No prior data visible to B; A cannot read.

Tolerance: exact.

Test level: security. Evidence type: ownership. Test label: `page-reuse`.

## AC-005 - REL-001

Precondition: Several admitted requests.

Input: Cancel, finish and inject forward failure.

Behavior: Release reservations/pages once.

Expected result: Capacity returns to baseline without double free.

Tolerance: exact counters.

Test level: integration. Evidence type: lifecycle. Test label: `reclaim`.

## AC-006 - FR-004

Precondition: Mixed prompt lengths and decode budgets.

Input: Tick scheduler across both types.

Behavior: Bound prefill chunk; interleave eligible requests.

Expected result: No monopolization by unbounded prefill.

Tolerance: configured chunk <=4 in test.

Test level: integration. Evidence type: scheduler. Test label: `rounds`.

## AC-007 - FR-005

Precondition: Active request with partial progress.

Input: CANCEL then repeated scheduler ticks.

Behavior: Invalidate before acknowledging cancellation.

Expected result: No later token or completion-success event for request.

Tolerance: zero late commits.

Test level: acceptance. Evidence type: lifecycle. Test label: `cancel`.

## AC-008 - PERF-003

Precondition: Two or more always eligible decode requests.

Input: Several completed scheduler rounds.

Behavior: Count successful token grants per request.

Expected result: Grant counts differ by <=1.

Tolerance: one grant.

Test level: property. Evidence type: scheduler. Test label: `fairness`.

## AC-009 - PERF-002

Precondition: Cache reservations at capacity.

Input: Admit one more request.

Behavior: Check total reservation before admission.

Expected result: New request denied; prior requests unchanged.

Tolerance: exact.

Test level: acceptance. Evidence type: resource. Test label: `admission`.

## AC-010 - FR-006

Precondition: Protocol parser initialized.

Input: Unknown fields, malformed IDs, token counts and oversized line.

Behavior: Parse bounded record fully before mutation.

Expected result: Typed errors and no state change.

Tolerance: zero accepted invalid records.

Test level: fuzz/contract. Evidence type: parser. Test label: `protocol`.

## AC-011 - SEC-002

Precondition: Binary model loader.

Input: Truncated payload, extra bytes, huge dimensions, nonfinite weights.

Behavior: Check shapes/length/finite values before execution.

Expected result: Refuse unsupported or unsafe model.

Tolerance: exact rejection.

Test level: security. Evidence type: loader. Test label: `model-loader`.

## AC-012 - FR-007

Precondition: Pinned real checkpoint converted to FP32.

Input: 20 fixed token sequences, lengths 1..32.

Behavior: Compare original C++ logits to independent Transformers eager CPU FP32.

Expected result: Logits agree and confident top-1 matches.

Tolerance: max abs <=0.01; mean abs <=0.001; top-1 equal where ref margin >=0.02.

Test level: integration/differential. Evidence type: pretrained. Test label: `real-model`.

## AC-013 - FR-007

Precondition: Pinned model revision and all local artifacts.

Input: Conversion repeated twice.

Behavior: Record source hashes; deterministic output.

Expected result: Identical converted-model hashes.

Tolerance: exact.

Test level: reproducibility. Evidence type: pretrained. Test label: `model-convert`.

## AC-014 - SEC-001

Precondition: Trusted CLI vs optional network adapter boundary.

Input: Attempt body tenant spoofing against any implemented remote adapter.

Behavior: Derive identity only from trusted context.

Expected result: CLI documented as trusted; optional adapter rejects spoofing.

Tolerance: no auth claim without real auth tests.

Test level: security/review. Evidence type: boundary. Test label: `authority`.

## AC-015 - FR-008

Precondition: Real trace containing success, denial, cancellation.

Input: Generate offline report with malicious string fixture.

Behavior: Escape data; include source IDs and evidence links.

Expected result: No scripts/resources injected; all three outcomes inspectable.

Tolerance: exact; keyboard review required.

Test level: e2e. Evidence type: demo. Test label: `inspector`.

## AC-016 - NFR-001

Precondition: Fresh committed checkout.

Input: Install listed dependencies; build and tiny demo.

Behavior: Run complete documented sequence outside author tree.

Expected result: Build, meaningful tests and demo pass.

Tolerance: zero omitted required steps.

Test level: clean-environment. Evidence type: reproduction. Test label: `clean`.

## AC-017 - NFR-003

Precondition: Supported Linux compiler.

Input: Address and undefined-behavior sanitizer campaigns.

Behavior: Run unit, parser and lifecycle tests under instrumentation.

Expected result: No sanitizer findings.

Tolerance: zero.

Test level: system/security. Evidence type: sanitizer. Test label: `sanitizers`.

## AC-018 - SEC-004

Precondition: Public export and git history.

Input: Inspect tracked files, logs, fixtures and license inventory.

Behavior: Run allowlist/privacy checks and secret scanner.

Expected result: No private content or unapproved dependency license.

Tolerance: zero unresolved material findings.

Test level: release. Evidence type: publication. Test label: `public-audit`.

## AC-019 - PERF-001

Precondition: Reference host with source identity.

Input: Serial, contiguous and paged variants under same workloads.

Behavior: Warmup and retain >=5 independent repetitions.

Expected result: Raw distributions/resource counts and honest comparisons.

Tolerance: no cherry-picking; performance win not required.

Test level: performance. Evidence type: benchmark. Test label: `benchmark`.

## AC-020 - REL-002

Precondition: Active process with pending work.

Input: Kill process, restart and submit old session handle.

Behavior: Do not recover in-memory state implicitly.

Expected result: Old session rejected; new session starts empty.

Tolerance: exact.

Test level: fault-injection. Evidence type: restart. Test label: `restart`.

## AC-021 - NFR-002

Precondition: Known protocol/model version.

Input: Unknown version and invalid record.

Behavior: Return documented error; nonzero fatal exit.

Expected result: No silent coercion or arbitrary interpretation.

Tolerance: exact.

Test level: contract. Evidence type: compatibility. Test label: `version`.

## AC-022 - FR-009

Precondition: Scheduler with multiple sequences.

Input: Inspect execution and same-output baselines.

Behavior: Describe token scheduling vs fused execution separately.

Expected result: No fused-batching claim without actual fused backend evidence.

Tolerance: exact claim audit.

Test level: review. Evidence type: claims. Test label: `batching`.

## AC-023 - FR-001

Precondition: Passing relevant tests in disposable trees.

Input: Deliberately remove causal mask or cache isolation guard.

Behavior: Run same checks, restore source and rerun.

Expected result: PASS -> expected FAIL -> PASS.

Tolerance: all selected critical mutations killed.

Test level: mutation. Evidence type: negative-control. Test label: `mutation`.

## AC-024 - NFR-001

Precondition: Evidence runner and final claims index.

Input: Tamper with a retained output and rerun verification.

Behavior: Rehash raw output and source identity.

Expected result: Changed evidence rejected; no Markdown-only PASS.

Tolerance: exact.

Test level: acceptance. Evidence type: evidence. Test label: `evidence-integrity`.
