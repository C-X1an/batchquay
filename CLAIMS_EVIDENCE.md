# Claims and evidence scope

| Claim | Current evidence and limit |
|---|---|
| Original C++20 decoder, owned paged cache and bounded actor | Existing implementation retained and tested; no replacement engine or hosted-model wrapper. |
| Tiny numerical equivalence | Seeded full-prefix oracle across three cache/execution variants; fixed max/RMS tolerances remain unchanged. Historical receipts identify their source. |
| Real checkpoint numerical equivalence | Real pinned SmolLM2-135M checkpoint passed locally: 20 sequences, 326 positions, max absolute error 0.0002955963 and mean 0.0000086230; all 311 confident top-1 positions matched. Current source-bound records and their scope are listed in the criterion index. This is not a generated-language quality claim. |
| Deterministic conversion | Two actual conversions produced the same BQW1 SHA256. Weights are not distributed. |
| Ownership, cancellation, reclamation and restart | Native and child-process tests exercise these paths. A corrected independently assessed terminal-replay exception documents new-generation reuse and absence of a completed-result ledger. |
| Performance comparison | Six fixed synthetic workloads, 1/2/4/8/16 simultaneous requests, warmups and at least five repetitions; exact output parity, native RSS, logical KV and round-visible token timings. All runs retained; no universal paged-cache advantage or fused batching claimed. |
| Independent review | Separate initial read-only findings preceded fixes; follow-up reviews found further issues. Final approval is a separate hashed artifact referenced by the criterion index. Self-review is not substituted. |
| Security and licenses | Actual history/export secret scans, detection canary, resolved-package advisory scan and installed notice checks executed. Final complete-candidate audit is rerun after evidence commits. No security certification or arbitrary-native-code isolation claim. |
| Reproduction and Linux checks | Fresh committed hash-locked reproduction and current supported-Linux sanitizer/analyzer evidence are release gates, not inferred from workflow files. |
| Full product complete / production ready | Experimental full-release eligibility is shown only by the current criterion index and release gate. Production readiness is not claimed. |

The criterion index is the current machine-readable release view. Existing schema-v1 receipts document the earlier source only. Public stream capture replaces known absolute local path prefixes and records original raw-stream hashes; raw bytes remain local. Receipt hashes are local integrity bindings, not signatures or third-party attestation. Source/release manifests bind code, contracts, workflows, licenses and docs; the final publication audit separately covers every evidence file and current referenced history to avoid a self-hash loop.
