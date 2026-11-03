(ns vehicle.wheel
  "Wheel -- hub + tire-ring node group with Pacejka magic-formula tire model.
   Restored from kami-vehicle (kotoba-lang/kami-engine, deleted PR #82),
   ADR-2607010930."
  (:require [vehicle.vec3 :as v3]))

;; contact-mode: :hub | :tire-ring

(defn pacejka-road-dry []
  {:b-long 10.0 :c-long 1.65 :d-long 1.0 :e-long 0.97
   :b-lat 8.5 :c-lat 1.30 :d-lat 1.0 :e-lat 0.97})

(defn pacejka-road-wet []
  (merge (pacejka-road-dry)
         {:b-long 8.0 :c-long 1.65 :d-long 0.70 :e-long 0.95
          :b-lat 7.0 :c-lat 1.30 :d-lat 0.70 :e-lat 0.95}))

(defn new-wheel [id axle-n1 axle-n2 radius width]
  {:id id
   :hub-nodes []
   :tire-nodes []
   :axle-n1 axle-n1
   :axle-n2 axle-n2
   :radius radius
   :width width
   :angular-velocity 0.0
   :steer-angle 0.0
   :max-steer-angle 0.55
   :brake-torque 0.0
   :drive-torque 0.0
   :spin-inertia 1.5
   :pressure 2.4
   :reference-pressure 2.4
   :tire (pacejka-road-dry)
   :grounded false
   :last-slip-ratio 0.0
   :last-slip-angle 0.0
   :contact-mode :hub})

(defn- clamp [v lo hi] (min hi (max lo v)))

(defn set-steer [wheel target]
  (assoc wheel :steer-angle (clamp target (- (:max-steer-angle wheel)) (:max-steer-angle wheel))))

(defn- rs-signum
  "Rust f32::signum semantics: 0.0 -> 1.0, negative -> -1.0."
  [x]
  (if (neg? x) -1.0 1.0))

(defn- magic-formula [slip b c d e]
  (let [bs (* b slip)]
    (* d (Math/sin (* c (Math/atan (- bs (* e (- bs (Math/atan bs))))))))))

(defn pacejka-force
  "Evaluate the tire force at the contact patch. `p` is a PacejkaParams map,
   `c` is `{:fz :vx :vy :vs}`. Returns `{:fx :fy :slip-ratio :slip-angle}`."
  [p c]
  (let [{:keys [fz vx vy vs]} c
        denom (max (Math/abs vx) 0.5)
        slip-ratio (clamp (/ (- vs vx) denom) -2.0 2.0)
        slip-angle (if (< (Math/abs vx) 0.5)
                     (* (rs-signum vy) (min (/ (Math/abs vy) 0.5) 1.0) 0.20)
                     (Math/atan (/ vy (Math/abs vx))))
        mu (max fz 0.0)
        fx (* (magic-formula slip-ratio (:b-long p) (:c-long p) (:d-long p) (:e-long p)) mu)
        fy (* (magic-formula slip-angle (:b-lat p) (:c-lat p) (:d-lat p) (:e-lat p)) mu)
        limit (* mu (max (:d-long p) (:d-lat p)))
        mag (Math/sqrt (+ (* fx fx) (* fy fy)))
        [fx fy] (if (and (> mag limit) (> mag 1e-3))
                  (let [s (/ limit mag)] [(* fx s) (* fy s)])
                  [fx fy])]
    {:fx fx :fy (- fy) :slip-ratio slip-ratio :slip-angle slip-angle}))

(defn cornering-stiffness [p fz]
  (* (:b-lat p) (:c-lat p) (:d-lat p) fz))

(defn wheel-frame
  "Returns `[forward left up]` orthonormal basis given the steered yaw and
   the chassis up vector."
  [chassis-forward chassis-up steer-yaw]
  (let [up (v3/normalize-or-zero chassis-up)
        cf (v3/normalize-or-zero chassis-forward)
        s (Math/sin steer-yaw)
        cs (Math/cos steer-yaw)
        right (v3/cross cf up)
        forward (v3/normalize-or-zero (v3/add (v3/scale cf cs) (v3/scale right s)))
        left (v3/normalize-or-zero (v3/cross up forward))]
    [forward left up]))
