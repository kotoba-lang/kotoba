(ns kami-app-giemon.caterpillar
  "Giemon Caterpillar — heavy dual-track UGV, 380x300mm footprint, 6 drive
  wheels per side, 360-degree LiDAR + stereo camera, no manipulator arm.
  1:1 port of `caterpillar_body`/`caterpillar_sensors`/`build_caterpillar`
  from the legacy `kami-app-giemon` crate (kotoba-lang/kami-engine, deleted
  in PR #82 \"Remove Rust workspace\") as part of the clj-wgsl migration
  (ADR-2607010930, `com-junkawasaki/root`).

  See `kami-app-giemon.armcrawler` for the part-map/exclusion conventions
  shared by every model namespace in this restoration."
  (:require [kami-app-giemon.geom :as g]
            [kotoba.lang.text :as str]))

(def armor [0.22 0.25 0.29])
(def rubber [0.12 0.12 0.13])
(def steel [0.55 0.58 0.62])
(def aluminium [0.76 0.78 0.80])
(def sensor [0.12 0.68 0.82])

(defn- box-part [id name color scale translate rotation]
  {:id id :name name :color color
   :scale scale :translate translate :rotation rotation})

(defn- cyl-part [id name color radius height translate rotation]
  (box-part id name color [radius height radius] translate rotation))

(defn caterpillar-body-parts []
  (let [rot90x (g/quat-from-rotation-x (/ Math/PI 2))]
    (concat
     [(box-part "cat_body" "Chassis Armour" armor
                [0.380 0.080 0.200] [0.0 0.040 0.0] g/quat-identity)]
     (for [[id name tz] [["cat_track_l" "Left Track" -0.132]
                         ["cat_track_r" "Right Track" 0.132]]]
       (box-part id name rubber
                 [0.400 0.060 0.065] [0.0 0.030 tz] g/quat-identity))
     (let [wheel-xs [-0.150 -0.090 -0.030 0.030 0.090 0.150]]
       (for [[si tz] (map-indexed vector [-0.132 0.132])
             [wi wx] (map-indexed vector wheel-xs)]
         (let [s (if (zero? si) "l" "r")
               s-cap (str/upper s)]
           (cyl-part (str "cat_wh_" s wi) (str "Drive Wheel " s-cap (inc wi))
                     steel 0.021 0.052 [wx 0.020 tz] rot90x))))
     [(box-part "cat_elec" "Electronics Bay" [0.10 0.35 0.15]
                [0.120 0.040 0.160] [0.100 0.100 0.0] g/quat-identity)
      (box-part "cat_batt" "Battery Pack (18650 x 8)" [0.20 0.20 0.22]
                [0.140 0.035 0.160] [-0.110 0.097 0.0] g/quat-identity)
      (box-part "cat_rpi" "Raspberry Pi 5" [0.10 0.32 0.10]
                [0.085 0.016 0.056] [-0.120 0.099 0.0] g/quat-identity)])))

(defn caterpillar-sensors-parts []
  [(box-part "cat_top" "Sensor Platform" aluminium
             [0.220 0.010 0.160] [-0.010 0.085 0.0] g/quat-identity)
   (cyl-part "lidar" "LiDAR 360" sensor
             0.030 0.028 [-0.010 0.099 0.0] g/quat-identity)
   (cyl-part "imu_gps" "IMU + GPS" aluminium
             0.015 0.008 [-0.010 0.113 0.0] g/quat-identity)
   (box-part "cam_mast" "Camera Mast" aluminium
             [0.012 0.065 0.012] [0.085 0.118 0.0] g/quat-identity)
   (box-part "cam_head" "Stereo Camera" sensor
             [0.032 0.022 0.024] [0.085 0.161 0.005] g/quat-identity)])

(defn build-caterpillar
  "All Giemon Caterpillar UGV parts: body + sensors. Mirrors
  `build_caterpillar`."
  []
  (concat (caterpillar-body-parts) (caterpillar-sensors-parts)))
