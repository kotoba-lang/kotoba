# kotoba-lang/d3

[![CI](https://github.com/kotoba-lang/d3/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/d3/actions/workflows/ci.yml)

A **native, from-scratch reimplementation of the core `d3.js` "scales +
shape generators" modules** (the `d3-scale` and `d3-shape` equivalents) —
explicitly *not* a JS-interop wrapper around real d3.js. Zero third-party
runtime deps; every namespace is `.cljc`, so it runs on JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM.

Scope is purely the *data → geometry* pipeline: turn numeric domains and
data series into SVG-renderable EDN geometry (path `d` strings, tick
positions, pie-slice angles). Out of scope for v1: DOM selections/data
binding (`d3-selection`), transitions/animation, and force-directed layout
(that's the separate sibling `force3d` repo).

Output is wire-compatible with [`kotoba-lang/svg`](https://github.com/kotoba-lang/svg)'s
Hiccup-like `[:tag {:attrs} & children]` convention: feed a `d` string
straight into `[:path {:d (line-generator pts)}]` for `svg.core/render` to
render — `d3` does not depend on `svg` directly (keeps this lib
dependency-free), but its output shape is designed to slot straight in.

## Current surface

`kotoba.lang.d3.scale` — pure domain → range mapping functions (≈ d3-scale):

- `linear-scale` / `linear-invert` — linear interpolation and its inverse
- `log-scale` / `log-invert` — logarithmic domain mapping (any base, default 10)
- `ordinal-scale` — map discrete domain values to arbitrary range values by position
- `point-scale` — evenly space a discrete domain across a numeric range (≈ d3's `scalePoint`)
- `band-scale` — evenly-spaced, padded bands for bar charts, returning `{:start :end :width}` per domain value (≈ d3's `scaleBand`)

`kotoba.lang.d3.shape` — pure data → SVG path `d` string generators (≈ d3-shape):

- `line-generator` — straight-line-segment path through a seq of `[x y]` points (or maps + `:x`/`:y` accessors)
- `area-generator` — like `line-generator`, closed down to a `:baseline` for filled area charts
- `arc-generator` — `{:inner-radius :outer-radius :start-angle :end-angle}` → an SVG arc path for pie/donut wedges, correctly handling both the large-arc-flag (span > 180 degrees) and full-circle (span >= 360 degrees, which cannot be a single SVG arc command) edge cases
- `pie-layout` — turn a seq of numeric values into `{:value :start-angle :end-angle}` slices proportional to each value's share of the total (angles sum to a full circle); feed each slice into `arc-generator` for the geometry

All fns are plain functions over plain data — no stateful scale/generator
objects. Scales return closures you call with a value; shape generators are
called directly with points/config and return a string or seq of maps.

## Install

```clojure
io.github.kotoba-lang/d3 {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.d3.scale :as scale]
         '[kotoba.lang.d3.shape :as shape])

;; scale
(def x (scale/linear-scale [0 100] [0 1]))
(x 50) ;=> 1/2

;; line + area
(shape/line-generator [[0 0] [10 5] [20 0]])
;=> "M0,0L10,5L20,0"

;; pie + arc
(def slices (shape/pie-layout [1 1 2]))
(shape/arc-generator (merge {:inner-radius 0 :outer-radius 100} (first slices)))
```

## Verify

```sh
kbb -M:test
```
