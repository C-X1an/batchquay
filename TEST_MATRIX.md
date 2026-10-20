# Test and acceptance matrix

The [criterion index](verification/criterion_status.json) contains current status and source-bound receipt paths. This table records fixed requirements, not a second mutable readiness tally. Historical schema-v1 receipts are checked with --historical.

| Criterion | Locked requirement / label | Required receipt categories |
|---|---|---|
| AC-001 | FR-001 / tiny-numerics | core |
| AC-002 | FR-002 / cache-equivalence | core |
| AC-003 | FR-003 / cache-owner | core |
| AC-004 | SEC-003 / page-reuse | core |
| AC-005 | REL-001 / reclaim | core |
| AC-006 | FR-004 / rounds | core |
| AC-007 | FR-005 / cancel | core |
| AC-008 | PERF-003 / fairness | core |
| AC-009 | PERF-002 / admission | core |
| AC-010 | FR-006 / protocol | core |
| AC-011 | SEC-002 / model-loader | core |
| AC-012 | FR-007 / real-model | real-model |
| AC-013 | FR-007 / model-convert | real-model |
| AC-014 | SEC-001 / authority | public-audit |
| AC-015 | FR-008 / inspector | core, browser |
| AC-016 | NFR-001 / clean | clean |
| AC-017 | NFR-003 / sanitizers | sanitizers |
| AC-018 | SEC-004 / public-audit | public-audit, security-online |
| AC-019 | PERF-001 / benchmark | benchmark |
| AC-020 | REL-002 / restart | core |
| AC-021 | NFR-002 / version | core |
| AC-022 | FR-009 / batching | core, benchmark |
| AC-023 | FR-001 / mutation | mutation |
| AC-024 | NFR-001 / evidence-integrity | evidence-integrity |

Native and Python methods cover numerical properties, protocol/lifecycle, ownership/reclamation, evidence corruption, benchmark accounting, downloader behavior and synthetic conversion. Seeded sequences, repetitions and child invocations are not additional independent test designs. Mocked downloader unit responses do not establish real checkpoint fetching or pretrained conformance. The real checkpoint gate is mandatory.
