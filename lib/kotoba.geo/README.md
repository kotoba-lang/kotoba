# kotoba-lang/geo

[![CI](https://github.com/kotoba-lang/geo/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/geo/actions/workflows/ci.yml)

Geospatial domain logic in pure Clojure `.cljc`: Web Mercator (EPSG:3857)
projection, tile coordinate math, GIS mesh generation (flat + globe/sphere),
billboard marker data, and a pure tile-cache state machine.

This is a **domain port**, not a renderer. No network, no I/O, no GPU calls
in any `kotoba.geo.*` namespace — every function is a pure transform over
plain Clojure data (maps/vectors), portable across JVM / ClojureScript / SCI.

`src/kotoba/geo_golden.kotoba` is the first native Kotoba policy-v7
qualification slice. It covers the Tokyo Web Mercator forward/inverse golden
and an outward-facing globe-patch triangle using explicit f64 arithmetic and
qualified sin/cos, exp/log, and atan2. CI compares the CLJC oracle with the
Kotoba reference executor, restricted JavaScript, and typed Wasm. General
map/vector mesh APIs remain CLJC until a structured f64 ABI is qualified.

## Origin

Ported from `kami-engine/kami-geo` (Rust), part of the
[kami-engine](https://github.com/kotoba-lang/kami-engine) game-engine
workspace that is being retired in favor of pure-Clojure "kotoba" authority
repos (`90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md`). The
`kami-geo` crate had been deleted from `kami-engine`'s working tree without
being committed; this repo recovers and preserves that domain logic before
the deletion is committed upstream. See git history of `kami-engine` at
`kami-geo/` for the original Rust source (`Cargo.toml`,
`src/{lib,billboard,mesh,projection,tile}.rs`).

## Namespaces

| Namespace | Ported from | Notes |
|---|---|---|
| `kotoba.geo.constants` | `projection.rs` / `tile.rs`/ `mesh.rs` literals | Extracted numeric constants; EDN authority mirror at `resources/kotoba/geo/constants.edn` (checked byte-for-byte by `kotoba.geo.constants-test`, same pattern as `kotoba-lang/kami-scene-contracts`) |
| `kotoba.geo.projection` | `projection.rs` | WGS84 ⇄ world-px ⇄ tile-coord, `visible-tiles` viewport query |
| `kotoba.geo.tile` | `tile.rs` | Tile cache / fetch-state / LRU eviction, as pure functions over an immutable manager map (the Rust source was a `&mut self` struct) |
| `kotoba.geo.mesh` | `mesh.rs` | Tile quads, DEM-displaced flat/globe patches, GeoJSON-ish line ribbon / polygon fill / polygon extrude, ear-clipping triangulation, antimeridian-safe ring splitting |
| `kotoba.geo.billboard` | `billboard.rs` | Billboard marker/label data (position/size/anchor/color/atlas-index) |
| `kotoba.geo.noise` | `mesh.rs` (private helpers) | Procedural value-noise / fBm used by `globe-tile-patch`'s default relief |
| `kotoba.geo.vec3` / `kotoba.geo.math` | `mesh.rs` / `projection.rs` (private helpers) | Small portable 3-vector and scalar-math helpers (`#?(:clj ... :cljs ...)` so trig/sqrt/etc. work on JVM and ClojureScript) |

## Usage

```clojure
(require '[kotoba.geo.projection :as proj])
(require '[kotoba.geo.mesh :as mesh])

(proj/lng-lat->world-px (proj/lng-lat 139.7671 35.6812) 12.0)
;; => {:x ... :y ...}

(proj/visible-tiles (proj/lng-lat 0.0 0.0) 2.0 512 512)
;; => [{:z 2 :x ... :y ...} ...]

(mesh/tile-quad)
;; => {:vertices [...] :indices [...]}  ; pos3+norm3+uv2 interleaved, triangle-list indices
```

## What's unported (out of scope)

The recovered `kami-geo` Rust crate was already almost entirely pure
domain logic (no `wgpu`/GPU calls, `kami-render` was an unused declared
dependency) — nothing meaningfully GPU-coupled needed to be dropped. Two
narrow exceptions:

- **`BillboardInstance`'s `#[repr(C)] derive(bytemuck::Pod, Zeroable)`
  byte-layout attributes** (48-byte packed GPU vertex-buffer struct). This
  is a wgpu buffer-upload concern with no Clojure equivalent.
  `kotoba.geo.billboard/billboard-def->instance` produces the same *field
  values* as plain data; a renderer-side adapter is responsible for
  packing them into an actual GPU buffer.
- **`tile.rs`'s `mesh_handle` / `texture_handle: Option<u32>`** fields on
  `CachedTile` are kept as opaque ids (plain data, not touched by this
  repo) — the renderer that owns the actual GPU mesh/texture is out of
  scope here, same as upstream.

**H3 indexing** was *not* present anywhere in the recovered `kami-geo`
Rust source (`Cargo.toml` had no h3 dependency; no H3 code in any of the
5 source files) — there was nothing to port. If H3 cell indexing is
needed going forward, it should be added here as new `kotoba.geo.h3`
domain logic (e.g. wrapping/porting an H3 algorithm), not recovered from
kami-engine history.

## Test

```sh
kbb -M:test
kbb -M:lint
```

## License

Apache License 2.0.
