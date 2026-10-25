(ns kotoba.lang.kami-nv-compat.wadachi-sim.index
  "wadachi-sim — clean-room AV simulation engine (wadachi-sim 轍). Portable
  .cljc port of src/wadachi-sim/index.ts. Wave 33 (closes wadachi-sim).

  The canonical KAMI implementation behind the nv-compat/drive-sim facade.
  Owns the scenario world, the per-tick physics advance, the sensor rig,
  and the closed-loop driving step that plugs a driving model in
  (e.g. Alpamayo VLA) to steer the ego.

  A DriveSim is an atom holding {:init :scenario :rig :dt :command
  :speed-limit :tick}. Since scenario/actor maps are plain immutable
  Clojure data, no scenario-cloning is needed (unlike the TS class, which
  deep-copies on construction/reset to avoid aliasing a caller's arrays) —
  :init and :scenario safely share structure until a step produces a NEW
  scenario value.

  A driving model is just a plain function `(fn [obs] {:trajectory [...]})`
  (Clojure functions-as-values, not a TS class/protocol).

  Civilian, SAE-L4 ceiling, simulation-only (no actuation). ADR-2605261800
  D1 (DriveSim -> wadachi-sim); AV scope per ADR-2605242000 / ADR-2606010600."
  (:require [kotoba.lang.kami-nv-compat.kami-drive.unicycle :as unicycle]
            [kotoba.lang.kami-nv-compat.wadachi-sim.world :as world]
            [kotoba.lang.kami-nv-compat.wadachi-sim.sensors :as sensors]))

;; SensorRig    {:camera? :lidar? :radar?}
;; SensorFrame  {:tick :time :ground-truth :camera? :lidar? :radar?}
;; DriveSimConfig {:scenario :rig :hz :command? :speed-limit?}

(defn make-drive-sim
  "A closed-loop / open-loop AV simulator. step! advances the world one
  tick; sense samples the configured sensors against the current world."
  [cfg]
  (atom {:init (:scenario cfg)
         :scenario (:scenario cfg)
         :rig (:rig cfg)
         :dt (/ 1.0 (:hz cfg))
         :command (or (:command cfg) "keep_lane")
         :speed-limit (:speed-limit cfg)
         :tick 0}))

(defn reset-sim!
  "Reset to the initial scenario."
  [sim]
  (swap! sim assoc :scenario (:init @sim) :tick 0))

(defn world
  [sim]
  (:scenario @sim))

(defn scene
  "Build the current kami-rt scene (ground + actors + obstacles)."
  [sim]
  (world/build-sensor-scene (:scenario @sim)))

(defn sense
  "Sample all configured sensors against the current world."
  [sim]
  (let [{:keys [scenario rig tick dt]} @sim
        gt (world/ground-truth scenario)
        need-scene? (or (:camera rig) (:lidar rig))
        sc (when need-scene? (scene sim))
        camera-frame (when (:camera rig) (sensors/sample-camera scenario gt sc (:camera rig)))
        lidar-scan (when (:lidar rig) (sensors/sample-lidar scenario sc (:lidar rig)))
        radar-dets (when (:radar rig) (sensors/sample-radar scenario (:radar rig)))]
    (cond-> {:tick tick :time (* tick dt) :ground-truth gt}
      camera-frame (assoc :camera camera-frame)
      lidar-scan (assoc :lidar lidar-scan)
      radar-dets (assoc :radar radar-dets))))

(defn- to-ego-frame
  [ego a]
  (let [c (Math/cos (- (:yaw ego)))
        s (Math/sin (- (:yaw ego)))
        dx (- (:x a) (:x ego))
        dy (- (:y a) (:y ego))
        rvx (- (:vx a) (* (:speed ego) (Math/cos (:yaw ego))))
        rvy (- (:vy a) (* (:speed ego) (Math/sin (:yaw ego))))]
    {:id (:id a) :kind (:kind a)
     :x (- (* dx c) (* dy s)) :y (+ (* dx s) (* dy c))
     :vx (- (* rvx c) (* rvy s)) :vy (+ (* rvx s) (* rvy c))}))

(defn observation
  "The ego-frame observation a driving model consumes (actors -> ego frame)."
  [sim]
  (let [{:keys [scenario command speed-limit]} @sim
        ego (:ego scenario)]
    {:ego {:x 0.0 :y 0.0 :yaw 0.0 :speed (:speed ego)}
     :command command
     :agents (mapv #(to-ego-frame ego %) (:actors scenario))
     :speed-limit speed-limit}))

(defn step!
  "Advance one tick. With :model, the ego is driven closed-loop by the
  model's first dynamic action; otherwise an explicit :action is applied
  (default: hold). Actors advance by their scripted constant velocity."
  ([sim] (step! sim {}))
  ([sim opts]
   (let [action0 (or (:action opts) {:accel 0.0 :curvature 0.0})
         action (if-let [model (:model opts)]
                  (let [out (model (observation sim))
                        traj (:trajectory out)]
                    (if (> (count traj) 1) (traj 1) action0))
                  action0)
         {:keys [scenario dt]} @sim
         e (:ego scenario)
         bev (unicycle/step-unicycle {:x (:x e) :y (:y e) :yaw (:yaw e) :speed (:speed e)} action dt)
         new-ego (merge e bev)
         new-actors (mapv (fn [a] (-> a
                                       (update :x + (* (:vx a) dt))
                                       (update :y + (* (:vy a) dt))))
                           (:actors scenario))]
     (swap! sim (fn [s] (-> s
                            (assoc-in [:scenario :ego] new-ego)
                            (assoc-in [:scenario :actors] new-actors)
                            (update :tick inc))))
     nil)))

(defn run-rollout!
  "Run a closed-loop rollout: at each tick sense -> drive -> advance.
  Returns the per-tick sensor frames."
  [sim model num-ticks]
  (vec (for [_ (range num-ticks)]
         (let [frame (sense sim)]
           (step! sim {:model model})
           frame))))
