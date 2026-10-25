# kotoba-lang/kami-app-isekai

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-app-isekai`
Rust crate (2107 lines across `lib.rs`/`omniverse.rs`/`pipelines.rs`, deleted in
kotoba-lang/kami-engine PR #82 "Remove Rust workspace from kami-engine") as part of
the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What this is

The original crate was primarily a `wasm-bindgen` entrypoint (`run_isekai_v2`/
`run_isekai_v2_scene`) orchestrating `KamiApp` builder calls, a per-frame `on_update`
tick closure driving DEC field simulation (`kami_dec::ScalarField`/`EdgeField`/
`FaceField` — heat/moisture/wind/EM fields tightly coupled to native `Rc<RefCell<...>>`
state and `kami_pipelines` GPU adapters), voxel-chunk streaming, and an Omniverse/
PhysX/USD facade — native WASM/wgpu substrate with no meaningful portable
representation as a whole program.

Rather than attempt a 1:1 tick-loop port (which would carry no computational value
without the native simulation state it operates on), this restoration extracts the
genuinely **portable computational kernels and configuration data**:

| Namespace | From | Purpose |
|---|---|---|
| `kami-app-isekai.voxel-world` | `lib.rs` | 2-octave value noise, voxel palette, `terrain-height` generation rule (+ `terrain-voxel-at`, which uses it column-by-column), pre-authored demo-house voxel layout |
| `kami-app-isekai.pipelines` | `pipelines.rs` | breathing-gradient clear-color function (pure time -> RGB) |
| `kami-app-isekai.omniverse` | `omniverse.rs` | default USDA scene-description text constant |
| `kami-app-isekai.heightmap-color` | *(new, not a restoration)* | pure height -> RGB gradient + grid sampler, giving `terrain-height` its first real visualization (see Render proof below) |

**Excluded entirely** (native-only, no portable logic): the wasm-bindgen entrypoints,
the per-frame DEC tick closure and its native `Rc<RefCell>` field state, voxel-chunk
GPU streaming/upload, and the Omniverse/USD/PhysX parse-and-drive orchestration.

## Render proof: `terrain-height` as a real, pixel-verified heightmap

`voxel-world/terrain-height` (a 2-octave value-noise ridge, `[wx wz] -> height`,
confined to `[terrain-height-min, terrain-height-max)` = `[18.0, 30.0)`) had never
produced a single rendered pixel anywhere in this repo — it only ever fed
`terrain-voxel-at`'s stone/grass/air `cond`. `render-test/render_pixel_test.cljk`
closes that gap: it samples `terrain-height` over a 40x40 grid of world `(x,z)`
coordinates, maps each height to a color via `heightmap-color/height->color` (deep
blue low -> grass green mid -> near-white high), and draws one colored `:rect` quad
per cell through [kotoba-lang/webgpu](https://github.com/kotoba-lang/webgpu)'s
`kami.sprite-gpu` GPU-instanced-quad pipeline in a real headless-Chromium/WebGL2
canvas (`kami.playwright`), then `readPixels`-verifies specific cells: the rendered
byte at `terrain-height`'s exact analytic floor (world origin `(0,0)`, height
`18.0` exactly) matches `height->color`'s expected byte exactly, ditto for the
highest- and closest-to-median-height sampled cells, plus a monotonic
brightness/blueness check across the three — grounded in the kernel's own math,
not a guessed color.

This is a test/demo-only sibling dependency, **not** part of this repo's own
`deps.edn` (`kbb -M:test`/`-M:lint` stay zero-dep): it needs sibling checkouts
of `kotoba-lang/webgpu` and `kotoba-lang/expr` next to this repo (the same layout
the west-managed superproject already uses, `orgs/kotoba-lang/{kami-app-isekai,
webgpu,expr}`). Run with `kbb -M:render-test` (see `bb.edn`); see
`.github/workflows/ci.yml`'s `render-verify` job for the exact CI layout, including
the cross-platform headless-Chromium resolution fix (`kotoba-lang/webgpu` PR #9's
technique, reapplied inline since that PR isn't merged yet).

## スライムハント (Slime Hunt) — a real, playable win/lose game

`game.html` + `dev/slime_hunt/game.cljk` + `public/games/slime-hunt/{scene.edn,logic.cljc}`:
a real-time dodge/collect arena, the first actual playable win/lose game to use this repo's
`voxel-world`/`heightmap-color` terrain kernel for anything besides a standalone visualization.
WASD/arrows move the player; dodge 3 elemental slimes (3 lives, drive's exact mechanic) while
collecting all 8 glowing "kotodama orb" pickups. Same production-proven architecture as
[gftdcojp/network-isekai](https://github.com/gftdcojp/network-isekai)'s live games (e.g. "KAMI
Drive"): `logic.cljc` (a small guest-DSL, not full Clojure — see `kotoba-lang/kami-engine`'s
`kami-engine-clj`) is compiled to real WASM bytes via `kotoba.engine-clj`, instantiated against
`kami.host` (`kotoba-lang/webgpu`'s browser ECS/ABI), ticked every `requestAnimationFrame`, and
rendered via `kami.scene2d` + `kami.webgl` (GPU-instanced 2D quads, WebGL2 — the SAME
`kami.sprite-gpu` pipeline the render-proof above pixel-verifies, not Canvas2D). The player's
visual + move-speed and the 3 slime variants are composed via `kotoba-lang/kami-isekai-assets`
(`kami.isekai.chargen`/`monsters`/`status`), and the arena background is a static bake of this
repo's own `terrain-height` + `heightmap-color` kernel — see `scripts/gen_scene.cljk`, which
regenerates `public/games/slime-hunt/scene.edn` from all of the above (nothing hand-drawn).

Dev-only, needs sibling checkouts next to this repo (same layout the render-test above uses):
`kotoba-lang/{webgpu,kami-isekai-assets,kami-engine}` — see `deps.edn`'s `:gen-scene`/
`:cljs-game` aliases for exactly which ones each step needs.

```bash
kbb -M:slime-hunt-scene   # (re)bake scene.edn from the composers + terrain kernel
kbb -M:slime-hunt-build   # compile dev/slime_hunt/game.cljk -> dev/out/game.js (cljs.main, no npm)
python3 -m http.server 8931   # serve the repo root
# open http://localhost:8931/game.html
```

## Status

Restored (scoped) — 12 `kbb -M:test` tests / 53 assertions, 0 failures (the
original had no `#[test]`s in any of the 3 files; these provide coverage of the
ported kernels/data), plus the render-test above (not part of `kbb -M:test`) and
the スライムハント playable game above (verified by real Playwright playthroughs — see
this feature's PR description for the win-path and lose-path evidence).

## Develop

```bash
kbb -M:test
kbb -M:lint
kbb -M:render-test   # pixel-verified GPU render proof (needs sibling kotoba-lang/webgpu + expr checkouts)
```
