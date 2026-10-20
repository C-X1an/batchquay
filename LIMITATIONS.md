# Limitations

This is a bounded experimental CPU runtime. Experimental release eligibility and production readiness are different claims; consult the current criterion index and its independent assessment.

Tiny synthetic numerical checks and real pinned SmolLM2-135M conformance are separate gates. Real numerical execution has passed on the documented CPU reference environment, but neither gate measures generated-language quality, model training, GPU behavior or mature-engine speedups.

FP32 storage/activations use FP64 reductions and angles; there is no cross-platform bitwise-FP32 guarantee. Token scheduling is a single actor with sequential kernels. Stdout backpressure and a long scalar kernel can block all work. Equal grant counts do not imply equal wall-clock latency, admission fairness or remote authentication. There is no fused batching backend.

The local process, filesystem and controller are trusted. Owner labels are not credentials. Validated cache access uses copied values; page handles/epochs reject stale or wrong owners, and reuse clears payloads before publishing new ownership. Arbitrary hostile native code and host-memory inspection are outside this boundary. Clearing is not OS-certified secure erasure; timing/access-pattern leakage remains.

Model/cache limits and reservation counters are not an OS RSS ceiling. Use an isolated process or cgroup for hostile-input research. No public inference listener, runtime model download, dynamic plugin execution, durable request recovery, distributed quota or production availability is supplied. Restart abandons in-memory state. The terminal-replay exception documents intentional ID reuse, absent completed-result ledger and retry/output-attribution risk.

Default benchmarks use six fixed synthetic workloads on the actual shared host. Reported token timings are visible at completed native grant-round boundaries and exclude model loading; process-wall time is separate. RSS is an OS high-water measurement, while logical/allocated KV values describe payload accounting. No HTTP latency, p99 production throughput, energy/cost study or dedicated-host guarantee follows. Real-model performance requires its own explicitly executed --model benchmark.

Fresh committed reproduction uses a new isolated hash-locked dependency environment on the same OS/toolchain; it is not a clean machine image. Separate read-only automated review is recorded as such, not presented as a human audit or certification. Raw local evidence is preserved privately; public Git bundles contain disclosed path/LF transformations, original hashes and immutable semantic snapshots. Public CI archives retain their nonpersonal raw originals.
