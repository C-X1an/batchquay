# Deployment and operations
## Supported baseline
One trusted Linux x86-64 host with C++20 compiler, CMake >=3.25, Ninja or Make, Python >=3.11. Core tiny fixture generation uses Python standard library; differential tests additionally need NumPy. Current NumPy 2.5 series requires Python >=3.12; Python 3.11 uses a supported compatible NumPy pin. Exact executed environment is in verification receipts, not inferred from recommendations. No runtime service dependencies, credentials or GPU.

```sh
make bootstrap
make build
make test
make differential
make integration
make demo
make sanitize
make mutation
make benchmark
make verify
make clean-verify
```
`make format` applies available clang-format; `make fmt` checks formatting. `make lint` uses strict compilation and compiler diagnostics, plus a separately available static analyzer; any unavailable requested analyzer is BLOCKED, not silently skipped. `make typecheck` is C++ compilation plus Python syntax checking; it is not a claim of Python static type proof. `make security` runs local input/privacy/integrity checks; `make security-online` additionally needs network-capable dependency/scanner tooling. `make real-model` requires the pinned downloadable checkpoint and independent reference dependencies. Refer to Makefile for exact implemented commands and limitations. `make clean` removes only generated owned build directories, never user data.

## Demo and deployment topology
Run `make demo` locally; inspect the generated static HTML report offline. The main credible hosted demonstration is this reviewed static report plus source, CI and evidence, hosted on public GitHub Pages. It has no live inference endpoint and must not pretend otherwise. Optional trusted-operator CPU VM uses an unprivileged account, read-only source/model, writable owned run directory, no exposed port, cgroup memory/CPU limits, and an SSH-controlled CLI. Containers/VM images are not required for the core; never introduce Kubernetes just to label this infrastructure.

## Operations
Startup validates config/model fully before accepting requests. Failure is fail-closed with nonzero setup exit. stdout backpressure blocks progress instead of buffering unbounded token queues. Shutdown discards in-memory requests; the controller must record interruption and resubmit deliberately with a new session. No transparent retry of generation: duplicates can produce multiple independently billed/observed outputs in a future adapter. One operator owns model and configuration. No database, schema migrations or durable user state. Preserve only model input hashes and allowlisted synthetic receipts for reproduction.

Health is process liveness plus successful HELLO/STATUS; a model-load failure is not ready. Metrics are live/reserved/physical pages, denials, per-request terminal events and caller-observed latency. Logs are bounded JSONL with no prompt text. There is no production uptime SLO. Alert only in an optional operator wrapper on unexpected process exit, repeated E_NUMERIC/E_INTERNAL, exhausted capacity, or disk nearing receipt quota.

## Recovery and rollback
Dependency install failure: inspect exact version/platform and resolver output; use a supported compatible release, document any canonical impact, continue standard-library work. Flaky test: retain repetitions and root cause; retry-until-green is not a fix. Model download/reference unavailable: mark only real-model tasks BLOCKED; tiny kernel work continues, not represented as real-model evidence. Corrupt workspace: preserve diff/receipts, recover a clean checkout; do not overwrite user changes. CI failure: inspect runner/compiler difference and reproduce locally. Benchmark instability: retain all runs, inspect load/warmup/thread settings, report variance. Merge conflict: orchestrator resolves and retests. Low-quality executor: reject and escalate, not endless local patches. No DB migration recovery applies because no DB exists; a future persistent change requires a new reviewed migration design.

Rollback is a clean previously verified source tag plus matching model format/hash. An old receipt does not verify current HEAD. Preserve model manifests, not private weights in Git. No remote cloud resource is created by local bootstrap. Optional paid VM/billing/domain actions require explicit purchase authorization.

## Cost tiers (USD, rates researched 2026-10-19; not actual spending)
|Tier|Services and assumptions|Fixed / variable|Controls and added signal|
|---|---|---|---|
|Local/free|Existing CPU hardware, public repository, ordinary public CI, offline report or public GitHub Pages|$0 incremental cloud; hardware/electricity excluded|No keys, no billing; complete correctness/demo path|
|Credible hosted demo|Static Pages, or OPTIONAL DigitalOcean Basic 2 vCPU/4 GiB CPU host|Static $0; optional VM advertised $24/month cap or $0.03571/hour, before taxes/extras|SSH only, no live public endpoint, stop/delete explicitly, bound storage/transfer; tests another environment|
|Premium/scale experiment|OPTIONAL CPU-optimized 2 vCPU/4 GiB dedicated-CPU VM|Advertised $42/month cap or $0.0625/hour; 10 hours compute arithmetic $0.625, excluding extras|Better noise control, not more functionality; short bounded runs, no GPU required|

DigitalOcean pricing source: https://www.digitalocean.com/pricing/droplets . Pages plan eligibility: https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site . Prices/free-tier terms may change; recheck before any authorized purchase. Larger GitHub runners are not assumed free. No cloud deployment or operating cost has been observed.
