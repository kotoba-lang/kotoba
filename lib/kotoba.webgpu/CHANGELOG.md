# Changelog

kami-webgpu — declarative WebGPU + UI/input/audio/state from EDN (hiccup for the GPU).

## Unreleased

### Graph pipelines can declare `:blend` (2026-08-04)

`build-pipeline` recognised `:shader :cull :depth :color :fullscreen :fragment`
and nothing else — `blend` appeared **nowhere** in `kami/webgpu.cljs`, so every
pipeline this executor could build was opaque. That is the single structural
reason the alpha-blended half of the open-world pipeline family had nowhere to
live: `kami.pipelines` describes `:water`, `:particle`, `:atlas` (and
`:vegetation`) as `:blend :alpha`, and this executor could not express any of
them regardless of whether their shaders existed. They do exist —
`kami-engine/kami-render/src/shaders/scene_particle.wgsl` is a complete
camera-facing billboard with age/life fade — they simply had no pipeline slot.
See ADR-2608040400.

A pipeline may now declare `:blend :alpha`; `:none` and absent stay opaque. The
vocabulary is deliberately `kami.pipelines`' own `#{:none :alpha}` so a graph
names a blend the same way that table does, and `test/graph_blend_test.cljk`
fails if the two drift.

`:alpha` is straight (non-premultiplied) source-alpha over. An unknown mode
throws rather than rendering opaque — a silently-ignored blend reads as a shader
bug until someone finds the typo, the same failure the custom `:uniforms` path
is guarded against. A pipeline declaring `:blend` with no `:color` target also
throws.

**No existing pipeline declares `:blend`**, so every graph in this repo builds a
byte-identical descriptor to before. **Not verified on a real GPU**: no gate in
this repo can drive a WebGPU device, so this ships proven only to the level of
"the descriptor is constructed and nothing existing changed". The first caller to
use it should confirm on hardware.

### Custom render graphs: caller-supplied uniforms, and SSAO tiering that stays out of their way (2026-08-03)

Two changes that together let a domain package drive this executor with its own
graph instead of reaching past it to `org-w3-webgpu` and growing a second
renderer.

**`:uniforms` + `{:uniform <name>}` binds + `write-uniform!`.** `build-bind`
recognised exactly four uniform binds — `:uniform`, `:atmosphere-uniform`,
`:ssao-uniform`, `:style-uniform` — all engine-owned buffers of fixed size, so a
graph with a uniform of its own had no way to express one. A graph may now
declare `{:uniforms {:my-thing {:size 192}}}`, bind it with
`{:uniform :my-thing}`, and write it with
`(write-uniform! ctx :my-thing floats)`. Unknown names throw on both paths: an
unbound uniform renders a frame of zeroes, which reads as a shader bug for as
long as it takes to find the typo.

**`adaptive-ssao-graph` no longer invents an `:ssao` target.** Its enabled
branch did `(assoc-in graph [:targets :ssao :scale] scale)` unconditionally, so
any graph that declared no SSAO target got one carrying a scale and no
`:color`/`:depth` — and target allocation then called `createTexture` with
`format: null`. Every custom graph therefore failed at init before reaching its
own pipeline, with the real error swallowed by the WebGL2 fallback's `.catch`.
It now returns the graph untouched when `:targets` has no `:ssao`. The default
graph declares one, so its behaviour is unchanged.

Found while building `kotoba-lang/byoubu-gpu`, which renders a backdrop as one
fullscreen pass through this executor — verified in Chrome on a real WebGPU
device.

### Reuse geometry command streams with WebGPU render bundles (2026-07-16)

World streaming changes instance-buffer contents, but not the pipeline/bind-group/
geometry draw command sequence. The renderer now records one compatible
`GPURenderBundle` per active geometry pipeline and replays it across frames. A
geometry-group signature invalidates the bundle when resident draw counts change;
instance-buffer growth clears all bundles because it replaces the GPU buffer handle.
Backend frame evidence reports `:render-bundle-count` for deterministic browser gates.

Royale's fixed-frame Chromium SwiftShader gate at 319 submitted instances recorded
two bundles, one queue submit per frame, no GPU validation errors, and no device loss.
Under the same 180-frame warmup / 5-second sample, current-main SSAO measured
75.4 ms median / 79.8 ms p95 before and 74.9 ms / 78.5 ms after (0.7% median,
1.6% p95 improvement). This removes JS command-recording work but does not pretend
to close the software-GPU raster wall or the 16.7 ms hardware target. A tested
half-resolution-HDR alternative regressed to 75.2 ms and was rejected.

### `draw!` caches per-frame instance-buffer work for a static scene (2026-07-10)

Found via `com-junkawasaki/root` ADR-2607100100's M4 investigation: a real-browser
benchmark (`kami-app-amenominaka`, Playwright + full Chromium, static scene, 60 frames)
showed `draw!`'s frame time scaling with instance count even when nothing in the scene
changed between frames — 15,000 instances cost ~34ms/frame (≈29fps). Reading the code
found why: every `draw!` call unconditionally re-sorted `:instances` by geometry kind,
re-grouped them, re-marshaled the packed model-matrix+color+material `Float32Array`, and
re-uploaded it to the GPU via `write-buffer!` — even for a scene composed once and drawn
every `requestAnimationFrame` with the exact same value, the overwhelmingly common usage
pattern.

`init!`'s returned context now carries an `:instance-cache` atom; `draw!` factors that
sort/group/centroid/marshal work into a new pure `compute-instance-data`, keyed on
`(:instances ir)` by **reference** (`identical?`, not `=` — cheap, and correct for the
common "compose once, draw every frame" pattern; a caller that rebuilds an equal-but-
not-identical instances vector every frame just won't hit the cache, not a correctness
issue) and skips the GPU `write-buffer!` entirely on a cache hit.

Backward compatible: a caller that builds a context map without going through `init!`
(no `:instance-cache` key) just always takes the cache-miss path — same behavior as
before, no crash (`some->` guards every cache read/write).

Measured improvement (same benchmark, same machine, before → after): 5,000 instances
11.4ms→0.47ms/frame; 15,000 instances 34.0ms→0.85ms/frame; 20,000 instances (capped at
`MAX-INST` 16,384) 36.3ms→1.03ms/frame — roughly a 30-40× reduction in per-frame cost at
the high end, confirmed by re-running the existing `kami-app-amenominaka` M2 real-browser
smoke test (`test/render/verify_m2_render.cljs`) unchanged and getting the identical
correct screenshot. `kbb -M:test`'s existing `.cljc` suite (unaffected — this change is
`.cljs`-only) stays green throughout.

Note this closes the *actual* wall ADR-2607100100 M4 investigated — a redundant re-upload,
not a GPU rendering-capacity limit. `wgsl` `@compute`-based GPU-side instance generation
(the ADR's original speculative M4 direction) was not pursued since it wouldn't have
addressed this specific, now-measured bottleneck; it remains available as future work if a
*different* real wall is found later (e.g. from the still-unaddressed `MAX-INST` 16,384
hard cap silently truncating larger scenes — a correctness gap, not a performance one,
flagged separately).

### Dedup pass across kotoba-lang/{sprite-gpu,gpu,webgl} (2026-07-09)

Three standalone repos (`kotoba-lang/sprite-gpu`, `kotoba-lang/gpu`, `kotoba-lang/webgl`) each
carried a duplicate of a namespace that also lives here (`kami.sprite-gpu`, `kami.gpu`,
`kami.webgl`), left over from the abandoned "clj-wgsl Phase-4" split-migration + independent
"restore" commits (2026-07-02). All three pairs were diffed in detail rather than assumed:

- **`sprite-gpu`** — `kami.sprite-gpu` (here) wins. It has the `:rect` half-extent bug fix (PR #10,
  above) that the standalone repo's copy never received; the standalone repo's own git history has
  no commits beyond CI/lint housekeeping since its restore. `kotoba-lang/sprite-gpu`'s
  `kotoba.sprite-gpu` is now a thin re-export of this namespace.
- **`gpu`** — `kami.gpu` (here) wins, though the diff is docstring-only (no functional bug on
  either side — every `def`/`defn` body was byte-identical). `kami.gpu` reflects the more current
  "capability-gated render-graph contract" doc pass; the standalone repo received no comparable
  work. `kotoba-lang/gpu`'s `kotoba.gpu` is now a thin re-export of this namespace.
- **`webgl` — the SURPRISING one: the standalone repo was more current here, not this repo.**
  `kotoba-lang/webgl`'s `kotoba.webgl` was already `.cljc` with a `#?(:clj ...)` fallback branch
  (JVM-safe capability queries + explicit "browser-only executor" errors instead of blowing up on
  `js/navigator`), backed by its own JVM test (`webgl-test`). `kami.webgl` here was plain `.cljs`
  with none of that — a real feature gap, not just docs. So instead of repointing consumers away
  from the standalone repo's content, **that `.cljc` structure was ported INTO this repo**:
  `src/kami/webgl.cljs` → `src/kami/webgl.cljc` (adds the `:clj` branch, verbatim-ported from
  `kotoba.webgl`'s), `src/kami/webgl/glsl.cljs` → `src/kami/webgl/glsl.cljc` (pure data, no
  reader-conditional needed — its content was already byte-identical between the two repos), and a
  new `test/webgl_test.cljk` (ported from the standalone repo's) wired into `kbb -M:test`, giving
  `kami.webgl` JVM coverage it never had. This also matches this repo's own stated design
  philosophy ("A `.cljc`-first library", per `deps.edn`'s header comment). `kotoba-lang/webgl`'s
  `kotoba.webgl` is now, in turn, a thin re-export of this (now at-parity) namespace.

Consumers: `network-isekai`, `net-babiniku`, and everything else already depending on this repo are
unaffected (same public API, same behaviour, `kami.webgl` gained functionality rather than losing
any). `kotoba-lang/scene2d` and `kotoba-lang/webgl` (the repo, for its own internal use before this
change) have been repointed from the standalone `sprite-gpu`/`gpu` repos to depend on this repo
directly. See each affected repo's own README/CHANGELOG for its side of this.

### Renderer (`kami.webgpu`)
- Declarative WebGPU from a pure EDN render-IR — CLJS drives the browser WebGPU API directly
  (no Rust, no wasm, no per-frame string marshaling).
- Render graph as data: shaders, offscreen targets, samplers, pipelines, and an ordered
  `:passes` array are all EDN; the executor interprets them (reorder/add passes by editing data).
- Real shadows: a sun shadow-map pass + PCF sampling, expressed as the first `:passes` entry.
- PBR materials as per-instance EDN (metallic / roughness / emissive).
- Known footgun fixed: GPU buffers written with `writeBuffer` need `COPY_DST`, or the write
  silently no-ops and the buffer reads as zeros (the original "clear works, no geometry" bug).

### Data-driven domains (each EDN, ADR-0040)
- `kami.ui` — HUD as EDN → DOM overlay (`:panel` / `:bar` / `:text` / `:minimap`).
- `kami.input` — key/pointer bindings → axes & actions, as data.
- `kami.audio` — sound cues as EDN recipes, synthesized via Web Audio.
- `kami.fsm` — animation/behaviour state machines as data.
- `kami.physics` — collision layers + matrix as data; `separate` resolves overlaps.
- `kami.netsync` — replication schema (what syncs) as data; `snapshot` / `apply-snapshot` / `interp`.
- `kami.level` — spawns + shrinking zone (storm) + objective as data.
- `kami.webgpu.ir` — render-IR shape + a camera rig (`rig->camera`), cross-platform `.cljc`.

### Cross-platform (ADR-0042)
- The `.cljc` interpreters are the same source the web (CLJS), native (kotoba-clj→WASM, via
  kami-script-runtime), and JVM (babashka) all run. Verified determinism: the native scatter RNG
  matches the web's xorshift sequence — same EDN → same world.

### Tests
- `kbb -M:test` — the `.cljc` interpreters on the JVM (examples + properties; 8 tests / 42 assertions).
- `kbb -M:verify` / superproject `scripts/verify-clj-everywhere.sh` — all surfaces in one command
  (JVM + native WASM + native renderer).
- CI: GitHub Actions runs `kbb -M:test` on every push.
- Bug found via coverage work and fixed upstream: kotoba-clj `into` overflowed when the dst was
  at exact capacity (a vector literal); now returns a correctly-sized new vector.
- **Bug fixed: `kami.sprite-gpu/prim->quad`'s `:rect` case doubled the rendered width/height.**
  A prior agent (kotoba-lang/kami-isekai-assets PR #4) found this while validating a Canvas2D
  probe against the GPU path but left the fix to this repo. `:w`/`:h` are FULL width/height in
  the sprite2d vocabulary (`kami.sprite2d.cljs`'s reference `:rect` painter draws
  `fillRect(dx-w/2, dy-h/2, w, h)`), but `prim->quad` was passing them straight into `:size`,
  which the sprite-SDF vertex shader consumes as a HALF-extent (quad corners ±1 scaled by
  `:size`) — a `[:rect {:w 100 :h 50}]` rendered at ~200×100px instead of ~100×50px. Fixed by
  halving `:w`/`:h` in `prim->quad`; `:r`/`:rx`/`:ry` (circle/ellipse/arc) were already radii
  (= half-extents) and needed no change. New pixel-verified regression test
  (`test/playwright_rect_extent_test.cljk`, wired into `kbb -M:render-test`) renders the probe in a
  real headless WebGL2 browser and measures its on-screen bounding box; confirmed it fails
  against the pre-fix code (measured ~200×100px) and passes against the fix (~100×50px).
  Investigated before fixing: no scene in this repo or in `gftdcojp/network-isekai`'s
  `public/games/*/scene.edn` (26 of 31 use `:rect`) currently renders through this GPU path —
  every one of those scenes uses `:render/sprite2d` (the correct Canvas2D painter); the
  GPU/instanced path (`:render/gpu2d`) exists in `network-isekai`'s `isekai/game.cljc` but no
  scene opts into it. `kotoba-lang/kami-isekai-assets`'s render-adapter does feed this path, but
  its own render_pixel_test.clj only exercises `:ellipse`/`:circle` primitives (the slime
  preset), not `:rect`. So no shipped/tested content depended on the buggy half-extent
  behaviour — the fix is a straight correctness fix, not a breaking behaviour change to any
  live consumer.
