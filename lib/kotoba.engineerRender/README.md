# kotoba-lang/engineer-render

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-eng-render`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

2D/3D engineering rendering: schematic lines, pads, dimension annotations,
hatching, grid overlay, ruler, crosshair cursor, FEA color maps. Built on top
of the native `kami-render` (wgpu) provider.

| Namespace | Restored from | Purpose |
|---|---|---|
| `engineer-render.draw-list` | `EngDrawList` | Per-frame draw-command buffer (EDN commands — the `EngDrawCmd` enum's 10 variants map to `{:cmd <kind> ...}` maps) |
| `engineer-render.color-map` | `ColorMap` + `sample`/`hsv_to_rgb` | FEA post-processing color maps (jet/viridis/coolwarm/grayscale/rainbow) |
| `engineer-render.viewport` | `EngViewport` | Pan/zoom + screen<->world coordinate transforms |

What-to-draw is EDN; the wgpu command recorder itself stays native
(ADR-2607010930 principle). Depends on `kotoba-lang/engineer` for shared
contracts (constraint/DRC/etc).

## Status

Restored — all 3 concerns ported from the original 250-line Rust `lib.rs`
(draw-command variants kept as plain EDN maps rather than a closed enum, so
new command kinds don't require a schema change), with both original Rust
unit tests mirrored 1:1 in `test/engineer_render_test.cljk` (+1 smoke test,
+1 draw-list buffer sanity test not present in the original but covering
public API surface).

## Develop

```bash
kbb -M:test
```
