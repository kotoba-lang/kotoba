(ns kotoba.lang.kami-nv-compat.kami-drive.unicycle
  "Clean-room BEV unicycle kinematics — JVM port of src/kami-drive/unicycle.ts.
  The motion model behind the nv-compat/alpamayo VLA facade: a plan of
  {accel, curvature} dynamic actions rolls out to Alpamayo's trajectory format
  (ego-frame 3D translation + 3×3 rotation per waypoint, 0-yaw at t0).
  Clean-room from-spec kinematics; no Alpamayo/Cosmos/DRIVE source. Civilian
  autonomous-mobility, SAE-L4 ceiling. Wave 8 of ADR-2607020130.")

(def ^:const default-max-speed 30)   ; m/s (~108 km/h; below any L4 urban need)

(defn yaw->mat3
  "Yaw (rad) -> row-major 3×3 rotation about +z."
  [yaw]
  (let [c (Math/cos yaw)
        s (Math/sin yaw)
        neg-s (+ 0.0 (- s))]   ; normalize -0.0 -> 0.0 (Clojure = distinguishes them)
    [c neg-s 0.0 s c 0.0 0.0 0.0 1.0]))

(defn step-unicycle
  "One forward-Euler unicycle step. `max-speed` clamps the integrated speed to
  [0, max-speed]. `state` = {:x :y :yaw :speed}; `action` = {:accel :curvature}."
  ([state action dt]
   (step-unicycle state action dt default-max-speed))
  ([{:keys [x y yaw speed]} {:keys [accel curvature]} dt max-speed]
   {:x    (+ x (* speed (Math/cos yaw) dt))
    :y    (+ y (* speed (Math/sin yaw) dt))
    :yaw  (+ yaw (* speed curvature dt))
    :speed (min max-speed (max 0 (+ speed (* accel dt))))}))

(defn rollout-trajectory
  "Roll out an action sequence into Alpamayo-format waypoints. The first
  waypoint is t0 = `initial`; then one per action at `dt` spacing. Planning
  starts in the ego frame (origin, 0-yaw)."
  ([initial actions dt]
   (rollout-trajectory initial actions dt default-max-speed))
  ([initial actions dt max-speed]
   (let [emit (fn [state t action]
                {:t          t
                 :translation [(:x state) (:y state) 0]
                 :rotation   (yaw->mat3 (:yaw state))
                 :speed      (:speed state)
                 :accel      (:accel action)
                 :curvature  (:curvature action)})]
     (loop [i 0 s initial out [(emit initial 0 {:accel 0 :curvature 0})]]
       (if (>= i (count actions))
         out
         (let [s' (step-unicycle s (nth actions i) dt max-speed)]
           (recur (inc i) s' (conj out (emit s' (* (inc i) dt) (nth actions i))))))))))

(defn trajectory-length
  "Arc length of a trajectory (sum of segment lengths in the ego/BEV plane)."
  [wps]
  (loop [i 1 d 0]
    (if (>= i (count wps))
      d
      (let [p0 (get-in wps [(dec i) :translation])
            p1 (get-in wps [i :translation])
            dx (- (nth p1 0) (nth p0 0))
            dy (- (nth p1 1) (nth p0 1))]
        (recur (inc i) (+ d (Math/hypot dx dy)))))))
