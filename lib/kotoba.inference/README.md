# kotoba-lang/inference

CLJC-first inference runtime contracts and verification for Kotoba/Kotodama.

This repository owns the portable inference layer:

- `kotodama.inference.*` CLJC runtime specs and host ports
- `torch` model graph contracts
- `num` tensor compute contracts for CPU, WASM, WGSL, and WebGPU hosts
- explicit adapter declarations for browser, wasm, native, remote, and edge hosts
- real-model verification for local Gemma GGUF artifacts

The core foundation is `kotoba-lang/torch` plus `kotoba-lang/num`. JavaScript
model runtimes such as Transformers.js, ONNX, and ONNX Runtime Web are not
portable foundations for this repo.

`kotodama.inference.runtime/optimized-transformer` carries measured device
tuning through the portable runtime contract. An adapter is resolved by num,
translated into scheduler settings by torch, then attached here as explicit
`:latency`, `:throughput`, or `:fallback` intent. This prevents a host from
silently treating Xavier like B70 or applying Strix's two-slot throughput
profile to a latency-sensitive request.

## Encrypted LM-head proof

The JVM host includes a bounded, cryptographic encrypted-inference slice. A
client encrypts a fixed-point hidden state with 2048-bit Paillier; the server
uses plaintext model weights to compute encrypted candidate logits through
`paillier.core/encrypted-matvec`; only the client decrypts and selects the token.
The cryptographic primitive is owned by the standalone
[`kotoba-lang/paillier`](https://github.com/kotoba-lang/paillier) library;
`inference` owns only the LLM protocol, quantization, token selection, and proof
receipt.

```sh
kbb -M:verify-encrypted-lm-head
```

This proves ciphertext-only **linear LM-head inference**, including randomized
ciphertexts, modular-overflow rejection, exact fixed-point parity, and an
executable timing receipt. It does not claim FHE or a fully encrypted
Transformer: attention, normalization, activations, Softmax, and the preceding
hidden-state computation remain outside the encrypted boundary. See
`docs/ADR-encrypted-lm-head-paillier.md` for the threat model and non-claims.

## Layout

```text
cljc/src/    portable runtime contracts
cljc/test/   CLJC contract tests
kotoba/      Kotoba decision cores (authority for host policy)
resources/   precompiled KIR artifacts for those cores
verify/      maturity gates and local-model verification
browser/     browser worker/client surface
shaders/     WGSL kernels
docs/        ADRs
```

The PTQ1_0 production kernel sources are also library resources under
`resources/kotodama/inference/kernels/native/`.  Consumers resolve them through
`kotodama.inference.ptq1`; parity and benchmark gates load those exact resource
bytes rather than a second copy under `verify/`.  The same catalog records host
runtime qualification separately, so the K16 production Vulkan runtime cannot
silently qualify the Metal row-tile candidate.

## Verify

```sh
kbb -M:test
kbb -M:verify-maturity
kbb -M:verify-torch-num
```

Local model verification expects a local Ollama `gemma4:e4b` GGUF artifact:

```sh
kbb -M:verify-gguf
KOTODAMA_VERIFY_FULL_MLP=1 KOTODAMA_VERIFY_FULL_LAYERS=2 KOTODAMA_VERIFY_FULL_VOCAB=1 kbb -M:verify-gemma-num
```

Hosted Ternary Bonsai 2 27B measurements are recorded separately from the
native runtime evidence in
`verify/evidence/ternary-bonsai-hosted-turbo4-20260920.json`. The record covers
Hugging Face L4/T4 endpoints using real TurboQuant `turbo4` K/V, an RTX PRO
6000 Q4_0-KV operational reference, 32K through 256K cold-prefill outcomes,
failure boundaries, cost per million prompt tokens, and an explicitly
unmeasured analytical prefix-reuse ceiling.

`gemma4-e4b-num-smoke` proves 2 composed transformer blocks against golden
logits; it does not tokenize, sample, or run the full model. End-to-end
single-request text generation (real tokenizer, every real transformer block,
greedy sampling, no KV-cache — recompute-from-scratch) is:

```sh
kbb -M:verify-gemma-generate
# optional env: KOTODAMA_VERIFY_MODEL, KOTODAMA_VERIFY_GGUF_PATH,
# KOTODAMA_VERIFY_PROMPT, KOTODAMA_VERIFY_MAX_TOKENS
```

This is CPU-bound recompute-from-scratch (no KV-cache — see
`kotodama.inference.decode`'s docstring) against the model's full real layer
count, so it is slow (see the PR that introduced it for observed tokens/sec).

## Kernel: workgroup-per-row K-quant dot (`shaders/ggml_kdot_wg.wgsl`)

`shaders/ggml_kdot.wgsl` is the ggml reference laid out one thread per output
row; `shaders/ggml_kdot_wg.wgsl` is the same arithmetic laid out one 64-thread
workgroup per row with word loads and a shared-memory reduction. Same bindings
and `Meta`, different dispatch (`(rows, positions, 1)`). Parity and timing:

```sh
deno run --unstable-webgpu --allow-read verify/kdot_wg_parity.js [rows] [blocks]
```

Measured 2026-09-18 on `[10240 x 2560]` Q4_K (kernel time from 21 dispatches in
one command buffer, because a single submit on Deno/wgpu pays a 13–18 ms round
trip that has nothing to do with the kernel): Intel Arc Pro B70 (wgpu→Vulkan)
reference 0.80 ms / workgroup 0.147 ms = 100 GB/s; AMD Radeon 8060S (RADV
gfx1151) 0.557 → 0.138 ms = 107 GB/s; Apple M1 Max (Metal) 1.60 → 0.288 ms =
51 GB/s; NVIDIA Tegra Xavier (nvgpu Vulkan) 19.1 → 1.06 ms = 14 GB/s. Oracle and
pseudo-random parity within 2e-5 on all four. murakumo is not Metal-first: a
kernel gate carries all four backends or it is red for the missing one. The generation host (`host/metal_kdot.cljk`) still
dispatches the reference kernel; wiring this one in is root ADR-2609181800 M2.

`verify/decode_step_bench.js [layers]` streams one Gemma4 e4b decode step's
weights (42 × 7 projections + the 262144 × 2560 Q6_K lm_head, 3.0 GB) through
the same kernel in three submit shapes. 2026-09-18: per-projection submit +
readback (today's host shape) 3.9 s/token on B70, 3.7 s on AMD 8060S, 4.4 s on
M1 Max; one command buffer per token 40.5 / 39.9 (per-layer) / 71.8 ms — a
62–97× difference that is the whole of the recorded 8.4 s/token. It is a
weight-stream floor (24.7 tok/s on B70), not a generation rate. Needs ~8 GB
free GPU memory; do not run the full size on a serving node.

`shaders/q8k_quantize.wgsl` quantises an f32 activation row into ggml's
`block_q8_K` stream on the GPU (one 64-thread workgroup per 256-block, bsums
included), so a decode step never brings the hidden state back to the host.
`verify/q8k_quantize_parity.js` checks it against a JS port of
`quantize_row_q8_K_ref` (qs/bsums exact; `d` within the backend's f32 division
bound, 1 ulp Metal / 2 ulp Intel and AMD) and feeds both streams through
`ggml_kdot_wg.wgsl`. 2026-09-18: 10240-wide × 3 rows in 0.006–0.018 ms.

## Nex-N2.5-mini admission (JVM-free)

```sh
kbb --backend sci verify/gguf_inventory.cljk <Nex-N2.5-mini-Uncensored-IQ4_XS.gguf>
```

Reads the GGUF header on node fs (no JVM) and prints the architecture inventory:
`qwen35moe`, 40 blocks (30 gated-delta-net linear-attention + 10 GQA), 256 experts
top-8 + shared expert, IQ4_XS / Q5_K / Q6_K weights, 248,320-token gpt2-style
tokenizer with the chat template embedded. Gate `:nex-n25-mini-gguf-admission`
pins the expected values. Owner 2026-09-18: Nex is the verification target and
the finished path is Kotoba + amu native only; the Gemma4/JVM host is the
correctness oracle's history, not the road.

`ggml_kdot_wg.wgsl` also reads **Q5_K (13)** and **IQ4_XS (23)** — the two
types Nex-N2.5-mini adds (attn_qkv is Q5_K; 391 of 733 tensors are IQ4_XS).
`verify/nex_kdot_parity.js` runs the real `blk.0.attn_gate.weight` and
`blk.0.attn_qkv.weight`, cut from the served GGUF, against JS ports of ggml's
generic reference dots: 2026-09-18 maxAbs 6e-7 / 1.2e-6, identical on M1 Max,
Intel B70 and AMD 8060S. Gate `:nex-kdot-parity`.

`shaders/ggml_kdot_moe.wgsl` is the same dot over a **packed expert tensor**
(`ffn_*_exps` [cols, rows, 256]) with the eight selected expert ids read from a
GPU buffer — the router's top-k never returns to the host. Verified on the real
`blk.0.ffn_gate_exps.weight` (142.6 MB) for experts {0, 255, 7, 64, 128, 199, 31,
250} in shared-input and per-expert-input modes (`verify/nex_moe_gather_parity.js`,
gate `:nex-moe-gather-parity`): maxAbs 3.6e-7, identical on M1 Max / B70 / AMD.

`shaders/deltanet_step.wgsl` is the gated delta-net recurrence for one decode
token (Nex's 30 linear-attention layers): one workgroup per value head, one
thread per state column, state updated in place on the GPU. `verify/
deltanet_step_parity.js` carries state across 16 tokens against an f64
reference of the FLA recurrent gated delta rule: worst relative error 5e-7 on
M1 Max / B70 / AMD; 30 layers step in 2.1–3.1 ms per token (gate
`:deltanet-step-parity`). The conv1d, q/k L2 norms and gated output norm around
it are the next kernels.

`shaders/nex_ops.wgsl` holds every non-matvec op of a qwen35moe decode step
(RMSNorm, L2 norm, gated RMSNorm, silu·up, conv1d step with GPU ring state,
router softmax + top-8 + weight normalisation, delta-net gate/decay, weighted
expert sum + shared gate, NEOX partial RoPE, one-query GQA attention with the
attn gate, two-stage argmax over 248,320 logits) as one module with one entry
point each and one 7-slot bind-group layout. `verify/nex_ops_parity.js` checks
all eleven against f64 references of the llama.cpp graph at Nex shapes — all
pass on M1 Max / Intel B70 / AMD 8060S (gate `:nex-ops-parity`). With the
K-quant dots, the expert gather and the delta-net step, every kernel of a Nex
decode step now exists; composing them into one command buffer against real
weights needs a GPU that is not serving.

## The composed Nex decode step (`verify/nex_decode_step.js`)

```sh
deno run --unstable-webgpu --allow-read --allow-env verify/nex_decode_step.js <Nex-N2.5-mini-Uncensored-IQ4_XS.gguf> 760,6511,314,9338,369 8 11751,13,220,97034,95779,103725,95895,9398
```

All 40 layers of Nex-N2.5-mini on the GPU from the served GGUF (18.45 GB with
`token_embd`), **one command buffer per token**, the only readback the argmax
token id. Matvecs use `shaders/ggml_kdot_f32.wgsl` (weights dequantised
in-kernel, f32 activations — what llama.cpp's GPU backends do; the Q8_K
activation path diverged from them by 7% at layer 0). 2026-09-18 on M1 Max:
layer 0 and layer 3 match an f64 reference (`verify/nex_layer0_reference.js`) to
~1e-6; after the prompt the top-8 next tokens equal llama.cpp Metal's set and
order, the top-1/top-2 logprob gap matches both llama.cpp builds to 0.04, and
the first two greedy tokens equal the B70 Vulkan control host's (" Paris", ".").
68 ms/token (14.7 tok/s) vs llama.cpp Metal 56.5 tok/s on the same Mac — the
3.9× is kernel bandwidth, the next co-scientist target. Gate
`:nex-decode-step-parity`. Two bugs this harness found and fixed: the value-head
→ key-head mapping is `h % k_heads` (llama.cpp), not `h / group`; and 18 GB of
queued `writeBuffer`s must be flushed with a submit per tensor or wgpu drops the
small ones.

Four layouts of the f32-activation dot exist — `ggml_kdot_f32` (r1), `_r8`,
`_v3`, `_v3b` — same arithmetic, different work layout; `verify/kdot_f32_bench.js`
times them on real Nex tensors. The fastest one depends on backend **and** type
(Intel: Q5_K v3 162 GB/s, IQ4_XS v3b; AMD: Q5_K r8 151, IQ4_XS r1; Metal: v3b),
so the decode harness carries a (backend, type) → layout table. Gate
`:kdot-f32-layouts`. M1 Max composed step: 68 → 54 ms/token.

## Stable JVM production entry point (`kotodama.inference.host.jvm`)

Downstream JVM hosts (e.g. `kotoba-lang/murakumo-studio`) should call the
promoted host adapter, **not** the `verify/` smoke code:

```clojure
(require '[kotodama.inference.host.jvm :as gemma])

;; one-shot (loads + closes the GGUF around the call):
(gemma/generate
  {:kotodama/model        "gemma4:e4b"   ; local Ollama tag, resolved via `ollama show`
   ;; :kotodama/model-path "/path/to.gguf" ; or a resolved GGUF path instead of :model
   :kotodama/prompt       "The capital of France is"
   :kotodama/max-tokens   16
   :kotodama/cache-weights? false        ; true keeps dequant weights in RAM (~20GB, faster)
   :kotodama/use-kv-cache?  true         ; default; pure speed optimisation
   :kotodama/on-token     (fn [id text nanos] ...)}) ; optional streaming callback
;; => {:kotodama/text "..." :kotodama/generated-token-ids [...]
;;     :kotodama/stop-reason :eos|:max-tokens :gemma4/block-count 42 ...}

;; reuse a session across calls (load once, generate many):
(let [s (gemma/load-model {:kotodama/model "gemma4:e4b" :kotodama/cache-weights? true})]
  (gemma/generate {:kotodama/session s :kotodama/prompt "..." :kotodama/max-tokens 16})
  (gemma/close-model s))
```

`host.jvm` implements the real Gemma4 **per-layer-embedding (PLE)** architecture
(the `inp_gate` / `proj` / `post_norm` / `per_layer_*` tensors the older
`stable-block-forward` omits), plus QK/V norms, rotate-half NEOX RoPE (partial
rotary on global layers), the gated GELU MLP, KV-sharing, and a KV-cache. The
`.cljc` kernel stays pure (no file IO); all GGUF reading lives in this
`.clj`-only namespace, per `kotodama.inference.ports`.

Verify:

```sh
CACHE_WEIGHTS=1 kbb -M:verify-gemma-ple-generate   # end-to-end via host.jvm/generate
CACHE_WEIGHTS=1 kbb -M:verify-gemma-kvcache         # KV-cache == from-scratch, + tok/s
```

> Status: the decode loop, tokenizer (SentencePiece `add_dummy_prefix`), GGUF
> weight decode and output projection are verified correct (a 0-layer forward
> greedily predicts the input token); the KV-cache is verified to be output-
> identical to a from-scratch run. The native Q8_K × Q4_K/Q6_K path now matches
> Ollama on the fixed full-42-layer raw-completion probe: both produce token
> `9079`, `" Paris"`. The former dequantize-then-double-matmul reference path
> produces `" hopefully"`; this proved that ggml's activation quantization and
> reduction order are model semantics for parity, not merely an optimization.

The legacy weight-cached verifier retains its 24 GiB JVM heap contract. The
native path mmaps quantized tensor windows, requires no whole-tensor
dequantization, passed with a 4 GiB heap, and measured 1.94 GiB maximum RSS on
Apple M4:

```sh
CACHE_WEIGHTS=1 KOTODAMA_VERIFY_MAX_TOKENS=1 kbb -M:verify-gemma-ple-generate
scripts/build-native-kdot.sh
kbb -M:verify-native-kdot
kbb -M:verify-native-gemma-parity
```

For numerical parity work, emit compact activation fingerprints for every
attention, MLP, PLE, and output stage without retaining full activations:

```sh
CACHE_WEIGHTS=1 \
KOTODAMA_VERIFY_MAX_TOKENS=1 \
KOTODAMA_TRACE_EDN=/tmp/gemma4-trace.edn \
kbb -M:verify-gemma-ple-generate
```

`KOTODAMA_FLOAT32=1` additionally uses explicit float32 projection
accumulation for comparison with ggml. It is a diagnostic bridge; exact Ollama
parity still requires the same quantized reduction order. Set
`KOTODAMA_GGML_K_DOT=1` to use the scalar reference implementation of ggml's
Q8_K activation quantization and Q4_K/Q6_K block-dot directly from GGUF bytes.
This avoids whole-tensor dequantization and is correctness-oriented; native
SIMD/Metal kernels are still required for production throughput. After running
`scripts/build-native-kdot.sh`, set `KOTODAMA_NATIVE_K_DOT=1` to mmap each
quantized tensor and execute the same contract through JDK FFM without copying
or materializing its weights.

Current Apple M4 fixed-probe measurements (one six-token prompt plus one output
token) are 19.4 s for the pthread CPU K-dot path versus 0.566 s wall time for a
warm Ollama/Metal run (`prompt_eval_duration` 0.141 s). Output parity is real;
throughput parity is not. Metal K-dot, persistent GPU buffers, and fused decode
remain required.

The experimental persistent Metal path uses the same GGUF bytes and K-dot
contract through a binary JVM↔Deno worker. Weights are uploaded once and cached
as WebGPU buffers:

```sh
deno run --unstable-webgpu --allow-read verify/metal_kdot.js
kbb -M:verify-metal-kdot-worker
KOTODAMA_METAL_K_DOT=1 KOTODAMA_VERIFY_MAX_TOKENS=2 \
  kbb -M:verify-gemma-ple-generate
```

On Apple M4 it preserves `" Paris."` generation and measures roughly 15–20 ms
for one `[10240,2560]` Q4_K projection. The binary protocol now groups Q/K/V
and MLP gate/up projections that share an activation: each group performs one
Q8_K quantization/upload, command submission, and combined readback while each
K-dot retains official ggml reduction order. This reduced the fixed probe from
about 17.1 to 15.1 s for the first token and from 11.2 to 8.4 s for the warm
second token on Apple M4. Readbacks between attention, MLP, and PLE stages plus
JVM-side normalization/elementwise work remain dominant; full-layer GPU
residency/fusion is still required.

## Ollama-compatible HTTP server

The JVM host can run behind Ollama's local HTTP wire contract. Model sessions
are loaded lazily and retained across requests, so the GGUF mmap, KV/weight
caches, and persistent Metal worker are reused instead of recreated:

```sh
# defaults to 127.0.0.1:11434; an optional first argument overrides the port
KOTODAMA_METAL_K_DOT=1 kbb -M:serve-ollama 11434

curl http://127.0.0.1:11434/api/tags
curl http://127.0.0.1:11434/api/generate \
  -d '{"model":"gemma4:e4b","prompt":"The capital of France is"}'
```

Implemented endpoints are `GET /api/version`, `GET /api/tags`,
`POST /api/show`, `GET /api/ps`, `POST /api/generate`, and `POST /api/chat`,
plus an OpenAI-compatible `POST /v1/chat/completions` and `GET /v1/models`.

**The two surfaces disagree about streaming, on purpose.** `/api/*` streams
NDJSON unless a request says `"stream": false`; `/v1/chat/completions` returns
one JSON object unless a request says `"stream": true`, and streams SSE
(`data: ` frames terminated by `data: [DONE]`) when it does. That is the
upstream behaviour of each wire — a shared default would be wrong for exactly
one of them, and wrong in a way that reads as a client bug. `n` above 1 is a
400 rather than one choice presented as the sample that was requested. Generate supports
Ollama's default newline-delimited streaming and `"stream": false`, plus
`num_predict`, `temperature`, `top_k`, `top_p`, `seed`, and `keep_alive`
(seconds or a duration string such as `"5m"`; `0` unloads once the request is
answered, a negative value holds the model indefinitely). Idle sessions are
unloaded by a reaper, and `/api/ps` reports the real future `expires_at`.
`keep_alive` accepts Go-style compound durations (`"1h30m"`), because reading
only the first component would silently truncate the request.

`:memory-budget-bytes` on the service bounds how much may stay resident,
counted in **declared** model size from the catalogue rather than measured
residency — the JVM cannot see a dequantised GGUF's real footprint, and a
budget from a guess would evict live sessions on invented numbers. Exceeding
it unloads least-recently-used sessions; a model too large on its own is
refused **without** evicting anything, since taking working models down to
serve a request that was always going to fail is worse than the failure. The
default, `0`, means "not measured" and admits every load. The
transport has real loopback HTTP tests for response shape, streaming chunks,
lazy loading, session reuse, expiry, model-not-found errors, and disposal.
Model pull/push/copy/delete, embeddings, blobs, scheduling across multiple
models, and exact behavior for every Ollama option remain future compatibility
work. There is still no model-acquisition path on this surface.

## JVM-independent vLLM client

The native `kotoba-vllm-infer` client executes request bounds from
`kotoba/vllm_infer_core.kotoba`, compiled by Amu to KEXE. Its narrow host
delegates loopback HTTP to curl. The runtime bundle contains no JVM or
JavaScript engine, and rejects non-loopback endpoints.

```sh
scripts/build-native-vllm-cli.sh
target/native-vllm-cli/kotoba-vllm-infer \
  --prompt 'Explain memory bandwidth in one sentence.' --max-tokens 64
```

The JVM reference executes the same shipped Kotoba policy:

```sh
kbb -M:vllm-cli --prompt 'Explain memory bandwidth in one sentence.' \
  --max-tokens 64
```

Both clients write the vLLM response to stdout and one JSON measurement record
to stderr. External wall time includes client startup; `request_ms` isolates
HTTP plus model generation.

### Qwen4Exp MTP qualification on B70

The same namespace now admits Expert-aware NVMe streaming independently of
MTP. `expert-stream-audit` verifies the official 48-layer, 512-expert,
top-10 packed expert layout, all 96 routed tensors, and all 387 base-decoder
Hyper-Connection tensors before naming the decoder executable. For the BF16 source it
derives 9,830,400 bytes per expert and a 4,718,592,000-byte worst-case routed
working set per token; GGUF runtimes must measure their quantized value rather
than reuse the BF16 number. The streaming contract is lossless and keeps MTP
off because the current streaming seam is single-token decode.

```sh
kbb -M:verify-qwen4exp-expert-stream
```

Checkpoint admission is metadata evidence only. Real execution additionally
requires deterministic cache-off/cache-on runs, emitted-token parity and
measured end-to-end tok/s through `expert-stream-qualification`.

`kotodama.inference.qwen4exp` admits the exact Qwen4Exp MTP tensor set, but
checkpoint completeness is not treated as proof that speculative decoding is
correct. `execution-qualification` separately requires deterministic MTP-OFF
and MTP-ON runs, exact emitted-token parity, and then records whether MTP
actually improves end-to-end throughput.

The reproducible B70 harness is `verify/qwen4exp-b70-bench.sh`. It runs the
Qwen4Exp hyper-connection / sparse-MoE decoder through a commit-pinned SYCL
host, executes the separate MTP decoder, captures raw token IDs, and restores
the resident vLLM service even when qualification fails. The 2026-08-28
qualification evidence is in
`verify/evidence/qwen4exp-mtp-b70-20260828.json`.

That measured IQ1_S target + Q4_K_M MTP combination is deliberately **not
qualified**: MTP-OFF was deterministic, MTP-ON was not, all three MTP runs
diverged from the target, aggregate draft acceptance was 4/374 (1.07%), and
median end-to-end output throughput fell from 5.46 to 3.01 tok/s. The MTP
route must therefore remain disabled for this artifact pair. This result does
not reject the Qwen4Exp architecture or MTP in general; it rejects this pinned
engine/checkpoint/quantization/device combination.

The separate resident qualification is recorded in
`verify/evidence/qwen4exp-flash-next-b70-resident-20260828.json`. B70 now serves
the same Flash Next target at 32,768 tokens with one slot, 18 GPU layers, Q8 KV,
and MTP disabled. A clean short request completed in 15 seconds at 6.35 prompt
tok/s and 6.29 generation tok/s, and reboot proof observed health 200 plus fleet
join enrollment 201. This qualifies resident short generation and restart
recovery only. An approximately 8K-token cold agent job remained around 11--12
prompt tok/s and exceeded the synchronous public timeout, so 32K capacity must
not be reported as qualified synchronous 32K end-to-end service.

The B70 runtime compatibility record is
`verify/evidence/qwen4exp-b70-runtime-compatibility-20260829.json`. SGLang,
KTransformers, and vLLM did not reach model-specific generation for this exact
Qwen4Exp checkpoint on Intel XPU, so their B70 tok/s values are `N/A`, not zero.
The checked limits are architecture/backend admission and memory capacity; the
6.29 generation tok/s SYCL llama.cpp resident result above is only a control
and is not used to rank those three runtimes.

The evidence keeps the comparison-end resident snapshot separate from current
operations. A 2026-08-29 closing check observed Flash Next inactive/disabled
and the 27B llama.cpp service active/enabled on port 8090. That later switch is
recorded, but it does not change the three Flash Next runtime `N/A` results.

`/api/chat` needs delimiters on the model spec, because this runtime does not
implement Go templates and will not guess markers for a model whose real ones
it has not read:

```clojure
{"gemma4:e4b"
 {:name "gemma4:e4b"
  :kotodama/chat {:turn-open {1 "<start_of_turn>system\n"   ; role codes from
                              2 "<start_of_turn>user\n"     ; ollama-chat-core
                              3 "<start_of_turn>model\n"
                              4 "<start_of_turn>tool\n"}
                  :turn-close "<end_of_turn>\n"
                  :generation-open "<start_of_turn>model\n"}}}
```

A model without them answers **400**, and is not loaded. A conversation that
is empty, contains an unknown role, or ends on `assistant`/`system` is also a
400 — the last message must be one the model would answer.

### The policy of this surface is written in Kotoba

Route admission, request-option defaults, session expiry, and duration
accounting are **not** written in Clojure. They live in `kotoba/*_core.kotoba`
and are executed from precompiled KIR (ADR-2608138800):

| core | decides |
|---|---|
| `ollama_protocol_core.kotoba` | which route a (method, path) is, whether it reads a body, wire `done_reason`, error kind → HTTP status |
| `ollama_options_core.kotoba` | `num_predict` / `stream` / `keep_alive` / `top_k` defaults and normalisation |
| `ollama_session_core.kotoba` | expiry, `expires_at`, eviction under a budget, reaper cadence, `*_duration` accounting |
| `ollama_chat_core.kotoba` | which roles exist, which name them, and which role a conversation may end on |
| `openai_chat_core.kotoba` | the `/v1` envelope: streaming default (off), `max_tokens`, `n`, object tags, `finish_reason`, SSE framing |
| `kernel_math_core.kotoba` | engine arithmetic — dot, RMS scale, softmax, SiLU (float-typed, outside the native gate) |

`kotodama.inference.host.ollama-server` owns transport only — sockets, JSON,
threads, locks, and the clock. The compiler is a **test-time** dependency:
production loads `resources/kotodama/oracle/*.kir.edn` through
`kotodama.inference.host.oracle` and interprets it, and a missing artifact
fails the server at start rather than falling back to a second, unreviewed
copy of the policy in Clojure.

```sh
kbb -M:test:gen    # recompile kotoba/*_core.kotoba → resources/kotodama/oracle/
kbb -M:test        # includes the parity gate: shipped artifact == fresh
                       # compile, semantics vs the Ollama wire contract, and
                       # native-boundary admission
```

### JVM-free build path (opt-in)

The same artifact can be compiled with no JVM at all.
`nbb.edn` pins `io.github.kotoba-lang/amu` to the **same :git/sha the `:test`
alias carries**, and `scripts/kotodama/oracle_gen.cljk` runs that compiler's
pipeline (analyze → admission → lower) under nbb/Node:

```sh
kbb --backend sci scripts/kotodama/oracle_gen.cljk         # parity gate: all 7 cores must
                                             #   compile byte-identical to the
                                             #   shipped artifacts (exit 1 on drift)
kbb --backend sci scripts/kotodama/oracle_gen.cljk --write # regenerate the shipped artifacts
```

The nbb route is byte-compatible with the JVM route on purpose: the KIR text it
writes is identical to what `kbb -M:test:gen` writes, verified across all
seven cores (2026-09-01). `kbb --backend sci run-tests.cljk` (see run-tests.cljk) re-checks
the same gate JVM-free. The JVM commands above remain the authority and are
unchanged; rollback is one command — `git rm nbb.edn scripts/kotodama/oracle_gen.cljk`.
nbb caches its resolved deps under `.nbb/` in the working tree (untracked).

Editing a core without regenerating is caught by the parity gate, not by the
semantics tests — those run against the shipped artifact and would keep
passing. Both failure modes are demonstrated in ADR-2608138800.

## Local MLX host adapter (`kotodama.inference.mlx`, Apple Silicon)

A thin `IModelRuntime` host adapter (same shape as `kotodama.inference.ollama`)
for a local, already-running OpenAI-compatible MLX server — either Apple's
own `mlx_lm.server` or mu-hashmi/mlx-moe's `serve` (single-node MoE, SSD-paged
experts; the fleet planner that launches it lives in `kotoba-lang/murakumo`'s
`murakumo.infer.moe`). Both speak the same `/v1/chat/completions` wire shape,
so one client covers both — `:backend` only labels which process convention
the caller launched:

```clojure
(require '[kotodama.inference.mlx :as mlx]
         '[kotodama.inference.ports :as ports])

(def rt (mlx/mlx-runtime {:base-url "http://127.0.0.1:8080"
                          :model "mlx-community/Qwen3.6-35B-A3B-4bit"
                          :backend :mlx-lm}))    ; or :mlx-moe
(def session (ports/load! rt {}))
(ports/generate! rt session "..." {:kotodama/max-new-tokens 64 :kotodama/temperature 0.2})
```

`generate!` is the only method that talks over HTTP; `forward!` throws (no
raw-tensor endpoint on either server), matching the Ollama adapter's own
limitation. See `cljc/test/kotodama/inference/mlx_test.cljc` for the pure
(no-I/O) coverage — the HTTP path is verified by hand against a running
`mlx_lm.server`/`mlx-moe serve`, the same standard the Ollama adapter holds
itself to.

`kotoba-lang/num` and `kotoba-lang/torch` are sibling local dependencies. A
standalone checkout should place them next to this repository, or use a monorepo
layout that preserves `../num` and `../torch`.

## Native Runtime Status

The former Rust WebGPU/native runtime experiment, Cargo metadata, and Rust
integration tests have been removed from this repository. Runtime backends should
live in adapter repositories and consume the CLJC contracts here.
