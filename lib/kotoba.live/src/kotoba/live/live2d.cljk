(ns kotoba.live.live2d
  "Live2D — a 2D (Cubism-style) avatar driven from the same beat-synced show.

  VRM is a 3D rig; Live2D is a 2D parameter-warp avatar. Both are authored as
  data and driven by the *same* choreography: the show clock's `DancePose`
  and `BeatPhase` map onto the standard Cubism parameters (`ParamAngleX/Y/Z`,
  `ParamBodyAngle*`, `ParamBreath`, eye blink, mouth lipsync). So one
  `:dance/setlist` animates a VRM *or* a Live2D performer.

  This is the **data + driver** layer: it parses `:dance/live2d`, resolves
  per-frame parameter values, and emits a render-IR `:live2d` entry. The
  actual `.moc3`/`.model3.json` ArtMesh warp + Live2D physics is host-side
  (the Cubism runtime), exactly as VRM mesh skinning is."
  (:require [kotoba.lang.text :as str]
            [kotoba.live.edn-util :as eu]
            [kotoba.live.mathx :as mathx]))

(def ^:private tau mathx/tau)

(defn default-binding []
  {:model "" :home [0.0 0.0 0.0] :scale 1.0 :physics true
   :lipsync "ParamMouthOpenY" :motions [] :active-motion nil :params {}})

(defn- parse-motion-key [km]
  {:time (eu/num (get km :t)) :params (eu/param-map (get km :params))})

(defn- parse-motion [mm]
  (let [name (get mm :name)]
    (when name
      {:name name
       :file (let [f (get mm :file)] (when (and f (not (str/blank? f))) f))
       :looping (boolean (get mm :loop))
       :keys (vec (sort-by :time (mapv parse-motion-key (or (get mm :keys) []))))})))

(defn from-edn
  "Parse a `:dance/live2d` map."
  [m]
  (merge (default-binding)
         {:model (or (get m :model) "")
          :home (or (eu/opt-vec3 (get m :home)) [0.0 0.0 0.0])
          :scale (let [s (get m :scale)] (if (and s (pos? s)) (double s) 1.0))
          :physics (if (contains? m :physics) (boolean (get m :physics)) true)
          :lipsync (eu/ident (get m :lipsync) "ParamMouthOpenY")
          :motions (vec (keep parse-motion (or (get m :motions) [])))
          :active-motion (eu/ident (get m :motion) nil)
          :params (eu/param-map (get m :params))}))

(defn- blink-value [t]
  (let [m (- t (* 3.0 (mathx/floor (/ t 3.0))))]
    (if (< m 0.12)
      (min 1.0 (mathx/abs (- (/ m 0.06) 1.0)))
      1.0)))

(defn sample-motion
  "Sample a named inline motion's parameters at `time` seconds (linear
  interpolation; loops if the motion is `:looping true`). `nil` for an
  unknown motion or a file-only motion (no inline `:keys`)."
  [binding motion-name time]
  (when-let [motion (first (filter #(= motion-name (:name %)) (:motions binding)))]
    (let [keys* (:keys motion)]
      (when (seq keys*)
        (let [duration (:time (last keys*))
              t (if (and (:looping motion) (pos? duration))
                  (- time (* duration (mathx/floor (/ time duration))))
                  time)]
          (cond
            (<= t (:time (first keys*))) (:params (first keys*))
            (>= t duration) (:params (last keys*))
            :else
            (let [i (loop [i 0]
                      (if (and (< i (dec (count keys*))) (< (:time (nth keys* (inc i))) t))
                        (recur (inc i))
                        i))
                  a (nth keys* i)
                  b (nth keys* (inc i))
                  f (if (> (:time b) (:time a)) (/ (- t (:time a)) (- (:time b) (:time a))) 0.0)
                  ks (into #{} (concat (keys (:params a)) (keys (:params b))))]
              (into {} (keep (fn [k]
                               (let [va (get (:params a) k) vb (get (:params b) k)]
                                 (cond
                                   (and va vb) [k (+ va (* (- vb va) f))]
                                   va [k va]
                                   vb [k vb]
                                   :else nil)))
                             ks)))))))))

(defn drive
  "Resolve the parameter values for this frame: the rest `:params` overlaid
  with the standard Cubism parameters driven by the beat-synced `pose`.
  `voice-mouth` (the `:dance/avatar :voice` vowel weight, when authored)
  drives the mouth lipsync instead of the default beat-open."
  [binding pose phase voice-mouth]
  (let [deg (fn [r] (mathx/to-degrees r))
        clamp (fn [lo hi x] (max lo (min hi x)))
        p (transient (:params binding))
        p (assoc! p "ParamAngleX" (clamp -30.0 30.0 (deg (:root-yaw pose))))
        p (assoc! p "ParamAngleZ" (clamp -30.0 30.0 (deg (:spine-sway pose))))
        p (assoc! p "ParamBodyAngleX" (clamp -10.0 10.0 (deg (* (:root-yaw pose) 0.5))))
        p (assoc! p "ParamBodyAngleZ" (clamp -10.0 10.0 (deg (:spine-sway pose))))
        p (assoc! p "ParamAngleY" (clamp -30.0 30.0 (* (:vertical-bob pose) 200.0)))
        p (assoc! p "ParamBreath" (+ 0.5 (* 0.5 (mathx/sin (* (:time phase) 1.5)))))
        blink (blink-value (:time phase))
        p (assoc! p "ParamEyeLOpen" blink)
        p (assoc! p "ParamEyeROpen" blink)
        mouth (or voice-mouth (* (- 1.0 (mathx/cos (* (:beat-frac phase) tau))) 0.5))
        p (assoc! p (:lipsync binding) (clamp 0.0 1.0 mouth))
        p (persistent! p)
        p (if-let [name (:active-motion binding)]
            (if-let [mp (sample-motion binding name (:time phase))]
              (merge p mp)
              p)
            p)]
    p))

(defn render-entry
  "Build the render-IR `:live2d` entry for the given driven parameters."
  [binding driven]
  {:kind :live2d :model (:model binding) :pos (:home binding) :scale (:scale binding)
   :physics (:physics binding) :params driven})
