# kotoba-lang/force3d

[![CI](https://github.com/kotoba-lang/force3d/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/force3d/actions/workflows/ci.yml)

**Pure Clojure/cljc 3D force-directed graph layout simulation** — analogous to
[d3-force-3d](https://github.com/vasturiano/d3-force-3d) (the 3D extension of
d3.js's force layout), reimplemented from scratch operating purely on EDN
data. No DOM, no rendering, no JS interop. Every namespace is `.cljc`, so it
runs on JVM / SCI / ClojureScript / GraalVM / kotoba-WASM — anywhere kotoba
EDN data flows.

`force3d` is a portable reimplementation of the force-directed-layout
*algorithm*, independent of `kami-engine`'s Rust `kami-graph` crate (which
implements Merkle-DAG-PCB + force-directed layout inside the kami-engine WGPU
renderer). This library is not a wrapper around that crate — no FFI/WASM
bridge — it exists so any kotoba consumer (JVM backends, browser cljs, SCI
scripts, GraalVM natives) can lay out a graph in 3D without depending on the
game engine.

## Data shape

A simulation state is a plain map: `{:nodes [...] :links [...] :forces {...}
:alpha n :alpha-min n :alpha-decay n :velocity-decay n}`.

- A **node** is a map with at least `{:id ... :x .. :y .. :z .. :vx .. :vy ..
  :vz ..}` — position and velocity. Extra keys (`:radius`, `:fixed?`, ...)
  are preserved and readable by forces.
- A **link** is a map `{:source id :target id :strength .. :distance ..}`
  where `id` matches a node's `:id`.

## Forces

Each force is a plain function `(fn [sim] sim)` (or `(fn [sim opts] sim)`,
partially-applied), stored in `:forces` as `{keyword -> force-fn}`:

- `charge` — pairwise repulsion (negative `:strength`, default) / attraction
  (positive `:strength`) between every pair of nodes, Coulomb-like
  (`strength / distance^2`). Brute-force O(n²) in v1 — a Barnes-Hut octree
  is a plausible future optimization for large graphs, intentionally not
  built now.
- `link` — spring force pulling linked node pairs toward a target
  `:distance` (per-link override supported).
- `center` — gravitates the whole node set toward a center point (default
  the origin), preventing drift.
- `collision` — prevents node overlap given each node's `:radius`.

All forces operate on `x`/`y`/`z` — this is the differentiator from plain 2D
d3-force.

## Simulation / tick loop

- `simulation nodes links opts` — construct simulation state (analogous to
  `d3.forceSimulation`); fills in `0.0` defaults for missing position/
  velocity fields.
- `tick sim` — apply every force once, integrate velocity → position (with
  velocity decay / friction), and decay `:alpha`.
- `simulate sim [max-ticks]` — run `tick` until `:alpha` falls below
  `:alpha-min` or `max-ticks` (default `1000`) is reached; returns the final
  state.
- `node-by-id sim id`, `distance a b` — small read helpers.

`:fixed? true` on a node pins it — forces still see it, but neither
integration nor other nodes' reactive velocity ever move it.

## Install

```clojure
io.github.kotoba-lang/force3d {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.force3d.core :as f3d])

(def sim
  (f3d/simulation
   [{:id :a :x 0.0 :y 0.0 :z 0.0}
    {:id :b :x 50.0 :y 0.0 :z 0.0}]
   [{:source :a :target :b :distance 20.0 :strength 1.0}]))

(def final (f3d/simulate sim))

(f3d/node-by-id final :a)
;=> {:id :a :x ... :y ... :z ... :vx ... :vy ... :vz ...}

(f3d/distance (f3d/node-by-id final :a) (f3d/node-by-id final :b))
;=> ~20.0
```

## Verify

```sh
kbb -M:test
```
