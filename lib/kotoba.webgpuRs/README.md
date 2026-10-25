# kotoba-lang/webgpu-rs

**SSoT for `kotoba.webgpu-rs.*`** — pure-CLJC port of the retired Rust
`kami-webgpu-rs` CPU-side domain (render-IR parse, mat4, geometry, demo scene, …).

This is **not** the browser WebGPU executor (`kotoba-lang/webgpu` / `kami.webgpu`).
ADR-2607102200 addendum 8 restored this package as the home after a temporary
merge into webgpu.

## Not everything here is a port

`kotoba.webgpu-rs.prefab` has no Rust original. It is the data-level prefab
(named, nestable, per-instance-overridable authoring unit → render-IR
instances) that kami-engine ADR-0040 places on the EDN side of the boundary,
and it lives here because the scene → render-IR authority
(`kotoba.webgpu-rs.scene`) does.

Its `:trees` template — two parts, trunk and canopy, from one declaration —
already existed, hardcoded in Clojure inside `scene/scatter`. The oracle test
`prefab-oracle-reproduces-scene-trees` asserts the general expander reproduces
that shipped output exactly, for every coordinate the real royale scene
scatters. `scene.cljc` is deliberately **not** rewritten to route through the
expander yet; equivalence is proven first.

## Test

```sh
kbb -M:test
```
