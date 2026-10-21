# Current measured assessment

Source baseline: `a14ba115674e33c887393b0ef80addf4cc76ee46`.
Source SHA256: `cc01a3e9b6aa9621b783ccc9093f4cc618afbf993c50505e7c9652d2f90892db`.
Release-scope SHA256: `82814a8e4e699507f383c35498715dba1000d38782c718093ad3dfda5164137f`.

Read the criterion index for final readiness and hashed independent review. These observations are derived from the linked execution records; they are not a separate approval.

Real checkpoint: 20sequences, 326positions; maximum error 0.00029559626465, weighted mean 8.62300120475e-06; 311confident positions all match.

| Workload | Variant | Median ms | Min–max ms | Max RSS MiB |
|---|---|---:|---:|---:|
| short-single | serial-recompute | 13.517 | 13.118–14.144 | 4.89 |
| short-single | contiguous | 2.236 | 2.074–2.356 | 4.89 |
| short-single | paged | 2.245 | 2.101–2.848 | 4.77 |
| long-single | serial-recompute | 1573.332 | 1218.317–4682.100 | 5.02 |
| long-single | contiguous | 27.546 | 20.116–35.204 | 4.93 |
| long-single | paged | 30.653 | 23.052–32.479 | 4.86 |
| mixed-four | serial-recompute | 1769.789 | 1640.563–1789.011 | 5.01 |
| mixed-four | contiguous | 48.603 | 46.923–50.996 | 5.66 |
| mixed-four | paged | 52.111 | 50.481–53.397 | 5.01 |
| mixed-eight | serial-recompute | 2651.863 | 2248.717–2784.735 | 5.08 |
| mixed-eight | contiguous | 77.751 | 75.821–78.612 | 6.66 |
| mixed-eight | paged | 77.844 | 73.823–84.276 | 5.06 |
| mixed-two | serial-recompute | 2143.319 | 1882.964–2325.839 | 5.09 |
| mixed-two | contiguous | 40.746 | 28.400–42.061 | 5.18 |
| mixed-two | paged | 46.600 | 34.049–47.118 | 5.07 |
| mixed-sixteen | serial-recompute | 12359.253 | 11577.872–13702.512 | 5.34 |
| mixed-sixteen | contiguous | 216.828 | 188.714–243.292 | 8.73 |
| mixed-sixteen | paged | 226.785 | 205.092–278.973 | 5.89 |

All18warmups and90measurements plus native raw JSON/stderr/command data are retained. Fixed synthetic inputs and exact output parity; native round-visible latency excludes model loading and pipe/controller costs. Shared host, no affinity/frequency isolation. RSS includes model/allocator/harness and is not a KV ceiling.

Actual Linux CI: [run 39470783484](https://github.com/C-X1an/batchquay/actions/runs/39470783484). See ci-observation.json and retained CI receipts for sanitizer/static/fresh-environment scope.

Historical failures remain scoped to their original source. Earlier missing tools, incompatible dependency pins, Windows pipe/path problems, scanner checksum matches, wrong browser interpreter and development source-race rejection were investigated; none is promoted to a current PASS. Selected mutations retain their expected semantic failures between baseline passes.

Not measured: pretrained-model performance, generated-language quality, GPU/fused GEMM, HTTP inference/authentication, production traffic/availability and hostile native-code isolation. These are outside this experimental release. No performance advantage or security certification is claimed.
