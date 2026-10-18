# Test and acceptance matrix

The contract was locked before implementation. PASS means the stated finite local check passed, not independent certification. Full release remains NOT READY.

|Criterion|Requirement / check|Status|Evidence and limitation|
|---|---|---|---|
|AC-001|FR-001 / tiny-numerics|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-002|FR-002 / cache-equivalence|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-003|FR-003 / cache-owner|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-004|SEC-003 / page-reuse|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-005|REL-001 / reclaim|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-006|FR-004 / rounds|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-007|FR-005 / cancel|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-008|PERF-003 / fairness|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-009|PERF-002 / admission|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-010|FR-006 / protocol|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-011|SEC-002 / model-loader|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-012|FR-007 / real-model|BLOCKED|[pretrained](verification/published/pretrained/record.json), [model-fetch](verification/published/model-fetch/record.json). Pinned pretrained checkpoint not fetched; Transformers not installed. No numerical conformance claim.|
|AC-013|FR-007 / model-convert|BLOCKED|[conversion](verification/published/conversion/record.json), [pretrained](verification/published/pretrained/record.json). Synthetic deterministic conversion passed; real checkpoint conversion hash gate not run.|
|AC-014|SEC-001 / authority|PASS|[core](verification/published/core/record.json). Trusted local CLI only; no network adapter/authentication claim. Public boundary explicitly documented.|
|AC-015|FR-008 / inspector|PASS|[core](verification/published/core/record.json), [browser](verification/published/browser/record.json). Actual process report, script-string escaping tests and set_content browser keyboard/layout inspection; not hosted navigation.|
|AC-016|NFR-001 / clean|FAIL|[clean](verification/published/clean/record.json). Fresh committed source checkout passed on same installed host; fresh dependency provisioning and hash-lock remain unestablished.|
|AC-017|NFR-003 / sanitizers|PASS|[sanitizers](verification/published/sanitizers/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-018|SEC-004 / public-audit|BLOCKED|[core](verification/published/core/record.json), [online-security](verification/published/online-security/record.json). Local export/content checks passed; independent full-history scanner and transitive license inventory not run.|
|AC-019|PERF-001 / benchmark|FAIL|[benchmark](verification/published/benchmark/record.json). Five repetitions per variant on one tiny workload; reference-host, mixed-workload, serving-latency and RSS study not done.|
|AC-020|REL-002 / restart|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-021|NFR-002 / version|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-022|FR-009 / batching|PASS|[core](verification/published/core/record.json), [benchmark](verification/published/benchmark/record.json). Sequential interleaving is explicitly not called fused batching; source and output baseline checks support this narrow claim.|
|AC-023|FR-001 / mutation|PASS|[mutation](verification/published/mutation/record.json). Local finite automated checks only; independent release review remains separate.|
|AC-024|NFR-001 / evidence-integrity|PASS|[core](verification/published/core/record.json). Local finite automated checks only; independent release review remains separate.|

## Named test count and types
15 native cases plus 18 Python test methods (2 numerical, 7 process-system, 3 evidence/report, 4 synthetic conversion, 2 downloader retry/integrity) = 33 named checks. The 100 seeded numerical sequences and three execution variants are property cases within that count, not 300 additional test designs. The two downloader tests mock network responses explicitly; they do not prove the real checkpoint downloaded. Native process tests execute the real compiled program.

Fuzz/hostile input testing is a finite seeded parser/model campaign, not continuous coverage-guided fuzzing. Sanitizers cover native and process tests, not an arbitrary hostile native plugin. No broad mutation score, security certification or production coverage is asserted.
