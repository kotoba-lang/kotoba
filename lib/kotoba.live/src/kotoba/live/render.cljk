(ns kotoba.live.render
  "Render-IR bridge — project a dance `ShowSnapshot` into the render-IR EDN
  shape (`{:globals ... :camera ... :lights ... :materials ... :meshes ...
  :animations ... :instances [...]}`) that native/web executors already
  consume. The dance show is authored as `:dance/*` EDN, ticked by
  `kotoba.live.show`, and *rendered* from data too: [[show->render-ir]] turns
  the per-frame snapshot into this map — the performer, crowd, and camera
  framing draw on every platform with no per-renderer code.

  The performer is emitted both as a placeholder instance (for v1 renderers)
  and, when a VRM is bound, as a skinned `:meshes` avatar with `:material` +
  `:skin` refs — so a host that understands the fuller vocabulary draws the
  real rig. This module only builds the EDN description; the actual GPU
  draw call, VRM mesh skinning, and audio playback device I/O are host-side
  (out of scope for this port — see README)."
  (:require [kotoba.lang.text :as str]
            [kotoba.live.avatar :as avatar]
            [kotoba.live.camera :as camera]
            [kotoba.live.mathx :as mathx]))

(defn- instance [pos color size yaw emissive]
  {:pos pos :color color :size size :yaw yaw :metallic 0.0 :roughness 0.7 :emissive emissive})

(defn- fixture-light-kind [fixture]
  (if (= fixture :spot) :spot :directional))

(defn show->render-ir
  "Project `snap` (a `kotoba.live.show/snapshot` result) + `avatar-binding`
  (see `kotoba.live.avatar`) + `cam` (a `kotoba.live.camera` rig) +
  `stage-props` into the render-IR map."
  [snap avatar-binding cam stage-props]
  (let [pose (:performer-pose snap)
        [px py pz] (:root-translation pose)
        s (max 0.01 (:scale avatar-binding))
        barf (+ (get-in snap [:phase :bar]) (get-in snap [:phase :bar-frac]))
        [cam-off cam-lk] (camera/framing-at cam barf)
        cam-eye [(+ px (nth cam-off 0)) (+ py (nth cam-off 1)) (+ pz (nth cam-off 2))]
        cam-target [(+ px (nth cam-lk 0)) (+ py (nth cam-lk 1)) (+ pz (nth cam-lk 2))]
        perf-y (+ py (:vertical-bob pose))
        perf-instance (instance [px perf-y pz] [1.0 0.82 0.72]
                                 [(* 0.9 s) (* 1.8 s)] (:root-yaw pose)
                                 (+ 0.12 (* 0.3 (:arms-up pose))))
        crowd-instances
        (mapv (fn [fan]
                (let [[color emissive] (if (:stick-raised fan)
                                          [(:stick-color fan) 0.6]
                                          [[0.28 0.30 0.38] 0.0])]
                  (instance (:position fan) color [0.45 (max 0.2 (:body-height fan))] 0.0 emissive)))
              (:crowd snap))
        stage-instances
        (mapv (fn [prop] (instance (:pos prop) (:color prop) (:size prop) 0.0 (:emissive prop)))
              stage-props)
        instances (into [perf-instance] (concat crowd-instances stage-instances))
        [tr tg tb] (get-in snap [:vj :palette :primary])
        sky {:horizon [(+ 0.15 (* 0.4 tr)) (+ 0.18 (* 0.4 tg)) (+ 0.22 (* 0.4 tb))]
             :sun-dir [-0.4 -0.85 -0.35]
             :sun [1.0 0.96 0.85]}
        globals {:sky sky :eye cam-eye :target cam-target}
        lights (mapv (fn [lf]
                       {:kind (fixture-light-kind (:fixture lf))
                        :color (:color lf)
                        :intensity (:intensity lf)
                        :dir (:aim lf)
                        :cast-shadow (= (:fixture lf) :spot)})
                     (:lighting snap))
        camera-ir {:eye cam-eye :target cam-target :fov (:fov cam) :near 0.1 :far 500.0}
        materials [{:id :performer :model :mtoon :base [1.0 0.82 0.72] :shade [0.7 0.55 0.5]
                    :alpha-mode :mask :alpha-cutoff 0.5}]
        meshes (if (and (:vrm avatar-binding) (not (str/blank? (:vrm avatar-binding))))
                 (let [weights (avatar/expression-weights avatar-binding (:cheer-loudness snap)
                                                           (get-in snap [:phase :beat-frac])
                                                           (get-in snap [:phase :time]))
                       voice (:voice avatar-binding)
                       weights (if voice
                                 (let [beat (+ (get-in snap [:phase :beat]) (get-in snap [:phase :beat-frac]))]
                                   (if-let [[vname w] (avatar/vowel-weight voice beat)]
                                     (assoc weights vname w)
                                     (assoc weights "aa" 0.0)))
                                 weights)
                       names (into (set (map :name (:expressions avatar-binding))) (keys weights))
                       expressions (into {} (map (fn [n] [(keyword n) (double (get weights n 0.0))])) names)]
                   [{:id :performer :url (:vrm avatar-binding) :pos [px perf-y pz]
                     :rot [0.0 (mathx/sin (* (:root-yaw pose) 0.5)) 0.0 (mathx/cos (* (:root-yaw pose) 0.5))]
                     :scale s :material :performer :skin :rig :expressions expressions :cast-shadow true}])
                 [])
        animations (if-let [clip (:clip avatar-binding)]
                     [{:target :performer :clip clip :time (get-in snap [:phase :time]) :interp :linear :weight 1.0}]
                     [])]
    {:globals globals :camera camera-ir :lights lights :materials materials
     :meshes meshes :animations animations :instances instances}))
