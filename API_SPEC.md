# BatchQuay API and data contract
Version 1.0. This file defines target interfaces before implementation. Implemented coverage is reported separately.

## Executable interfaces
`batchquay logits MODEL TOKEN...` returns one JSON object containing `logits`, a list of vocabulary-sized FP32 logit arrays, one per input position. Tokens are decimal integers. At least one and at most 256 positions; every token must be less than vocabulary size. `--recompute` before MODEL selects the serial full-prefix recomputation baseline; `--paged` selects the owned-page cache rather than contiguous cache. `batchquay serve MODEL [PAGES PAGE_TOKENS LIVE_LIMIT PREFILL_CHUNK]` runs the actor protocol. Defaults are bounded by 256 MiB cache, 16-token pages, 16 live requests and chunk 4; a page count is derived from model dimensions and the byte ceiling when not supplied. `--version` prints `batchquay 0.1.0 protocol=1 model=1`.

Engine has no HTTP, RPC, database, model API, shell execution, remote model loading or network listener. Model path is a trusted operator argument, not a client request field. The standard-input channel has one trusted controller. Owner fields exercise internal isolation; they do NOT authenticate a caller.

## Closed ASCII record protocol
Input is one record per line, <=8192 bytes excluding newline. Only these exact productions are accepted. Integers are decimal, unsigned and range checked; extra/missing fields are errors. IDs are 1..64 ASCII letters, digits, `_` or `-`. A session is an opaque ID emitted at startup; generation is a strictly increasing unsigned integer. A session mismatch is never silently corrected.

```text
HELLO 1
SUBMIT SESSION OWNER ID OUTPUT_LIMIT TOKEN_COUNT TOKEN...
STEP SESSION
CANCEL SESSION OWNER ID GENERATION
STATUS SESSION
```
`HELLO 1` returns the current session and protocol; other versions are errors. SUBMIT reserves ceil((TOKEN_COUNT+OUTPUT_LIMIT)/PAGE_TOKENS) page credits atomically before changing live state. TOKEN_COUNT and OUTPUT_LIMIT are positive; sum <=256. Duplicate live OWNER/ID is rejected. Acceptance returns a generation; clients must retain it for cancellation. Different owners may use the same ID. A cancelled/completed ID may be reused with a new generation. STEP processes one round over the live handles that existed at round start. Each gets <=PREFILL_CHUNK prompt steps or one decode grant, not both. New arrivals are processed in subsequent rounds. CANCEL requires session+owner+ID+generation; wrong/stale values are refused and do not alter state. STATUS exposes aggregate live/reserved/physical-page counters, not other owners' content.

Outputs are one JSON object per line, flushed after each input record. The service emits an initial hello. Control response has `event`, plus relevant `session`, `owner`, `id`, `generation`. Token records also have `token` and a monotonically increasing per-request `index`. Terminal events are `finished`, `cancelled`, or `failed`. A STEP response wraps its ordered events in `events`; an empty round is valid. `error` responses include a stable bounded `code`, never exception text with file paths or private input. Fatal command/model setup errors use stderr and exit 2; handled protocol errors leave the process usable. Successful process exhaustion exits 0. No outcome is inferred from an empty output.

Error codes: E_FORMAT, E_VERSION, E_SESSION, E_LIMIT, E_TOKEN, E_DUPLICATE, E_NOT_FOUND, E_OWNER, E_STALE, E_CAPACITY, E_MODEL, E_NUMERIC, E_INTERNAL. Resource exhaustion must not be mislabeled numerical success. Syntax failure precedes mutation. No unbounded retry queue. Controller backpressure blocks stdout/actor progress; this is not a wall-clock latency guarantee.

## Model container BQW1
Little-endian byte order; exact payload length. Header is four bytes `BQW1`, eight u32 values (version=1, vocab, dim, hidden, layers, heads, kv_heads, max_positions), then IEEE754 f32 epsilon and rope_theta. Header size 44 bytes. All are positive; `heads` divides dim; `kv_heads` divides heads; head dimension is even. Supported shape ceilings: vocab <=65536, dim <=2048, hidden <=8192, layers <=64, heads <=32, kv_heads <=32, max_positions <=256. Total file <=1 GiB. Products and expected byte size must be checked using bounded wide arithmetic before tensor allocation. epsilon and theta are finite and positive.

Payload is finite row-major f32 in this order: tied embedding[vocab,dim]; for each layer: attention norm[dim], Q[dim,dim], K[kv_heads*head_dim,dim], V[same], O[dim,dim], post-attention norm[dim], gate[hidden,dim], up[hidden,dim], down[dim,hidden]; final norm[dim]. No tensor names, pickle, arbitrary code or optimizer state. Tied output projection uses the embedding matrix. Unsupported bias, non-tied head, non-default rope scaling and alternate architecture must be rejected by conversion rather than dropped. Bfloat16 values are converted numerically to f32.

All model artifacts are trusted operator-selected but parsed defensively. The native loader detects accidental shape/length/nonfinite corruption, not authenticity. Converter records source revision, per-file SHA256 and output SHA256. Local downloader validates pinned metadata before release; do not trust a branch named `main` or a mutable filename as a content pin.

## Model semantics
Pre-norm decoder: x += O(attention(RMSNorm(x))); x += down(SiLU(gate(RMSNorm(x))) * up(RMSNorm(x))). Split-half RoPE uses angle position / theta^(2i/head_dim), with `(a*cos-b*sin, b*cos+a*sin)`. Query head h attends to KV head floor(h/(heads/kv_heads)). Only positions <= current position are visible. Logits are unnormalized; greedy chooses the lowest index on exact ties. EOS is an ordinary token in the bounded token-ID interface; generation terminates at the requested output budget, cancellation or failure. This is not a text-chat protocol.

## Cache and state
Arena pages carry an allocation epoch and exact request owner tuple. Handles are valid only when both match. Page length is `layers*2*page_tokens*kv_heads*head_dim` floats. Logical order `[layer][K/V][within_page_position][kv_component]`. Page payload is cleared before reassignment; no prefix sharing. Per-layer initialized lengths gate reads. Reservation and actual page counts are different metrics. Generations never wrap; exhausted counters refuse further admission. Released pages cannot be reused via old handles even if an ID is reused.

Data is in memory only. A crash loses all requests; new process obtains a fresh session, rejects old-session commands, and starts empty. No database migration. Model/protocol version incompatibility is refused, not auto-converted. Local evidence uses JSONL plus raw command outputs, never stored user secrets.
