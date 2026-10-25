# torch-clj — ニューラルネット module graph を EDN データとして

[![CI](https://github.com/kotoba-lang/torch/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/torch/actions/workflows/ci.yml)

A PyTorch-style neural-network module graph defined as **plain EDN data**, with
a pure shape-&-parameter engine. Like its sibling libraries, torch-clj treats
the model as data — a `{layer args}` map is the same shape as a JSONLogic rule —
so a network is generated, diffed, versioned, shipped, and stored (Datomic /
kotoba) exactly like any other EDN value.

- **Portable `.cljc` model kernel** for JVM and ClojureScript; numerical
  execution and reference training use the sibling `num` library.
- **Describe first, execute explicitly.** torch-clj propagates shapes and
  counts parameters without tensor math. `torch.num-backend` performs a real
  forward pass, and `torch.train` provides a deliberately small CPU reference
  training path.
- **Data-first.** The model is plain EDN; host-specific layer types arrive
  through `torch.ports/ILayer`, not by editing the kernel.

Sibling libs: [jsonlogic-clj](../jsonlogic) (rules-as-data),
[dmn-clj](../org-omg-dmn) (decision tables), [vllm-clj](../vllm) (LLM inference
requests-as-data).

## Why a shared library (org placement)

Per the three-org rule, the **reusable** module-graph kernel lives in
**com-junkawasaki**; **public-benefit** model/actor instances that consume it
live in **etzhayyim**; any **business/private deployment** lives in
**gftdcojp**. torch-clj is the dep — it carries no domain models and no engine
bindings (those are host-injected ports).

## The model: a module graph as EDN (`torch.model`)

A layer is a one-key `{type args}` map; a model is a sequential of layers (or a
bare vector, read as an implicit sequential). Builders are threadable data:

```clojure
(require '[torch.model :as m])

;; an MLP, written as data
(def mlp
  (m/sequential
   (m/linear 784 256) (m/relu)
   (m/linear 256 10)  (m/softmax)))
;; => {:torch/module :sequential
;;     :torch/layers [{:linear [784 256]} {:relu {}}
;;                    {:linear [256 10]}  {:softmax {}}]}

;; the literal form is just as valid — no builders required
(def cnn
  [{:conv2d [1 8 3 1 1]} {:relu {}} {:maxpool2d [2]}
   {:flatten {}} {:linear [1568 10]}])

;; sub-models nest and compose
(def block (m/sequential (m/linear 64 64) (m/relu)))
(m/sequential (m/linear 32 64) block (m/linear 64 10))
```

Nested Sequentials execute in recursive leaf order across inference, autograd,
optimizers, summaries, and checkpoints. `torch.model/layer-entries` exposes each
leaf plus its stable index path; checkpoint names retain module structure (for
example `layers.1.layers.0.weight`) instead of flattening names ambiguously.

Built-in layer types: `:linear :conv2d :maxpool2d :avgpool2d :embedding
:batchnorm :layernorm :groupnorm :dropout :flatten :relu :silu :gelu
:sigmoid :tanh :softmax :attention :multihead-attention`.

`:attention` means parameter-free self-attention over a single
`[sequence embedding]` tensor — `(m/attention)` is single-head,
`(m/attention num-heads)` splits `embedding` evenly across heads (an error if
it doesn't divide). It has no batch axis, mask, or learned QKV projections;
`(m/multihead-attention embed-dim num-heads)` adds independent learned Q/K/V
and output weight/bias projections in the same data-first model form. Learned
attention accepts `[sequence embedding]` or batch-first
`[batch sequence embedding]`; `(m/multihead-attention d h {:causal? true})`
enables causal masking. Llama-compatible rotary position embedding is enabled with
`{:rope? true}`; `:rope-theta`, `:position-offset`, and
`:context-position-offset` support long-context and cached/cross-attention positions.
RoPE is applied head-wise to projected Q/K (not V), including its inverse-rotation
VJP on Metal. Training/VJP calls accept one runtime options map per layer,
including a `[batch sequence]` `:key-padding-mask` whose non-zero keys are ignored:

```clojure
(train/loss-and-gradients model weights input target
  {:layer-options [{:context encoder-hidden-states
                    :key-padding-mask padding-mask}]})
```

Incremental autoregressive inference reuses projected, RoPE-rotated keys and
values without a host readback:

```clojure
(let [initial-cache (nb/init-kv-cache backend 4096 embed-dim)
      {:keys [output cache]}
      (nb/multihead-attention-step layer layer-weights one-token initial-cache)]
  {:logits output :cache cache})
```

The step accepts `[1 embed]` or `[batch 1 embed]`; its output matches the same
layer's full causal pass token-for-token, verified on Apple Metal. A cache from
`init-kv-cache` preallocates K/V once and appends device-to-device without changing
either GPUBuffer handle. Pass the batch size as the fifth argument, for example
`(init-kv-cache backend 4096 embed-dim :f32 8)`. Its token-major backing makes
each batched append contiguous while attention receives a batch-first view. The
older nil-start immutable cache remains supported.

`(m/llama-block embed heads hidden)` is a bias-free pre-normalized decoder
block: RMSNorm → RoPE causal attention → residual → RMSNorm → SwiGLU → residual.
Blocks are ordinary model layers for full-sequence inference and training. For
incremental multi-layer decoding, allocate one cache per block and advance all
blocks with one token:

```clojure
(def caches (nb/init-llama-caches backend model 4096))
(nb/llama-model-step model weights one-token caches)
;; => {:output hidden-state :caches updated-per-layer-caches}
```

Two stacked blocks are verified token-for-token against their full causal model
on Apple Metal while every layer retains its originally allocated K/V handles.

A complete decoder can be described as ordinary layers:

```clojure
(m/sequential (m/embedding vocab embed)
              (m/llama-block embed heads hidden)
              (m/llama-block embed heads hidden)
              (m/rmsnorm embed)
              (m/lm-head embed vocab))
```

`llama-lm-step` accepts one token ID and returns `{:logits [1 vocab] :caches ...}`.
`torch.generate/sample-token` supports greedy,
temperature, top-k, nucleus/top-p, and repetition-penalty policies. Randomness is
passed explicitly as `:random-value`, keeping sampling reproducible and allowing a
server to own its RNG stream. Native WebGPU serving now keeps logits device-resident:
simple greedy requests use `num.array/argmax-rows` and return one u32 per request.
Untruncated temperature-softmax (`top-k=nil`, `top-p=1`) uses a token-ID-order CDF
on both host and device, preserving explicit-random-value reproducibility while
returning only one u32. Shared batch ownership releases the logits buffer exactly
once across completion, cancellation, and ragged rows.

`torch.tokenizer/tokenizer` builds a portable BPE tokenizer from ID-ordered
tokens and merge pairs. It supports BOS/EOS, SentencePiece-style space prefixes,
Unicode codepoints, and GGUF-style `<0xHH>` UTF-8 byte fallback. The same `.cljc`
implementation is verified on JVM and Node. `torch.generate/generate-text` joins
tokenization, prompt prefill, cached token steps, sampling, EOS termination, and
decoding for synchronous runtimes; GPU callers use the same sampling policy through
the asynchronous device-selection boundary.

### GGUF model loading

`torch.gguf/load-file` parses GGUF v2/v3 with long file offsets, typed/nested
metadata arrays, `general.alignment`, and bounds-checked positional reads rather
than loading the entire model file. `read-tensor` decodes F32, F16, Q8_0, Q4_K,
and Q6_K (including their packed per-block scale layouts);
`llama-model`, `gguf-tokenizer`, and `load-llama-weights` construct the model,
tokenizer, transpose GGUF linear matrices, upload weights, and handle tied output
embeddings.

Q4_K, Q6_K, and Q8_0 linear tensors remain packed at their GGML bit rates and
execute through fused CPU/Metal quantized matmul without a dense weight
allocation. Quantized token embeddings use packed device-native lookup; when
`output.weight` is tied/missing, the LM head shares that exact packed buffer
through a zero-copy matrix view. Llama
grouped-query attention is supported when
`head_count_kv` evenly divides `head_count`, including training and fixed-capacity
KV-cache decoding on Metal; K/V projections and caches use the reduced KV width.
Both general attention and complete Embedding → multi-block GQA Llama → LM-head
decode have full/cached parity tests for batch 2 on Apple Metal, with stable
GPUBuffer handles across every token.

Host-side static batching is available through `generate-text-batch`. A single
step callback receives one token per request and shared per-layer caches; rows
that reach EOS early are padded so unfinished rows continue without changing the
fixed GPU batch layout. Prompts currently need equal encoded lengths. Ragged
prefill and device-executed continuous batching remain future work.

`torch.kv-cache` provides the ownership layer for that next serving mode. It
maintains a bounded physical-block free list, per-sequence block tables and
refcounts, lazily reserves prompt/decode positions, shares forked prefix blocks,
and emits explicit copy-on-write commands when two forks would write the same
partial block. Its FIFO scheduler admits work up to a configured running batch,
leaves an oversized head request queued transactionally when memory is exhausted,
and immediately admits waiting work after a completed sequence releases blocks.
Allocator invariants are executable through `valid?` and covered on JVM and by
CLJS compilation. `torch.paged-runtime` consumes allocator placements and submits
prefix-copy before token-write on the storage queue, then passes each sequence's
logical block table to its attention callback. The corresponding physical
write/copy/paged-GQA kernels are implemented and independently live-verified in
`num.deno-gpu`; publishing that new num revision and wiring the complete Llama
step to this bridge are still required. Request cancellation/timeouts and a
production concurrent HTTP server also remain before claiming Ollama-equivalent
continuous serving.

The bridge now executes a complete Embedding → two GQA Llama blocks → RMSNorm →
LM-head decode against those physical kernels. The live verifier compares every
token's vocabulary logits with the ordinary full causal CPU model, checks the
allocator/device placements, and releases both layers' physical pools:

```sh
kbb -M:deno-paged-llama-verify
deno run --allow-all target/deno-paged-llama-verify.cjs
# Apple M4: full two-block paged Llama parity: passed
#           allocator/device placement alignment: passed
#           physical paged pools release: passed
```

That verifier temporarily overrides the pinned `num` dependency with the sibling
`../num` checkout. Normal consumers still use the published SHA; the override can
be removed after the paged Metal revision is merged and pinned.

`torch.continuous` adds request turnover on top of the shared layer pools. It
supports different prompt lengths, FIFO admission under both batch and block
limits, synchronous CPU and Promise-based WebGPU stepping, per-request sampling,
pause-on-block-exhaustion, EOS/length eviction, and immediate admission after
blocks are released. The live fixture fills every block with two ragged requests,
finishes one, reuses its block to prefill a waiting third request, and completes
all three through the same two physical Metal layer pools:

```sh
kbb -M:deno-continuous-verify
deno run --allow-all target/deno-continuous-verify.cjs
# Apple M4: ragged continuous request turnover: passed
#           paged blocks fully reusable: passed
#           shared physical pools release: passed
```

`tick-batched` and `tick-batched-async` classify EOS/length completions first,
release their blocks, pause rows that cannot grow, and group every remaining
runnable request into one Llama batch call in stable order. Ragged prefill is still
request-local.

Serving lifecycle controls now include bounded waiting queues with explicit
backpressure rejection, cancellation of queued or running requests, absolute
deadlines, timeout eviction, immediate block release, and counter/gauge snapshots
for submissions, admissions, rejections, completions, prompt/decode tokens,
microbatches, active queues, peaks, and free blocks per layer.

Submission rejects a prompt that can never fit the physical paged-KV capacity.
If decode reaches the per-sequence capacity, it completes with `length` and
releases every block instead of remaining permanently paused. This invariant was
also exercised by the longer ChatML control-token prompt on real Metal.

The lower execution API also provides `llama-lm-paged-batch-step`: QKV and FFN
projections remain batch tensors while each layer resolves request-specific RoPE
positions and performs one fused ragged paged-attention dispatch. A length-1 and
length-2 prefix advanced together match both ordinary full causal sequences on
CPU and Apple Metal:

```sh
kbb -M:deno-paged-batch-llama-verify
deno run --allow-all target/deno-paged-batch-llama-verify.cjs
# Apple M4: ragged fused paged Llama parity: passed
#           batched physical pools release: passed
```

The continuous Metal verifier configures both callbacks and proves that `[:a :b]`
is selected automatically into one fused decode call before their blocks are
released and reused to prefill request `:c`.

`torch.ollama` translates `/api/generate` options and deadlines into continuous
engine submissions and emits Ollama-shaped token/final payloads.
`torch.ollama-http/handler` is a standard Fetch handler suitable for `Deno.serve`;
it implements `GET /api/version`, `GET /api/tags`, `GET /api/ps`,
`POST /api/show`, `POST /api/copy`, `DELETE /api/delete`, `POST /api/embed`, and streaming NDJSON or
non-streaming `POST /api/generate` and `POST /api/chat`, including JSON 400/404
errors. Chat validates ordered system/user/assistant text history, renders a
model-specific prompt from GGUF `tokenizer.chat_template`, and returns Ollama
`message.role/content` chunks. The renderer recognizes Llama 2 `[INST]`, Llama 3
header tokens, and ChatML; an unknown Jinja family fails explicitly instead of
silently applying the wrong prompt. Models without template metadata retain the
deterministic portable prompt.
Images, thinking, structured output, and tool calls remain explicit unsupported
boundaries rather than being silently ignored. Its live
Request/Response verifier checks headers, status codes, three NDJSON records, and
the assembled non-stream response:

`/api/embed` accepts one string or a batch, runs the real Llama embedding and
decoder blocks through the resident model, stops before the LM head, takes the
last causal hidden row, and returns L2-normalized vectors. Context overflow obeys
`truncate`; unsupported output dimensions fail explicitly. The cached step is
checked against full-sequence CPU hidden states, while the registry verifier runs
two inputs through the public GGUF on Apple Metal and checks dimensions, unit
norms, lifecycle refcounts, and final GPU cleanup.

The same listener also exposes the Ollama-supported OpenAI compatibility surface:
`GET /v1/models`, `GET /v1/models/{model}`, `POST /v1/chat/completions`, and
`POST /v1/embeddings`. Chat defaults to non-streaming as OpenAI clients expect;
streaming uses `text/event-stream`, one `data:` frame per native generation
chunk, and a terminal `[DONE]`. Both forms preserve OpenAI choices and token
usage envelopes while executing through the same resident model and cancellation
path as `/api/chat`. Unsupported multiple choices, tools, response formats,
stop sequences, and non-float embedding encodings fail explicitly with an
OpenAI-shaped error instead of being silently ignored.

```sh
kbb -M:deno-ollama-http-verify
deno run --allow-all target/deno-ollama-http-verify.cjs
# native Ollama plus OpenAI models/chat/embeddings, SSE cancellation: passed
```

`serve!` starts a real Deno listener (default `127.0.0.1:11434`) and exposes its
graceful `.shutdown()` lifecycle. Every generate request receives a stable request
ID and AbortSignal context; a client disconnect invokes the injected `cancel!`
callback exactly once and response completion removes the listener. The verifier
also starts an ephemeral TCP port, reaches it with `fetch`, aborts a separate
in-flight request, and shuts the server down.

When the service provides `generate-stream!`, each generated chunk is encoded and
enqueued as one NDJSON record through a byte `ReadableStream`; the handler does not
wait for generation completion. Stream close/error/reader-cancel each run cleanup
once, while TCP reader cancellation propagates to `Request.signal` and `cancel!`.
The live test emits chunks at 0/60/120 ms, proves the first bytes arrive before
100 ms, cancels the reader, and confirms producer timers and generation are
cancelled. The HTTP layer still receives injected generation callbacks; model
loading can be supplied through the registry below; authentication and production
observability remain.

`torch.model-registry` bounds loaded resources by byte budget. Catalog models are
loaded lazily, acquire/release references prevent active eviction, Ollama
`keep_alive` values (`5m`, seconds, `0`, or `-1`) set expiry, and inactive models
are evicted in deterministic LRU order until a new model fits. Explicit unload,
forced administrative unload, live catalog/tag snapshots, and residency/load/
eviction metrics are included. The unload callback is where GGUF weights, paged
K/V pools, and device resources are released. `/api/tags` accepts a snapshot
function, so loaded/active registry state is visible without rebuilding the HTTP
handler. `/api/copy` creates an independently loadable catalog alias without
sharing resident ownership; `/api/delete` releases an inactive resource before
removing its descriptor and rejects active or unknown models without corrupting
the registry. A production host still needs to connect its GGUF loader callback to
model-specific continuous engines.

`torch.registry-runtime` supplies that serialization without `swap!` retries:
JVM mutations run under one lock, while CLJS mutations execute without an event-
loop yield. This matters because loader/unloader callbacks have GPU side effects
and must never be repeated by a failed CAS. A 24-thread acquire/release test loads
and unloads exactly once, and the Deno HTTP verifier reads dynamic tags from the
same runtime before expiry unloads the resource. Failed budget admission loads and
retires only the new candidate; existing LRU resources are planned first and are
not physically evicted unless the complete capacity plan succeeds.

`torch.gguf-resource` is the concrete JVM registry factory: a filesystem
descriptor uses the real byte size, then `load-file`, `llama-model`,
`gguf-tokenizer`, and `load-llama-weights` construct the resource. Optional
`engine-fn` builds its continuous serving engine, and unload calls
`release-weights!`, which deduplicates tied/aliased dense and packed handles.
Factory composition and cleanup are tested; a public full GGUF checkpoint is not
downloaded as part of the default test suite. An opt-in verifier now exercises a
real public checkpoint without mocks: it parses GGUF v3, decodes legacy Q5_0
blocks (including tensors whose 32-value blocks span narrow logical rows), keeps
all 13 Q5_0 weights packed through matrix multiplication and embedding, builds
the Llama graph and SentencePiece tokenizer, runs cached greedy decode, validates
finite logits/token bounds, and releases the KV cache and all weights.

```sh
curl -L --fail -o /tmp/tiny-random-llama.Q4_K_M.gguf \
  https://huggingface.co/ybelkada/tiny-random-llama-Q4_K_M-GGUF/resolve/main/tiny-random-llama.Q4_K_M.gguf
shasum -a 256 /tmp/tiny-random-llama.Q4_K_M.gguf
# f06746ef9696d552d3746516558d5e9f338e581fd969158a90824e24f244169c
kbb -M:public-gguf-verify /tmp/tiny-random-llama.Q4_K_M.gguf
# Apple M4 JVM reference run: 1,627,808 bytes, 21 tensors, load 6.39 s,
# four cached decode tokens 0.40 s; 13 packed Q5_0 weights; status :passed.
```

This checkpoint has random weights and proves compatibility/lifecycle, not text
quality. The verifier is CPU-hosted because the current GGUF parser is JVM-only;
an explicit portable bundle now joins that parser to the Deno/Metal host and
proves the same real checkpoint through the full Llama graph:

```sh
kbb -M:gguf-bundle-export /tmp/tiny-random-llama.Q4_K_M.gguf \
  target/tiny-random-llama-metal.tgb
kbb -M:deno-public-gguf-metal-verify && \
  deno run --allow-all target/deno-public-gguf-metal-verify.cjs \
  target/tiny-random-llama-metal.tgb
# Apple M4: CPU expected = Metal generated = [30821 25334 12729 26193]
# full Embedding → 2 Llama blocks → RMSNorm → 32k LM head: 1.01 s
# released: 25 weight/cache buffers, 2,415,376 bytes
# remaining transient GPU buffers: 0
```

`TGBNDL1` is a bounded manifest + binary-payload container: packed tensors stay
raw U8, dense fallback tensors use little-endian F32, and tokenizer/config/test
metadata remains readable EDN. The public fixture shrinks from 12,656,318-byte
text EDN to 2,993,475 bytes (76.3% smaller). The Deno reader validates magic,
manifest/payload bounds, F32 alignment, and dense shape size before GPU upload.
Apple M4 reads and decodes this fixture in 192 ms. It is an inference
interchange, not yet direct JVM↔Deno IPC.

The same real bundle is also exercised through the actual `Deno.serve` Ollama
surface rather than a fake generation callback. Both streamed NDJSON and
non-stream `/api/generate` contexts match the CPU reference IDs, cancellation is
delivered after a live client disconnect, and all request caches plus resident
weights return GPU live storage to baseline:

```sh
kbb -M:deno-public-gguf-ollama-verify && \
  deno run --allow-all target/deno-public-gguf-ollama-verify.cjs \
  target/tiny-random-llama-metal.tgb
# Apple M4 warm run: first NDJSON byte 373 ms; complete four-token stream 1090 ms
# stream/non-stream parity, incremental delivery, disconnect cancel: passed
# GPU baseline restored: passed
```

This concrete server adapter currently gives each request a fixed KV cache. The
portable paged continuous scheduler is verified separately; connecting this
real async Metal adapter to its ragged microbatch loop remains the next serving
step, along with production admission control.

The real checkpoint now also runs through that paged scheduler itself. Three
different public-tokenizer prompts are admitted two at a time, prefilled at
their independent lengths, decoded through fused ragged Metal microbatches, and
compared with CPU greedy reference IDs. All logical blocks return to the pool,
and all physical pools, weights, and transient tensors return to GPU baseline:

```sh
kbb -M:deno-public-gguf-continuous-verify && \
  deno run --allow-all target/deno-public-gguf-continuous-verify.cjs \
  target/tiny-random-llama-metal.tgb
# Apple M4: CPU/continuous Metal token parity: passed
# ragged real prompts in fused microbatch: passed
# 4 ticks; 15 prefill single calls; 2 fused batch calls
# paged blocks reusable / GPU baseline restored: passed
```

Both single-request and batched paged Llama blocks now release projection,
RoPE, attention, residual, and SwiGLU intermediates at their ownership boundary;
the verifier's created/destroyed byte and buffer deltas must balance exactly.
The final serving boundary in this sequence was routing live Ollama callbacks
through the shared engine instead of per-request fixed caches.

`torch.continuous-ollama` now closes that boundary. It serializes submit,
admission, async GPU ticks, timeout expiry, and cancellation through one Promise
lane; coalesces concurrently arriving HTTP requests before admission; publishes
only each request's newly generated token delta; and supports both live NDJSON
and collected non-stream responses. A real-socket verifier submits a streamed
`Hello` and non-streamed `Hi there` concurrently, then disconnects a third live
request after its first chunk:

```sh
kbb -M:deno-public-gguf-continuous-http-verify && \
  deno run --allow-all target/deno-public-gguf-continuous-http-verify.cjs \
  target/tiny-random-llama-metal.tgb
# Apple M4: concurrent stream/non-stream CPU parity: passed
# HTTP requests shared fused microbatch: passed
# completed reasons: length, length, cancelled
# paged blocks reusable / GPU baseline restored: passed
```

This is now an actual shared paged Metal Ollama path, not parallel isolated
fixed caches. The next boundary was multi-model routing through the registry.

`torch.metal-resource` and `torch.registry-ollama` add real multi-model routing.
A catalog descriptor lazily reads `TGBNDL1`, uploads weights, constructs physical
paged pools and a continuous host, while unload refuses active work and releases
all pools/weights. Each HTTP request acquires the named resource and releases it
with Ollama `keep_alive`; stream close/cancel is exactly-once. `/api/tags` reads
the catalog plus residency flags, `/api/ps` lists only currently resident Metal
resources, and `/api/show` reads model/configuration details from the compact
bundle manifest without uploading its tensor payload.

```sh
kbb -M:deno-public-gguf-registry-verify && \
  deno run --allow-all target/deno-public-gguf-registry-verify.cjs \
  target/tiny-random-llama-metal.tgb
# Apple M4: model-name routed CPU parity / dynamic residency tags: passed
# Ollama ps/show follow real Metal residency: passed
# Ollama chat runs through the resident public-GGUF Metal model: passed
# Ollama normalized batched embeddings run on Metal: passed
# Ollama copy/delete mutate the live model catalog: passed
# OpenAI chat/embeddings use the resident public-GGUF Metal model: passed
# inactive model-a LRU-evicted when model-b loads under a 1.5-model budget
# each model loaded/unloaded exactly once; resident bytes: 0
# GPU baseline restored: passed
```

The remaining production work is now operational scale rather than a missing
model route: long-context soak/load tests, durable catalog configuration,
authentication, telemetry, and deployment hardening.

The lifecycle verifier observes a copied alias appear in `/api/tags` and disappear
after deletion before starting Metal inference. Pure registry tests additionally
cover duplicate destinations, unknown names, active-delete rejection, and
exactly-once unload of an inactive alias.

A whole-graph Metal benchmark covers more than an isolated kernel: two Llama
blocks, 256 hidden width, 4 query/2 KV heads, every linear and token embedding
Q4_K-packed, tied LM head, causal prefill, and fixed-capacity KV-cache decode.

```sh
kbb -Sdeps '{:deps {io.github.kotoba-lang/num {:local/root "../num"}}}' \
  -M:deno-quantized-llama-benchmark && \
deno run --allow-all target/deno-quantized-llama-benchmark.cjs
# Apple M4, 16 tokens:
# packed 479,232 bytes vs dense equivalent 3,407,872 bytes (7.11x)
# full cold 42.806 ms; full warm prefill 23.815 ms
# cached decode 8.852 ms/token; full/cached parity passed
```

This deterministic synthetic model verifies orchestration, storage, and kernel
integration. It is not a quality or real-checkpoint tokens/sec claim.

When `:context` is present, Q is projected from the current model value while K/V
are projected from the separate context sequence, enabling UNet-style cross-attention
with different query/key lengths. VJP and MSE results expose the context gradient at
`[:layer-input-gradients layer-index :context]`. The four-argument `torch.core/run`
uses the same options through the optional runtime-backend port, so inference and
training share the exact context/mask contract.
`:conv2d` executes full NCHW batches and
supports scalar/pair kernels, stride, padding, dilation, groups, depthwise
convolution, and bias. `torch.num-backend/random-weights` produces a
`[out-ch in-ch/groups kh kw]` kernel; hand-supplied rank-2 `[kh kw]` kernels
(the original single-channel form) still work unchanged. `:groupnorm` uses
`(m/groupnorm num-groups num-channels)` and `:silu` uses `(m/silu)`.

## Shape & parameter engine (`torch.shape`, `torch.core`)

Shapes are batch-agnostic feature shapes (`[784]`, `[3 32 32]` for CHW). Each
built-in is a pure `(args, in-shape) → [:ok out] | [:error msg]` function;
nothing throws on bad user data. `torch.core/summary` walks the whole network:

```clojure
(require '[torch.core :as core])

(core/summary mlp [784])
;; => {:torch/in-shape  [784]
;;     :torch/layers    [{:torch/layer :linear  :torch/args [784 256]
;;                        :torch/out-shape [256] :torch/params 200960} …]
;;     :torch/out-shape    [10]
;;     :torch/total-params 203530
;;     :torch/error        nil}

(core/infer-shape cnn [1 28 28])  ;=> [10]
(core/total-params mlp)           ;=> 203530
```

A shape error stops propagation and is reported (it never throws):

```clojure
(:torch/error (core/summary [{:linear [784 256]} {:linear [999 10]}] [784]))
;; => "linear in-features 999 ≠ input last dim 256"
```

## Validation (`torch.validate`)

Static structural checks (well-formed layers, known types, sane arity), returned
as a pure vector of problem maps. `valid?` is true iff there are no `:error`s.

```clojure
(require '[torch.validate :as v])

(v/valid? mlp)                       ;=> true
(v/problems [{:linear [10]}])
;; => [{:torch/severity :error :torch/code :layer/arity :torch/path "0"
;;      :torch/msg ":linear needs ≥ 2 positional args, got [10]"}]
```

## Ports (`torch.ports`)

Two host-injected protocols. `ILayer` is the layer vocabulary (default delegates
to `torch.shape`); `IBackend` is *optional* real tensor execution. Add a custom
layer without touching the kernel:

```clojure
(require '[torch.ports :as ports])

(def scale-ports
  (ports/with-layers
    (reify ports/ILayer
      (custom-layer? [_ t] (= t :scale))
      (shape-of  [_ _ _ in] [:ok in])   ; shape-preserving
      (params-of [_ _ _] 0))))

(core/summary scale-ports [{:linear [10 20]} {:scale [2.0]}] [10])
;; :scale is unknown to the built-ins, known to the host
```

A host that binds a real engine implements `IBackend`; `core/run` then performs
an actual forward pass. With no backend, torch-clj is shape-only and `run`
throws — by design.

### Reference autocast

`torch.num-backend/num-backend` accepts `{:autocast-dtype :f16}` or `:bf16`.
Inputs and parameters are materialized in num's physical two-byte storage, and
linear, NCHW convolution, GroupNorm, ReLU, and SiLU keep that dtype through
typed reference operations. The CPU oracle supports both types; num's
Deno→Metal backend supports packed f16 GEMM, elementwise, convolution, and
GroupNorm kernels with f32 accumulation.

For an asynchronous GPU backend, generate or load weights directly in target
storage with `(random-weights backend model seed {:dtype :f16})`. This avoids a
device→host→device cast; existing typed weights are reused without copying.

The full torch model dispatch is verified on Apple M4 Metal:

```sh
kbb -M:deno-autocast-verify
deno run --allow-all target/deno-autocast-verify.cjs
# torch conv→GroupNorm→SiLU f16: passed
```

On a backend exposing num's typed tensor kernels, F16 autocast now executes
parameter-free and learned multi-head attention without returning to f32:
projection GEMMs, transpose, last-axis bias, stable-softmax attention, and output
projection all retain physical half storage. Causal attention is supported;
key-padding masks remain on the f32 path and are rejected explicitly. Standalone
softmax is likewise still rejected instead of silently changing dtype. Training
keeps f32 master tensors, while mask-free F16 attention now uses num's fused
device-resident backward rather than leaving the GPU.

## Reference training (`torch.train`)

The model EDN and the same weight vector accepted by `torch.num-backend` now
drive reverse-mode autodiff and immutable SGD updates directly:

```clojure
(require '[num.array :as a] '[num.cpu :as cpu]
         '[torch.num-backend :as nb] '[torch.train :as train])

(def backend (cpu/cpu-backend))
(def weights (nb/random-weights backend mlp 42))
(def input  (a/from-vec backend (repeat 784 0.1) [1 784]))
(def target (a/from-vec backend (cons 1.0 (repeat 9 0.0)) [1 10]))

(def step (train/sgd-step mlp weights input target 0.01))
(:loss step)    ; scalar MSE before this update
(:weights step) ; new arrays; the original weights remain unchanged
```

For stateful optimization, `torch.optim/adamw-step` consumes the aligned
weights and gradients returned by `torch.train/loss-and-gradients`. It returns
both new weights and immutable first/second-moment state; pass that state into
the next step. Learning rate, betas, epsilon, and decoupled weight decay are
configurable, with AdamW defaults when omitted. On an f32 `ITensorBackend`, each
parameter update is a fused device dispatch that produces new weight, first-moment,
and variance buffers; first-step zero slots are allocated on-device. No parameter,
gradient, or optimizer slot is downloaded.

`torch.optim/sgd-step` implements PyTorch SGD semantics over the same aligned
device tensors: momentum, first-step buffer initialization, dampening, coupled
weight decay, Nesterov, and maximize are supported. Momentum buffers are
immutable optimizer state and remain on the tensor backend; invalid Nesterov
combinations and mismatched parameter/gradient layouts fail before an update.
`torch.train/optimizer-step` connects model execution, MSE backward, and either
`:sgd` or `:adamw` in one call, returning the next weights and optimizer state.

`torch.optim/grad-scaler` and `scaled-adamw-step` provide dynamic loss scaling:
call `loss-and-gradients` with the scaler's `:scale`, then pass the scaled
gradients to the optimizer. Gradients are unscaled before AdamW, non-finite
values skip the update and back off the scale, and stable steps grow it at the
configured interval. Unscaled gradients and optimizer state remain f32; this
is the control path used by the mixed-precision training API below.
For an asynchronous GPU backend, `scaled-adamw-step-async` performs unscale and
non-finite detection in one device dispatch per parameter, reads back only the
one-scalar flags, then either launches fused GPU AdamW or skips every update and
backs off the scale. It returns a Promise in ClojureScript and a completed
`CompletableFuture` on the JVM.

### Checkpoints and PyTorch state dictionaries

`torch.safetensors/save-weights!` and `load-weights` write and read stable
PyTorch-style parameter names. Linear and attention projection matrices are
transposed at the file boundary (`[out,in]` externally, `[in,out]` internally),
while convolution and normalization tensors retain their native layout. Loading
is strict by default: missing and unexpected tensors fail before execution.

For restartable training, `torch.checkpoint/save-checkpoint!` stores model
weights, every AdamW first/second moment, optimizer step/options, GradScaler
state, and caller-owned JSON training position in one safetensors file. The
write uses a sibling temporary file, fsync, and atomic replacement where the
filesystem supports it. `load-checkpoint` validates the schema and complete
tensor set before returning state accepted directly by the next training step:

```clojure
(require '[torch.checkpoint :as checkpoint])

(checkpoint/save-checkpoint!
 "run.safetensors" model weights
 {:optimizer-state optimizer-state
  :optimizer-options {:learning-rate 1.0e-3}
  :scaler scaler
  :training-state {:epoch 3 :batch 120}})

(def resumed (checkpoint/load-checkpoint "run.safetensors" backend model))
```

Training checkpoints use F64 storage to preserve the CPU reference backend's
double intermediates even for logically-f32 arrays. Tests interrupt an
AdamW+GradScaler run, reload it, and prove that every subsequent loss, weight,
moment, variance, and scaler value is exactly equal to uninterrupted training.

`torch.train/mixed-precision-adamw-step` and its GPU-capable asynchronous twin
`mixed-precision-adamw-step-async` connect these pieces for
linear/attention and conv2d/GroupNorm/SiLU/ReLU models: it casts the forward pass to f16 or bf16,
computes f32 gradients, unscales and checks them, then updates immutable f32
master weights with AdamW. Non-finite gradients skip the optimizer step and
back off the scaler; both successful updates and forced-overflow skips are
tested. On Deno Metal, mask-free learned attention keeps projection and
attention activations in physical F16, runs the attention VJP on-device, uses
f32 device stability reductions for projection bias and MSE, and materializes
f32 parameter gradients before the master update. Beyond its reported scalar
loss, the asynchronous API reads back only overflow flags before fused AdamW. Apple M4 verification covers
F16 prediction, all eight Q/K/V/output projection gradients, GradScaler state,
and updated master-weight parity against the CPU oracle.

The same path now trains a complete language-model graph: Embedding → two
pre-normalized GQA Llama blocks → final RMSNorm → vocabulary LM head. Packed-F16
activation gradients and f32 master-parameter gradients remain on Metal through
all 21 trainable tensors. `:deno-metal-llama-train-verify` uses repeated token
IDs to exercise embedding scatter-add semantics, then compares prediction,
every VJP, GradScaler/AdamW state, and updated weights with an independent f32
CPU oracle using `kv-heads=1` and two query heads.

Language-model training can select stable token-label cross entropy with
`{:loss :cross-entropy :ignore-index -100}`. Labels retain integer-valued f32
storage while logits stay packed F16; mean reduction excludes ignored positions,
and the loss-scaled logit VJP feeds the same asynchronous GradScaler/AdamW path.
The Metal verifier uses shifted next-token labels and ignores the final position,
rather than training logits against a synthetic MSE target.
Its vocabulary is 32,000, embedding width is 128, SwiGLU width is 256, sequence
length is 8, and each block uses four query heads with two KV heads. On Apple M4,
the full two-block forward, cross-entropy backward, asynchronous AdamW step, and
complete prediction/gradient/updated-weight readback take 44.02 seconds with
411,066,140 tracked peak live GPU bytes. All 21 parameter VJPs stay within a 1%
tensor-range maximum plus bounded mean-error gate, and every updated weight uses
the stricter elementwise CPU-oracle tolerance.

The reference path supports recursively nested sequential models composed from
`:linear/:conv2d/:embedding/:groupnorm/:layernorm/:rmsnorm/:flatten/:relu/:silu/:sigmoid/:tanh/:gelu/:softmax/:attention/:multihead-attention/:llama-block/:lm-head`, with MSE and
stateful PyTorch-style SGD plus immutable AdamW. NCHW grouped convolution, affine GroupNorm, SiLU, and
multi-head self-attention all have real reverse-mode gradients; tests verify
both finite-difference agreement in `num` and decreasing loss through the
public torch model/weight representation. It is not yet a replacement for
PyTorch's broader optimizer catalog, general GPU autograd, or mixed-precision
coverage for every layer.

`Flatten` follows PyTorch's batch-preserving default: `[N,C,H,W]` becomes
`[N,C*H*W]`, is zero-copy in forward execution, and reshapes its VJP back to the
exact input shape. Consequently the documented
`Conv2d → activation → Flatten → Linear` CNN form now runs and trains through
the same EDN model rather than remaining shape-only syntax.

The standalone two-linear-layer Metal trainer follows num's current MSE VJP
contract, including an explicit device-resident upstream scalar seed. Its full
backward/update result matches CPU on Apple M4 and lowers loss from `0.75249` to
`0.16486`; the verifier guards shader binding count as well as numeric parity.

For an explicit vector-Jacobian product, `prediction-and-gradients` accepts an
upstream tensor with the prediction's shape. This is equivalent to PyTorch's
`prediction.backward(gradient)` and avoids imposing or synchronously reading a
scalar loss:

```clojure
(train/prediction-and-gradients model weights input upstream-gradient)
;; => {:prediction ... :input-gradient ... :gradients [...]}
```

On an f32 WebGPU backend, learned attention uses device-native projection GEMMs,
matrix transposes, bias row reductions, fused attention forward/backward, and
gradient accumulation. MSE forward and its VJP are also device-native; on an async
backend `loss-and-gradients` returns `:loss` as a Promise for the final scalar
readback while prediction and gradients are immediately usable GPU arrays. The
immutable `sgd-step` update is composed from device elementwise multiply/subtract,
so parameter and gradient buffers are never downloaded. AdamW now follows the same
GPU-resident path: four learned-attention steps on Apple M4 verify every final
weight, first moment, variance, and the decreasing loss trajectory against CPU.
The same verifier runs Nesterov SGD with momentum and weight decay, comparing
every final projection weight, every momentum buffer, and the complete loss
trajectory against CPU without parameter readback during the update.
The Apple M4 verifier covers both the finite async update and an injected infinity:
the finite path advances AdamW and GradScaler, while overflow leaves weights and
optimizer state unchanged and halves the scale. Only scalar control flags cross the
device boundary.

Learned MultiheadAttention is verified on both JVM and compiled ClojureScript:
all eight projection tensors receive gradients, a Q-weight gradient matches a
central finite difference, identity projections match parameter-free attention,
and SGD lowers the deterministic fixture loss. Run the portable verifier with:

```sh
kbb -M:cljs-learned-attention-verify
node target/learned-attention-verify.cjs
```

Its forward and explicit-VJP paths are device-native on WebGPU/Metal: projection
GEMMs, last-axis bias broadcasts, fused multi-head attention, transposes, bias
reductions, MSE loss/VJP, and all eight parameter gradients stay in GPU buffers
until final verification readback. The Apple M4 check covers explicit VJP plus
ordinary MSE training, comparing prediction, input gradient, loss, and every
projection weight/bias gradient plus the separate context gradient against the CPU
backend. The fixture uses query length 3 and context length 2 with different padding
masks per batch. It then performs eight
public `sgd-step` iterations, checks the complete loss trajectory and all final
weights against CPU, and confirms loss decreases from `0.09691` to `0.06289`
while the independent `torch.core/run` inference result also matches (32/32 checks):

```sh
kbb -M:deno-metal-attention-verify
deno run --allow-all target/deno-metal-attention-verify.cjs
```

## State dicts and safetensors

`torch.state-dict/manifest` assigns stable PyTorch-style names such as
`layers.0.weight` and `layers.1.q_proj.weight`. Dense internal matrices use
`[in,out]` for `x @ W`; the checkpoint boundary automatically transposes them to
PyTorch `[out,in]`. Conv and normalization tensors already use standard layouts.

```clojure
(require '[torch.safetensors :as safe]
         '[torch.state-dict :as state])

(def external (state/state-dict model weights))
(def restored (state/load-state-dict model external))
(def loaded (safe/load-weights "model.safetensors" backend model))
```

The JVM reader validates the header length, every tensor byte window, dtype,
declared shape, missing names, and unexpected names before loading. Tensor payloads
remain on disk until requested, so a checkpoint is not materialized wholesale.
F32, F16, and BF16 checkpoints are decoded and uploaded as f32 by default for the
current attention kernels; `:dtype` can request another num storage dtype.

Large Hugging Face checkpoints may be passed as
`model.safetensors.index.json`. The loader opens each declared shard lazily,
confines shard filenames to the index directory, and rejects missing,
unexpected, duplicated, or incorrectly assigned tensors before allocating model
weights. `torch.huggingface/load-llama-resource` additionally reads a standard
Llama `config.json`, validates every HF tensor shape, converts linear matrices
from `[out,in]` to the engine's `[in,out]`, supports grouped-query attention and
tied embeddings, and constructs the complete runnable model:

```clojure
(require '[torch.huggingface :as hf])

(def resource
  (hf/load-llama-resource "config.json"
                          "model.safetensors.index.json"
                          backend
                          {:tokenizer-path "tokenizer.json"
                           :tokenizer-config-path "tokenizer_config.json"}))
```

The tokenizer loader supports the standard Llama byte-fallback BPE JSON:
contiguous vocabulary IDs, ordered merges, UTF-8 byte tokens, normalizer space
prefix/prepend semantics, TemplateProcessing BOS/EOS insertion, special-token
skipping, and decoder prefix stripping. It rejects unknown normalizers or
decoders instead of silently emitting IDs that differ from Transformers.

`torch.huggingface-resource` connects these artifacts to the bounded model
registry. Its descriptor accounts for the deduplicated byte total of config,
index, every shard, tokenizer, and tokenizer config; acquire loads once,
concurrent references share the resident resource, and release/expiry/eviction
destroys every distinct weight handle once. An optional engine factory receives
the complete model/tokenizer/weights resource for Ollama or OpenAI serving:

```clojure
(require '[torch.huggingface-resource :as hf-resource]
         '[torch.model-registry :as registry])

(def descriptor
  (hf-resource/descriptor
   "hf-llama" "config.json" "model.safetensors.index.json"
   {:tokenizer-path "tokenizer.json"
    :tokenizer-config-path "tokenizer_config.json"}))

(def callbacks (hf-resource/callbacks backend engine-fn))
(def models
  (-> (registry/registry (:size descriptor)
                         (:load-fn callbacks) (:unload-fn callbacks))
      (registry/register descriptor)))
```

The loader was also verified against a third-party, non-fixture checkpoint:

```sh
curl -L --fail -o /tmp/tiny-random-hf-llama-config.json \
  'https://huggingface.co/dacorvo/tiny-random-llama/resolve/main/config.json?download=true'
curl -L --fail -o /tmp/tiny-random-hf-llama.safetensors \
  'https://huggingface.co/dacorvo/tiny-random-llama/resolve/main/model.safetensors?download=true'
curl -L --fail -o /tmp/tiny-random-hf-llama-tokenizer.json \
  'https://huggingface.co/dacorvo/tiny-random-llama/resolve/main/tokenizer.json?download=true'
curl -L --fail -o /tmp/tiny-random-hf-llama-tokenizer-config.json \
  'https://huggingface.co/dacorvo/tiny-random-llama/resolve/main/tokenizer_config.json?download=true'

# model SHA-256: f2862981ba362b49503e463b4969a1d87496953a98858f4b0e1110bd13ab0a1c
kbb -M:public-safetensors-verify \
  /tmp/tiny-random-hf-llama-config.json \
  /tmp/tiny-random-hf-llama.safetensors \
  /tmp/tiny-random-hf-llama-tokenizer.json \
  /tmp/tiny-random-hf-llama-tokenizer-config.json
```

That public F32 model has one 128-wide Llama block and a 32,000-token
vocabulary. The verifier loads all 12 standard tensors and executes the complete
embedding → decoder → norm → LM-head graph, producing `[1,32000]` finite logits.
For `Hello, world! こんにちは`, it emits
`[1,15043,29892,3186,29991,29871,30589,30389,30353,30644,30449]`, exactly the
same IDs as Hugging Face `tokenizers` 0.21.4, and decodes them losslessly.
The public verifier then acquires this model through the registry, prefills
`Hi` into a real KV cache, greedily generates two tokens, releases the request,
expires the model, and asserts `loads=1`, `unloads=1`, `loaded-models=0`, and
`resident-bytes=0`.
Its weights are random; this proves format/layout/runtime compatibility, not
language quality.

### Hugging Face → Apple Metal serving

The JVM exporter converts the same safetensors resource into a portable
`TGBNDL1` v3 bundle. It streams tensor payloads through a temporary file and
atomically replaces the destination, so it does not retain a second complete
model payload in heap. Dense HF matrices are already transposed into the Metal
runtime's execution layout; tokenizer normalization/decoder options travel in
the manifest with the weights:

```sh
kbb -M:hf-bundle-export \
  /tmp/tiny-random-hf-llama-config.json \
  /tmp/tiny-random-hf-llama.safetensors \
  /tmp/tiny-random-hf-llama-tokenizer.json \
  /tmp/tiny-random-hf-llama-tokenizer-config.json \
  target/tiny-random-hf-llama-metal.tgb

# Full Llama CPU/Metal greedy parity and buffer release
kbb -M:deno-public-gguf-metal-verify
deno run --allow-all target/deno-public-gguf-metal-verify.cjs \
  target/tiny-random-hf-llama-metal.tgb

# Real Ollama streaming/non-streaming HTTP and cancellation
kbb -M:deno-public-gguf-ollama-verify
deno run --allow-all target/deno-public-gguf-ollama-verify.cjs \
  target/tiny-random-hf-llama-metal.tgb

# Resident registry, Ollama management/chat/embed, and OpenAI APIs
kbb -M:deno-public-gguf-registry-verify
deno run --allow-all target/deno-public-gguf-registry-verify.cjs \
  target/tiny-random-hf-llama-metal.tgb
```

On Apple M4 the 34,646,927-byte public HF bundle produced the same four greedy
tokens on CPU and Metal (`[22056,1092,8384,8375]`). Releasing weights and cache
retired 14 buffers / 33,457,664 bytes with no transient buffers left. The real
Ollama socket returned its first streamed response before completion, matched
streaming and non-streaming contexts, propagated disconnect cancellation, and
restored the GPU baseline. The registry suite additionally passed Ollama
generate/chat/embed/ps/show/copy/delete, OpenAI models/chat/embeddings, dynamic
residency tags, LRU eviction, exactly-once load/unload, and ended with both
registry resident bytes and GPU live bytes back at baseline. The historical
verifier alias names contain `gguf`, but the verifier itself is now portable and
driven by the v2/v3 bundle manifest.

### Native distributed inference and Intel Arc Pro B70

`torch.device-profile/serving-profile` now consumes num's measured physical
device hints and produces scheduler settings for latency, throughput, or
fallback service. This keeps B70 on one MTP-assisted latency slot, admits two
qualified Strix Halo throughput slots, and keeps Xavier as a one-slot CUDA
fallback whose maximum-power and locked-clock prerequisites remain explicit.

The serving runtime is no longer tied to Apple Metal. `torch.device-profile`
admits Intel Arc Pro B70 only after identifying PCI device `8086:e223`, rejects
software adapters such as llvmpipe, and selects the existing WGSL tensor kernels
through WebGPU/Vulkan. B70 collectives deliberately use host-staged transfer;
peer-to-peer GPU access is not assumed.

`torch.parallel` defines deterministic tensor- and pipeline-parallel rank/layer
plans, column/row sharding, gather/reduce semantics, and GPipe microbatch order.
`torch.parallel-tcp` carries bounded, versioned activation envelopes over a real
TCP rank boundary. This is the transport/execution contract for multiple nodes;
it does not yet overlap communication with compute or provide a production
failure/rejoin protocol.

`torch.speculative` implements greedy verification, stochastic rejection
sampling, and MTP-head drafting. A continuous engine configured with
`:speculative-step-fn` commits multiple verified tokens per scheduler turn on
both synchronous and Promise/WebGPU hosts while tracking drafted/accepted-token
metrics. The model-specific draft/target callback owns KV writes; no unverified
token is published. Greedy target verification also accepts device-selected
argmax token IDs, and MTP heads can draft directly from bounded device candidate
sets. `verify-stochastic-device` now consumes device-resident target/draft logits
and delegates full-distribution temperature-softmax acceptance plus positive-
residual sampling to `num`, returning one verified token decision in 8 bytes.
The model-specific callback still owns draft/target forward passes and KV writes.

The server builds as one self-contained x86-64 Linux executable. Build-time uses
ClojureScript and Deno, but the resulting process needs neither a JVM, Node, nor
a separately installed Deno runtime:

```sh
scripts/build-native-server.sh target/kotoba-infer
target/kotoba-infer --bundle model.tgb --model model:latest \
  --device intel-b70 --host 127.0.0.1 --port 11434
```

The narrow admission policy in `kotoba/infer_schedule_core.kotoba` compiles with
Amu to sealed KEXE (`scripts/build-native-policy.sh`). It owns bounded
concurrency/draft width, MTP head/full-offload admission, and the B70 PCI
identity; the build extracts both the scheduler and MTP admission symbols as
standalone native slices. General rank division remains
in the portable checked layer because integer division is not yet admitted by
the current Amu native subset; claiming otherwise would make KEXE and host
semantics diverge.

For a small JVM-free B70 qualification independent of model files:

```sh
scripts/build-native-b70-probe.sh target/kotoba-b70-probe
target/kotoba-b70-probe
```

The probe verifies PCI identity and executes an actual WGSL compute dispatch,
including GPU readback, rather than treating Vulkan enumeration as inference
readiness.

### Device-resident sampling evidence

The native resource keeps each single or fused-batch logits tensor on the GPU.
For `temperature=0` with repetition penalty 1, the continuous scheduler samples
through `num` row argmax. Greedy requests with repetition penalty and stochastic
requests with explicit `top-k <= 256` use device repetition penalty plus exact
top-k, followed by device temperature/top-p sampling. The limit is now 256 and
only the final 4-byte token ID crosses to the host. Requests without top-k and
with `top-p=1` now use the full-softmax device kernel with the same 4-byte
boundary. Exact unbounded nucleus policies with `top-p < 1` stable-sort the
complete vocabulary on device and retain the same 4-byte boundary for
vocabularies through 1,048,576.
Intermediate prefill logits, finished rows, and cancelled rows share explicit
reference-counted ownership.

```sh
kbb -M:deno-device-sampling-verify
deno run --allow-all target/deno-device-sampling-verify.cjs model.tgb
```

With `temperature=0.7`, `top-k=8`, `top-p=0.9`, and repetition penalty 1.2,
the public tiny Llama fixture produced the same IDs on Apple M4 and Intel Arc Pro
B70 (`[23639,27919,26381,7335]`). Four decode selections caused four readbacks
totaling 16 bytes, zero full-logits readback, and returned live GPU buffers to
baseline, including cancel-before-sample. On the B70, five native HTTP requests
measured 0.6394 seconds cold and 0.1256–0.1326 seconds warm for four tokens
(about 30.2–31.8 tok/s warm). This is a tiny public correctness fixture, not a
large-model throughput claim; it also does not prove that top-k selection is the
bottleneck at realistic model sizes.

The same fixture without top-k (`temperature=0.7`, `top-p=1`, repetition penalty
1.2) produced `[15988,16001,16005,16009]` on both adapters. The combined bounded
and full-softmax verification made eight 4-byte readbacks and no full-logits
readback. At vocabulary 262,144 the isolated full-softmax kernel median was
14.26 ms on M4 and 11.95 ms on B70. The final B70 native HTTP build measured
0.6291 seconds cold and 0.1231–0.1257 seconds warm for four tokens.

With exact unbounded nucleus (`top-k=nil`, `top-p=0.9`), the fixture produced
`[7119,2862,22514,30876]` on both adapters. At vocabulary 262,144 the isolated
stable-sort/nucleus median was 26.9 ms on M4 and 25.1 ms on B70, and the
production-size selected token matched an independent host sorting oracle. The
B70 native HTTP path measured 0.6616 seconds cold and 0.1625–0.1695 seconds warm
for four tokens (about 23.6–24.6 tok/s warm).

Remaining sampling maturity is explicit: exact nucleus above vocabulary
1,048,576 and top-k above 256 are not admitted, and stochastic speculative
rejection currently models temperature-softmax distributions without top-k,
top-p, or repetition transforms. The current device MTP surface covers bounded
draft selection and target verification, not a model-specific fused multi-head
forward kernel.

## Expert-aware NVMe streaming

`torch.expert-stream` opens an indexed model artifact once and serves
positional expert slices into direct buffers under `num.expert-cache`'s exact
byte ceiling. `prefetch!` uses a bounded executor and returns joinable futures,
so a Qwen4Exp decoder can overlap routing/attention with next-layer reads while
joining at the expert matmul boundary. The implementation is file-format
neutral: inference owns the tensor/expert index; torch owns file resources;
num owns cache policy.

```sh
kbb -M:test -n torch.expert-stream-test
```

## Test

```
kbb -X:test
```
