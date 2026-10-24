(ns floorplan-lab.motion
  "Dead-reckoning: integrate a walking trajectory (position + heading) from
  a stream of motion samples (accelerometer + gyroscope). Part of the
  indoor floorplan-lab (ADR-2607140600 Phase 3a device-capability bridge)
  -- SOFTWARE ONLY, no real CoreMotion involved; samples are either
  `floorplan-lab.sensing-bridge`-adapted driver output or, in this lab's
  tests, synthetic data.

  Each sample is a map {:ax :ay :az :gx :gy :gz :dt}: ax/ay = body-frame
  horizontal acceleration (m/s^2), gz = yaw rate (rad/s) about the
  vertical axis, dt = the sample's time interval (s). az/gx/gy/mx/my/mz
  are accepted (via `floorplan-lab.sensing-bridge/motion-sample-from-raw9`)
  but unused by this 2D-floorplan estimator -- elevation/tilt/multi-floor
  fusion is explicitly out of scope for this first increment.

  METHOD (naive dead-reckoning -- explicitly NOT a Kalman filter; see
  README \"Future work\"): heading[n] = heading[n-1] + gz*dt (gyro
  integration); world-frame acceleration is body acceleration rotated by
  the JUST-updated heading; velocity and position are each advanced by
  semi-implicit (symplectic) Euler integration of that world-frame
  acceleration. There is no bias correction, no zero-velocity update
  (ZUPT), and no drift compensation -- pure double integration, which is
  exactly why real dead-reckoning needs a filter in production. This lab
  keeps the core integrator legible and pushes cheap corrections (e.g.
  BLE trilateration) into the fusion layer instead
  (`floorplan-lab.fusion/correct-with-ble`).")

;; ---------- portable math (mirrors kotoba.sensing-host's :clj/:cljs split) ----------

#?(:clj (defn- sin ^double [^double x] (Math/sin x))
   :cljs (defn- sin [x] (js/Math.sin x)))

#?(:clj (defn- cos ^double [^double x] (Math/cos x))
   :cljs (defn- cos [x] (js/Math.cos x)))

(defn- rotate-to-world
  "Rotate body-frame [AX AY] into world-frame by HEADING (radians,
  0 = +x axis, counter-clockwise positive)."
  [ax ay heading]
  (let [c (cos heading) s (sin heading)]
    [(- (* ax c) (* ay s))
     (+ (* ax s) (* ay c))]))

(defn step
  "Advance STATE ({:x :y :heading :vx :vy}, meters/radians/(m/s)) by one
  motion SAMPLE (this namespace's docstring shape; missing keys default
  to 0.0, so a sample can carry only what it has). Pure, side-effect-free
  -- callers fold this over a sample seq (see `walk-trajectory`)."
  [state {:keys [ax ay gz dt] :or {ax 0.0 ay 0.0 gz 0.0 dt 0.0}}]
  (let [heading' (+ (:heading state) (* gz dt))
        [wx wy] (rotate-to-world ax ay heading')
        vx' (+ (:vx state) (* wx dt))
        vy' (+ (:vy state) (* wy dt))
        x' (+ (:x state) (* vx' dt))
        y' (+ (:y state) (* vy' dt))]
    {:x x' :y y' :heading heading' :vx vx' :vy vy'}))

(def initial-state
  "The walker's pose at t=0: origin, facing +x (heading 0), at rest."
  {:x 0.0 :y 0.0 :heading 0.0 :vx 0.0 :vy 0.0})

(defn walk-trajectory
  "Fold `step` over SAMPLES (a seq of motion samples per this namespace's
  docstring), starting from `initial-state` (or an explicit START-STATE).
  Returns the seq of every intermediate pose INCLUDING the start state as
  index 0 -- so a reading taken \"at motion sample i\" pairs with
  `(nth trajectory (inc i))`, and `floorplan-lab.fusion/collect-wall-points`
  takes a `:sample-index` directly into this returned seq (index 0 is the
  pre-walk pose, useful for a reading taken before the first sample)."
  ([samples] (walk-trajectory initial-state samples))
  ([start-state samples]
   (reductions step start-state samples)))
