(ns kotoba.lang.kami-nv-compat.wadachi-sim.sensors
  "wadachi-sim — clean-room sensor models (camera / LiDAR / radar). Portable
  .cljc port of src/wadachi-sim/sensors.ts. Wave 29 (partial) + wave 33
  (sample-camera, unblocked by utsushimi.render-bridge; closes this file).

  DriveSim's value is sensor-realistic ground truth; these models reproduce
  that on the kami-rt ray tracer + the utsushimi camera projection:
    - CameraSensor : kami-rt RGB frame + projected 2D bounding-box ground truth
    - LidarSensor  : BVH ray-cast scan -> range image + 3D point cloud
    - RadarSensor  : per-object range / azimuth / radial-velocity detections

  All sensors are mounted on the ego with a planar offset + yaw and a mast
  height; their forward axis follows the ego heading. Deterministic,
  CPU-only.

  ADR-2605261800 SD1/D6 (DriveSim -> wadachi-sim)."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]
            [kotoba.lang.kami-nv-compat.utsushimi.render-bridge :as rb]
            [kotoba.lang.kami-nv-compat.wadachi-sim.world :as world]))

;; ── sensor mount ─────────────────────────────────────────────────────────
;;
;; SensorMount {:forward :left :height :yaw}

(def default-mount
  "forward/left offset from the ego origin (ego frame, m); height = mast
  height above ground (m); yaw = offset from the ego heading (rad)."
  {:forward 1.5 :left 0.0 :height 1.5 :yaw 0.0})

(defn sensor-pose
  "World-space sensor pose ({:origin :heading}) for an ego + mount."
  [ego mount]
  (let [c (Math/cos (:yaw ego))
        s (Math/sin (:yaw ego))
        origin [(- (+ (:x ego) (* (:forward mount) c)) (* (:left mount) s))
                (+ (:y ego) (* (:forward mount) s) (* (:left mount) c))
                (:height mount)]]
    {:origin origin :heading (+ (:yaw ego) (:yaw mount))}))

;; ── camera sensor ────────────────────────────────────────────────────────
;;
;; CameraConfig {:width :height :vfov-deg :mount}
;; CameraBox {:id :kind :bbox2d}
;; CameraFrame {:rgb :boxes :width :height}

(defn sample-camera
  "Render an RGB frame + projected 2D ground-truth boxes for the scenario."
  [scenario gt scene cfg]
  (let [{:keys [origin heading]} (sensor-pose (:ego scenario) (:mount cfg))
        target [(+ (origin 0) (Math/cos heading)) (+ (origin 1) (Math/sin heading)) (origin 2)]
        up [0.0 0.0 1.0]
        aspect (/ (double (:width cfg)) (:height cfg))
        cam (bvh/look-at origin target up (:vfov-deg cfg) aspect)
        rgb (:framebuffer (kami-rt/trace-image-cpu scene cam (:width cfg) (:height cfg)))
        proj (rb/make-proj-camera origin target up (:vfov-deg cfg) aspect)
        boxes (keep (fn [o]
                      (let [aabb (world/world-aabb ((:center o) 0) ((:center o) 1) (:extent o) (:yaw o))
                            bbox (rb/project-aabb proj (:min aabb) (:max aabb) (:width cfg) (:height cfg))]
                        (when bbox {:id (:id o) :kind (:kind o) :bbox2d bbox})))
                    gt)]
    {:rgb rgb :boxes (vec boxes) :width (:width cfg) :height (:height cfg)}))

;; ── LiDAR sensor ─────────────────────────────────────────────────────────
;;
;; LidarConfig {:azimuth-fov-deg :azimuth-steps :elevation-fov-deg
;;              :elevation-steps :max-range :mount}
;; LidarReturn {:point :range :azimuth :elevation}
;; LidarScan   {:origin :returns :rays}

(defn sample-lidar
  "Cast a LiDAR scan against the scene BVH. Each (azimuth, elevation) ray
  that hits within :max-range yields a point."
  [scenario scene cfg]
  (let [{:keys [origin heading]} (sensor-pose (:ego scenario) (:mount cfg))
        az-half (/ (* (:azimuth-fov-deg cfg) Math/PI) 180.0 2.0)
        el-half (/ (* (:elevation-fov-deg cfg) Math/PI) 180.0 2.0)
        az-steps (:azimuth-steps cfg)
        el-steps (:elevation-steps cfg)
        az-step (if (> az-steps 1) (/ (* 2.0 az-half) (dec az-steps)) 0.0)
        el-step (if (> el-steps 1) (/ (* 2.0 el-half) (dec el-steps)) 0.0)
        returns (for [ai (range az-steps)
                      :let [az (+ (- az-half) (* ai az-step))
                            world-az (+ heading az)]
                      ei (range el-steps)
                      :let [el (+ (- el-half) (* ei el-step))
                            dir [(* (Math/cos el) (Math/cos world-az))
                                 (* (Math/cos el) (Math/sin world-az))
                                 (Math/sin el)]
                            hit (bvh/trace-closest (:soup scene) (:bvh scene) origin dir (:max-range cfg))]
                      :when hit]
                  {:point [(+ (origin 0) (* (dir 0) (:t hit)))
                           (+ (origin 1) (* (dir 1) (:t hit)))
                           (+ (origin 2) (* (dir 2) (:t hit)))]
                   :range (:t hit) :azimuth az :elevation el})]
    {:origin origin :returns (vec returns) :rays (* az-steps el-steps)}))

;; ── radar sensor ─────────────────────────────────────────────────────────
;;
;; RadarConfig    {:azimuth-fov-deg :max-range :mount}
;; RadarDetection {:id :range :azimuth :range-rate}

(defn- radar-consider
  "One candidate object -> a RadarDetection, or nil if outside FOV/range."
  [origin heading az-half max-range ego-vx ego-vy id x y vx vy]
  (let [dx (- x (origin 0))
        dy (- y (origin 1))
        range (Math/hypot dx dy)]
    (when (and (>= range 1e-3) (<= range max-range))
      (let [az0 (- (Math/atan2 dy dx) heading)
            az (Math/atan2 (Math/sin az0) (Math/cos az0))]
        (when (<= (Math/abs az) az-half)
          (let [losx (/ dx range)
                losy (/ dy range)
                range-rate (+ (* (- vx ego-vx) losx) (* (- vy ego-vy) losy))]
            {:id id :range range :azimuth az :range-rate range-rate}))))))

(defn sample-radar
  "Per-actor radar detections (range / azimuth / Doppler range-rate). Static
  obstacles have zero range-rate; only objects within FOV + range are
  returned. The ego's own velocity is included in the relative motion."
  [scenario cfg]
  (let [{:keys [origin heading]} (sensor-pose (:ego scenario) (:mount cfg))
        ego (:ego scenario)
        ego-vx (* (:speed ego) (Math/cos (:yaw ego)))
        ego-vy (* (:speed ego) (Math/sin (:yaw ego)))
        az-half (/ (* (:azimuth-fov-deg cfg) Math/PI) 180.0 2.0)
        max-range (:max-range cfg)
        actor-dets (keep (fn [a] (radar-consider origin heading az-half max-range ego-vx ego-vy
                                                  (:id a) (:x a) (:y a) (:vx a) (:vy a)))
                          (:actors scenario))
        obstacle-dets (keep (fn [o] (radar-consider origin heading az-half max-range ego-vx ego-vy
                                                     (:id o) (:x o) (:y o) 0.0 0.0))
                             (:obstacles scenario))]
    (vec (concat actor-dets obstacle-dets))))
