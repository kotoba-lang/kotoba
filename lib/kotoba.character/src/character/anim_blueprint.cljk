(ns character.anim-blueprint
  "Animation Blueprint: state machine for MetaHuman character animation.
  Provides a hierarchical state machine that blends animation clips,
  driven by parameters (speed, direction, emotion) and FACS controls.
  Restored from the legacy kami-engine/kami-character Rust crate's
  `anim_blueprint.rs` (deleted in kotoba-lang/kami-engine PR #82) as
  part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root)."
  (:refer-clojure :exclude [update])
  (:require [kotoba.lang.text :as str]))

(defn- anim-param [name default]
  {:name name :param-type (if (str/starts-with? name "is_") :bool :float)
   :value default :default-value default})

(defn metahuman-default
  "Create a MetaHuman default animation blueprint. Layers: body
  (locomotion), face (FACS-driven)."
  []
  (let [param-defaults
        [["speed" 0.0] ["direction" 0.0] ["is_moving" 0.0]
         ["emotion_happy" 0.0] ["emotion_sad" 0.0] ["emotion_angry" 0.0]
         ["blink" 0.0] ["look_x" 0.0] ["look_y" 0.0]
         ["jaw_open" 0.0] ["breath_cycle" 0.0]]
        parameters (into {} (map (fn [[n d]] [n (anim-param n d)]) param-defaults))
        body-layer
        {:name "body" :blend-mode :override :weight 1.0
         :states [{:name "idle" :state-type {:type :clip :clip-name "idle_breathe"} :play-rate 1.0 :looping true}
                  {:name "locomotion"
                   :state-type {:type :blend-space-1d :axis-param "speed"
                                :entries [{:clip-name "walk" :position 0.3}
                                          {:clip-name "jog" :position 0.6}
                                          {:clip-name "run" :position 1.0}]}
                   :play-rate 1.0 :looping true}]
         :transitions [{:source 0 :target 1 :duration 0.3 :blend-curve :ease-in-out
                         :conditions [{:param-name "is_moving" :comparison :greater :threshold 0.5}]
                         :priority 1}
                        {:source 1 :target 0 :duration 0.4 :blend-curve :ease-out
                         :conditions [{:param-name "is_moving" :comparison :less :threshold 0.5}]
                         :priority 1}]
         :active-state 0 :transition-progress 0.0 :transition-target nil}
        face-layer
        {:name "face" :blend-mode :additive :weight 1.0
         :states [{:name "face_idle" :state-type {:type :clip :clip-name "face_idle_micro"} :play-rate 1.0 :looping true}
                  {:name "face_talking"
                   :state-type {:type :blend-space-1d :axis-param "jaw_open"
                                :entries [{:clip-name "viseme_rest" :position 0.0}
                                          {:clip-name "viseme_open" :position 1.0}]}
                   :play-rate 1.0 :looping true}]
         :transitions [{:source 0 :target 1 :duration 0.15 :blend-curve :linear
                         :conditions [{:param-name "jaw_open" :comparison :greater :threshold 0.1}]
                         :priority 1}
                        {:source 1 :target 0 :duration 0.2 :blend-curve :ease-out
                         :conditions [{:param-name "jaw_open" :comparison :less :threshold 0.1}]
                         :priority 1}]
         :active-state 0 :transition-progress 0.0 :transition-target nil}]
    {:parameters parameters
     :layers [body-layer face-layer]
     :blend-profiles [{:name "upper_body"
                        :bone-weights {"head" 1.0 "neck" 1.0 "upperChest" 0.8 "chest" 0.5
                                       "leftShoulder" 0.9 "rightShoulder" 0.9
                                       "leftUpperArm" 1.0 "rightUpperArm" 1.0}}]}))

(defn set-param [bp name value]
  (if (get-in bp [:parameters name])
    (assoc-in bp [:parameters name :value] value)
    bp))

(defn- condition-met? [params {:keys [param-name comparison threshold]}]
  (let [val (get-in params [param-name :value] 0.0)]
    (case comparison
      :greater (> val threshold)
      :less (< val threshold)
      :equal (< (Math/abs (double (- val threshold))) 0.001)
      :not-equal (>= (Math/abs (double (- val threshold))) 0.001)
      :greater-equal (>= val threshold)
      :less-equal (<= val threshold))))

(defn- update-layer [params layer dt]
  (let [layer
        (if (nil? (:transition-target layer))
          (let [best
                (reduce
                 (fn [best t]
                   (if (and (= (:source t) (:active-state layer))
                            (every? #(condition-met? params %) (:conditions t))
                            (or (nil? best) (> (:priority t) (first best))))
                     [(:priority t) (:target t)]
                     best))
                 nil (:transitions layer))]
            (if best
              (assoc layer :transition-target (second best) :transition-progress 0.0)
              layer))
          layer)]
    (if-let [target (:transition-target layer)]
      (let [duration (or (:duration (first (filter #(and (= (:source %) (:active-state layer)) (= (:target %) target)) (:transitions layer))))
                          0.3)
            progress (+ (:transition-progress layer) (/ dt duration))]
        (if (>= progress 1.0)
          (assoc layer :active-state target :transition-target nil :transition-progress 0.0)
          (assoc layer :transition-progress progress)))
      layer)))

(defn update
  "Advance the state machine by `dt` seconds."
  [bp dt]
  (clojure.core/update bp :layers (fn [layers] (mapv #(update-layer (:parameters bp) % dt) layers))))

(defn layer-blend
  "Get the current blend `[active-state transition-target transition-progress]` for a layer."
  [bp layer-index]
  (let [layer (nth (:layers bp) layer-index)]
    [(:active-state layer) (:transition-target layer) (:transition-progress layer)]))
