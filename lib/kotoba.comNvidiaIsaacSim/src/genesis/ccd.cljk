(ns genesis.ccd
  "Continuous collision detection (time-of-impact) to stop tunnelling.

  Fast bodies can pass *through* a thin obstacle in a single discrete
  step. CCD finds the time-of-impact (TOI) inside the step so the
  integrator can stop at contact:
    - `sphere-plane-toi` — analytic TOI of a translating sphere vs a
      half-space.
    - `conservative-advancement-toi` — TOI of two translating convex
      polytopes, using `genesis.convex/gjk-distance` as the proximity
      oracle (Mirtich's conservative advancement).

  Returns the impact fraction in [0, 1] of the step, or nil if no impact.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/ccd.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.vec3 :as v3]
            [genesis.convex :as convex]))

(defn translated
  "A copy of `poly` translated by `off` (CCD advances bodies by translation)."
  [{:keys [verts]} off]
  (convex/->poly (mapv #(v3/add % off) verts)))

(defn sphere-plane-toi
  "TOI (fraction of the step) of a sphere of `radius` at `center` moving
  by `vel*dt` over the step, hitting the half-space {x : n.x >= offset}
  boundary plane n.x = offset (n unit). nil if it does not reach the
  plane."
  [center radius vel n offset dt]
  (let [n (v3/normalize-or-zero n)
        d0 (- (v3/dot n center) offset radius)
        closing (* (v3/dot n vel) dt)]
    (cond
      (<= d0 0.0) 0.0
      (>= closing -1e-9) nil
      :else
      (let [t (/ d0 (- closing))]
        (when (<= 0.0 t 1.0) t)))))

(defn conservative-advancement-toi
  "Conservative advancement TOI of two convex polytopes translating by
  `va*dt` and `vb*dt` over the step. nil if they never get within `margin`."
  [a b va vb dt margin]
  (let [rel (v3/scale (v3/sub va vb) dt)
        speed (v3/length rel)]
    (if (< speed 1e-9)
      nil
      (loop [t 0.0 iter 0]
        (if (>= iter 64)
          nil
          (let [at (translated a (v3/scale rel t))
                dist (convex/gjk-distance at b)]
            (if (<= dist margin)
              t
              (let [adv (max (/ (- dist margin) speed) 1e-4)
                    t' (+ t adv)]
                (if (>= t' 1.0) nil (recur t' (inc iter)))))))))))
