(ns terrain.splatmap
  "Splatmap: per-vertex material weights for terrain texture blending.

  Restored from kotoba-lang/kami-engine's kami-terrain/src/splatmap.rs (deleted
  in PR #82 \"Remove Rust workspace from kami-engine\") as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Decima uses 4-8 material
  layers blended by height, slope, and noise; here each vertex stores 4
  weights (grass, rock, sand, snow) summing to 1.0."
  (:require [terrain.heightmap :as heightmap]))

(def mat-grass 0)
(def mat-rock 1)
(def mat-sand 2)
(def mat-snow 3)

(defn- clamp [x lo hi] (max lo (min hi x)))

(defn normalize-weights
  "Normalize a 4-vector of weights to sum to 1.0 (no-op if sum is 0)."
  [weights]
  (let [sum (reduce + weights)]
    (if (> sum 0.0)
      (mapv #(/ % sum) weights)
      weights)))

(defn from-heightmap
  "Generate a splatmap from a heightmap using height + slope rules.

  Rules (Decima-inspired):
  - Below `sand-line`: sand
  - Above `snow-line`: snow
  - Slope > `rock-threshold`: rock
  - Otherwise: grass, blending toward snow with height"
  [hm sand-line snow-line rock-threshold]
  (let [{:keys [width depth data]} hm
        out (vec (for [z (range depth)
                        x (range width)]
                    (let [h (nth data (+ (* z width) x))
                          n (heightmap/normal hm x z)
                          slope (- 1.0 (nth n 1)) ; 0 = flat, 1 = vertical
                          base-weights
                          (cond
                            (< h sand-line) [0.0 0.0 1.0 0.0]
                            (> h snow-line) [0.0 0.0 0.0 1.0]
                            :else
                            (let [t (clamp (/ (- h sand-line) (- snow-line sand-line)) 0.0 1.0)]
                              [(- 1.0 (* t 0.3)) 0.0 0.0 (* t 0.3)]))
                          weights
                          (if (> slope rock-threshold)
                            (let [rock-blend (clamp (/ (- slope rock-threshold) (- 1.0 rock-threshold)) 0.0 1.0)
                                  scaled (mapv #(* % (- 1.0 rock-blend)) base-weights)]
                              (update scaled mat-rock + rock-blend))
                            base-weights)]
                      {:weights (normalize-weights weights)})))]
    {:width width :depth depth :data out}))
