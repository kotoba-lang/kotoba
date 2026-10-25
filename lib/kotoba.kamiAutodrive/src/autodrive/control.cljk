(ns autodrive.control
  "Tracking controllers: pure-pursuit lateral + PID longitudinal.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930."
  (:require [autodrive.geom :as g]
            [autodrive.types :as t]))

;; ─────────────────────────────── Pure pursuit ───────────────────────────────

(defn pure-pursuit
  "Pure-pursuit lateral controller config. Picks a lookahead point on the
  path and commands a normalised steer that arcs the vehicle onto it.

  The steer is `curvature * turn-radius-ref` (full deflection when the
  required arc radius equals the vehicle's reference turn radius). Decoupling
  from a bicycle wheelbase lets the same controller drive the car, a rudder
  ship, a banking aircraft, and a yawing multirotor. A target abeam-or-behind
  commands a hard turn toward it, so plants that can slow/stop recover
  instead of flying straight off."
  [lookahead lookahead-gain turn-radius-ref]
  {:lookahead lookahead :lookahead-gain lookahead-gain :turn-radius-ref turn-radius-ref})

(defn- lookahead-target
  "First waypoint at least `ld` ahead of `pos` along the path; falls back to
  the closest-then-forward waypoint, and finally the last point."
  [pos path ld]
  (let [n (count path)
        closest (first (apply min-key
                               (fn [[_ p]] (g/distance-sq2 p pos))
                               (map-indexed vector path)))]
    (or (some (fn [i] (when (>= (g/distance2 (nth path i) pos) ld) i))
              (range closest n))
        (dec n))))

(defn steer
  "Result: `[normalised-steer target-idx]`, steer in `[-1 1]` (positive =
  left). Returns `[0 (dec (count path))]` for a trivial path."
  [pp pose speed path]
  (if (< (count path) 2)
    [0.0 (max 0 (dec (count path)))]
    (let [ld (max 0.5 (+ (:lookahead pp) (* (:lookahead-gain pp) speed)))
          target-idx (lookahead-target (t/pos pose) path ld)
          target (nth path target-idx)
          local (t/to-local pose target)]
      (if (<= (:x local) 0.0)
        [(if (>= (:y local) 0.0) 1.0 -1.0) target-idx]
        (let [ld2 (max 1e-3 (g/length-sq2 local))
              curvature (/ (* 2.0 (:y local)) ld2)]
          [(min 1.0 (max -1.0 (* curvature (:turn-radius-ref pp)))) target-idx])))))

;; ─────────────────────────────── Speed PID ───────────────────────────────

(defn speed-controller
  [kp ki kd]
  {:kp kp :ki ki :kd kd :integral 0.0 :prev-err 0.0})

(defn reset-speed-controller [sc] (assoc sc :integral 0.0 :prev-err 0.0))

(defn update-speed
  "Returns `[speed-controller' throttle brake]`, throttle/brake each in
  `[0 1]`. A positive control effort is throttle; negative is brake."
  [sc target-speed current-speed dt]
  (let [err (- target-speed current-speed)
        integral (min 5.0 (max -5.0 (+ (:integral sc) (* err dt))))
        deriv (if (> dt 0.0) (/ (- err (:prev-err sc)) dt) 0.0)
        effort (+ (* (:kp sc) err) (* (:ki sc) integral) (* (:kd sc) deriv))
        sc' (assoc sc :integral integral :prev-err err)]
    (if (>= effort 0.0)
      [sc' (min 1.0 (max 0.0 effort)) 0.0]
      [sc' 0.0 (min 1.0 (max 0.0 (- effort)))])))

;; ─────────────────────────────── Curvature speed limit ───────────────────────────────

(defn- menger-curvature
  "Menger curvature of the triangle (a, b, c) = 1 / circumradius."
  [a b c]
  (let [area2 (Math/abs (- (* (- (:x b) (:x a)) (- (:y c) (:y a)))
                            (* (- (:x c) (:x a)) (- (:y b) (:y a)))))
        denom (* (g/distance2 a b) (g/distance2 b c) (g/distance2 c a))]
    (if (< denom 1e-6) 0.0 (/ (* 2.0 area2) denom))))

(defn curvature-speed-limit
  "Speed limit from path curvature: slower through tight turns.
  `lateral-accel-limit` is the comfort/grip cap (m/s^2)."
  [path idx lateral-accel-limit]
  (if (or (< (count path) 3) (zero? idx) (>= idx (dec (count path))))
    ##Inf
    (let [a (nth path (dec idx)) b (nth path idx) c (nth path (inc idx))
          kappa (menger-curvature a b c)]
      (if (< kappa 1e-4) ##Inf (Math/sqrt (/ lateral-accel-limit kappa))))))
