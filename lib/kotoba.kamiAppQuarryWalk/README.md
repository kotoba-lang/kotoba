# kotoba-lang/kami-app-quarry-walk

Safety-gated `.kotoba` configuration contract restored from the legacy `kami-engine/kami-app-quarry-walk`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace from
kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

The original crate (76 lines) was almost entirely a `wasm-bindgen` entrypoint
(`run_quarry_walk_v2`) orchestrating `KamiApp`/`kami_pipelines`/`kami_terrain_scene`
builder calls — native WASM/wgpu substrate with no portable logic of its own ("No
pipeline code here: game logic = biome selection + spawn + camera/input wiring. All
rendering reuses kami_pipelines.", per its own doc comment).

What IS portable is the game's **configuration**: spawn position, camera mode,
terrain/water adapter parameters. Typed scalar exports preserve that configuration
without exposing an open-ended host map. Rendering, input, terrain streaming, WebGPU,
physics, and the game loop remain capability-gated Kami responsibilities.

## Status

The reference evaluator, restricted JavaScript, and instantiated typed Wasm must agree
on observable values and ABI behavior. Generated Wasm bytes need not be identical.

## Develop

```bash
kbb -M:test
```
