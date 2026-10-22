# Current measured assessment

Source baseline: `56840f1972065a0854f261bcf2b0902bb47cd48c`.
Source SHA256: `62c25dfc5db2dcf7ee24c5c074ddb67eea3055ea74b81aa30ba23e94ba74f0c2`.
Release-scope SHA256: `d46fec5d9d0781cdd33f4668ae2d6026fcf00011274473a7e62674e98c9b594d`.

Read the criterion index for final readiness and hashed independent review. These observations are derived from the linked execution records; they are not a separate approval.

Real checkpoint: 20sequences, 326positions; maximum error 0.00029559626465, weighted mean 8.62300120475e-06; 311confident positions all match.

| Workload | Variant | Median ms | Min–max ms | Max RSS MiB |
|---|---|---:|---:|---:|
| short-single | serial-recompute | 8.334 | 8.213–10.508 | 5.40 |
| short-single | contiguous | 1.405 | 1.338–1.458 | 5.41 |
| short-single | paged | 1.420 | 1.330–1.481 | 5.29 |
| long-single | serial-recompute | 1046.374 | 988.641–1354.048 | 5.55 |
| long-single | contiguous | 19.836 | 19.510–25.038 | 5.45 |
| long-single | paged | 22.159 | 20.202–27.686 | 5.38 |
| mixed-four | serial-recompute | 1743.634 | 1561.882–1744.736 | 5.54 |
| mixed-four | contiguous | 44.833 | 35.359–45.446 | 6.17 |
| mixed-four | paged | 48.069 | 39.591–51.036 | 5.52 |
| mixed-eight | serial-recompute | 2443.183 | 2172.420–2731.967 | 5.61 |
| mixed-eight | contiguous | 70.463 | 52.386–75.904 | 7.18 |
| mixed-eight | paged | 75.307 | 61.198–76.450 | 5.57 |
| mixed-two | serial-recompute | 1998.358 | 1788.813–2084.703 | 5.61 |
| mixed-two | contiguous | 32.632 | 30.782–53.212 | 5.70 |
| mixed-two | paged | 34.101 | 31.355–38.894 | 5.60 |
| mixed-sixteen | serial-recompute | 39820.582 | 36241.153–40737.515 | 5.84 |
| mixed-sixteen | contiguous | 186.763 | 181.664–220.633 | 9.24 |
| mixed-sixteen | paged | 200.911 | 200.003–239.020 | 6.39 |

All18warmups and90measurements plus native raw JSON/stderr/command data are retained. Fixed synthetic inputs and exact output parity; native round-visible latency excludes model loading and pipe/controller costs. Shared host, no affinity/frequency isolation. RSS includes model/allocator/harness and is not a KV ceiling.

Actual Linux CI: [run 39821713717](https://github.com/C-X1an/batchquay/actions/runs/39821713717). See ci-observation.json and retained CI receipts for sanitizer/static/fresh-environment scope.

Historical failures remain scoped to their original source. Earlier missing tools, incompatible dependency pins, Windows pipe/path problems, scanner checksum matches, wrong browser interpreter and development source-race rejection were investigated; none is promoted to a current PASS. Selected mutations retain their expected semantic failures between baseline passes.

Not measured: pretrained-model performance, generated-language quality, GPU/fused GEMM, HTTP inference/authentication, production traffic/availability and hostile native-code isolation. These are outside this experimental release. No performance advantage or security certification is claimed.
