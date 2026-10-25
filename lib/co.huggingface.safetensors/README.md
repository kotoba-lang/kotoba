# kotoba-lang/org-huggingface-safetensors

[![CI](https://github.com/kotoba-lang/org-huggingface-safetensors/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-huggingface-safetensors/actions/workflows/ci.yml)

A pure `.cljc`, zero-dependency reader/writer for HuggingFace's
[**safetensors**](https://github.com/huggingface/safetensors) tensor-weight format.

Built for **ADR-2607051400** (`kotoba-lang` ML execution stack — N-D tensor engine, live
Metal/WebGPU backend, weight loading, kernels), **Phase 3 — "Weight loading (safetensors
reader)"**. This org's actual target models (TRELLIS, Hunyuan3D-2/2.1, UniRig) are all
CUDA-first research repos published on HuggingFace, and safetensors is what HuggingFace ships
those checkpoints as by default — it exists specifically to avoid the arbitrary-code-execution
risk of PyTorch's default pickle format. This repo reads that real format; it deliberately does
**not**, and never will, support pickle.

## Naming

This repo follows the reverse-domain `org-<vendor>-<spec>` naming rule ADR-2607041500 just
established for this org's external-spec `.cljc` libraries (`org-khronos-gltf`,
`org-khronos-glb`, `org-materialx`, `org-openusd`). safetensors is a HuggingFace-authored format
(`github.com/huggingface/safetensors`) without its own dedicated top-level domain the way
`materialx.org`/`openusd.org` have — so `org-huggingface-safetensors` follows the
vendor-prefixed variant of that pattern (`org-khronos-gltf` = standards-body + format name),
rather than the bare `org-materialx`/`org-openusd` variant (format name *is* the domain). If this
org later decides plain `kotoba-lang/safetensors` reads better (there's no name collision either
way — both were free at the time this repo was created), that's a mechanical GitHub rename +
`path-overrides` entry, same recipe as the `usd`→`org-openusd` rename and the
`kenchi-actor`→`kenchi-clj` rename before it.

## What this is (and isn't)

- Reads/writes the real safetensors byte layout: an 8-byte little-endian header-length prefix, a
  UTF-8 JSON header (tensor name → `{dtype, shape, data_offsets}`, plus an optional
  `__metadata__` string→string map), then the raw contiguous little-endian tensor data.
- **No pickle support, ever** — that's the entire point of the format existing.
- No memory-mapping / lazy loading — `read-bytes` decodes every tensor into a full in-memory host
  array up front. Real "load only the tensors you need" lazy access (useful for the
  multi-GPU-shard use case the spec's own README calls out) is a fast-follow, not implemented
  here.
- The JSON codec (`safetensors.json`) and the IEEE-754 bit-level codecs (`safetensors.dtype`) are
  hand-written and dependency-free — the same "small, zero-dep, from-scratch text/byte format"
  approach `kotoba-lang/org-openusd`'s USDA reader already established for this org's external
  format libraries (ADR-2607041500 precedent), rather than pulling in a JSON library.

## API

```clojure
(require '[safetensors.core :as st])

;; from a file
(st/read-file "model.safetensors")
;; => {:metadata {"format" "pt", ...}      ;; or nil if the file has no __metadata__
;;     :tensors  {"layer.0.weight" {:dtype :f32 :shape [768 768] :data #<double[]>}
;;                "layer.0.bias"   {:dtype :f32 :shape [768]     :data #<double[]>}
;;                ...}}

;; from bytes you already have (e.g. fetched over HTTP) — `read-file` is just this + file I/O
(st/read-bytes some-byte-array)

;; writing (used internally to build this repo's own round-trip test fixtures; also useful for
;; producing safetensors files from kotoba-lang-computed tensors)
(st/write-bytes {:metadata {"note" "hello"}
                  :tensors {"w" {:dtype :f32 :shape [2] :data [1.0 2.0]}}})
(st/write-file "out.safetensors" {...})
```

`read-bytes`/`read-file` accept a JVM `byte[]` or (best-effort, host-dependent) a
ClojureScript/JS `Uint8Array`. `write-bytes`/`write-file`'s `:tensors` values accept any
seq/array of numbers (or booleans for `:bool`) — not just this repo's own decoded output — so you
can hand it plain Clojure vectors.

### Return shape: plain maps, not `kotoba-lang/num` tensors — by design, not by omission

`ADR-2607051400`'s Phase 1 (a shape-aware N-D tensor type for `kotoba-lang/num`, with
broadcasting/reshape/axis-reductions) is **designed but not yet landed** as of when this repo was
built (`num`'s `src/num/` has `array.cljc`/`cpu.cljc`/`wgsl_backend.cljc`/`sparse.cljc` — dense
1D/2D vector-and-matrix ops and CSR sparse matvec — but no `tensor.cljc` or any N-D/shape-aware
type; checked directly against `orgs/kotoba-lang/num`'s tree, not assumed).

So `:data` here is a plain host numeric array, not a `num` tensor — returning a fake/partial `num`
integration that doesn't actually exist would be exactly the kind of overclaiming
ADR-2607051400 itself explicitly warns against. Wiring `read-bytes`'s `:tensors` map into real
`num` N-D tensors (once Phase 1 lands) is the natural fast-follow this repo is deliberately
shaped for: `:shape` is already a plain vector and `:data` is already a flat array in the
row-major order a `num` tensor constructor would want, so that integration should be a thin
adapter function, not a rewrite.

## Dtype support

| safetensors label | keyword | bytes/elem | decoded Clojure array type | notes |
|---|---|---|---|---|
| `BOOL` | `:bool` | 1 | `boolean-array` | |
| `I8`   | `:i8`   | 1 | `long-array` | sign-extended |
| `U8`   | `:u8`   | 1 | `long-array` | |
| `I16`  | `:i16`  | 2 | `long-array` | |
| `U16`  | `:u16`  | 2 | `long-array` | |
| `F16`  | `:f16`  | 2 | `double-array` | real IEEE 754 binary16 bit-level decode (1/5/10 sign/exp/mantissa, bias 15) |
| `BF16` | `:bf16` | 2 | `double-array` | real bfloat16 bit-level decode (1/8/7, bias 127 — top 16 bits of an F32, **not** the same layout as F16) |
| `I32`  | `:i32`  | 4 | `long-array` | |
| `U32`  | `:u32`  | 4 | `long-array` | |
| `F32`  | `:f32`  | 4 | `double-array` | real IEEE 754 binary32 decode (1/8/23, bias 127) |
| `C64`  | `:c64`  | 8 | `double-array` | interleaved `[re0 im0 re1 im1 ...]`, each part an F32 |
| `F64`  | `:f64`  | 8 | `double-array` | real IEEE 754 binary64 decode (1/11/52, bias 1023) |
| `I64`  | `:i64`  | 8 | `long-array` | exact for the full signed 64-bit range on JVM |
| `U64`  | `:u64`  | 8 | `long-array` | exact for values `< 2^63`; values `>= 2^63` don't fit a signed `long` — a documented limitation, not silently wrong (real model weights essentially never use unsigned 64-bit values anywhere near that range) |
| `F4`, `F6_E2M3`, `F6_E3M2`, `F8_E5M2`, `F8_E4M3`, `F8_E8M0`, `F8_E4M3FNUZ`, `F8_E5M2FNUZ` | — | — | **not supported** | real dtypes in the current spec (sub-byte/microscaling and 8-bit float formats) — `label->dtype` raises a clear "known but not yet supported" error, distinct from an unknown/invalid dtype string. The spec's own README calls sub-1-byte dtypes out as "alignment tricky" / needing "non traditional APIs"; out of scope for this pass. F32/F16/BF16 (this repo's primary target) and F64/I64/I32/I8/U8/BOOL cover everything TRELLIS/Hunyuan3D-2/UniRig checkpoints actually use. |

**F16 vs BF16 — the classic bug this dtype table exists to prevent:** both are 16 bits wide, but
F16 is 1 sign / 5 exponent / 10 mantissa bits (bias 15) while BF16 is 1 sign / 8 exponent / 7
mantissa bits (bias 127, i.e. exactly an F32's top 16 bits with the mantissa truncated).
Conflating them silently produces wildly wrong magnitudes — BF16's exponent range matches F32's
(~1e38 max) while F16's is much narrower (65504 max). `safetensors.dtype` implements both from
their real, independently-looked-up layouts (see its docstring for the exact spec citations) and
`dtype_test.clj`'s `f16-and-bf16-are-not-the-same-layout` test pins that they actually diverge.

### Portability note (`.cljc`, JVM-verified this pass)

The JSON codec and the F16/F32/BF16 bit-level math are pure arithmetic (`+`/`*`/`mod`/`quot`,
plus `bit-and`/`bit-shift-right` only ever on values already known to fit in 31 bits) with no
`#?(:clj/:cljs)` branching at all — that code should compile and run identically under
ClojureScript. The genuinely host-specific seam is isolated to `safetensors.bytes` (byte-array
type, UTF-8 encode/decode, file I/O) plus a couple of `long`-coercion calls in `safetensors.core`
needed to satisfy JVM `aset` on primitive arrays for I64/U64 values. This repo's own test suite
runs under Clojure/JVM (`kbb -M:test`); ClojureScript compilation is not yet exercised in CI
— a fast-follow if/when this repo needs a cljs/Deno consumer (per ADR-2607051400 Phase 2's Deno
target), not claimed as done today.

## Testing

Three independent layers, specifically so a symmetric bug in this repo's own writer and reader
can't hide behind a passing test suite:

1. **Hand-built bytes, independent of this repo's own writer** (`core_test.clj`,
   `hand-built-bytes-decode-correctly`): a safetensors byte buffer assembled from a literal JSON
   header string and literal IEEE-754 bit patterns (`1.0f = 0x3F800000`, `2.0f = 0x40000000`,
   `42i32 = 0x0000002A`), decoded with `read-bytes` and checked against independently-known
   values — `safetensors.core/write-bytes` is never called in this test.
2. **Own writer → own reader round-trip** (`own-writer-round-trip-all-supported-dtypes`): every
   supported dtype, values chosen to be exactly representable in each target format so equality
   is a meaningful check rather than an accidental rounding coincidence.
3. **A real, small, publicly-published safetensors file**
   (`real-huggingface-fixture-parses-correctly`): `hf-internal-testing/tiny-random-bert`'s
   `model.safetensors` (~508KB, 100 tensors, fetched from huggingface.co — vendored at
   `test/resources/tiny-bert.safetensors` so CI doesn't depend on network access), checked
   against facts independently confirmed with **Python** (`struct.unpack` + `json.loads` +
   `array`) before this test was written: exact tensor count, the real `__metadata__` map
   (`{"format": "pt", "cls.predictions.decoder.bias": "cls.predictions.bias"}` — yes, real
   PyTorch-saved safetensors files can have non-`"format"` keys in `__metadata__`, since the spec
   only requires string→string), the dtypes actually used (`{F32, I64}`), specific tensors'
   shapes, and that `bert.embeddings.position_ids` decodes to the standard BERT
   `arange(0, 512)` buffer.

Plus `dtype_test.clj`'s **F16/BF16 bit-level reference-value tests**, pulled independently from
the Wikipedia half-precision/bfloat16 pages (not derived from this repo's own encoder):

| bits | format | expected | note |
|---|---|---|---|
| `0x3C00` | F16 | `1.0` | |
| `0xC000` | F16 | `-2.0` | |
| `0x7BFF` | F16 | `65504.0` | largest finite F16 |
| `0x0001` | F16 | `2^-24` | smallest positive subnormal |
| `0x03FF` | F16 | `1023 * 2^-24` | largest subnormal |
| `0x3555` | F16 | `0.333251953125` | closest F16 value to 1/3 |
| `0x3F80` | BF16 | `1.0` | |
| `0x4000` | BF16 | `2.0` | |
| `0x4049` | BF16 | `3.140625` | π truncated to BF16 |

Run: `kbb -M:test`.

## Provenance

Built 2026-07-05 for ADR-2607051400 (`com-junkawasaki/root`) Phase 3. Format grounded directly
against `github.com/huggingface/safetensors`'s README and `safetensors/src/tensor.rs` (the real
`Dtype` enum and `bitsize()` table), not guessed.
