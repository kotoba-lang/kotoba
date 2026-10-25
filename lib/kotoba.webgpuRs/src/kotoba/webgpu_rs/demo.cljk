(ns kotoba.webgpu-rs.demo
  "A royale-style procedural demo scene (fixed 170-prop scatter + a ball at
  the origin) shared by kami-webgpu-rs's PNG and live-window examples so
  both render the same world. Direct port of kami-webgpu-rs's
  `demo_city` — pure data generation (deterministic xorshift32, same
  [[kotoba.webgpu-rs.rng]] as [[kotoba.webgpu-rs.scene]]), no wgpu calls.
  The examples themselves (`examples/live.rs`, `examples/render_png.rs`)
  are 100% host-adapter (window event loop / PNG file write) and are not
  ported — see the README.

  No network, no I/O."
  (:require [kotoba.webgpu-rs.render-ir :as ir]
            [kotoba.webgpu-rs.rng :as rng]))

(def ground-instance
  {:pos [0.0 -0.5 0.0] :color [0.34 0.52 0.30] :size [400.0 1.0] :yaw 0.0
   :metallic 0.0 :roughness 0.95 :emissive 0.0})

(def ball-instance
  {:pos [0.0 0.0 0.0] :color [0.30 0.62 1.0] :size [0.9 1.9] :yaw 0.0
   :metallic 0.2 :roughness 0.35 :emissive 0.5})

(def ^:const prop-count 170)
(def ^:const scatter-spread 90.0)

(defn- scatter-props []
  (loop [i 0 rs (rng/make) out (transient [])]
    (if (>= i prop-count)
      (persistent! out)
      (let [[r1 r2 & after-xz] rs
            x (* (- (* r1 2.0) 1.0) scatter-spread)
            z (* (- (* r2 2.0) 1.0) scatter-spread)]
        (if (< (Math/sqrt (+ (* x x) (* z z))) 8.0)
          (recur (inc i) after-xz out)
          (let [[r3 & after-test] after-xz]
            (if (< r3 0.4)
              (recur (inc i) after-test
                     (-> out
                         (conj! {:pos [x 0.0 z] :color [0.45 0.32 0.2]
                                 :size [0.33 1.3] :yaw 0.0
                                 :metallic 0.0 :roughness 0.95 :emissive 0.0})
                         (conj! {:pos [x 1.3 z] :color [0.28 0.55 0.30]
                                 :size [1.1 1.6] :yaw 0.0
                                 :metallic 0.0 :roughness 0.95 :emissive 0.0})))
              (let [[r4 r5 & after-h] after-test
                    h (+ 2.0 (* r4 5.0))
                    [color metallic roughness] (if (< r5 0.5)
                                                  [[0.62 0.60 0.66] 0.8 0.25]
                                                  [[0.70 0.66 0.55] 0.05 0.85])]
                (recur (inc i) after-h
                       (conj! out {:pos [x 0.0 z] :color color :size [2.0 h] :yaw 0.0
                                   :metallic metallic :roughness roughness :emissive 0.0}))))))))))

(defn demo-city
  "`[globals instances]` for the royale demo — ground plane + up to 170
  scattered buildings/trees + a ball at the origin."
  []
  [(assoc ir/default-globals
          :horizon [0.74 0.84 0.95]
          :sun-dir [-0.4 -0.85 -0.35]
          :sun [1.0 0.96 0.85]
          :eye [45.0 40.0 45.0]
          :target [0.0 0.0 0.0])
   (-> (into [ground-instance] (scatter-props))
       (conj ball-instance))])
