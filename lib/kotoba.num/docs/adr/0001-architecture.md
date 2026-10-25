# ADR-0001 — num-clj architecture: portable BLAS/sparse contract + injected GPU backends

- Status: Accepted
- Date: 2026-06-28
- Context tags: gpu, compute, blas, sparse, webgpu, wgsl, portable-cljc, backend-dispatch

## Decision

Build num-clj as a **BLAS-level dense + sparse** numerical library whose *core* (array
type, op protocol, public API, a pure-Clojure CPU reference backend) is
**zero-dependency, all `.cljc`**, and whose GPU acceleration is delivered by **backends
injected behind a single protocol** `num.protocol/IBackend`. The **portable-primary** GPU
backend is **WGSL compute via WebGPU/wgpu** (one shader → Metal/Vulkan/DX12/WebGPU);
**vendor-native** backends (cuBLAS / Metal Performance Shaders / rocBLAS) are optional
fast paths behind the same protocol.

## Why this shape

- **Portability is the franchise.** kudaki-clj / nagare-clj are valuable because the
  *same* `.cljc` kernel runs on JVM / SCI / cljs / GraalVM / WASM. A GPU library that
  forced a native dep would break that. So native code lives ONLY in injected backends;
  the core and the CPU reference stay pure and portable, and a host with no GPU still
  runs everything (slowly) on the CPU backend.
- **One seam, many backends** mirrors the org: `MemStore ‖ DatomicStore`, the
  `cae-solver` `[:solver :kind]` dispatch, the actors' injected Store/Advisor. The seam
  here is `IBackend`; a `handle` is an opaque buffer per backend.
- **WGSL-first reaches every GPU without three kernels.** wgpu compiles one WGSL compute
  shader to MSL (Apple), SPIR-V (Vulkan → AMD/ROCm-class, NVIDIA, Intel), DXIL (D3D12),
  and WebGPU (browser). The driver does per-GPU codegen/scheduling, so "optimized for
  each GPU" comes from writing the kernel *well once* (tiling, coalescing), not from
  vendor lock-in. Vendor-native backends exist for the last increment of throughput.
- **BLAS-level + sparse is the right scope** for the consumers: nagare/kudaki need
  `SpMV` + `AXPY` + `dot` (Krylov) and dense `GEMM`/`GEMV` (element/operator kernels).
  Not a full autodiff tensor framework — that is a different, larger library.

## Module boundaries

```
num.protocol  IBackend — the seam (alloc/copy, level-1, ewise/reduce, gemv/gemm, spmv)
num.array     NDArray {:backend :handle :shape} — the value users hold
num.sparse    CSR (host structure; backends upload indices on first spmv)
num.cpu       CpuBackend — pure .cljc over double-array; the ORACLE + fallback
num.core      public API; reads operands' backend, dispatches through IBackend
num.wgsl      WGSL compute shaders + IGpuDevice host port + IBackend⇄shader plan
```

The invariant: **the CPU backend is the reference oracle**, and the backend **contract
suite** (`num.contract`) asserts any GPU backend reproduces it to f32 tolerance —
`WgslBackend ≡ CpuBackend`, exactly like `MemStore ≡ DatomicStore`.

## Backends

| kind | mechanism | host | role |
|---|---|---|---|
| `:cpu` | pure Clojure / `double-array` | any | reference oracle + fallback |
| `:wgsl` | WGSL compute via wgpu/WebGPU (host-injected `IGpuDevice`) | browser (cljs) / native wgpu | **portable primary** |
| `:cuda` | cuBLAS / cuSPARSE via Panama or JCuda | JVM + NVIDIA | fast path |
| `:metal` | Metal Performance Shaders via FFM | JVM + Apple | fast path |
| `:rocm` | rocBLAS / hipSPARSE via Panama | JVM + AMD | fast path |

num-clj ships no native code: `:wgsl` execution is the host-injected `IGpuDevice` port
(browser fills it from `navigator.gpu`; a native host from a wgpu binding); the vendor
backends are alternative `IBackend` impls behind aliases.

## Staged roadmap (multi-session)

- **S0 — portable core (this session).** array + CSR + `IBackend` + pure-Clojure CPU
  reference backend + public API + backend contract suite. WGSL shaders (tiled GEMM,
  CSR SpMV, AXPY, tree reduce) + `IGpuDevice` port + dispatch plan. Tests green.
- **S1 — live WGSL backend.** The **full IBackend contract** (axpy, scal, dot, nrm2,
  ewise add/sub/mul, reduce sum/max/min, gemv, tiled gemm, csr spmv) is **verified on
  real Apple M4 Metal** (wgpu via Deno WebGPU) ≡ the CPU reference — `verify/
  metal_contract.js`, 13/13. The complete shader set lives in `num.wgsl`; the
  `WgslBackend` deftype (`num.wgsl-backend`) dispatches them through the injected
  `IGpuDevice` and is compile-checked on the JVM. **Note (sync vs async):** a
  *synchronous* WgslBackend needs a device with BLOCKING readback (native wgpu binding
  / vendor backend); the browser/Deno WebGPU path is async, which the JS harness
  originally used standalone.
  **Update (ADR-2607051400 §Phase 2 — the async IBackend variant is now real, not
  remaining):** `num.deno-gpu` implements a live `IGpuDevice` over Deno's native
  `navigator.gpu`, plus `WgslBackendAsync` — an `IBackend` that dispatches `num.core`'s
  ops through it. Verified on real Apple M1 Max Metal, cross-checked against `num.cpu`'s
  oracle THROUGH `num.core`/`num.array` (not a standalone JS harness this time):
  `kbb -M:deno-verify && deno run --allow-all target/deno-gpu-verify.cjs` →
  `Deno WgslBackendAsync ≡ CPU oracle: 14 passed, 0 failed`. Still remaining: a JVM
  Panama→wgpu-native `IGpuDevice` (blocking) so the *synchronous* `WgslBackend` can run
  the Clojure contract on-GPU from the JVM — the async/cljs half of this line item is
  done, the JVM/native-blocking half is not.
- **S2 — vendor fast paths.** `:cuda` (cuBLAS/cuSPARSE) and `:metal` (MPS) behind the
  same protocol + contract; benchmark vs WGSL.
- **S3 — consumer wiring.** Inject a num-clj backend into nagare-clj's `linsolve`
  (PCG/BiCGStab → device `SpMV`/`AXPY`/`dot`) and kudaki-clj's element/assembly loops,
  so the existing portable solvers run on GPU unchanged. Register under the `cae-solver`
  contract as accelerated backends. **Demonstrated on Metal** (`verify/metal_pcg.js`): a
  Jacobi-preconditioned CG — the same Krylov loop nagare's `linsolve` runs — solves a
  2-D Poisson system (N=1024) **entirely with num-clj's GPU kernels on Apple M4**,
  converging in 64 iterations to ‖r‖/‖b‖ ≈ 9e-6 ≡ the analytic solution. Remaining: the
  Clojure-side injection once a blocking native `IGpuDevice` (S1 tail) exists.
- **S4 — breadth.** f16/bf16, batched GEMM, more sparse formats (ELL/blocked), fused
  kernels, a small JIT for elementwise chains.

## Consequences

- The core is provably portable (a portability-guard test, like kudaki/nagare, can lint
  the kernel namespaces); GPU specifics never leak into it.
- A program written today on `:cpu` runs unchanged on a GPU tomorrow — caller code names
  no vendor.
- num-clj becomes the shared GPU substrate the CAE solvers (and any other com-junkawasaki
  numerics) accelerate through, instead of each growing its own native path.

## Rejected alternatives

- **A single vendor backend (CUDA-only).** Locks out Apple/AMD/browser and breaks WASM
  portability; WGSL-first reaches all of them from one kernel.
- **A full autodiff tensor framework (JAX-like).** Larger and orthogonal; the consumers
  need BLAS + sparse, not reverse-mode AD. Can layer on later.
- **Native code in the core.** Would forfeit the cljs/WASM portability that is the
  reason the sibling solvers exist. Native lives only in injected backends.
