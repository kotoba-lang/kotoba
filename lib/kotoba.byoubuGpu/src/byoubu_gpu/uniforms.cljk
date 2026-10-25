(ns byoubu-gpu.uniforms
  "Scene spec -> the flat float list the WGSL `BU` uniform expects.

  The layout is not restated here: `pack` walks
  `byoubu-gpu.shader/uniform-fields`, the same vector the struct declaration
  is generated from, so the CPU and GPU sides cannot drift. A uniform whose
  packing silently disagrees with its struct is the classic WebGPU bug — the
  frame renders, and every value after the first misaligned field is garbage.

  Portable `.cljc`, no browser types: the browser half converts to a
  Float32Array."
  (:require [byoubu.color :as color]
            [byoubu-gpu.shader :as shader]))

(defn- rgb01
  "Hex -> [r g b 1.0] in 0..1. Values go to the GPU linearly in the same sRGB
  numbers the CSS plate and the SVG poster use; the swapchain is an *-unorm
  format, so what the shader writes is what the other tiers wrote."
  [hex]
  (if-let [[r g b] (color/hex->rgb hex)]
    [(/ (double r) 255.0) (/ (double g) 255.0) (/ (double b) 255.0) 1.0]
    [0.0 0.0 0.0 1.0]))

(def view-width
  "World units the frame spans — the same constant
  `byoubu.render.poster/view-width` uses to turn `:dune-wavelength` into
  crests per frame. Sampling FBM in raw world units gives one period every few
  pixels and renders as a sawtooth."
  2400.0)

(defn pack
  "Backdrop + frame state -> a vector of floats, `shader/uniform-bytes` long.

  `state`: {:time seconds :width px :height px}"
  [backdrop state]
  (let [p       (:byoubu/palette backdrop)
        scene   (:byoubu/scene backdrop)
        hz      (shader/horizon backdrop)
        wl      (or (get-in scene [:terrain :dune-wavelength]) 200.0)
        amp     (or (get-in scene [:terrain :dune-amplitude]) 0.4)
        haze    (or (get-in scene [:atmosphere :haze-density]) 0.3)
        vign    (or (get-in scene [:grade :vignette]) 0.25)
        stars   (or (get-in scene [:sky :stars :density]) 0.0)
        seed    (double (or (:byoubu/seed backdrop) 0))
        w       (double (or (:width state) 1600))
        h       (double (max 1.0 (or (:height state) 900)))
        cycles  (/ view-width wl)
        by-field {:sky-zenith  (rgb01 (:sky-zenith p))
                  :sky-mid     (rgb01 (:sky-mid p))
                  :sky-horizon (rgb01 (:sky-horizon p))
                  :haze        (rgb01 (:haze p))
                  :ridge-far   (rgb01 (:ridge-far p))
                  :ridge-near  (rgb01 (:ridge-near p))
                  :dune-lit    (rgb01 (:dune-lit p))
                  :dune-shadow (rgb01 (:dune-shadow p))
                  :star        (rgb01 (:star p))
                  :p0          [hz vign haze stars]
                  :p1          [cycles amp (mod seed 211.0) cycles]
                  :p2          [(double (or (:time state) 0.0)) (/ w h) w h]}]
    (vec (mapcat (fn [[field _]]
                   (or (get by-field field)
                       (throw (ex-info (str "byoubu-gpu: no packer for uniform field "
                                            field)
                                       {:field field}))))
                 shader/uniform-fields))))

(defn float-count [] (* 4 (count shader/uniform-fields)))
