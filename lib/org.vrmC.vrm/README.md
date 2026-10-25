# kotoba-lang/vrm

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-vrm` Rust crate
(kotoba-lang/kami-engine, deleted in PR #82 "Remove Rust workspace from kami-engine") as
part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

VRM (Virtual Reality Model, a glTF 2.0 extension) is the humanoid avatar format used by
VRoid/VRChat-style pipelines. This crate restores the full parse/decompose/compose/export
pipeline plus the runtime physics/animation systems the original data model supported:
spring-bone (jiggle-physics) simulation, node constraints (aim/rotation/roll bone rigging),
facial expression weight resolution, and first-person mesh-visibility culling.

## Status

All 15 original Rust modules ported 1:1 to CLJC (4,704 lines of Rust -> ~2,650 lines of
CLJC across 17 namespaces — 2 extra namespaces, `vrm.json` and `vrm.math`, are supporting
infrastructure the Rust original got for free from `serde_json` and `glam`, ported locally
per the zero-dependency restoration convention).

| Namespace | Restored from | Lines | Purpose |
|---|---|---|---|
| `vrm` | `lib.rs` (250) | 78 | Root: pipeline docs, re-exports, error convention |
| `vrm.glb` | `glb.rs` (166) | 113 | GLB binary container parse/write facade (see below, ADR-0048 §5) |
| `vrm.gltf-types` | `gltf_types.rs` (292) | 53 | glTF 2.0 constants + document defaults |
| `vrm.vrm-types` | `vrm_types.rs` (620) | 212 | VRM data shapes, humanoid/expression-preset tables |
| `vrm.parse` | `parse.rs` (508) | 276 | VRM 1.0 GLB -> VrmDocument parser |
| `vrm.compat` | `compat.rs` (429) | 238 | VRM 0.x -> 1.0 conversion layer |
| `vrm.humanoid` | `humanoid.rs` (143) | 93 | Bone mapping <-> skeleton conversion |
| `vrm.part` | `part.rs` (283) | 128 | Avatar part decomposition (body/hair/face/...) |
| `vrm.compose` | `compose.rs` (627) | 408 | Merge parts into one VrmDocument |
| `vrm.export` | `export.rs` (325) | 161 | VrmDocument -> GLB export |
| `vrm.convert` | `convert.rs` (149) | 95 | Accessor -> interleaved vertex/index buffers |
| `vrm.spring` | `spring.rs` (301) | 176 | Spring-bone (jiggle) physics simulator |
| `vrm.constraint` | `constraint.rs` (172) | 93 | Node constraint solver (aim/rotation/roll) |
| `vrm.expression` | `expression.rs` (304) | 116 | Expression weight -> morph/material/UV resolver |
| `vrm.firstperson` | `firstperson.rs` (135) | 45 | First-person mesh visibility resolver |
| `vrm.json` | *(infra, no Rust source)* | 171 | Dependency-free JSON parser/serializer |
| `vrm.math` | *(infra, no Rust source)* | 198 | glam-equivalent Vec3/Quat/Mat4 |

Tests: 25 `deftest`s / 116 assertions across `test/vrm_test.cljk` (namespace-loads smoke
test + the 4 original `lib.rs` integration tests: parse, decompose, compose+export
roundtrip, skeleton extraction) and `test/vrm/{glb,humanoid,part,expression,firstperson}_test.cljc`
(one test per original `#[test]` in the corresponding Rust module — `parse.rs`, `compat.rs`,
`compose.rs`, `export.rs`, `convert.rs`, `spring.rs`, and `constraint.rs` had no `#[cfg(test)]`
blocks in the original, so nothing to port there beyond the integration coverage above).
Spring-bone physics and the node-constraint solver were additionally sanity-checked in the
REPL (gravity pulling a hanging chain to a stable non-trivial rotation; a rotation
constraint reproducing its source's delta) since neither had Rust unit tests to port.

## GLB container framing (ADR-0048 §5)

`vrm.glb`'s actual container framing (12-byte header + JSON chunk + BIN chunk, magic
numbers, padding) used to be hand-rolled here — but the same format was *also*
independently hand-rolled (write-only) in `kotoba-lang/gltf`, a real
duplicated-implementation risk (ADR-0048 §5, `kotoba-lang/kami-engine`). `vrm.glb` is
now a thin facade over **`kotoba-lang/glb`** (`:local/root "../glb"`, the single
canonical GLB codec both repos depend on): `parse-glb`/`write-glb` delegate to
`glb/parse-glb-raw`/`glb/write-glb-raw` (the raw, bytes-in/bytes-out tier — no JSON
encode/decode, since this repo's own `vrm.json` still owns that), preserving the
exact original call signatures (`parse-glb` still returns raw JSON chunk bytes, not
a parsed map; `write-glb` still takes positional `(json bin)` byte-seq args), so
every existing call site (`vrm.parse`, `vrm.export`, the tests) needed zero changes.
`glb-magic`/`glb-version`/`chunk-json`/`chunk-bin`/`u32->le-bytes`/`string->byte-seq`/
`byte-seq->string`/`pad-len` are now re-exports of `glb`'s canonical definitions.

Platform divergence (little-endian f32 byte encoding for the GLB binary container) is
isolated behind `#?(:clj ... :cljs ...)` reader conditionals; everything else is pure,
portable EDN data + functions. No cross-repo dependency: `vrm.humanoid/to-kami-skeleton`
produces a `kotoba-lang/skeleton`-compatible `{:bones [...]}` map directly rather than
requiring that sibling repo, and `vrm.math` re-implements `kotoba-lang/skeleton`'s
`skeleton/math.cljc` conventions locally.

## Develop

```bash
kbb -M:test
```
