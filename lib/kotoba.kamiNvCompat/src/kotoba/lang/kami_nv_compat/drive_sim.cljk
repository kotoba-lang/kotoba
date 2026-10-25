(ns kotoba.lang.kami-nv-compat.drive-sim
  "Drop-in NVIDIA DRIVE Sim API-compat facade — portable .cljc port of
  src/drive-sim.ts. A sensor-realistic, scenario-driven autonomous-vehicle
  simulator: a scenario world + ego + traffic actors, a sensor rig of
  cameras / LiDAR / radar producing frames + ground truth, stepped open- or
  closed-loop, so AV test scripts port to KAMI via require-path-only changes.

  DriveSim itself and the sensor rig / ground-truth machinery are already
  ported 1:1 in wadachi-sim.index (make-drive-sim, reset-sim!, world, scene,
  sense, observation, step!, run-rollout!) and wadachi-sim.{world,sensors}
  (default-mount, sensor-pose, build-sensor-scene, ground-truth) — callers
  require those namespaces directly, matching the kami-rt.index /
  omni-kit-app barrel precedent. No scenario-cloning is needed on this side
  either, for the same reason wadachi-sim.index gives: scenario/actor maps
  are plain immutable Clojure data.

  Real new logic ported here: default-ego + create-scenario (sensible
  defaults for a scenario world), create-camera / create-lidar / create-
  radar (sensor config builders with defaults), and obstacles-from-stage
  (the USD scenario bridge — DRIVE Sim scenarios are USD).

  Backed by the clean-room wadachi-sim engine (sensors grounded in the
  kami-rt ray tracer + utsushimi projection). No DRIVE Sim source/binaries;
  from-spec reproduction (Google v. Oracle, 593 U.S. ___ (2021)). Canonical
  engine: wadachi-sim.

  Charter: civilian, SAE-L4 ceiling, simulation-only (no actuation), and any
  closed-loop driving model runs under the `nv-compat/alpamayo` Murakumo-only
  inference posture.

  Trademark: NVIDIA® / DRIVE® / DRIVE Sim are trademarks of NVIDIA
  Corporation; API-compat identifiers only.

  ADR-2605261800 §D1/D6 (DriveSim -> wadachi-sim). Wave 40 of
  ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.omni-usd :as usd]
            [kotoba.lang.kami-nv-compat.wadachi-sim.sensors :as sensors]))

(def default-ego
  "EgoState {:x :y :yaw :speed :extent}."
  {:x 0 :y 0 :yaw 0 :speed 8 :extent [2.4 1 0.75]})

(defn create-scenario
  "Build a scenario world with sensible defaults. `opts` =
  {:ego :actors :obstacles :ground-half-size}; :ego partially overrides
  default-ego (its :extent falls back to default-ego's extent, matching the
  TS nullish-coalescing guard)."
  ([] (create-scenario {}))
  ([opts]
   (let [ego-opts (:ego opts)]
     {:ego              (merge default-ego ego-opts
                                {:extent (or (:extent ego-opts) (:extent default-ego))})
      :actors           (or (:actors opts) [])
      :obstacles        (or (:obstacles opts) [])
      :ground-half-size (or (:ground-half-size opts) 100)})))

;; ── sensor config builders (DRIVE Sim sensor rig) ───────────────────────────

(defn create-camera
  "CameraConfig {:width :height :vfov-deg :mount}."
  ([] (create-camera {}))
  ([cfg]
   {:width    (or (:width cfg) 320)
    :height   (or (:height cfg) 180)
    :vfov-deg (or (:vfov-deg cfg) 40)
    :mount    (or (:mount cfg) sensors/default-mount)}))

(defn create-lidar
  "LidarConfig {:azimuth-fov-deg :azimuth-steps :elevation-fov-deg
  :elevation-steps :max-range :mount}."
  ([] (create-lidar {}))
  ([cfg]
   {:azimuth-fov-deg   (or (:azimuth-fov-deg cfg) 360)
    :azimuth-steps     (or (:azimuth-steps cfg) 180)
    :elevation-fov-deg (or (:elevation-fov-deg cfg) 30)
    :elevation-steps   (or (:elevation-steps cfg) 8)
    :max-range         (or (:max-range cfg) 80)
    :mount             (or (:mount cfg) (assoc sensors/default-mount :height 1.8))}))

(defn create-radar
  "RadarConfig {:azimuth-fov-deg :max-range :mount}."
  ([] (create-radar {}))
  ([cfg]
   {:azimuth-fov-deg (or (:azimuth-fov-deg cfg) 120)
    :max-range       (or (:max-range cfg) 150)
    :mount           (or (:mount cfg) sensors/default-mount)}))

;; ── USD scenario bridge (DRIVE Sim scenarios are USD) ───────────────────────

(defn obstacles-from-stage
  "Build static obstacles from a parsed USD stage: each triangle becomes a
  box obstacle sized to its own AABB — one obstacle per triangle, not a
  merged per-mesh box (algorithm-for-algorithm port of the TS source). Ties
  the kami-usd reader (R1.4) to DriveSim so a USD scene can seed a
  simulation."
  ([stage] (obstacles-from-stage stage "unknown"))
  ([stage kind]
   (let [flat (usd/stage->flat-scene stage)]
     (vec
       (map-indexed
         (fn [i tri]
           (let [mins (reduce (fn [mn v] (mapv min mn v)) [##Inf ##Inf ##Inf] tri)
                 maxs (reduce (fn [mx v] (mapv max mx v)) [##-Inf ##-Inf ##-Inf] tri)
                 cx   (/ (+ (mins 0) (maxs 0)) 2.0)
                 cy   (/ (+ (mins 1) (maxs 1)) 2.0)]
             {:id     (str "usd-" i)
              :kind   kind
              :x      cx
              :y      cy
              :yaw    0
              :extent [(max 0.05 (/ (- (maxs 0) (mins 0)) 2.0))
                       (max 0.05 (/ (- (maxs 1) (mins 1)) 2.0))
                       (max 0.05 (/ (- (maxs 2) (mins 2)) 2.0))]}))
         (:triangles flat))))))

(def kami-engine "wadachi-sim")
(def adr "ADR-2605261800")
