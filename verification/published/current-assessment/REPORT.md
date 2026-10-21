# Current measured assessment

Source baseline: `05007149398de6a0b1c5c65ce255f3082d532800`.
Source SHA256: `7c1606370a8c3309dd38d2ac0dcf845e82fe4eb48a46916dbf31fb241cedf1fd`.
Release-scope SHA256: `032f7f8d69b38497a77baa07a347a81733d94ab93faf927df9eeedda4bbcac73`.

Read the criterion index for final readiness and hashed independent review. These observations are derived from the linked execution records; they are not a separate approval.

Real checkpoint: 20sequences, 326positions; maximum error 0.00029559626465, weighted mean 8.62300120475e-06; 311confident positions all match.

| Workload | Variant | Median ms | Min–max ms | Max RSS MiB |
|---|---|---:|---:|---:|
| short-single | serial-recompute | 9.282 | 9.018–10.423 | 4.89 |
| short-single | contiguous | 1.504 | 1.436–1.652 | 4.88 |
| short-single | paged | 1.901 | 1.486–3.231 | 4.77 |
| long-single | serial-recompute | 993.356 | 975.167–1018.082 | 5.02 |
| long-single | contiguous | 19.157 | 18.376–20.963 | 4.93 |
| long-single | paged | 22.137 | 21.602–25.048 | 4.86 |
| mixed-four | serial-recompute | 1274.533 | 1240.966–1290.400 | 5.01 |
| mixed-four | contiguous | 34.688 | 32.747–35.128 | 5.66 |
| mixed-four | paged | 37.110 | 35.390–38.640 | 5.01 |
| mixed-eight | serial-recompute | 1967.229 | 1944.993–2169.599 | 5.08 |
| mixed-eight | contiguous | 51.833 | 50.103–57.225 | 6.66 |
| mixed-eight | paged | 57.469 | 54.500–61.267 | 5.06 |
| mixed-two | serial-recompute | 1660.829 | 1580.753–1814.798 | 5.09 |
| mixed-two | contiguous | 28.372 | 27.966–30.196 | 5.18 |
| mixed-two | paged | 31.450 | 31.012–32.025 | 5.07 |
| mixed-sixteen | serial-recompute | 38412.511 | 37777.121–39751.859 | 5.32 |
| mixed-sixteen | contiguous | 187.673 | 178.921–190.196 | 8.72 |
| mixed-sixteen | paged | 206.348 | 198.535–220.615 | 5.89 |

All18warmups and90measurements plus native raw JSON/stderr/command data are retained. Fixed synthetic inputs and exact output parity; native round-visible latency excludes model loading and pipe/controller costs. Shared host, no affinity/frequency isolation. RSS includes model/allocator/harness and is not a KV ceiling.

Actual Linux CI: [run 39578438934](https://github.com/C-X1an/batchquay/actions/runs/39578438934). See ci-observation.json and retained CI receipts for sanitizer/static/fresh-environment scope.

Historical failures remain scoped to their original source. Earlier missing tools, incompatible dependency pins, Windows pipe/path problems, scanner checksum matches, wrong browser interpreter and development source-race rejection were investigated; none is promoted to a current PASS. Selected mutations retain their expected semantic failures between baseline passes.

Not measured: pretrained-model performance, generated-language quality, GPU/fused GEMM, HTTP inference/authentication, production traffic/availability and hostile native-code isolation. These are outside this experimental release. No performance advantage or security certification is claimed.
