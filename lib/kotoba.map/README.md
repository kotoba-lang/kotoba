# kotoba-map

[![CI](https://github.com/kotoba-lang/map/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/map/actions/workflows/ci.yml)

Pure-Clojure `.cljc` domain-logic port of `kami-map` — the KAMI Engine
WebGPU map renderer for `maps.etzhayyim.com` (`kotoba-lang/kami-engine`,
Rust) — per ADR-2607010930 (clj-wgsl migration Phase 4, kami-engine
retirement).

No network, no I/O (except a JVM-only `String`/byte-array conversion in
`kotoba.map.mvt`, guarded by `#?(:clj ...)`). Portable across JVM /
ClojureScript / SCI / GraalVM.

**`kotoba.map.data` is the one exception** — see its own section below. It
is not part of the `kotoba.map` aggregate namespace's "no I/O" namespace
list; it is an opt-in data layer with I/O reached only through injected
ports, per this repo's own port-not-embed convention.

## Namespaces

| Namespace | Ported from (Rust) | What it does |
|---|---|---|
| `kotoba.map.mvt` | `kami-map/src/mvt.rs` (whole file) | Self-contained Mapbox Vector Tile (MVT) PBF decoder: varint/tag/length-delimited field reading, zigzag-delta geometry command stream, `Value` message decoding, layer/feature filtering. |
| `kotoba.map.color` | `parse_hex_color` (`lib.rs`) | `#rrggbb`/`#rrggbbaa` → `[r g b a]` doubles. |
| `kotoba.map.constants` | Hardcoded literals throughout `lib.rs` | Zoom thresholds, scene-scale radii, lat/zoom clamps, default tile URLs, Earth radius — extracted into `resources/kami/map/constants.edn` (canonical) and mirrored here as I/O-free defs. |
| `kotoba.map.projection` | `active_projection_mode`, `cosmic_blend`, `cosmic_system_blend`, `clamp_lat`, the `set_zoom`/`on_wheel`/`fit_bounds` zoom clamp | Projection-mode selection and viewport-value clamps. |
| `kotoba.map.sphere` | `globe_position`, `globe_normal`, `globe_lng_lat_from_position`, `ray_sphere_hit`, `sphere_mesh_at`, `ring_mesh`, `ring_ribbon_mesh`, `spiral_ring_mesh`, `orbit_xz` | Globe vector math and procedural ring/spiral mesh generation (flat `pos+normal+uv` vertex buffers, matching the Rust `(Vec<f32>, Vec<u32>)` shape). |
| `kotoba.map.orbital` | `scene_cislunar_orbit_radius`, `scene_solar_orbit_radius`, `orbital_phase_angle`, `orbital_scene_position`, `equatorial_anchor`, `display_body_radius` | Orbital/celestial scene-scale math for the Cosmic projection mode. |
| `kotoba.map.fly` | The fly-animation block of `KamiMap::frame` + `fly_to` | Fly-to camera easing as a pure state-transition step function. |
| `kotoba.map.tile_url` | `get_dem_tile_url` | `{z}/{x}/{y}` tile URL templating. |
| `kotoba.map.input` | `input.rs`'s Globe/Cosmic drag branch, `on_pointer_down`/`up` | Pointer-drag panning for Globe/Cosmic projection modes, as pure state transitions (no `unsafe static mut`). |

## Data layer: `kotoba.map.data`

Client-side-first tile data, wired to the CLJC restoration of kotoba's
content-addressed graph (`90-docs/adr/2607010930-clj-wgsl-migration.md`
Phase 6, `kotoba-lang/root` superproject): kotobase.net serves only
`block.get` CID lookups (delivery-only), and the browser resolves +
assembles tiles client-side.

```
tile {:z :x :y} + layer
  -> quad-store.core index lookup (via kqe.core/query)     -- resolve-tile-cid
  -> CID
  -> kotoba-client.core/hydrate-via-blocks (CID-verified)   -- fetch-tile-layer
  -> raw MVT bytes
  -> kotoba.map.mvt/decode-layer-features                   -- fetch-tile-layer
  -> {:features [...]}
```

```clojure
(require '[quad-store.core :as qs] '[kotoba.map.data :as data])

;; however the tile index gets populated (sync/commit from kotobase.net):
(def db (data/index-tile-layer (qs/empty-db) {:z 14 :x 2620 :y 6332} "roads" "bafy...cid"))

;; client-side fetch + decode, ports injected (no owned I/O):
(data/fetch-tile-layer {:db db :fetch-block my-block-get-fn :store my-store}
                        {:z 14 :x 2620 :y 6332} "roads")
;; => {:features [...]}  (nil if the tile/layer isn't indexed)
```

This is an **alternative** data source, not a replacement for
`kotoba.map.tile-url`'s `{z}/{x}/{y}` HTTP template — a host with only a
conventional XYZ tile server still uses `tile-url`. `kotoba.map.data` is
for hosts that resolve tiles through kotoba's IPLD graph instead.

**Not in this namespace** (tracked follow-ups, not silently omitted):
visible-tile computation from a viewport (depends on the not-yet-ported
`kami-geo` crate, see "Unported" below — this namespace takes tile keys as
input, it does not compute them), spatial (H3) tile-index sharding
strategy, and populating the tile index in the first place (this
namespace only reads it).

## Unported (out of scope) — and why

This crate's core is a `wasm_bindgen` WebGPU renderer; most of it is
inherently GPU-bound or JS-bridge code with no portable domain logic:

- **The `KamiMap` struct and its `wgpu`-resource fields** (device, queue,
  surface, pipelines, bind groups, buffers, textures, depth/shadow maps) —
  GPU state, not portable.
- **`KamiMap::create`, `frame`, `resize`, `upload_tile`, `upload_dem_tile`,
  render-pass encoding** — GPU pipeline setup and draw calls.
- **`rebuild_mesh_for`, `add_layer_from_mesh`, `build_layer`,
  `build_globe_tile_mesh`, `push_transient_mesh`, `make_unlit_bind_group`,
  `build_cosmic_meshes`, `build_atmosphere_meshes`** — these call into
  `kami_geo::mesh` / `kami_render` (line-ribbon tessellation, tile-quad
  geometry) and create `wgpu::Buffer`s directly; the not-yet-ported
  `kami-geo`/`kami-render` crates and GPU buffer allocation are both out of
  scope for this port.
- **`unproject`, `project`, `fit_bounds`, `visible_globe_tiles`,
  `globe_camera_position`, `sphere_view_projection`, `update_camera_uniform`,
  the Flat/Web-Mercator branch of `input.rs`'s `on_pointer_move`** — all call
  `kami_geo::projection::{lng_lat_to_world_px, world_px_to_lng_lat,
  visible_tiles}`, which live in the not-yet-ported `kami-geo` crate. When
  `kami-geo` is ported, these become straightforward pure-function ports on
  top of it.
- **`tle_scene_position` / `tle_scene_position_from_cache`** — SGP4 TLE
  orbit propagation depends on the external `sgp4` crate's numerical
  propagator (and `sgp4::chrono` date handling); out of scope for a
  domain-logic port. `kotoba.map.orbital` covers the surrounding
  scene-scale math (`scene_cislunar_orbit_radius` etc.) that this feeds
  into.
- **`set_weather_preset`** — delegates to `kami_atmosphere_scene::resolve_weather`,
  a separate not-yet-ported crate.
- **`compare.html` / `test.html`** — browser wasm-bindgen test harness
  pages, not domain logic.
- **`wasm-bindgen` JS bridge surface itself** (`#[wasm_bindgen]` methods
  returning JSON strings) — an FFI concern, not domain logic; the pure
  functions underneath (mvt decode, color parse, projection math) are
  ported and can be re-wrapped by a real host bridge later.

## Usage

```clojure
(require '[kotoba.map.mvt :as mvt])

(mvt/decode-layer-features pbf-bytes {:z 14 :x 2620 :y 6332} "roads")
;; => {:features [{:geometry {:type :line-string :coordinates [[lng lat] ...]}
;;                 :properties {"highway" "primary"}} ...]}

(require '[kotoba.map.color :as color])
(color/parse-hex-color "#ff8800")
;; => [1.0 0.53333... 0.0 1.0]

(require '[kotoba.map.projection :as proj])
(proj/active-projection-mode 3.0)
;; => :globe

(require '[kotoba.map.sphere :as sphere])
(sphere/globe-position 139.767 35.681 2048.0) ;; Tokyo, on a globe of radius 2048

(require '[kotoba.map.fly :as fly])
(-> (fly/fly-target [0.0 0.0] 2.0 139.767 35.681 8.0 1200.0)
    (fly/step 600.0))
```

## License

Apache License 2.0.
