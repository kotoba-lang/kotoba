(ns autodrive.dynamics
  "High-fidelity dynamics plants for the non-car classes: hydrodynamic ship,
  aerodynamic fixed-wing, and rotor-thrust multirotor. Each implements
  `autodrive.plant/Plant`, so the same autopilot drives them — only the body
  physics differs.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  All plants interpret the normalised command uniformly:
    * throttle - brake = longitudinal force/accel demand (propeller / engine
      thrust / forward tilt),
    * steer in [-1, 1] = normalised turn demand (rudder angle / bank angle /
      yaw-rate),
  so pure-pursuit + PID transfer across classes unchanged.

  Integration is sub-stepped inside each `step` for numerical stability at
  the autopilot's coarse outer `dt`."
  (:require [autodrive.types :as t]
            [autodrive.plant :as plant]))

(def ^:const G 9.81)
(def ^:const SUBSTEPS 8)

(defn isa-density
  "ISA troposphere air density (kg/m^3) at geopotential altitude `h` (m)."
  [h]
  (let [h (min 11000.0 (max 0.0 h))]
    (* 1.225 (Math/pow (- 1.0 (* 2.25577e-5 h)) 4.2559))))

;; ─────────────────────────────── Ship (hydrodynamic) ───────────────────────────────

(defrecord ShipHydro [pose u v r limits m11 m22 m33 d11 d11q d22 d22q d33 d33q t-max rudder-k rudder-max]
  plant/Plant
  (pose [this] (:pose this))
  (speed [this] (Math/hypot (:u this) (:v this)))
  (step [this cmd dt]
    (let [cmd (t/clamp-cmd cmd)
          h (/ dt SUBSTEPS)
          tau-u (* (- (:throttle cmd) (:brake cmd)) (:t-max this))
          delta (* (:steer cmd) (:rudder-max this))]
      (loop [i 0 u (:u this) v (:v this) r (:r this) pose (:pose this)]
        (if (>= i SUBSTEPS)
          (assoc this :u u :v v :r r :pose pose)
          (let [tau-r (* (:rudder-k this) delta u (Math/abs u))
                du (/ (+ (- tau-u (* (:d11 this) u) (* (:d11q this) u (Math/abs u)))
                         (* (:m22 this) v r))
                      (:m11 this))
                dv (/ (- (- (* (:d22 this) v) (* (:d22q this) v (Math/abs v)))
                         (* (:m11 this) u r))
                      (:m22 this))
                dr (/ (- tau-r (* (:d33 this) r) (* (:d33q this) r (Math/abs r))) (:m33 this))
                u' (+ u (* du h)) v' (+ v (* dv h)) r' (+ r (* dr h))
                yaw' (+ (:yaw pose) (* r' h))
                s (Math/sin yaw') c (Math/cos yaw')
                x' (+ (:x pose) (* (- (* u' c) (* v' s)) h))
                y' (+ (:y pose) (* (+ (* u' s) (* v' c)) h))]
            (recur (inc i) u' v' r' (t/pose2 x' y' yaw'))))))))

(defn ship-hydro [pose limits]
  (let [m 2000.0
        m11 (* 1.1 m)
        m22 (* 1.6 m)
        lpp (* 2.0 (:footprint-radius limits))
        iz (/ (* m lpp lpp) 12.0)
        m33 (* 1.2 iz)
        t-max (* m11 (:max-accel limits))
        d11q (/ t-max (* (:max-speed limits) (:max-speed limits)))]
    (->ShipHydro pose 0.0 0.0 0.0 limits m11 m22 m33
                 (/ (* 0.05 t-max) (:max-speed limits)) d11q
                 (* 0.3 m22) 300.0 20000.0 5000.0
                 t-max 180.0 (:max-steer limits))))

;; ─────────────────────────────── Fixed-wing (aerodynamic) ───────────────────────────────

(defrecord FixedWing [pose airspeed altitude stalled limits mass wing-area cd0 k-induced cl-max t-max cd-brake bank-max]
  plant/Plant
  (pose [this] (:pose this))
  (speed [this] (:airspeed this))
  (step [this cmd dt]
    (let [cmd (t/clamp-cmd cmd)
          h (/ dt SUBSTEPS)
          rho (isa-density (:altitude this))
          phi (* (:steer cmd) (:bank-max this))
          thrust (* (:throttle cmd) (:t-max this))]
      (loop [i 0 airspeed (:airspeed this) pose (:pose this) stalled (:stalled this)]
        (if (>= i SUBSTEPS)
          (assoc this :airspeed airspeed :pose pose :stalled stalled)
          (let [v (max 1.0 airspeed)
                q (* 0.5 rho v v (:wing-area this))
                cl-need (/ (* (:mass this) G) (* q (max 0.2 (Math/cos phi))))
                stalled' (> cl-need (:cl-max this))
                cl (min cl-need (:cl-max this))
                cd (+ (:cd0 this) (* (:k-induced this) cl cl) (* (:brake cmd) (:cd-brake this)))
                drag (* q cd)
                v-dot (/ (- thrust drag) (:mass this))
                stall-speed (Math/sqrt (/ (* 2.0 (:mass this) G) (* rho (:wing-area this) (:cl-max this))))
                airspeed' (max (* 0.5 stall-speed) (+ airspeed (* v-dot h)))
                load (/ (* cl q) (* (:mass this) G))
                psi-dot (if (> load 1.0)
                          (* (/ (* G (Math/sqrt (- (* load load) 1.0))) airspeed')
                             (Math/signum phi))
                          0.0)
                yaw' (+ (:yaw pose) (* psi-dot h))
                s (Math/sin yaw') c (Math/cos yaw')
                x' (+ (:x pose) (* airspeed' c h))
                y' (+ (:y pose) (* airspeed' s h))]
            (recur (inc i) airspeed' (t/pose2 x' y' yaw') stalled')))))))

(defn stall-speed
  "Stall speed at `plane`'s current altitude (m/s)."
  [plane]
  (let [rho (isa-density (:altitude plane))]
    (Math/sqrt (/ (* 2.0 (:mass plane) G) (* rho (:wing-area plane) (:cl-max plane))))))

(defn fixed-wing [pose altitude limits]
  (let [mass 1200.0
        wing-area 16.0
        t-max (* 1.5 mass (:max-accel limits))]
    (->FixedWing pose (* 0.55 (:max-speed limits)) altitude false limits mass wing-area
                 0.025 0.045 1.4 t-max 0.08 (max (:max-steer limits) 0.6))))

;; ─────────────────────────────── Multirotor (rotor) ───────────────────────────────

(defrecord Multirotor [pose vx vy tilt limits drag-c a-max tilt-max tilt-tau yawrate-max lat-damp]
  plant/Plant
  (pose [this] (:pose this))
  (speed [this] (Math/hypot (:vx this) (:vy this)))
  (step [this cmd dt]
    (let [cmd (t/clamp-cmd cmd)
          h (/ dt SUBSTEPS)
          a-dem (* (- (:throttle cmd) (:brake cmd)) (:a-max this))
          tilt-des (min (:tilt-max this) (max (- (:tilt-max this)) (Math/atan (/ a-dem G))))
          yaw-dot (* (:steer cmd) (:yawrate-max this))]
      (loop [i 0 tilt (:tilt this) pose (:pose this) vx (:vx this) vy (:vy this)]
        (if (>= i SUBSTEPS)
          (assoc this :tilt tilt :pose pose :vx vx :vy vy)
          (let [alpha (min 1.0 (/ h (:tilt-tau this)))
                tilt' (+ tilt (* (- tilt-des tilt) alpha))
                yaw' (+ (:yaw pose) (* yaw-dot h))
                a-fwd (* G (Math/tan tilt'))
                s (Math/sin yaw') c (Math/cos yaw')
                ax0 (* a-fwd c) ay0 (* a-fwd s)
                v-lat (+ (- (* vx s)) (* vy c))
                a-lat (* (- (:lat-damp this)) v-lat)
                ax1 (+ ax0 (* a-lat (- s)))
                ay1 (+ ay0 (* a-lat c))
                spd (Math/hypot vx vy)
                ax (- ax1 (* (:drag-c this) spd vx))
                ay (- ay1 (* (:drag-c this) spd vy))
                vx' (+ vx (* ax h))
                vy' (+ vy (* ay h))
                x' (+ (:x pose) (* vx' h))
                y' (+ (:y pose) (* vy' h))]
            (recur (inc i) tilt' (t/pose2 x' y' yaw') vx' vy')))))))

(defn multirotor [pose limits]
  (let [mass 1.5 rho 1.225 cd 0.5 area 0.1]
    (->Multirotor pose 0.0 0.0 0.0 limits
                  (/ (* 0.5 rho cd area) mass)
                  (:max-accel limits) 0.5 0.15 3.0 2.5)))
