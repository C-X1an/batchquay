# Evaluation and benchmark plan
Targets, observations and external reference results are separate. No performance advantage is a release requirement.

## Core measurements
|Experiment|Claim/workload|Controls|Instrument and summary|Required evidence|
|---|---|---|---|---|
|Numerical oracle|Original decoder matches full-prefix NumPy reference; 100 seeded sequences lengths 1..32|Identical FP32 weights, full-prefix dense oracle, every-position logits|Maximum absolute and RMS error, finite checks; locked tolerances|Inputs, seed, dimensions, raw metrics and source hash|
|Real model|Pinned SmolLM2-135M matches independent Transformers eager CPU FP32; 20 fixed sequences|Same source revision, exact weights, no sampling or flash attention|max/mean absolute error; top-1 when reference margin >=0.02|Checkpoint/config/token input hashes, runtime versions, complete metrics|
|Serial vs cache|Cache avoids prefix recomputation on the same tiny/real model|Serial full-prefix recomputation, contiguous incremental and paged incremental, same model/tokens|Wall-clock p50/p95 per run, total elapsed, process resource usage, page utilization|>=5 independent repetitions, one warmup, all raw samples|
|Scheduler|Round-robin admission and cancellation under mixed lengths|1,2,4,8,16 clients; prompt lengths 4,16,64,128; output16,32; identical arrivals per variant|TTFT and inter-token latency from caller monotonic clock; grants, denials, cancellations|Complete event trace, reservations, seed, caller timing|
|Memory|Capacity/ownership under repeated lifecycle changes|Fixed max pages; enough cycles to force reuse; successful and rejected admissions|Reserved/physical pages plus RSS sampled externally; do not equate logical counts with RSS|Trace and resource samples|

Default benchmark environment is the actual host, not an invented reference machine. Record CPU model, logical cores, RAM, OS/kernel, compiler/build flags, Python/NumPy, affinity, BLAS threads and background-load limitations. Release benchmarks use optimized builds; sanitizer observations are separate. Pin OMP/BLAS threads to one for cross-variant scalar comparison. Repeat warmup once per variant, rotate variant order per repetition, retain every repetition, and use monotonic_ns. Report median and full range across repetitions; small samples do not justify narrow tail-confidence claims. Per-token p99 requires enough samples and an explicit estimator; do not compute p99 over five run totals and call it serving tail latency.

Synthetic token sequences and random weights are labelled synthetic. Separate DESIGN CAPACITY (16 live, 256 positions, 256 MiB cache defaults), TESTED CAPACITY (specific workloads executed), OBSERVED CAPACITY (measured limits), and REAL USER/PRODUCTION SCALE (none). An offline smoke run proves tooling only. Real-model performance is NOT YET MEASURED until that model actually runs.

Raw path `.local-runs/bench/<id>/`; reviewed synthetic receipts may be exported to `verification/published/`. Plots may be produced from retained CSV/JSON but are not necessary for release; tables in the offline inspector suffice. A slowdown is a useful result: identify paging, scalar loops, allocator, thread or protocol overhead. Never alter the workload to hide regression.

## Layered verification
Unit tests cover math shapes, arena handles and transition guards. Differential/property tests use an independently expressed full-prefix oracle. Contract/fuzz tests include bounded malformed protocol and binary mutations. Integration uses real child processes, not a mock engine. System tests kill/restart the actual process. Security checks attempt stale handles, owner mismatch, count/shape overflows and HTML injection. Sanitizers run actual unit and lifecycle paths. Clean reproduction starts from a committed checkout. Optional network adapters require real authentication tests and are excluded until implemented.

Critical test-the-tests protocol: obtain baseline PASS; make one targeted mutation in an isolated temporary source copy; run the same relevant suite and require the expected failure; discard the copy; rerun baseline PASS. Preserve all three outputs. Mutation count is limited to selected invariants, not a global mutation score. Never disable a failing assertion, skip a test silently or claim a mock establishes a real integration.

An independent verifier starts read-only and writes findings BEFORE fixes. It must inspect what could pass while still broken, compare tests with locked criteria, and audit scope of results. A single assistant's self-review is not independent-agent verification. Final integrator fixes validated findings and reruns affected checks. Release requires no unresolved material findings; missing external verification stays NOT RUN, not PASS.
