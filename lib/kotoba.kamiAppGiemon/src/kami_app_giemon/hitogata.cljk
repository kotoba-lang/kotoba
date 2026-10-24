(ns kami-app-giemon.hitogata
  "Giemon Bipede — 17-DOF humanoid, ~285mm tall, standing display pose. 1:1
  port of `hitogata_legs`/`hitogata_torso`/`hitogata_arms`/`build_hitogata`
  from the legacy `kami-app-giemon` crate (kotoba-lang/kami-engine, deleted
  in PR #82 \"Remove Rust workspace\") as part of the clj-wgsl migration
  (ADR-2607010930, `com-junkawasaki/root`).

  See `kami-app-giemon.armcrawler` for the part-map/exclusion conventions
  shared by every model namespace in this restoration."
  (:require [kami-app-giemon.geom :as g]))

(def shell [0.88 0.90 0.93])
(def accent [0.18 0.55 0.88])
(def servo [0.22 0.25 0.28])
(def gripper-color [0.30 0.72 0.55])

(defn- box-part [id name color scale translate rotation]
  {:id id :name name :color color
   :scale scale :translate translate :rotation rotation})

(defn- cyl-part [id name color radius height translate rotation]
  (box-part id name color [radius height radius] translate rotation))

(defn hitogata-legs-parts []
  (let [rot90x (g/quat-from-rotation-x (/ Math/PI 2))]
    (mapcat
     (fn [[leg-x s cap]]
       [(box-part (str "foot_" s) (str "Foot " cap) shell
                   [0.060 0.015 0.035] [leg-x 0.0075 0.005] g/quat-identity)
        (cyl-part (str "ankle_" s) (str "Ankle " cap) servo
                  0.008 0.014 [leg-x 0.015 0.0] rot90x)
        (box-part (str "shin_" s) (str "Shin " cap) shell
                  [0.016 0.072 0.016] [leg-x 0.051 0.0] g/quat-identity)
        (cyl-part (str "knee_" s) (str "Knee " cap) servo
                  0.010 0.016 [leg-x 0.087 0.0] rot90x)
        (box-part (str "thigh_" s) (str "Thigh " cap) shell
                  [0.018 0.074 0.018] [leg-x 0.124 0.0] g/quat-identity)
        (cyl-part (str "hip_" s) (str "Hip " cap) servo
                  0.011 0.018 [leg-x 0.161 0.0] rot90x)])
     [[-0.028 "l" "L"] [0.028 "r" "R"]])))

(defn hitogata-torso-parts []
  [(box-part "pelvis" "Pelvis" shell
             [0.080 0.020 0.038] [0.0 0.171 0.0] g/quat-identity)
   (box-part "torso" "Torso" shell
             [0.058 0.082 0.034] [0.0 0.222 0.0] g/quat-identity)
   (box-part "chest_panel" "Chest Panel" accent
             [0.034 0.040 0.003] [0.0 0.218 0.019] g/quat-identity)
   (cyl-part "neck" "Neck" servo
             0.009 0.010 [0.0 0.263 0.0] g/quat-identity)
   (box-part "head" "Head" shell
             [0.040 0.038 0.035] [0.0 0.282 0.0] g/quat-identity)
   (box-part "visor" "Camera Visor" accent
             [0.032 0.006 0.003] [0.0 0.286 0.019] g/quat-identity)])

(defn hitogata-arms-parts []
  (let [rot90x (g/quat-from-rotation-x (/ Math/PI 2))
        arm-ang (Math/toRadians 20.0)]
    (mapcat
     (fn [[sx s cap]]
       (let [shoulder [(* sx 0.040) 0.255 0.0]
             arm-dir [(* sx (Math/sin arm-ang)) (- (Math/cos arm-ang)) 0.0]
             arm-rot (g/quat-from-rotation-z (* sx arm-ang))
             elbow (g/v3+ shoulder (g/v3-scale arm-dir 0.062))
             wrist (g/v3+ elbow (g/v3-scale arm-dir 0.055))]
         [(cyl-part (str "shoulder_" s) (str "Shoulder " cap) servo
                    0.010 0.014 shoulder rot90x)
          (box-part (str "upper_arm_" s) (str "Upper Arm " cap) shell
                    [0.015 0.062 0.015] (g/v3+ shoulder (g/v3-scale arm-dir 0.031)) arm-rot)
          (cyl-part (str "elbow_" s) (str "Elbow " cap) servo
                    0.009 0.012 elbow rot90x)
          (box-part (str "forearm_" s) (str "Forearm " cap) shell
                    [0.013 0.055 0.013] (g/v3+ elbow (g/v3-scale arm-dir 0.028)) arm-rot)
          (cyl-part (str "wrist_" s) (str "Wrist " cap) servo
                    0.008 0.010 wrist g/quat-identity)
          (box-part (str "hand_" s) (str "Hand " cap) gripper-color
                    [0.014 0.020 0.009] (g/v3+ wrist (g/v3-scale arm-dir 0.012)) arm-rot)]))
     [[-1.0 "l" "L"] [1.0 "r" "R"]])))

(defn build-hitogata
  "All Giemon Bipede humanoid parts: legs + torso + arms. Mirrors
  `build_hitogata`."
  []
  (concat (hitogata-legs-parts) (hitogata-torso-parts) (hitogata-arms-parts)))
