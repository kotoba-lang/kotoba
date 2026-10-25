# kotoba-kami-app-shibuya

[![CI](https://github.com/kotoba-lang/kami-app-shibuya/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/kami-app-shibuya/actions/workflows/ci.yml)

**Shibuya street digital-twin scene model, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) port of the `kami-app-shibuya`
Rust crate (`shibuya.etzhayyim.com` — OSM city mesh + kami-genesis
full-physics multi-agent sim), per ADR-2607010000. This library owns the
pure data/config layer: the `Scene` model (buildings, roads, point objects),
its derived geometry (centre, static-obstacle bounds, road-sampled spawn
points), the 4-DOF agent URDF generator, and the point-asset
footprint/colour lookup tables. It does **not** own wgpu rendering,
wasm_bindgen entry points, or physics stepping — see "Unported" below.

No network, no I/O — callers read/parse scene EDN (e.g. from
`resources/kotoba/shibuya/*.edn`) and hand it to `parse-scene`. Portable
`.cljc` across JVM / ClojureScript / SCI / GraalVM.

## Maturity

| | |
|---|---|
| Role | capability (scene/config data, pre-physics) |
| Tests | 10 tests / 89 assertions, all green (synthetic fixture) |
| Physics stepping | not ported — see below |
| Rendering | not ported — see below |

## Namespace

Single namespace, `kotoba.shibuya` — the ported surface (scene model +
agent spawn config + URDF generation + lookup tables) is small enough that
splitting it into `kotoba.shibuya.scene` / `kotoba.shibuya.agent` etc.
would add indirection without a real seam. Revisit if/when physics stepping
or a render-IR layer is ported here.

## Contract

```clojure
(require '[kotoba.shibuya :as shibuya]
         '[clojure.edn :as edn]
         '[clojure.java.io :as io])

;; caller reads/parses EDN — this library performs no I/O
(def raw (with-open [r (io/reader (io/resource "kotoba/shibuya/shibuya_scramble.synthetic.edn"))]
           (edn/read (java.io.PushbackReader. r))))
(def scene (shibuya/parse-scene raw))

(shibuya/valid-scene? scene)
(shibuya/scene-center scene)             ;; => [cx cy 0.0]
(shibuya/building-obstacles scene)       ;; => [{:min [...] :max [...]} ...]
(shibuya/spawn-points scene 6)           ;; => [{:pos [x y 3.0] :yaw radians} ...]

;; pre-physics agent setup (size/mass/color/drive/steer-phase) — does not
;; construct or step an articulation/contact world
(shibuya/agent-spawn-config (first (shibuya/spawn-points scene 6)) 0)

;; pure string-template URDF for a 4-DOF floating-base agent body
(shibuya/agent-urdf [4.2 1.9 1.6] 1100.0)

;; point-asset lookup tables
(shibuya/object-footprint "tree")        ;; => [4.0 4.0]
(shibuya/object-color "traffic_signals") ;; => [0.96 0.74 0.10]
```

## Fixture

`resources/kotoba/shibuya/shibuya_scramble.synthetic.edn` — a small,
hand-authored, invented scene (5 buildings, 3 roads, 3 point objects) used
for test coverage only. **The real OSM-derived, ODbL-baked fixture the
original Rust crate loaded is not present anywhere in this monorepo
checkout** (`70-tools/e7m-sim/scenes/shibuya/shibuya_scramble.scene.json`,
built offline by `osm_to_citymesh.py` — verified absent, not merely
unfound). This repo does not fabricate or approximate real Shibuya
geometry; the synthetic fixture exists purely so `kotoba.shibuya` has
something to parse and exercise in tests, and every object in it carries
`:provenance "synthesized-demo"` accordingly.

## Unported (stays Rust + wgpu in `kami-engine`, or unported anywhere)

Per ADR-2607010000's scope decision, only pure data/config math was
ported. The following remain host-adapter/engine concerns in the original
crate and were intentionally left out:

- **`MeshAcc` / `push_mesh`** — wgpu render-mesh batch accumulation; a
  render-IR concern, not scene/config data.
- **All `#[wasm_bindgen]` entry points** (`run_shibuya_v1`,
  `run_splat_viewer_v1`, `run_splat_physics_v1`,
  `shibuyaLoadSplat`/`shibuyaLoadSplatPly`/`shibuyaClearSplat`) — browser/JS
  host bindings, not domain logic.
- **The `SPLAT` thread_local + Gaussian-splat overlay** — GPU point-cloud
  rendering, no kotoba equivalent needed.
- **`publish_pick`** — writes to `window.__shibuya_pick`; a browser-DOM
  bridge, not scene data.
- **Physics stepping** (`Agent::step`, `Agent::body_world`, `ContactWorld`,
  `Articulation3dConfig`, `kami_articulated::parse_urdf` usage) — no kotoba
  port of the kami-genesis rigid-body/articulation contact solver exists
  anywhere in `kotoba-lang` yet (verified by grep across `orgs/`). Ported
  `agent-urdf` here stops at generating the URDF *config string*; parsing
  it into an articulation and stepping contacts is future work once the
  solver itself is ported. `agent-spawn-config` covers everything
  `Agent::new`/`Agent::place` set up *before* stepping began.

## Why

`kami-app-shibuya` is being demoted from "engine semantics authority" to
"adapter that executes a kotoba contract" (ADR-2607010000). This library is
the kotoba-side scene/config contract: buildings, roads, point-asset
metadata, and pre-physics agent configuration as plain data, independent of
whichever renderer or physics adapter eventually consumes it.

## License

Apache License 2.0.
