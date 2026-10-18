# BatchQuay product requirements

Version 1.0; design contract, not a completion claim. Research as of 2026-10-19.

## Product thesis and users
BatchQuay is a bounded CPU transformer inference runtime and scheduling workbench for engineers who need to explain how model execution, request state and scheduling interact. Its primary users are inference/backend engineers and technical reviewers. They should be able to reproduce a numerical comparison, inspect a cache-ownership failure and measure an honest performance tradeoff without cloud access.

The problem is not lack of another general model server. It is the difficulty of seeing whether an optimization preserves model semantics and request boundaries. The deliverable is an original, narrow inference engine with independently checkable results, not a replacement for llama.cpp, vLLM or SGLang.

## User stories and use cases
An engineer loads an approved local model, runs known token IDs, and compares per-position logits against a full-prefix reference. A reviewer interleaves two requests, cancels one and confirms the other's output matches isolated execution. An operator submits work beyond the configured cache reservation and receives a denial before existing requests are harmed. A performance engineer compares serial recomputation, contiguous caching and paged scheduling on the same fixed workload, including cases where the proposed design is slower.

## Scope
The finishable core is one Linux host, one owning process, one tied-embedding Llama-family model, deterministic greedy generation, a bounded local control protocol, a paged KV arena and round-robin request scheduling. The initial numerical kernel may be a separately documented milestone, but full completion requires actual SmolLM2-135M integration and the scheduler/acceptance gates. No fixed delivery dates are promised.

CLI inputs come from a trusted host. The eventual loopback HTTP adapter is OPTIONAL and cannot establish tenant authentication merely by accepting a tenant field. Fused batched GEMM, an optimized BLAS backend, GPU execution and a text-tokenizer frontend are OPTIONAL. Token scheduling is required; calling serial matvec loops a fused batching optimization is prohibited.

## Stable requirements
|ID|Requirement|Contract|
|---|---|---|
|FR-001|Original C++ decoder|Implement FP32 tied-embedding decoder with RMSNorm, half-rotation RoPE, grouped-query causal attention, residuals and SwiGLU; reject unsupported architectures.|
|FR-002|Incremental equivalence|Cached one-token execution must match an independently implemented full-prefix oracle within locked numerical tolerances.|
|FR-003|Owned paged cache|Every live cache page belongs to exactly one request handle; stale generations and incorrect owners are rejected.|
|FR-004|Bounded scheduling|Actor-owned round-robin scheduler interleaves admitted requests, with bounded prefill chunks and one decode token per eligible round.|
|FR-005|Cancellation|A successful cancellation acknowledgment is terminal; it invalidates the request before any subsequent output can be committed.|
|FR-006|Closed local protocol|Expose versioned bounded request/control records and structured outputs; caller supplies token IDs, not executable code or paths.|
|FR-007|Public pretrained integration|Import and execute pinned SmolLM2-135M weights without pickle or remote code; compare real logits with a separately installed reference implementation.|
|FR-008|Inspectable demo|Generate an offline, escaped report from actual successful, denied and cancelled executions, with a visible source/evidence identity.|
|FR-009|Explicit batching semantics|Offer multi-sequence token scheduling. Distinguish this from fused batched matrix execution; a fused backend is optional and must have separate evidence.|
|SEC-001|Authority boundary|The local CLI host is trusted. An optional remote adapter derives tenant identity from authentication, never a client body field. No multi-user authentication claim for the CLI.|
|SEC-002|Input and allocation bounds|Validate shape products, counts, token ranges, binary length, finite weights, IDs and record length before unsafe use or large allocation.|
|SEC-003|Cache reuse isolation|Retired cache pages cannot be read through old handles and are cleared before reuse; cross-request prefix sharing is disabled.|
|SEC-004|Public-safe supply chain|No resume, secrets, employer files, private endpoints, raw agent transcripts or downloaded model weights in the public repository. Pin externally fetched material and retain notices.|
|REL-001|Resource reclamation|Terminal states release page reservations and owned pages exactly once, including cancellation and forward failure.|
|REL-002|Explicit restart semantics|Process failure loses in-memory requests; restarting does not silently resume or claim exactly-once generation. Clients obtain an explicit new session.|
|NFR-001|Reproducibility|A fresh committed checkout can build and run the deterministic core without network credentials or a GPU.|
|NFR-002|Compatibility and diagnostics|Version protocol/model format; refuse incompatible formats; emit bounded error envelopes and use a documented nonzero exit for fatal input.|
|NFR-003|Maintainability and checks|Build with strict compiler warnings; maintain meaningful tests and run address/undefined-behavior sanitizers on supported Linux.|
|PERF-001|Honest measurement|Retain raw latency and resource observations with source, environment and workload metadata. Report all repetitions and target/result distinctions.|
|PERF-002|Bounded design capacity|Default full runtime limits: 16 live requests, at most 256 total positions per request, 16-token pages, model payload at most 1 GiB, cache at most 256 MiB. Smaller limits are configurable.|
|PERF-003|Fair grant accounting|For continuously eligible equal-weight decode requests, completed decode-grant counts differ by at most one after each completed scheduler round; do not interpret this as equal wall-clock latency.|

## Nonfunctional targets and scope of guarantees
Correctness takes precedence over speed. TARGET: all locked numerical/lifecycle criteria pass. TARGET: bounded resident cache allocation stays within configured page capacity; this does not bound interpreter/toolchain memory or all process RSS. TARGET: the tiny demo runs within 30 seconds on the declared reference host; this is not an observed number. No model-wide latency SLO is promised before measurement.

A request is admitted only after reserving ceil((prompt tokens + output budget)/page tokens) pages worth of capacity. Physical pages may be allocated lazily, but reservations cannot exceed total capacity. This conservative reservation prevents a late allocation shortage from silently damaging an accepted request. Cancellation occurs at a control-record boundary; a scalar/BLAS kernel already executing is not preempted. No hard sub-millisecond cancellation claim is made.

Supported reference environment: Linux x86-64, C++20 compiler, CMake >=3.25, Python >=3.11. GCC and Clang are validation targets; other platforms remain unverified until tested. CPU FP32 is the reference execution precision. Public model bfloat16 parameters are converted numerically to FP32, not reinterpreted as FP32 bytes.

## Privacy, retention and accessibility
Use only synthetic prompts for public evidence. Weights are downloaded locally into ignored storage and are not checked in. Default reports contain request IDs, numeric metrics and synthetic token IDs, not real user text. Local raw runs have an explicit retention policy: delete after 30 days unless retained by the operator; the program does not promise secure erasure. No telemetry or outbound network access in the engine.

The offline report must work without JavaScript, with headings, table headers, keyboard navigation, semantic text and no color-only outcomes. Command-line results are machine readable and errors are on stderr or typed records, never ambiguous prose mixed into logits.

## Edge cases and failure policy
Reject empty prompts, out-of-vocabulary tokens, duplicate live request IDs, invalid owners, exhausted quotas, unknown handles, stale generations, unsupported dimensions, zero/negative limits, NaN/Inf weights, overflowed tensor products, truncated/extra binary payloads and protocol garbage. Generation IDs never wrap; exhaustion is fatal and documented. On a numerical error, terminate that request and reclaim its state; no partial result is represented as successful completion. On process crash, all work is explicitly lost and must be resubmitted under a new session.

## Explicit non-goals
No new transformer research, model training, arbitrary architectures, distributed serving, consensus, speculative decoding, quantization, untrusted plugin execution, agent tools, prompt-injection detector, Internet-facing SaaS, authentication platform, cross-tenant prefix cache, timing confidentiality, production availability or useful language capability from random weights. Optional additions cannot delay core validation or dilute the central evidence.
