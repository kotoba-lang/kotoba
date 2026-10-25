# kotoba-lang/webgl

**SSoT for `kami.webgl`** — WebGL2 browser executor for the same EDN render-IR as
`kami.webgpu`. Capability queries are `.cljc` (JVM-safe); draw paths are `:cljs`.

Depends on `gpu` (`kami.gpu` resolve) and `sprite-gpu` (SDF quads). Does **not**
depend on `webgpu` (avoids the inverted cycle from the pre-addendum-6 dedup).

The arbitrary-mesh fallback batches shared geometry through a per-mesh
mat4/color instance buffer and `drawElementsInstanced`. Static instance data is
cached instead of rebuilding and uploading it every frame. The downstream
modeler browser gate renders 20,000 sphere instances / 11.2 million resident
triangles in one draw on a forced WebGL2 context.

`kotoba.webgl` / `kotoba.webgl.glsl` are thin facades.

See ADR-2607102200 addendum 6.

## Test

```sh
kbb -M:test
```
