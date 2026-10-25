(ns kotoba.map
  "kotoba-map: pure-Clojure domain-logic port of `kami-map`
  (kotoba-lang/kami-engine's WebGPU map renderer for maps.etzhayyim.com),
  per ADR-2607010930 (clj-wgsl migration Phase 4).

  This library ports the byte-parsing and math that is genuinely portable
  and host-independent: MVT vector-tile decoding, hex color parsing,
  projection-mode selection, globe/sphere vector math and procedural
  ring/spiral mesh generation, orbital scene-scale math, fly-to easing,
  tile URL templating, and Globe/Cosmic-mode pointer panning. See the
  per-namespace docstrings and the repo README for exactly what maps to
  which Rust source function, and what was intentionally left unported
  (wgpu pipelines/buffers/textures, the wasm-bindgen `KamiMap` struct and
  its GPU-resource-holding fields, SGP4 TLE propagation, and the Flat/Web
  Mercator pixel-projection math that lives in the not-yet-ported
  `kami-geo` crate).

    (require '[kotoba.map.mvt :as mvt])
    (mvt/decode-layer-features pbf-bytes {:z 14 :x 2620 :y 6332} \"roads\")

    (require '[kotoba.map.color :as color])
    (color/parse-hex-color \"#ff8800\")

    (require '[kotoba.map.projection :as proj])
    (proj/active-projection-mode 3.0) ;; => :globe"
  (:require [kotoba.map.color]
            [kotoba.map.constants]
            [kotoba.map.fly]
            [kotoba.map.input]
            [kotoba.map.mvt]
            [kotoba.map.orbital]
            [kotoba.map.projection]
            [kotoba.map.sphere]
            [kotoba.map.tile-url]))

(def namespaces
  "The full set of sub-namespaces this port comprises, for tooling."
  '[kotoba.map.color
    kotoba.map.constants
    kotoba.map.fly
    kotoba.map.input
    kotoba.map.mvt
    kotoba.map.orbital
    kotoba.map.projection
    kotoba.map.sphere
    kotoba.map.tile-url])
