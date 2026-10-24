# num-clj (数)

[![CI](https://github.com/kotoba-lang/num/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/num/actions/workflows/ci.yml)

A **GPU-accelerated numerical compute library** for Clojure — BLAS-level dense and
sparse linear algebra (the NumPy/cuBLAS layer) with a **portable contract + injected
backends** so the *same* program runs on a pure-Clojure CPU, a WebGPU compute pipeline
in a browser tab, or cuBLAS on an H100. The core (array type, op protocol, CPU reference
backend, public API) is **zero-dependency, all `.cljc`** — it runs on JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM. GPU backends carry the native code and are
**host-injected** behind one protocol; the core never pulls a toolchain.

Sibling of [kudaki-clj](https://github.com/com-junkawasaki/kudaki-clj) (explicit FEA) and
[nagare-clj](https://github.com/com-junkawasaki/nagare-clj) (finite-volume CFD): those
zero-dep solvers express their hot loops (Krylov `SpMV`/`AXPY`, element `GEMM`) and, by
**injecting a num-clj GPU backend**, run on the GPU *without changing the portable
kernel* — the same way the design actor swaps a Store or an Advisor. Fits the wgpu/WebGPU
line of [kami-webgpu](https://github.com/com-junkawasaki/kami-webgpu) (declarative render)
and [kami-engine](https://github.com/com-junkawasaki/kami-engine) — num-clj is the GPU
**compute** half they lacked.

## Why a contract + injected backends (the whole idea)

One seam — `num.protocol/IBackend` — is all that separates "where the math runs" from
"what the math is". A `handle` is an opaque buffer: a `double-array` on CPU, a `GPUBuffer`
on WebGPU, a device pointer on CUDA. The array layer only moves handles through the
protocol, so:

```
num.core/matmul, spmv, axpy! …        ← one portable program (your code)
        │  dispatches through
        ▼
num.protocol/IBackend                 ← the ONE seam
        ├── num.cpu     (pure .cljc, zero-dep)      the ORACLE / fallback
        ├── num.wgsl    (WGSL compute via wgpu)     PORTABLE PRIMARY
        ├── :cuda       (cuBLAS / cuSPARSE)         NVIDIA fast path
        ├── :metal      (Metal Performance Shaders) Apple fast path
        └── :rocm       (rocBLAS / hipSPARSE)       AMD fast path
```

This is the same injection pattern as `MemStore ‖ DatomicStore` and the `cae-solver`
`[:solver :kind]` dispatch used across com-junkawasaki.

## "Optimized for each GPU" — without three vendor kernels

`num.device-profile` turns public PCI/architecture information into portable,
measured execution hints for the current Murakumo accelerators: Arc Pro B70
(SYCL + native MTP), Radeon 8060S/Strix Halo (Vulkan + two-slot throughput),
and Jetson AGX Xavier (CUDA fallback). Callers choose `:latency`, `:throughput`,
or `:fallback`; unknown devices fail closed to a single CPU slot. The profile is
data, so a host benchmark can override it without placing driver calls in num's
portable core.

The **primary** GPU backend is **WGSL compute via WebGPU/wgpu**. You write a compute
shader once (`num.wgsl`), and wgpu compiles it to each GPU's native ISA:

| Target | wgpu lowers WGSL to | Reaches |
|---|---|---|
| Apple | **Metal MSL** | M-series / AMD on macOS |
| Vulkan | **SPIR-V** | AMD (ROCm-class), NVIDIA, Intel, Linux |
| D3D12 | **DXIL** | Windows NVIDIA/AMD/Intel |
| Browser | **WebGPU** | any GPU, in a tab |

So one shader source is **per-GPU-optimized by the driver**. The shipped kernels
(`num.wgsl`) include a **16×16 shared-memory-tiled GEMM** (the canonical optimized GPU
kernel, ~16× less global traffic), a **scalar-CSR SpMV**, **AXPY**, and a **tree
reduction**. When raw vendor throughput matters, the optional `:cuda` / `:metal` /
`:rocm` backends drop cuBLAS / MPS / rocBLAS in behind the *same* `IBackend` — opt-in,
JVM/native only, never required.

## API (`num.core`, on `num.array` values)

```clojure
(require '[num.cpu :as cpu] '[num.array :as a] '[num.core :as nm] '[num.sparse :as sp])
(def b (cpu/cpu-backend))               ; swap for a GPU backend; nothing else changes

(def A (a/from-vec b [1 2 3 4] [2 2]))  ; 2×2
(def x (a/from-vec b [1 1] [2]))
(a/->vec (nm/matvec A x))               ;=> [3.0 7.0]
(nm/dot x x)                            ;=> 2.0
(a/->vec (nm/matmul A A))               ;=> [7.0 10.0 15.0 22.0]

(def K (sp/dense->csr 2 3 [1 0 2  0 3 0]))
(a/->vec (nm/spmv b K x))               ;=> [3.0 3.0]   (sparse A·x)
```

### Physical f16/bf16 storage

`from-vec` and `zeros` accept an optional dtype, and `cast` materializes a new
buffer rather than attaching a cosmetic label:

```clojure
(def half (a/from-vec b [0.1 0.2 0.3 0.4] [2 2] :f16))
(def brain (a/cast half :bf16))
(:dtype half)                              ;=> :f16
(a/->vec half)                             ; quantized host values
```

The CPU oracle stores f16/bf16 in real two-byte elements and implements typed
elementwise operations, activations, and GEMM with f32 accumulation followed by
output quantization. IEEE subnormals, infinities, NaNs, and round-to-nearest-even
are covered by tests on JVM and the core compiles and runs under ClojureScript.
The Deno/WebGPU→Metal backend also has real packed-f16 buffers and typed add,
sub, mul, div, unary activation, GEMM, grouped NCHW convolution, and GroupNorm
kernels. Because Deno's current Naga
rejects WGSL's advertised `enable f16`, those kernels use two IEEE halves per
`u32`, `unpack2x16float`/`pack2x16float`, and f32 evaluation/accumulation. Apple
M4 Metal verification proves four values occupy eight GPU bytes and matches the
CPU half oracle across all six kernel checks. This is physical half storage with quantized operation
boundaries, not a claim of native f16 ALU throughput; BF16 GPU kernels and typed
upsample/cat and BF16 GPU kernels remain open.

```sh
kbb -M:deno-dtype-verify
deno run --allow-all target/deno-gpu-dtype-verify.cjs
# Apple M4: physical bytes 8; Metal f16 6/6 passed
```

Ops: `axpy! scal! dot nrm2 add sub mul div sum amax amin matvec matmul spmv`.

## N-D tensors (`num.tensor`, ADR-2607051400 §Phase 1)

`num.core` above is deliberately 1-D-vector/2-D-matrix only (BLAS-shaped). `num.tensor`
sits on top and adds a real, arbitrary-rank, shape-aware layer: broadcasting, shape
manipulation, axis reductions, and batched matmul. It **extends `num.array/NDArray`**
rather than introducing a new type — `NDArray` is already `{:backend :handle :shape}`
with an arbitrary-length `shape` vector, and `nelems`/`from-vec`/`->vec` already work for
rank 0 (scalar) through arbitrary rank with no changes; what was missing was the
*operations*, not the type. `num.core` itself is untouched — same fast, non-broadcasting,
direct-to-`IBackend` dispatch as before, zero behavior change.

```clojure
(require '[num.cpu :as cpu] '[num.array :as a] '[num.tensor :as t])
(def b (cpu/cpu-backend))

;; broadcasting (NumPy-style: align from the trailing dim, size-1 stretches)
(def col (a/from-vec b [1 2 3] [3 1]))
(def row (a/from-vec b [10 20 30 40] [1 4]))
(a/->vec (t/add col row))                 ;=> [3 4] outer-sum, row i + col j per cell
(t/broadcast-shapes [3 4] [2 1 4])        ;=> [2 3 4]
(t/broadcast-shapes [2 3] [2 4])          ;=> throws (incompatible, non-1 mismatch)

;; reshape / transpose / squeeze / unsqueeze (data-preserving)
(def m (a/from-vec b (range 1 7) [2 3]))  ; [[1 2 3][4 5 6]]
(:shape (t/reshape m [3 2]))              ;=> [3 2]              (zero-copy relabel)
(a/->vec (t/transpose m))                 ;=> [1 4 2 5 3 6]      ([3 2], real data move)
(:shape (t/squeeze (a/from-vec b [1] [1 1 1])))    ;=> []
(:shape (t/unsqueeze m 0))                ;=> [1 2 3]

;; axis-parameterized reductions (nil axis = reduce everything; NumPy keepdims convention)
(a/->vec (t/sum m 0))                     ;=> [5 7 9]            (down columns)
(a/->vec (t/sum m 1))                     ;=> [6 15]             (across rows)
(:shape (t/sum m 1 {:keepdims? true}))    ;=> [2 1]
(a/->vec (t/mean m 0))                    ;=> [2.5 3.5 4.5]
(a/->scalar (t/amax m))                   ;=> 6.0                (full reduction)

;; batched matmul: last two dims are the matrix dims, leading dims broadcast
(def A (a/from-vec b (range 1 13) [2 2 3]))   ; 2 batches of 2×3
(def B (a/from-vec b (range 1 13) [2 3 2]))   ; 2 batches of 3×2
(:shape (t/matmul A B))                   ;=> [2 2 2]

;; production-shaped convolution: NCHW input, OIHW weights
(def image (a/from-vec b (range (* 2 4 32 32)) [2 4 32 32]))
(def weight (a/from-vec b (repeat (* 320 4 3 3) 0.01) [320 4 3 3]))
(:shape (t/conv2d-nchw image weight nil {:padding 1})) ;=> [2 320 32 32]
```

`conv2d-nchw` follows the PyTorch/ComfyUI tensor convention and supports
batching, multiple input/output channels, bias, scalar or pair
`stride`/`padding`/`dilation`, groups, and depthwise convolution. Its autograd
twin `num.autograd/conv2d-nchw*` propagates gradients to input, weight, and
bias under the same options; grouped padding+stride gradients are checked
element-by-element against central finite differences. This removes the
single-image/single-channel convolution fence for real UNet graphs. WGSL
backends now implement it device-native through the optional `ITensorBackend`
protocol; the same kernel covers batches, bias, groups/depthwise, stride,
padding, and dilation. For ungrouped convolution with output channels divisible
by four, a specialized kernel reuses each input load and coordinate calculation
across four output-channel accumulators; all other shapes retain the general
kernel. A 2×4×16×16 grouped fixture plus a depthwise+dilated
fixture pass against the CPU oracle on Apple M4 Metal. Other backends retain
the portable host implementation.

The same NCHW layer also includes the other structural UNet/VAE primitives:
`silu`, PyTorch-compatible biased-variance `group-norm-nchw`, `cat` for skip
connections, integer `upsample-nearest2d`, contiguous `slice-axis`, and
`pad-right-bottom-nchw` for Diffusers AutoencoderKL downsampling. Their forward
values and shape validation are hand-checked. SiLU dispatches through one device-native unary
WGSL kernel, GroupNorm uses one 256-thread reduction workgroup per normalization
group, nearest upsampling maps one thread per output, and `cat` uses queue-ordered
device-to-device slice dispatches. None requires tensor host readback. A complete
`GroupNorm → SiLU → upsample → skip cat` chain plus slicing and asymmetric
padding are verified against the CPU oracle on Apple M4 Metal. None of these
paths downloads intermediate tensors.
Packed F16 nearest upsampling and contiguous slicing also execute directly over
physical half buffers, including odd logical element counts and unaligned slice
offsets; uploads pad only the final storage word without changing tensor shape.
Immutable scalar scaling stays packed F16, while the terminal NCHW F16 to NHWC
f32 RGB conversion performs layout, range conversion, and unpacking in one
dispatch instead of allocating a full intermediate f32 tensor.
Rank-1 through rank-4 transpose, last-axis bias broadcasting, and fused
multi-head attention also have packed-F16 paths. Attention evaluates dot
products, scaling, and stable softmax in f32 registers and stores the result in
physical F16; the current typed kernel supports causal/unmasked execution while
the f32 kernel retains key-padding-mask support.
`num.autograd/cast*` records physical dtype conversion on the reverse-mode tape;
its VJP converts the upstream gradient back to the input dtype. Typed MSE
backward likewise preserves prediction storage and uses immutable typed scale,
allowing stable f32 subgraphs to sit inside an F16 training graph without
severing gradients.
On the Deno Metal backend, packed-F16 attention backward remains GPU-resident:
Q/K/V and upstream gradients are expanded by device kernels, the existing fused
f32 stable-softmax VJP computes conflict-free Q/K/V gradients, and cast kernels
return them to the typed graph. No tensor is downloaded; the implementation
reuses the same backward equations as the independently checked f32 path.
Typed projection bias backward likewise keeps the upstream tensor packed while
casting only its row reduction to the device's f32 `sum-rows` stability path.
Packed-F16 RMSNorm backward computes one pair of f32 row statistics, then emits
an F16 activation VJP and a conflict-free f32 affine-weight VJP entirely on the
device. SiLU backward is composed from typed elementwise kernels without host
materialization, completing the normalization and SwiGLU boundaries used by
Llama training.
Packed-F16 embedding backward assigns one invocation to each table element and
gathers all matching token positions into an f32 gradient. Repeated IDs are
therefore deterministic and race-free without atomics or host scatter-adds,
which closes the token-to-transformer training boundary for complete LMs.
`cross-entropy-loss*` accepts integer labels shaped like the logits without the
last class axis, supports `ignore-index`, uses max-subtracted softmax, and means
over valid rows. Its Metal path keeps per-row f32 statistics and scalar loss on
device and returns a packed-F16 logit VJP scaled by the upstream GradScaler seed.
`scale` provides an immutable device-native scalar multiply by combining a
device-to-device copy with the backend BLAS scale kernel.
`group-norm-silu-nchw` fuses the ubiquitous diffusion ResNet
`GroupNorm → SiLU` pair into one reduction/normalization kernel and one output
buffer. Packed F16 uses the same one-workgroup-per-group reduction strategy and
falls back to the scalar reference kernel only when an odd group size would
make a packed word straddle normalization groups.

Long-running graphs can explicitly end tensor lifetimes with
`num.array/release!`; `release-all!` deduplicates reshape/transpose aliases that
share one backing handle. Deno/WebGPU maps this to `GPUBuffer.destroy()`, while
GC-owned CPU storage treats it as a no-op. A released NDArray must never be used
again; model runtimes remain responsible for liveness/ownership scheduling.
`silu*` and `group-norm-nchw*` provide the
corresponding training path; GroupNorm propagates input plus affine weight/bias
gradients and the composed GroupNorm→SiLU chain is checked against central
finite differences. `cat*` and `upsample-nearest2d*` complete the skip-path
training graph; a branched upsample+channel-concat+SiLU loss matches central
finite differences for both source tensors.

Transformer forward execution now has two further device-native operations:
rank-1 last-axis bias broadcasting and fused rank-2/rank-3 multi-head attention.
The attention kernel accepts batches and different query/key sequence lengths,
performs stable per-head softmax, and emits concatenated heads without materializing
transpose, batched-matmul, or probability tensors on the host. `:causal?` and a
PyTorch-semantics `[batch,seqK]` key-padding mask apply in both forward and backward.
Both kernels match the CPU
oracle on Apple M4 Metal and allow learned Q/K/V/output projection attention to
remain GPU-resident through its complete forward pass. Its fused backward kernel
recomputes the stable softmax on-device and returns gradients for Q, K, and V;
`num.autograd/multi-head-attention*` selects that kernel automatically for an f32
`ITensorBackend`. A two-head cross-attention fixture (`seqQ=2`, `seqK=3`) verifies
forward plus all three gradients against the independently decomposed CPU autograd
graph on real Apple M4 Metal. A second graph adds learned Q/K/V/output matrices and
all four biases, exercising device-native GEMM, 2-D transpose, row reduction, fused
attention backward, shared-input gradient accumulation, and a device-resident MSE
loss reduction/VJP. Immutable SGD and fused AdamW updates allocate new GPU buffers
while leaving source parameters and optimizer slots unchanged. AdamW updates the
parameter, first moment, and variance in one dispatch with bias correction and
decoupled weight decay; nil first-step slots are zero-allocated on-device. A fused
unscale kernel simultaneously removes the loss scale and atomically reports NaN or
infinity through a one-element flag, leaving the full gradient on-device. Together,
loss, output, all gradients, and all
eight updated projection tensors plus batched causal+padding output/Q/K/V gradients
pass 27/27 checks without intermediate host
readback. Only final verification values are downloaded.

Autoregressive serving can keep K/V in a bounded physical block pool instead
of one contiguous allocation per sequence. `num.deno-gpu/paged-kv-write!`
writes one projected token directly to a `[block,offset]` slot;
`paged-kv-copy-block!` copies only the used prefix when a shared partial block
becomes copy-on-write; and `paged-gqa-attention` resolves a logical f32 block
table inside the Metal kernel while performing stable one-token grouped-query
attention. A live Apple M4 verifier uses the deliberately non-contiguous table
`[2,0]`, compares its result with ordinary CPU GQA, forks a one-token prefix
into another physical block, writes a divergent token, checks that result
independently, and returns every tracked GPU buffer to baseline:

```sh
kbb -M:deno-paged-kv-verify
deno run --allow-all target/deno-paged-kv-verify.cjs
# non-contiguous paged GQA parity: passed
# prefix COW block-copy parity: passed
# paged GPU storage release: passed
```

`paged-gqa-attention-batch` extends the same physical pools to one fused
multi-request dispatch. Query rows carry independent sequence lengths and padded
block-table rows, so ragged decode does not require padding K/V payloads or
materializing contiguous caches. The live verifier evaluates the length-3
`[2,0]` request and a length-2 fork `[1,_]` together and matches both CPU GQA
oracles.

**Host-materialized, not device-native (an explicit, documented tradeoff):**
`num.protocol/IBackend` has no notion of strides/gather/scatter — a handle is an opaque
flat contiguous buffer. Except for the native last-axis bias and fused attention
specializations above, rank-2 same-backend `matmul`, 2-D matrix transpose, and row-sum
are also device-native (these cover learned Linear backward). General
`broadcast-to`/arbitrary-rank `transpose`/axis-reductions/batched `matmul` still read
operands back via `arr/->vec`, compute with plain `double-array` loops (same style as
`num.cpu`'s reference loops), and re-upload via `arr/from-vec` — correct on ANY backend
today, but a host round-trip. `reshape`/`squeeze`/`unsqueeze` are the exception: for a
row-major contiguous layout they never move data, so they're zero-copy metadata edits.
Pushing the round-tripping ops into `IBackend` itself (so a GPU backend executes them
without leaving the device) is **Phase 2** work per ADR-2607051400, not this pass.

**Phase-1 scope vs. what's deferred, honestly:**
- Done: arbitrary-rank shape (the shape math — `row-major-strides`/`unravel`/`ravel`/
  `broadcast-shapes` — is plain `(count shape)`-generic with no rank ceiling anywhere;
  explicitly TESTED, not just asserted generic, at 0-D/1-D/2-D/3-D and at rank 4 per the
  ADR's "at least 4-D": `rank-4-reshape-and-transpose`, `rank-4-axis-reduction-matches-naive`,
  and `rank-4-batched-matmul-matches-naive` exercise reshape/transpose/axis-sum/batched-matmul
  on 4-D tensors against independently-written naive references), NumPy-style
  broadcasting (`broadcast-shapes`/`broadcast-to`) with the exact trailing-align/size-1
  rule, `reshape`/`transpose`/`squeeze`/`unsqueeze` (data-preserving, tested against
  hand-computed layouts), axis-parameterized `sum`/`amax`/`amin`/`mean` with `:keepdims?`
  (single axis, multiple axes, or all axes), and batched N-D `matmul` with batch-dim
  broadcasting.
- Deferred (not attempted this pass, left to Phase 2 per the ADR): a live GPU dispatch
  path for any of the above (everything here runs through the CPU-materialized
  `->vec`/`from-vec` seam regardless of which `IBackend` is injected); new WGSL kernels
  for N-D broadcast/batched-matmul (the ADR explicitly calls this out as Phase 2 net-new
  shader work); and proving `num.tensor` under ClojureScript via the `cljs-verify`
  harness (it's written in the same portable `.cljc` style — `Math/…`, `double-array`,
  `aget`/`aset`, `ex-info` — as the rest of this repo, but `test/num/cljs_verify.cljk`
  currently only exercises `num.contract` against `num.cpu`, not `num.tensor`; that
  wiring wasn't extended in this pass).

## Live GPU backend (Deno + WebGPU → Metal, ADR-2607051400 §Phase 2)

GGML Q8_0 inference now has a fused GPU GEMV kernel. Packed signed bytes and
per-32-value scales stay quantized in GPU storage and are decoded inside WGSL;
no full F32 matrix is materialized. Verify it against the CPU oracle on the
actual adapter:

```sh
kbb -M:deno-q8-verify
deno run --allow-all target/deno-q8-verify.cjs
# Apple M4: expected [73.76000009 95.44000039]
#           Metal    [73.75999451 95.43997955]
```

`num.quantized/matrix` additionally stores complete GGML Q5_0, Q4_K, Q6_K, and
Q8_0 blocks at their original 5.5/4.5/6.5625/8.5 bits per weight and exposes them as
`[in,out]` matrices. `num.quantized/matmul` decodes their packed fp16
super-scales, subblock scales/mins, and quant bits inside the compute kernel
while accumulating f32; it supports multi-row activations and never creates a
dense weight buffer. `num.quantized/table` performs device-native token lookup
from the same four formats, and `as-matrix` creates a zero-copy tied output-head
view over the exact same packed buffer.

```sh
kbb -M:deno-quantized-verify && \
  deno run --allow-all target/deno-quantized-verify.cjs
# Apple M4: Q5_0 CPU/Metal parity: passed
#           Q4_K CPU/Metal parity: passed
#           Q6_K CPU/Metal parity: passed
#           Q8_0 CPU/Metal parity: passed
#           packed embedding CPU/Metal parity: passed
```

Quantized GEMM uses a 64-lane K reduction and a four-row M tile, decoding each
weight once for up to four activation rows. The reproducible 1024×1024 Apple M4
benchmark forces readback for every iteration (completion, not submission):

```sh
kbb -M:deno-quantized-benchmark && \
  deno run --allow-all target/deno-quantized-benchmark.cjs
# Q4_K 589,824 bytes vs dense f32 4,194,304 bytes (7.11x smaller)
# decode cold: Q4_K 26.882 ms, dense 18.468 ms (compilation included)
# decode warm: Q4_K 14.680 ms/op, dense 16.691 ms/op

deno run --allow-all target/deno-quantized-benchmark.cjs prefill
# [64,1024] x [1024,1024]
# prefill cold: Q4_K 30.586 ms, dense 22.168 ms
# prefill warm: Q4_K 21.949 ms/op, dense 20.355 ms/op
```

These numbers are a deterministic kernel fixture, not a whole-model tokens/sec
claim; full model loading, sampling, and long-context cache traffic remain
separate costs.

`num.deno-gpu` promotes `verify/metal_contract.js`'s raw JS harness into a REAL
`num.wgsl/IGpuDevice` + `num.protocol/IBackend` implementation — `num.core`'s ops
(`axpy!`/`scal!`/`add`/`sub`/`mul`/`div`/`sum`/`amax`/`amin`/`dot`/`nrm2`/`matvec`/
`matmul`/`spmv`) now dispatch through the SAME WGSL kernels on real GPU hardware from
real Clojure code (ClojureScript compiled for Deno), not only from a standalone script.

```clojure
(require '[num.array :as a] '[num.core :as nm] '[num.deno-gpu :as dg])
(-> (dg/gpu-backend)                              ; async: device negotiation is Promise-based
    (.then (fn [gpu]
             (let [x (a/from-vec gpu [1 2 3] [3])
                   y (a/from-vec gpu [4 5 6] [3])]
               (.then (nm/dot x y) println)))))   ; host-value ops (dot/nrm2/sum/amax/amin,
                                                   ; arr/->vec) return a JS Promise on this
                                                   ; backend — see num.deno-gpu docstring
```

**Sync vs. async, resolved (not hand-waved):** a single WebGPU queue processes
submitted commands strictly in order, so `-alloc`/`-copy-from-host`/`-axpy`/`-scal`/
`-ewise`/`-gemv`/`-gemm`/`-spmv` are fully synchronous end-to-end — dispatching
`axpy!`/`scal!`/`add`/`sub`/`mul`/`div`/`matvec`/`matmul`/`spmv` through the Deno GPU
backend behaves exactly like a fully-synchronous backend would. Only the four ops that
read a value back to the host (`-copy-to-host`/`-reduce`/`-dot`/`-nrm2` — i.e.
`arr/->vec`, `sum`, `amax`, `amin`, `dot`, `nrm2`) are unavoidably async (`GPUBuffer.
mapAsync`) and return a JS `Promise` instead of an immediate value — a deliberate,
documented deviation from `IBackend`'s normal contract for this one host. Native
ClojureScript `async`/`await` (`^:async`/`js-await`) was tried first and confirmed NOT
supported by this repo's plain `kbb -M -m cljs.main` pipeline (no shadow-cljs); the
backend uses plain JS Promise `.then` interop instead, the same style
`kotoba-lang/host`'s `kami.backend.browser` already uses for its own browser GPU host
bring-up.

**Run it for real** (the only host with GPU access — confirmed working with Deno ≥ 2,
no `--unstable-webgpu` flag needed):

```bash
kbb -M:deno-verify && deno run --allow-all target/deno-gpu-verify.cjs
```

Large checkpoint hosts can bypass per-element JavaScript number allocation with
`num.deno-gpu/upload-byte-view`. It validates shape × dtype byte length and sends
an existing little-endian `ArrayBufferView` directly to WebGPU storage for f32
or f16 (padding only an odd f16 tail to WebGPU's four-byte write alignment).
`upload-f16-as-f32-byte-view` follows that upload with a packed-half expansion
kernel (`unpack2x16float`) and retires the temporary f16 buffer, allowing an f32
inference graph to consume half-precision checkpoint files without allocating a
host-side vector of decoded numbers. `upload-bf16-as-f32-byte-view` provides the
same path for packed bfloat16 by reconstructing each IEEE f32 bit pattern on GPU.
The live raw-upload gate covers both physical formats and exact buffer cleanup:

```bash
kbb -M:deno-raw-upload-verify
deno run --allow-all target/deno-raw-upload-verify.cjs
```

Arrow IPC has an optional end-to-end adapter in `integration/num/arrow_gpu.cljk`.
It borrows an uncompressed, non-nullable float32 values buffer from
`org-apache-arrow`, exposes a `Float32Array` over the same CPU `ArrayBuffer`, and
passes the identical bytes to `upload-byte-view`. There is no row materialization
or intermediate numeric vector. The CPU view is SIMD-ready but does not claim a
particular host JIT vectorized it; the GPU ownership boundary still performs one
measured `queue.writeBuffer`. Nullable columns fail closed until a masked kernel
exists. The live gate proves one 16-byte upload, device execution, and one 4-byte
scalar readback:

```bash
kbb -M:deno-arrow-upload-verify
deno run --allow-all target/deno-arrow-upload-verify.cjs
```

The CPU path also has an explicit WebAssembly SIMD gate. Its linear memory owns
the ingress bytes; Arrow borrows the values slice from that memory, then Num
passes the slice's byte offset directly to a `v128.load` / `f32x4.mul` /
`v128.store` kernel. The only copy is the named ingress write. There is no row
materialization or Arrow-to-SIMD copy, and a scalar tail preserves columns whose
row count is not divisible by four. This proves SIMD execution and backing
identity; it does not claim a speedup over a particular JavaScript JIT:

```bash
wasm-tools parse integration/num/arrow_f32_simd.wat -o target/arrow-f32-simd.wasm
kbb -M:deno-arrow-simd-verify
deno run --allow-read target/deno-arrow-simd-verify.cjs
```

For a same-artifact comparison against scalar Wasm, the benchmark uses the same
module, Arrow backing, float32 scale operation, element count, host, warm-up and
correctness oracle. It alternates execution order and reports every sample plus
the median. The timed region contains kernel calls only; the benchmark-only
buffer reset is excluded. Results qualify only that measured kernel and host.
The report records one-minute load and marks `publishable?` false when load
exceeds the host's logical CPU count; a high-load ratio is evidence that the
path runs, not a public performance claim:

```bash
wasm-tools parse integration/num/arrow_f32_simd.wat -o target/arrow-f32-simd.wasm
kbb -M:deno-arrow-simd-benchmark
deno run --allow-read --allow-sys=loadavg,cpus \
  target/deno-arrow-simd-benchmark.cjs
```

A qualified three-run record is checked in at
[`docs/evidence/arrow-wasm-simd-2026-08-30.json`](docs/evidence/arrow-wasm-simd-2026-08-30.json).
On its Apple M4 host, the explicit Wasm `f32x4` kernel completed this bounded
262,147-element float32 scale workload 3.66–3.72× faster than scalar Wasm.
All three runs used the same artifact and backing memory and remained below the
load gate. This is a kernel-and-host result, not a general Num, build, network,
protocol, or GPU speed claim.

### UNet Metal benchmark

The benchmark forces final readback, so it measures completed GPU work plus the
host transfer rather than near-zero queue submission latency. Full-width modes
run one cold iteration followed by five sequential warm iterations on the same
device/backend and report every sample plus the median; this avoids presenting
a single noisy run as a performance result:

```bash
kbb -M:deno-benchmark
deno run --allow-all target/deno-gpu-benchmark.cjs

# Full Stable-Diffusion-width 320→320 convolution at latent 64×64
deno run --allow-all target/deno-gpu-benchmark.cjs full
deno run --allow-all target/deno-gpu-benchmark.cjs full-f16

# F16 GroupNorm+SiLU at [1,320,64,64], including forced readback
deno run --allow-all target/deno-gpu-benchmark.cjs norm-f16
```

Measured on Apple M4 with input `[1,32,64,64]`, weights `[64,32,3,3]`, and a
full `NCHW conv(pad=1) → GroupNorm(8) → SiLU` chain:

| path | elapsed |
|---|---:|
| ClojureScript CPU oracle | 1300.98 ms |
| Metal cold (pipeline compile included) | 519.91 ms |
| Metal warm | 29.13 ms |

Warm speedup is **44.66×**, with maximum absolute error `2.38e-6` against the
CPU oracle. The full-width mode separately measures a real latent-resolution
`[1,320,64,64] × [320,320,3,3]` convolution. The four-output-channel kernel
produced f32 warm samples of `165.61, 108.65, 124.40, 208.58, 126.71 ms`
(median `126.71 ms`), with its interior constant-input result within `4.51e-7`
of the analytic value. Packed physical f16 produced
`601.75, 581.06, 652.13, 654.76, 603.05 ms` (median `603.05 ms`) on the same
case. Deno's Naga rejects native WGSL
`enable f16` despite the adapter advertising `shader-f16`, so f16 remains a
correctness/storage path rather than a performance claim: repeated
`unpack2x16float` of every convolution weight still dominates and leaves it
4.76× slower than f32 despite using half the persistent bytes.
The benchmark also checks explicit GPUBuffer lifetime. After the cold and five
warm executions the full-width case returns to its three persistent
input/weight buffers
(`8,930,560` bytes) from a `14,173,520`-byte peak.
Per-dispatch uniform buffers, implicit no-bias/no-mask buffers, and readback
staging buffers are destroyed after submission/use rather than accumulating
across diffusion steps. The live verifier repeats 100 temporary dispatches and
asserts both live buffer count and bytes return exactly to their baseline.
These are concrete completed-work measurements, not a claim of PyTorch/MPS-wide
parity: end-to-end model memory pressure, mixed precision, fusion, and complete
UNet throughput still require separate benchmarks.

This cross-checks the live GPU backend against `num.cpu`'s reference oracle (dispatched
through `num.core`/`num.array`, i.e. through `IBackend`, the same seam any real caller
uses) — **verified passing on real Apple M4 Metal hardware while building this**:
`Deno WgslBackendAsync ≡ CPU oracle: 48 passed, 0 failed` (BLAS, reductions,
sparse matvec, unary exp/relu/neg/SiLU/sigmoid/tanh/GELU and activation derivatives,
full NCHW/depthwise convolution, and
affine/non-affine GroupNorm, upsampling, skip concatenation, bias broadcasting,
and fused multi-head attention).

## Status

S0 is real and tested: the array/CSR types, the `IBackend` protocol, the **pure-Clojure
CPU reference backend**, the public API, and the **backend contract suite** (every op
checked against reference values — `CpuBackend ≡` any future GPU backend).

**S1 (live WGSL backend) is now real, not just shipped shaders.** `num.wgsl` ships the
compute shaders + the `IGpuDevice` host port + the dispatch plan; `num.wgsl-backend`
dispatches them through an injected device (synchronous variant, for a future native/
blocking device — not yet implemented); and **`num.deno-gpu` is a live, working
`IGpuDevice` + `IBackend` for Deno's native WebGPU**, verified end-to-end against the CPU
oracle through `num.core` on real Apple Metal hardware (previous section). What's still
NOT done: a JVM-side blocking device (Panama/FFM → wgpu-native) so the *synchronous*
`WgslBackend` can run the Clojure contract suite on-GPU from the JVM, and the
vendor-native (`:cuda`/`:metal`/`:rocm`) fast-path backends — see
`docs/adr/0001-architecture.md`.

```bash
kbb -X:test                                  # CPU backend satisfies the full IBackend contract (JVM)
kbb -M:cljs && node target/cljs-verify.js     # PROOF: the same .cljc core runs under ClojureScript
kbb -M:deno-verify && deno run --allow-all target/deno-gpu-verify.cjs   # PROOF: live GPU ≡ CPU oracle, real Metal
kbb -M:deno-attention-backward-verify && deno run --allow-all target/deno-attention-backward-verify.cjs # fused attention gradients on Metal
```

**Portability is proven, not just claimed.** The `.cljc` core (CPU backend, array/CSR
types, the full op contract) compiles to JS via ClojureScript and runs green on node —
`cljs CPU contract: 18 passed, 0 failed`. The WGSL kernels are verified on real
**Apple M4/M1 Metal** three separate ways now: the standalone harness
(`verify/metal_contract.js`, 13/13) including a Jacobi-PCG Poisson solve
(`verify/metal_pcg.js`), AND the live `num.deno-gpu` backend dispatched through real
`num.core`/`num.tensor` Clojure code (`deno-gpu-verify`, 51/51 against the CPU
oracle). So num-clj
genuinely spans pure-Clojure → cljs → live GPU from one source, with the GPU path no
longer only exercised by a script outside the Clojure dispatch seam.

`num.array/argmax-rows` is the device-selection boundary used by inference
servers. Its WGSL kernel assigns one 256-lane workgroup per contiguous logits
row, scans arbitrarily wide vocabularies in lane-strided order, and preserves the
lowest token index on exact ties. The Deno/WebGPU backend maps only the resulting
u32 indices: a verified two-row, 513-column fixture transfers 8 bytes instead of
4,104 bytes. `backend-stats` exposes `:selection-readbacks` and
`:selection-readback-bytes` so serving tests can prove that boundary rather than
infer it from token parity.

`num.array/top-k-row` extends that boundary to exact top-k candidates (bounded
to 256) from any row of a shared batch tensor. A sparse WGSL pass first applies
the standard sign-aware repetition penalty once per unique previous token; the
selection pass returns interleaved `[token-id, adjusted-logit]` pairs in stable
descending order. Each lane finds its local maximum once and only the winning
lane rescans for its successor, avoiding the original `O(k*vocab)` all-lane
rescan. The source row may be mutated and is explicitly documented as
disposable.

`sample-top-k-row` keeps those candidates on device and fuses temperature,
top-p, and categorical selection into one kernel, so each decode returns only a
4-byte token ID. `sample-softmax-row` handles the untruncated (`top-k=nil`,
`top-p=1`) distribution with parallel max/mass reduction and a token-order CDF,
also returning one 4-byte token ID. `sample-nucleus-row` handles `top-k=nil`,
`top-p<1` exactly: it pads to the next power of two, stable-sorts the complete
vocabulary by logit descending/token ID ascending with globally synchronized
bitonic stages, then finds and samples the exact nucleus on device. It supports
vocabularies through 1,048,576 and also returns 4 bytes.
`speculative-rejection-row` performs full-distribution temperature softmax,
proposal acceptance, and positive-residual
sampling with parallel contiguous vocabulary chunks, returning only an 8-byte
decision.

`num.expert-cache` is the portable policy core for Expert-aware NVMe
streaming. It accounts resident bytes (not virtual reservations), performs
deterministic LRU eviction over opaque `(layer, expert, projection)` keys, and
reads router rows with their physical stride. I/O and direct buffers are host
resources and therefore live in `kotoba-lang/torch`.

At vocabulary 262,144, median warm selection times were: Apple M4 19.3/22.9/
53.0 ms for k=8/40/256, 14.8 ms for full-softmax, 26.9 ms for exact nucleus,
and 13.7 ms for speculative rejection; Intel Arc B70 15.2/18.0/51.6 ms,
12.5 ms, 25.1 ms, and 12.2 ms respectively (three measured iterations after
one warm-up). The production-size nucleus result is also checked against an
independent host stable-sort oracle. These are isolated sampling-kernel
measurements over synthetic logits, not model throughput.

**Honest gap:** most `num.tensor` N-D ops (broadcast/transpose/axis-reduce/batched-matmul,
ADR-2607051400 §Phase 1) do not yet dispatch through `num.deno-gpu` or any GPU backend —
they are host-materialized (round-trip through `arr/->vec`/`arr/from-vec`) regardless of
which `IBackend` is injected. Metadata-only reshape/squeeze/unsqueeze and the
UNet path (SiLU, NCHW convolution, GroupNorm, nearest upsampling, cat) are
exceptions. Extending the WGSL kernel set to N-D broadcast/batched-
matmul dispatch is unimplemented net-new shader work, not attempted in this pass.
Explicit top-k above 256 and exact nucleus vocabularies above 1,048,576 remain
outside the admitted device boundary.
