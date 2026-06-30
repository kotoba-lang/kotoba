# ADR: kotodama CLJC inference uses torch + num

Status: proposed

Date: 2026-06-29

## Context

kotodama needs a browser/local inference surface that can eventually run real
models through wasm, WGSL/WebGPU, and compatible WebGL hosts. The first design
accidentally described this surface in terms of JavaScript libraries such as
Transformers.js and ONNX Runtime Web. Those libraries are not part of the
kotoba-lang inference foundation.

The workspace already has the two reusable CLJC foundations:

- `kotoba-lang/torch`: neural network/module graphs as EDN data.
- `kotoba-lang/num`: tensor compute and the WGSL/WebGPU backend contract.

## Decision

`kotodama.inference` is a CLJC-first inference contract over `torch` and `num`.

- The model graph is carried as `:kotodama/model-graph` and is torch-clj data.
- Tensor execution is selected by `:kotodama/compute-backend`, using num-clj
  backend names such as `:num/wgsl`, `:num/webgpu`, `:num/webgl`, `:num/wasm`,
  or `:num/native`.
- `:torch-transformer` is the primary LLM runtime.
- ONNX and ONNX Runtime Web are not portable runtime contracts.
- Transformers.js is not a runtime foundation.
- Browser WebGPU uses the num WGSL/WebGPU backend contract.
- Browser WebGL is allowed only if a host supplies a num-compatible WebGL
  backend. It is not implemented by Rust `wgpu`.

## Consequences

The public Kotoba/Kototama inference vocabulary remains EDN and CLJC. Host
adapters implement the `IModelRuntime` port by lowering torch-clj transformer
graphs to num-clj tensor operations. Browser and terminal implementations should
share this path through `:num/wgsl`, `:num/webgpu`, `:num/wasm`, or compatible
num backends.
Gemma graphs are represented as an embedding layer followed by indexed
`:gemma4-block` layers, final RMSNorm, tied output projection, and logit
softcap, so hosts can lower whole transformer blocks while preserving layer
identity in EDN.

Real-model maturity now depends on filling the transformer execution path:

1. GGUF/tokenizer/model artifact loading,
2. torch-clj transformer graph coverage,
3. lowering transformer ops to num-clj tensor ops,
4. live browser WebGPU and compatible WebGL host bindings,
5. parity tests against CPU/native references.

Live local-model checks may use Ollama with `gemma4:e4b` to prove the
`IModelRuntime` generation boundary reaches a real model. The check verifies
the local model identity and digest before generation. That check is operational
evidence only; it does not change the runtime foundation. A separate
`verify-gguf` gate resolves the same local model to its GGUF blob and reads the
artifact header, metadata, and tensor directory directly, proving that kotodama
can inspect the real Gemma 4 E4B model artifact, required weight shapes,
payload byte windows, and F32 weight samples without calling a model server.
The same gate now also decodes real Q4_K blocks from attention/MLP weights and
real Q6_K blocks from attention/token embedding weights into floating point
values using the GGML block layouts, so the direct path has moved past byte
inspection for the main quantized tensor classes used by this artifact. A companion
`verify-gemma-num` gate uploads those decoded real-model blocks into num-clj
NDArrays, decodes the BOS token embedding row from `token_embd.weight`, and
checks the resulting num tensor summaries through num reductions. The same gate
also applies Gemma RMSNorm with `blk.0.attn_norm.weight` to that BOS embedding,
decodes real rows from `blk.0.attn_q.weight`, `blk.0.attn_k.weight`, and
`blk.0.attn_v.weight`, and executes partial Q/K/V projections through
`num/dot`. It also verifies the real GGUF RoPE metadata and applies partial
Q/K RoPE for position 1 through the CLJC op. The same gate now materializes
head 0 Q/K/V values and verifies the single-token GQA attention boundary. It
also materializes all 8 Q heads over the 2 KV heads for the same single-token
case, verifies the GQA head-to-KV mapping, and projects the all-head attention
vector through the real output projection. The same verifier now evaluates a
two-token causal GQA path for token ids `[2 1]`, proving that the second query
can attend over the visible KV boundary with softmax weights.
It also projects that single-token attention output through real
`blk.0.attn_output.weight` rows, including a full-width 2560-row output
projection for the head0-only single-token attention vector. It also applies
`output_norm.weight` to the real BOS embedding, evaluates candidate logits
through the tied `token_embd.weight` output head, streams the full
262144-token tied embedding output head, and performs deterministic greedy/top-k
selection. The same gate now applies `blk.0.ffn_norm.weight`,
projects through real `blk.0.ffn_gate.weight` and `blk.0.ffn_up.weight` rows,
applies SiLU gating, and projects that partial activation through real
`blk.0.ffn_down.weight` rows. With `KOTODAMA_VERIFY_FULL_MLP=1`, the required
local-model gate now expands that same path to the full blk.0 MLP: all 10240
gate/up rows, full SiLU-gated activation, and all 2560 down-projection output
rows. It also composes the first Gemma transformer block for the BOS token:
all-head attention output residual, post-attention FFN RMSNorm, full gated MLP,
final residual block output, output RMSNorm, and candidate tied-embedding logits.
The same verifier now has a reusable single-token block composer and verifies
two-block composition through `blk.0 -> blk.1`, including the second block's
attention, output projection, residuals, FFN, output norm, and candidate logits.
It also binds that composer behind `torch/run` for indexed `:gemma4-block`
layers and verifies that the real GGUF `blk.0 -> blk.1` contract is satisfied
through the torch graph runner, not only through a hand-written verifier loop.
Finally, the verifier exposes a verification-only `IModelRuntime` adapter and
checks that `core/forward` can cross the normal runtime port, execute the same
real GGUF two-block `torch/run` path, and return deterministic candidate logits.
The adapter now keeps a per-session forward cache keyed by token ids and layer
count, and the verifier proves the second identical `core/forward` call is a
cache hit while preserving the same logits. The full block expected summaries
for `blk.0` and `blk.1` are now derived from that cached `core/forward` block
result instead of recomputing `blk.1` through a separate verifier loop.
Full 42-layer composition and generation through `torch` to `num` remain the
next maturity step.

`verify/maturity.edn` is the machine-readable coverage gate for this ADR. It
tracks required CLJC/Rust/num/torch/WebGPU/gemma4 checks and keeps known gaps
explicit until real browser WebGPU token generation lands on `num`.
`clojure -M:verify-maturity-run` executes the required non-model gates, while
`clojure -M:verify-maturity-run --include-local-model` also runs `gemma4:e4b`.
`clojure -M:verify-gguf` verifies the local GGUF artifact metadata, tensor
directory, tensor byte windows, F32 payload samples, Q4_K attention/MLP
dequantization samples, and Q6_K attention/token embedding dequantization
samples for `gemma4:e4b`, including the RoPE dimension/frequency metadata.
`clojure -M:verify-gemma-num` verifies that the same decoded quantized blocks
can be uploaded into num-clj tensors, that the BOS token embedding row can be
looked up from the real GGUF tensor, that `blk.0.attn_norm.weight` can be
applied as Gemma RMSNorm, and that partial Q/K/V projections for
`blk.0.attn_{q,k,v}.weight`, partial Q/K RoPE, head 0 Q/K/V materialization,
single-token GQA attention, and `blk.0.attn_output.weight` projection,
including a full-width head0-only output projection, can be evaluated on the
num CPU backend. It also verifies output RMSNorm, tied-embedding candidate and
full-vocabulary logits, greedy/top-k sampling, FFN RMSNorm, partial gated MLP projection,
SiLU gated activation, and partial FFN down projection on the same real GGUF
weights. `KOTODAMA_VERIFY_FULL_MLP=1 clojure -M:verify-gemma-num` additionally
verifies the fixed full blk.0 MLP contract and the composed blk.0 block output
contract on the same real GGUF weights.
`KOTODAMA_VERIFY_FULL_MLP=1 KOTODAMA_VERIFY_FULL_LAYERS=2 clojure -M:verify-gemma-num`
also verifies the reusable block composer across `blk.0 -> blk.1`, and checks
the same real two-block contract through `torch/run` over indexed
`:gemma4-block` layers and through `core/forward` over the `IModelRuntime` port,
including the session forward cache hit on a repeated call.
`clojure -M:verify-torch-num` is the minimal proof that a torch-clj graph can be
executed through a host backend that lowers layers to num-clj tensor ops; it
now also runs a two-layer `:gemma4-block` graph through a custom num-backed host
runner to prove the graph-level handoff for block composition.
