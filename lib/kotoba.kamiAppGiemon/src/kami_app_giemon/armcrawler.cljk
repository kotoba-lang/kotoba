(ns kami-app-giemon.armcrawler
  "ArmCrawler procedural geometry — rubber-track crawler chassis (2 tracks +
  8 drive wheels) + a 6-DOF display-pose arm (J1-J6 links) + a 2-finger
  gripper. 1:1 port of `crawler_chassis`/`arm_assembly`/`build_armcrawler`
  from the legacy `kami-app-giemon` crate (kotoba-lang/kami-engine, deleted
  in PR #82 \"Remove Rust workspace\") as part of the clj-wgsl migration
  (ADR-2607010930, `com-junkawasaki/root`).

  Every part is emitted as a map `{:id :name :color :scale :translate
  :rotation}` (a `kami-app-giemon.geom/transform` plus id/name/color) —
  the pure geometry data the original `push_box`/`push_cyl` calls fed into
  the native `CadSceneAdapter`. Building/uploading the actual GPU batches
  is native-only and excluded here."
  (:require [kami-app-giemon.geom :as g]))

;; ── colours (linear sRGB) ────────────────────────────────────────────────

(def aluminium [0.76 0.78 0.80])
(def steel [0.55 0.58 0.62])
(def rubber [0.12 0.12 0.13])
(def arm-body [0.96 0.55 0.13])
(def servo [0.22 0.25 0.28])
(def gripper-color [0.30 0.72 0.55])

(defn- box-part [id name color scale translate rotation]
  {:id id :name name :color color
   :scale scale :translate translate :rotation rotation})

(defn- cyl-part [id name color radius height translate rotation]
  (box-part id name color [radius height radius] translate rotation))

;; ── chassis ──────────────────────────────────────────────────────────────

(defn crawler-chassis-parts []
  (concat
   [(box-part "chassis" "Chassis" aluminium
              [0.220 0.060 0.160] [0.0 0.030 0.0] g/quat-identity)]
   (for [[id name z] [["track_l" "Left track" -0.105]
                       ["track_r" "Right track" 0.105]]]
     (box-part id name rubber
               [0.240 0.048 0.040] [0.0 0.024 z] g/quat-identity))
   (let [wheel-xs [-0.090 -0.030 0.030 0.090]
         rot90x (g/quat-from-rotation-x (/ Math/PI 2))]
     (for [[side-i z] (map-indexed vector [-0.105 0.105])
           [wi wx] (map-indexed vector wheel-xs)]
       (let [side (if (zero? side-i) "l" "r")
             side-cap (if (zero? side-i) "L" "R")]
         (cyl-part (str "wheel_" side "_" wi) (str "Drive wheel " side-cap (inc wi))
                   steel 0.0175 0.038 [wx 0.020 z] rot90x))))
   [(box-part "battery" "Battery (18650 x 4)" [0.20 0.20 0.22]
              [0.100 0.028 0.060] [0.0 0.0 0.0] g/quat-identity)]))

;; ── arm ──────────────────────────────────────────────────────────────────
;; Arm root mounted at (0.04, 0.060, 0.0) — top-front of chassis.
;; Display pose: slight forward lean, partially extended.

(defn arm-assembly-parts []
  (let [root [0.04 0.060 0.0]
        j1 (cyl-part "j1" "J1 - Waist" servo
                      0.022 0.040 (g/v3+ root [0.0 0.020 0.0]) g/quat-identity)
        l1-top (g/v3+ root [0.0 (+ 0.040 0.090) 0.0])
        l1 (box-part "l1" "Link 1 (shoulder)" arm-body
                      [0.030 0.090 0.030] (g/v3+ root [0.0 (+ 0.040 0.045) 0.0]) g/quat-identity)
        j2 (box-part "j2" "J2 - Shoulder pitch" servo
                      [0.040 0.032 0.040] (g/v3+ l1-top [0.0 0.016 0.0]) g/quat-identity)
        ang2 (Math/toRadians 30.0)
        l2-dir [(Math/sin ang2) (Math/cos ang2) 0.0]
        l2-rot (g/quat-from-rotation-z (- ang2))
        l2-mid (g/v3+ (g/v3+ l1-top [0.0 0.032 0.0]) (g/v3-scale l2-dir 0.050))
        l2 (box-part "l2" "Link 2 (upper arm)" arm-body
                      [0.028 0.100 0.028] l2-mid l2-rot)
        l2-end (g/v3+ (g/v3+ l1-top [0.0 0.032 0.0]) (g/v3-scale l2-dir 0.100))
        j3 (box-part "j3" "J3 - Elbow" servo
                      [0.036 0.030 0.036] (g/v3+ l2-end [0.0 0.015 0.0]) g/quat-identity)
        ang3 (Math/toRadians (+ 30.0 20.0))
        l3-dir [(Math/sin ang3) (Math/cos ang3) 0.0]
        l3-rot (g/quat-from-rotation-z (- ang3))
        l3-start (g/v3+ l2-end [0.0 0.030 0.0])
        l3-mid (g/v3+ l3-start (g/v3-scale l3-dir 0.040))
        l3 (box-part "l3" "Link 3 (forearm)" arm-body
                      [0.024 0.080 0.024] l3-mid l3-rot)
        l3-end (g/v3+ l3-start (g/v3-scale l3-dir 0.080))
        j4 (cyl-part "j4" "J4 - Forearm rotation" servo
                      0.016 0.030 l3-end (g/quat-from-rotation-z (- ang3)))
        l4-start (g/v3+ l3-end (g/v3-scale l3-dir 0.015))
        l4-mid (g/v3+ l4-start (g/v3-scale l3-dir 0.030))
        l4 (box-part "l4" "Link 4 (wrist)" arm-body
                      [0.020 0.060 0.020] l4-mid l3-rot)
        l4-end (g/v3+ l4-start (g/v3-scale l3-dir 0.060))
        j5 (cyl-part "j5" "J5 - Wrist pitch" servo
                      0.014 0.024 l4-end
                      (g/quat-from-rotation-z (+ (- ang3) (/ Math/PI 2))))
        grip-base (g/v3+ l4-end (g/v3-scale l3-dir 0.020))
        j6 (cyl-part "j6" "J6 - Wrist rotation" servo
                      0.012 0.020 grip-base (g/quat-from-rotation-z (- ang3)))
        fwd (g/v3-scale l3-dir 0.018)
        fingers (for [[gid gname offset-z] [["grip_l" "Gripper finger L" -0.012]
                                              ["grip_r" "Gripper finger R" 0.012]]]
                  (box-part gid gname gripper-color
                            [0.008 0.032 0.008]
                            (g/v3+ (g/v3+ grip-base fwd) [0.0 0.0 offset-z])
                            l3-rot))
        hat-pcb (box-part "hat_pcb" "ArmCrawlerHAT PCB" [0.12 0.38 0.18]
                           [0.065 0.002 0.056] [-0.06 0.061 0.0] g/quat-identity)
        rpi5 (box-part "rpi5" "Raspberry Pi 5" [0.10 0.32 0.10]
                        [0.085 0.016 0.056] [-0.06 0.052 0.0] g/quat-identity)]
    (concat [j1 l1 j2 l2 j3 l3 j4 l4 j5 j6] fingers [hat-pcb rpi5])))

(defn build-armcrawler
  "All ArmCrawler parts: chassis + arm assembly. Mirrors `build_armcrawler`."
  []
  (concat (crawler-chassis-parts) (arm-assembly-parts)))
