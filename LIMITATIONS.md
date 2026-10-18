# Limitations
This is a bounded experimental CPU runtime, not a production-serving platform.

The current successful numerical results use tiny synthetic weights. Mandatory real SmolLM2 checkpoint comparison is not yet run. No text-quality, useful-language-generation, model-training, GPU or mature-engine speedup claim follows from the tiny oracle result.

FP32 storage and activations use FP64 accumulations/angles; no cross-platform bitwise-FP32 guarantee. Sequential calls and interleaving do not constitute fused batching. The scheduler is a single actor; stdout backpressure and one long scalar kernel can block all work. Grant fairness does not guarantee latency, admission fairness or tenant authentication.

The CLI is a trusted local control interface. Owner strings are labels, not credentials. The local process, filesystem and operator are trusted. An internal borrowed C++ span must not be retained across release/reallocation; cache handle validation does not make arbitrary native pointer access safe. Page clearing is lifecycle hygiene, not OS-certified secure erasure. Timing and access-pattern leakage remain.

Model files and cache capacity are bounded, but accounting is not a hard OS RSS ceiling. Use a disposable process/cgroup for hostile input research. No Internet exposure, sandbox, dynamic code loading, network model retrieval in the runtime, durable pending work, replica recovery or distributed quota exists. Restart abandons in-memory requests.

Recorded benchmarks are a small shared-container process-wall-time experiment, not TTFT, p99 service latency, production throughput, energy or cost measurements. Dedicated reference-host and expanded mixed-workload measurements remain open. Clean committed checkout on the same installed host does not prove fresh dependency provisioning. Local self-review is not an independent review. See RELEASE_READINESS.md.
