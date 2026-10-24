# kotoba-lang/raytrace

[![CI](https://github.com/kotoba-lang/raytrace/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/raytrace/actions/workflows/ci.yml)

**hikari-rt (光)** — WebGPU ray-tracing primitive, ported pure to `.cljc`
from the Rust crate `kami-rt` (kotoba-lang/kami-engine) per
[ADR-2607010930](../../90-docs/adr/) (clj-wgsl migration Phase 4). The Rust
crate is retiring in favor of a `kotoba` authority repo, per the
repo-wide Rust-to-Clojure migration.

`kami.rt` (clj/edn, elsewhere) is the brain — it authors an EDN
ray-tracing recipe and normalizes it to a backend-neutral IR. This library
is the **portable executor half**: it builds the acceleration structure
and generates the WGSL ray-query trace shader from the same integrator
parameters.

## What's ported (everything — see "Why nothing is adapter-only" below)

| Rust source | `.cljc` namespace | What it does |
|---|---|---|
| `bvh.rs` (`Aabb`, `Tri`, `Node`, `Bvh`, `build`, `traverse`) | `kotoba.raytrace.bvh` | LBVH build (30-bit Morton sort + median split) and reference CPU traversal (slab AABB test + Möller–Trumbore ray/triangle) |
| `gpu.rs` (`GpuNode`, `GpuTri`, `to_gpu`) | `kotoba.raytrace.gpu` | Packs a built BVH into the flat node/triangle layout a WGSL storage buffer would bind |
| `lib.rs` (`RtConfig`, `fnum`, `wgsl_ray_query`) | `kotoba.raytrace.wgsl` + `kotoba.raytrace` | Integrator config + WGSL ray-query compute-shader text generation |
| *(external `glam` crate)* | `kotoba.raytrace.vec3` | Minimal Vec3 shim — kami-rt depended on `glam`; this is a from-scratch replacement, not a 1:1 port of any Rust file |
| hardcoded literals across all three files | `resources/kotoba/raytrace/config.edn` + `kotoba.raytrace.config` | `LEAF_MAX`, ray/AABB epsilons, Morton quantization scale, `RtConfig::default()` — extracted to EDN so they're tunable data |

### Why nothing is adapter-only

The task brief for this migration expects a GPU-dispatch/hardware-RT-extension
boundary to stay adapter-only. **kami-rt never had one.** Its own module doc
comments say so explicitly: `bvh.rs` and `gpu.rs` are described as "GPU-free
and unit-tested" / "the actual buffer upload + dispatch lives in kami-render
… needs a `wgpu::Device`" — that dispatch code lives in a *different* crate
(`kami-render`, out of scope for this port) and was never present here. So
every `.rs` file in `kami-rt` — BVH math, GPU buffer packing, WGSL shader
text generation — is pure, portable, GPU-free CPU code, and all of it is
ported as `.cljc`.

The one genuinely JVM-only addition is `kotoba.raytrace.gpu/pack-node` and
`pack-tri`: byte-exact `java.nio.ByteBuffer` packing matching the Rust
`#[repr(C)]`/`bytemuck::Pod` 48-byte layout. This is a **host convenience**
(no cljs equivalent, no GPU call either — just NIO), not required by the
pure port; `to-gpu` (the actual 1:1 port of `gpu.rs`'s public API) works on
every platform.

## Usage

```clojure
(require '[kotoba.raytrace.bvh :as bvh]
         '[kotoba.raytrace.gpu :as gpu]
         '[kotoba.raytrace :as rt])

(def tris [{:v0 [-1.0 -1.0 -5.0] :v1 [1.0 -1.0 -5.0] :v2 [0.0 1.0 -5.0] :id 0}])
(def scene (bvh/build tris))
(bvh/traverse scene [0.0 0.0 0.0] [0.0 0.0 -1.0])
;; => {:t 5.0 :tri-id 0}

(gpu/to-gpu scene)
;; => {:nodes [...] :tris [...]}  ; flat GPU-uploadable layout

(rt/wgsl-ray-query "gi" (rt/default-config))
;; => WGSL ray-query compute shader source (string)
```

## Test / lint

```sh
kbb -M:test
kbb -M:lint
```

## License

Apache License 2.0.
