(ns kotoba.webgpu-rs.scene
  "Bridge: a kami-clj `scene.edn` -> render-IR (globals + scattered prop
  instances), mirroring the web's deterministic scatter. Direct port of
  kami-webgpu-rs's `scene_to_ir` — pure EDN-in/data-out, deterministic
  (xorshift32, [[kotoba.webgpu-rs.rng]]) prop placement, no wgpu calls.

  No network, no I/O."
  (:require [kotoba.webgpu-rs.edn :as e]
            [kotoba.webgpu-rs.render-ir :as ir]
            [kotoba.webgpu-rs.rng :as rng]))

(def ground-instance-defaults
  {:pos [0.0 -0.5 0.0] :size [400.0 1.0] :yaw 0.0
   :metallic 0.0 :roughness 0.95 :emissive 0.0})

(defn- parse-camera-rig
  "`:camera {:distance :height :azimuth :look-height}` -> `[eye target]`,
  mirroring the Rust `camera` block: `eye = [dist*cos(az), h, dist*sin(az)]`,
  `target = [0, look-height, 0]`."
  [cam]
  (let [dist (e/numf (:distance cam))
        h (e/numf (:height cam))
        az (e/numf (:azimuth cam))
        lh (e/numf (:look-height cam))]
    [[(* dist (Math/cos az)) h (* dist (Math/sin az))]
     [0.0 lh 0.0]]))

(defn- scatter
  "The xorshift-driven prop scatter loop. Returns the vector of scattered
  instances (ground plane NOT included — callers prepend it), given
  `:render/props` map."
  [props]
  (let [n-iter (long (e/numf (:count props)))
        spread (let [s (e/numf (:spread props))] (if (zero? s) 140.0 s))
        buildings (into [] (filter map?) (:buildings props))
        n-buildings (count buildings)
        trees (:trees props)
        tree-ratio (if (map? trees) (e/numf (:ratio trees)) 0.0)]
    (loop [i 0 rs (rng/make) out (transient [])]
      (if (>= i n-iter)
        (persistent! out)
        ;; per Rust: draw1=x, draw2=z; a too-close-to-center hit `continue`s
        ;; WITHOUT consuming draw3 (tree-vs-building test) — the seq's head
        ;; after x/z is put back for the next iteration to re-read.
        (let [[r1 r2 & after-xz] rs
              x (* (- (* r1 2.0) 1.0) spread)
              z (* (- (* r2 2.0) 1.0) spread)]
          (if (< (Math/sqrt (+ (* x x) (* z z))) 11.0)
            (recur (inc i) after-xz out)
            (let [[r3 & after-test] after-xz
                  use-tree? (< r3 tree-ratio)]
              (cond
                ;; tree branch: config-driven (w/h/metallic/roughness/color
                ;; all static from `:trees`), no further rnd() draws.
                (and use-tree? (map? trees))
                (let [tw (e/numf (:w trees))
                      th (e/numf (:h trees))
                      tm (e/numf (:metallic trees))
                      tr (let [r (e/numf (:roughness trees))] (if (zero? r) 0.95 r))]
                  (recur (inc i) after-test
                         (-> out
                             (conj! {:pos [x 0.0 z] :color [0.45 0.32 0.2]
                                     :size [(* tw 0.3) (* th 0.5)] :yaw 0.0
                                     :metallic 0.0 :roughness 0.9 :emissive 0.0})
                             (conj! {:pos [x (* th 0.5) z] :color (e/vec3 (:color trees))
                                     :size [tw (* th 0.6)] :yaw 0.0
                                     :metallic tm :roughness tr :emissive 0.0}))))

                ;; building branch: draw4 selects the building (scaled by
                ;; building-table length, truncated, then modulo — matches
                ;; `(rnd() * buildings.len() as f32) as usize % buildings.len()`
                ;; exactly, including the redundant-looking modulo), draw5
                ;; interpolates height within [min-h, max-h].
                (and (not use-tree?) (pos? n-buildings))
                (let [[r4 r5 & after-building] after-test
                      b (nth buildings (mod (long (* r4 n-buildings)) n-buildings))
                      mn (e/numf (:min-h b))
                      mx (e/numf (:max-h b))
                      h (+ mn (* r5 (- mx mn)))
                      rgh (let [r (e/numf (:roughness b))] (if (zero? r) 0.7 r))]
                  (recur (inc i) after-building
                         (conj! out {:pos [x 0.0 z] :color (e/vec3 (:color b))
                                     :size [(e/numf (:w b)) h] :yaw 0.0
                                     :metallic (e/numf (:metallic b)) :roughness rgh
                                     :emissive 0.0})))

                :else
                (recur (inc i) after-test out)))))))))

(defn scene->ir
  "`scene-src` (a kami-clj `scene.edn` string or already-parsed map) ->
  `[globals instances]`. Live entities (player/bots) are appended by the
  caller, matching kami-webgpu-rs's own contract."
  [scene-src]
  (let [root (if (string? scene-src) (ir/root-map scene-src) scene-src)]
    (if-not (map? root)
      [ir/default-globals []]
      (let [sky (:render/sky root)
            globals (if (map? sky)
                       (assoc ir/default-globals
                              :horizon (e/vec3 (:horizon sky))
                              :sun-dir (e/vec3 (:sun-dir sky))
                              :sun (e/vec3 (:sun sky)))
                       ir/default-globals)
            ground-color (if (and (map? sky) (contains? sky :ground))
                            (e/vec3 (:ground sky))
                            [0.34 0.52 0.30])
            cam (:camera root)
            globals (if (map? cam)
                       (let [[eye target] (parse-camera-rig cam)]
                         (assoc globals :eye eye :target target))
                       globals)
            ground (assoc ground-instance-defaults :color ground-color)
            props (:render/props root)
            scattered (if (map? props) (scatter props) [])]
        [globals (into [ground] scattered)]))))
