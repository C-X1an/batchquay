# Test and acceptance matrix

Every locked criterion is required. Current release receipt collection is pending; historical schema-v1 evidence remains available under verification/published and must be verified with --historical.

| Criterion | Locked requirement / label | Current release state |
|---|---|---|
| AC-001 | FR-001 / tiny-numerics | Pending final source-bound evidence |
| AC-002 | FR-002 / cache-equivalence | Pending final source-bound evidence |
| AC-003 | FR-003 / cache-owner | Pending final source-bound evidence |
| AC-004 | SEC-003 / page-reuse | Pending final source-bound evidence |
| AC-005 | REL-001 / reclaim | Pending final source-bound evidence |
| AC-006 | FR-004 / rounds | Pending final source-bound evidence |
| AC-007 | FR-005 / cancel | Pending final source-bound evidence |
| AC-008 | PERF-003 / fairness | Pending final source-bound evidence |
| AC-009 | PERF-002 / admission | Pending final source-bound evidence |
| AC-010 | FR-006 / protocol | Pending final source-bound evidence |
| AC-011 | SEC-002 / model-loader | Pending final source-bound evidence |
| AC-012 | FR-007 / real-model | Pending final source-bound evidence |
| AC-013 | FR-007 / model-convert | Pending final source-bound evidence |
| AC-014 | SEC-001 / authority | Pending final source-bound evidence |
| AC-015 | FR-008 / inspector | Pending final source-bound evidence |
| AC-016 | NFR-001 / clean | Pending final source-bound evidence |
| AC-017 | NFR-003 / sanitizers | Pending final source-bound evidence |
| AC-018 | SEC-004 / public-audit | Pending final source-bound evidence |
| AC-019 | PERF-001 / benchmark | Pending final source-bound evidence |
| AC-020 | REL-002 / restart | Pending final source-bound evidence |
| AC-021 | NFR-002 / version | Pending final source-bound evidence |
| AC-022 | FR-009 / batching | Pending final source-bound evidence |
| AC-023 | FR-001 / mutation | Pending final source-bound evidence |
| AC-024 | NFR-001 / evidence-integrity | Pending final source-bound evidence |

The suites currently contain 17 native tests and Python methods for numerical properties, protocol/lifecycle, evidence corruption, benchmark accounting, downloader behavior and synthetic conversion. Repetitions, seeded sequences and child invocations are not additional independent test designs. Downloader unit tests use mocked network responses; real checkpoint fetching/conformance is a separate mandatory integration gate.
