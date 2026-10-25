(ns kotoba.lang.kami-nv-compat.assets.ur10
  "UR10 (Universal Robots) 6-DoF industrial arm asset wrapper — JVM port of
  src/assets/ur10.ts. Joint origins in modified-DH form per the publicly-
  distributed ur_description ROS package (github.com/ros-industrial/
  universal_robot, BSD-3). No mesh / no Isaac Sim USD refs — joint kinematics
  only, sufficient to drive a generic serial-chain FK kernel. Trademark:
  'Universal Robots'/'UR10' are trademarks of Universal Robots A/S;
  API-namespace localization only. Wave 7 of ADR-2607020130.")

(def ^:private half-pi (/ Math/PI 2))

;; UR10 joint origins per ur_description (BSD-3): shoulder_pan/lift, elbow,
;; wrist_1/2/3.
(def ^:private ur10-origins
  [{:xyz [0 0 0.1273]         :rpy [0 0 0]        :axis [0 0 1]}
   {:xyz [0 0 0]              :rpy [0 half-pi 0]  :axis [0 1 0]}
   {:xyz [-0.612 0 0]         :rpy [0 0 0]        :axis [0 1 0]}
   {:xyz [-0.5723 0 0.163941] :rpy [0 half-pi 0]  :axis [0 1 0]}
   {:xyz [0 -0.1157 0]        :rpy [0 0 0]        :axis [0 0 1]}
   {:xyz [0 0 0.0922]         :rpy [0 0 0]        :axis [0 1 0]}])

(def ur10-joint-names
  ["shoulder_pan_joint" "shoulder_lift_joint" "elbow_joint"
   "wrist_1_joint" "wrist_2_joint" "wrist_3_joint"])

;; Joint limits per UR10 datasheet (±2π all joints, elbow ±π; max velocity /
;; effort per ur_description). N·m effort, UR10 public spec.
(def ur10-lower [(* -2 Math/PI) (* -2 Math/PI) (- Math/PI) (* -2 Math/PI) (* -2 Math/PI) (* -2 Math/PI)])
(def ur10-upper [(* 2 Math/PI)  (* 2 Math/PI)  Math/PI    (* 2 Math/PI)  (* 2 Math/PI)  (* 2 Math/PI)])
(def ur10-vel-limit [2.16 2.16 3.15 3.20 3.20 3.20])
(def ur10-effort [330 330 150 54 54 54])

(defn make-ur10
  "UR10 6-DoF asset. opts: {:prim-path :name}. Returns a map with :joint-names,
  limits, per-joint origin xyz/rpy/axis, and :flat-xyz/:flat-rpy/:flat-axis
  fns (flat N×3 storage for a generic serial-chain FK kernel)."
  ([]
   (make-ur10 nil))
  ([{:keys [prim-path name] :or {prim-path "/World/UR10" name "ur10"}}]
   (let [xyz  (mapv :xyz ur10-origins)
         rpy  (mapv :rpy ur10-origins)
         axis (mapv :axis ur10-origins)]
     {:prim-path               prim-path
      :name                    name
      :joint-names             ur10-joint-names
      :dof-count               6
      :default-joint-positions [0 (- half-pi) 0 (- half-pi) 0 0]
      :default-joint-velocities (vec (repeat 6 0))
      :joint-lower-limits      ur10-lower
      :joint-upper-limits      ur10-upper
      :joint-velocity-limits   ur10-vel-limit
      :effort-limits           ur10-effort
      :joint-origin-xyz        xyz
      :joint-origin-rpy        rpy
      :joint-axis              axis
      :flat-xyz                (fn [] (vec (mapcat identity xyz)))
      :flat-rpy                (fn [] (vec (mapcat identity rpy)))
      :flat-axis               (fn [] (vec (mapcat identity axis)))})))
