# Current measured assessment

Source baseline: `ecc74c969bc72460b3243c5881e209bd592828c7`.
Source SHA256: `6907da7009d263ada9673c59a172cac7bdb0d4c0bc59886d8982f116d472804b`.
Release-scope SHA256: `57b861dc10fe60ab361c3ef43f6eeb5186385cccec4b14031ffc66c12140905a`.

Read the criterion index for final readiness and hashed independent review. These observations are derived from the linked execution records; they are not a separate approval.

Real checkpoint: 20sequences, 326positions; maximum error 0.00029559626465, weighted mean 8.62300120475e-06; 311confident positions all match.

| Workload | Variant | Median ms | Min–max ms | Max RSS MiB |
|---|---|---:|---:|---:|
| short-single | serial-recompute | 8.740 | 8.257–9.613 | 4.89 |
| short-single | contiguous | 1.527 | 1.379–1.730 | 4.88 |
| short-single | paged | 1.539 | 1.363–1.572 | 4.77 |
| long-single | serial-recompute | 1126.992 | 1051.119–1394.036 | 5.02 |
| long-single | contiguous | 20.152 | 19.122–28.262 | 4.93 |
| long-single | paged | 27.529 | 22.563–32.348 | 4.86 |
| mixed-four | serial-recompute | 1299.853 | 1258.886–1355.330 | 5.01 |
| mixed-four | contiguous | 33.478 | 32.384–34.356 | 5.66 |
| mixed-four | paged | 37.800 | 35.435–38.747 | 5.01 |
| mixed-eight | serial-recompute | 2061.293 | 1971.631–2110.172 | 5.08 |
| mixed-eight | contiguous | 56.407 | 52.895–69.292 | 6.66 |
| mixed-eight | paged | 61.283 | 56.487–74.883 | 5.06 |
| mixed-two | serial-recompute | 2029.251 | 1992.967–2080.617 | 5.09 |
| mixed-two | contiguous | 37.625 | 31.785–40.964 | 5.18 |
| mixed-two | paged | 40.115 | 38.110–42.000 | 5.08 |
| mixed-sixteen | serial-recompute | 37883.878 | 29148.640–46985.027 | 5.34 |
| mixed-sixteen | contiguous | 217.463 | 186.236–280.170 | 8.73 |
| mixed-sixteen | paged | 228.649 | 205.402–276.266 | 5.89 |

All18warmups and90measurements plus native raw JSON/stderr/command data are retained. Fixed synthetic inputs and exact output parity; native round-visible latency excludes model loading and pipe/controller costs. Shared host, no affinity/frequency isolation. RSS includes model/allocator/harness and is not a KV ceiling.

Actual Linux CI: [run 39565893537](https://github.com/C-X1an/batchquay/actions/runs/39565893537). See ci-observation.json and retained CI receipts for sanitizer/static/fresh-environment scope.

Historical failures remain scoped to their original source. Earlier missing tools, incompatible dependency pins, Windows pipe/path problems, scanner checksum matches, wrong browser interpreter and development source-race rejection were investigated; none is promoted to a current PASS. Selected mutations retain their expected semantic failures between baseline passes.

Not measured: pretrained-model performance, generated-language quality, GPU/fused GEMM, HTTP inference/authentication, production traffic/availability and hostile native-code isolation. These are outside this experimental release. No performance advantage or security certification is claimed.
