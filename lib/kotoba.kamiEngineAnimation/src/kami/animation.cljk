(ns kami.animation "Portable immutable keyframe and timeline evaluator.")

(defn keyframe
  ([time value] (keyframe time value :linear))
  ([time value interpolation]
   (keyframe time value interpolation {}))
  ([time value interpolation {:keys [tangent-in tangent-out broken?]
                              :or {tangent-in 0.0 tangent-out 0.0 broken? false}}]
   (when (neg? time) (throw (ex-info "keyframe time cannot be negative" {:time time})))
   {:keyframe/id (random-uuid) :keyframe/time time :keyframe/value value
    :keyframe/interpolation interpolation :keyframe/tangent-in tangent-in
    :keyframe/tangent-out tangent-out :keyframe/broken? broken?}))
(defn track [target keyframes]
  {:track/target target :track/keyframes (vec (sort-by :keyframe/time keyframes))})
(defn- lerp [a b t] (+ a (* (- b a) t)))
(defn- smoothstep [t] (* t t (- 3 (* 2 t))))
(defn- hermite [a b p tangent-out tangent-in duration]
  (let [p2 (* p p) p3 (* p2 p)
        h00 (+ (* 2 p3) (* -3 p2) 1) h10 (+ p3 (* -2 p2) p)
        h01 (+ (* -2 p3) (* 3 p2)) h11 (- p3 p2)]
    (+ (* h00 a) (* h10 duration tangent-out) (* h01 b) (* h11 duration tangent-in))))
(defn- interpolate [a b p kind tangent-out tangent-in duration]
  (case kind :step a :smooth (lerp a b (smoothstep p))
        :bezier (hermite a b p tangent-out tangent-in duration)
        :hermite (hermite a b p tangent-out tangent-in duration)
        (lerp a b p)))
(defn sample
  "Sample a scalar track at time. Values clamp outside its keyframe range."
  [{:track/keys [keyframes]} time]
  (when-not (seq keyframes) (throw (ex-info "track needs a keyframe" {})))
  (let [first-k (first keyframes) last-k (last keyframes)]
    (cond (<= time (:keyframe/time first-k)) (:keyframe/value first-k)
          (>= time (:keyframe/time last-k)) (:keyframe/value last-k)
          :else (let [[a b] (first (filter (fn [[a b]] (<= (:keyframe/time a) time (:keyframe/time b))) (partition 2 1 keyframes)))
                      duration (- (:keyframe/time b) (:keyframe/time a))
                      p (/ (- time (:keyframe/time a)) duration)]
                  (interpolate (:keyframe/value a) (:keyframe/value b) p
                               (:keyframe/interpolation a)
                               (:keyframe/tangent-out a 0.0) (:keyframe/tangent-in b 0.0) duration)))))

(defn timeline
  ([duration tracks] (timeline duration tracks {}))
  ([duration tracks {:keys [loop-start loop-end loop? playback-rate]
                     :or {loop-start 0 loop-end duration loop? false playback-rate 1.0}}]
   (when (or (not (pos? duration)) (< loop-start 0) (> loop-end duration) (>= loop-start loop-end))
     (throw (ex-info "invalid timeline or loop range" {:duration duration :loop-start loop-start :loop-end loop-end})))
   {:timeline/duration duration :timeline/tracks (vec tracks) :timeline/loop-start loop-start
    :timeline/loop-end loop-end :timeline/loop? loop? :timeline/playback-rate playback-rate}))
(defn evaluate [timeline time] (into {} (map (fn [t] [(:track/target t) (sample t time)]) (:timeline/tracks timeline))))

(defn playback-time [timeline elapsed]
  (let [scaled (* elapsed (:timeline/playback-rate timeline 1.0))
        start (:timeline/loop-start timeline 0) end (:timeline/loop-end timeline (:timeline/duration timeline))]
    (if (:timeline/loop? timeline)
      (+ start (mod (- scaled start) (- end start)))
      (max 0 (min (:timeline/duration timeline) scaled)))))
(defn evaluate-playback [timeline elapsed] (evaluate timeline (playback-time timeline elapsed)))

(defn auto-tangents
  "Calculate Catmull-Rom-style scalar slopes for a track, preserving key IDs."
  [{:track/keys [target keyframes]}]
  (track target
         (mapv (fn [i k]
                 (let [a (nth keyframes (max 0 (dec i))) b (nth keyframes (min (dec (count keyframes)) (inc i)))
                       dt (- (:keyframe/time b) (:keyframe/time a))
                       slope (if (zero? dt) 0.0 (/ (- (:keyframe/value b) (:keyframe/value a)) dt))]
                   (assoc k :keyframe/tangent-in slope :keyframe/tangent-out slope)))
               (range (count keyframes)) keyframes)))

(defn add-keyframe [timeline target frame]
  (update timeline :timeline/tracks
          (fn [tracks]
            (if-let [i (first (keep-indexed #(when (= target (:track/target %2)) %1) tracks))]
              (update tracks i #(track target (conj (:track/keyframes %) frame)))
              (conj tracks (track target [frame]))))))

(defn update-keyframe [timeline target frame-id f & args]
  (update timeline :timeline/tracks
          (fn [tracks]
            (mapv (fn [t]
                    (if (= target (:track/target t))
                      (track target (mapv #(if (= frame-id (:keyframe/id %))
                                             (apply f % args) %) (:track/keyframes t)))
                      t)) tracks))))

(defn move-keyframe [timeline target frame-id time]
  (update-keyframe timeline target frame-id assoc :keyframe/time time))

(defn delete-keyframe [timeline target frame-id]
  (update timeline :timeline/tracks
          (fn [tracks]
            (->> tracks
                 (mapv (fn [t]
                         (if (= target (:track/target t))
                           (track target (remove #(= frame-id (:keyframe/id %))
                                                 (:track/keyframes t))) t)))
                 (remove #(empty? (:track/keyframes %))) vec))))

;; Skeletal animation domain. Matrices are portable column-major vectors so
;; the same evaluated pose can be uploaded by WebGPU, WebGL2, or WASM hosts.
(defn bone
  ([id name] (bone id name nil {}))
  ([id name parent] (bone id name parent {}))
  ([id name parent {:keys [translation rotation scale]
                    :or {translation [0 0 0] rotation [0 0 0] scale [1 1 1]}}]
   {:bone/id id :bone/name name :bone/parent parent
    :bone/rest {:translation (vec translation) :rotation (vec rotation) :scale (vec scale)}}))

(defn skeleton [bones]
  (let [bones (vec bones) ids (mapv :bone/id bones) id-set (set ids)]
    (when-not (= (count ids) (count id-set))
      (throw (ex-info "duplicate bone id" {:ids ids})))
    (doseq [{:bone/keys [id parent]} bones]
      (when (and parent (not (id-set parent)))
        (throw (ex-info "bone parent not found" {:bone id :parent parent})))
      (loop [current parent seen #{id}]
        (when current
          (when (seen current) (throw (ex-info "bone hierarchy cycle" {:bone id :at current})))
          (recur (:bone/parent (first (filter #(= current (:bone/id %)) bones))) (conj seen current)))))
    {:skeleton/bones bones}))

(defn pose
  "Create a sparse map of bone-id to local TRS overrides. Missing channels
  retain the bone's rest-pose value."
  [entries]
  {:pose/bones (into {} (map (fn [[id trs]] [id (select-keys trs [:translation :rotation :scale])]) entries))})

(defn- mat4-mul [a b]
  (vec (for [c (range 4) r (range 4)]
         (reduce + (for [k (range 4)] (* (nth a (+ (* k 4) r)) (nth b (+ (* c 4) k))))))))
(defn- sin* [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- cos* [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))
(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))
(defn- trs-matrix [{:keys [translation rotation scale]}]
  (let [[x y z] translation [rx ry rz] rotation [sx sy sz] scale
        cx (cos* rx) sxr (sin* rx) cy (cos* ry) syr (sin* ry) cz (cos* rz) szr (sin* rz)
        t [1 0 0 0 0 1 0 0 0 0 1 0 x y z 1]
        mx [1 0 0 0 0 cx sxr 0 0 (- sxr) cx 0 0 0 0 1]
        my [cy 0 (- syr) 0 0 1 0 0 syr 0 cy 0 0 0 0 1]
        mz [cz szr 0 0 (- szr) cz 0 0 0 0 1 0 0 0 0 1]
        s [sx 0 0 0 0 sy 0 0 0 0 sz 0 0 0 0 1]]
    (mat4-mul t (mat4-mul mz (mat4-mul my (mat4-mul mx s))))))

(defn bone-world-matrices
  "Evaluate rest pose plus sparse local pose overrides into world matrices."
  [skeleton pose]
  (let [bones (:skeleton/bones skeleton) by-id (into {} (map (juxt :bone/id identity) bones))
        overrides (:pose/bones pose)]
    (doseq [id (keys overrides)]
      (when-not (by-id id) (throw (ex-info "pose targets unknown bone" {:bone id}))))
    (let [cache (atom {})
          world (fn world [id]
                  (or (get @cache id)
                      (let [bone (by-id id) local (trs-matrix (merge (:bone/rest bone) (get overrides id)))
                            result (if-let [parent (:bone/parent bone)] (mat4-mul (world parent) local) local)]
                        (swap! cache assoc id result) result)))]
      (into {} (map (fn [{:bone/keys [id]}] [id (world id)]) bones)))))

(defn bone-track-target
  "Canonical scalar timeline target for one bone TRS component."
  [bone-id channel axis]
  (when-not (#{:translation :rotation :scale} channel)
    (throw (ex-info "invalid bone animation channel" {:channel channel})))
  (when-not (#{:x :y :z} axis)
    (throw (ex-info "invalid bone animation axis" {:axis axis})))
  [:bone bone-id channel axis])

(defn evaluate-skeleton-pose
  "Evaluate canonical bone tracks into a sparse pose. Non-bone tracks are
  ignored, allowing object and skeletal channels on the same timeline."
  [skeleton timeline time]
  (let [bone-ids (set (map :bone/id (:skeleton/bones skeleton)))
        axis-index {:x 0 :y 1 :z 2}
        defaults {:translation [0 0 0] :rotation [0 0 0] :scale [1 1 1]}]
    (reduce (fn [result {:track/keys [target] :as t}]
              (if (and (vector? target) (= 4 (count target)) (= :bone (first target)))
                (let [[_ bone-id channel axis] target]
                  (when-not (bone-ids bone-id)
                    (throw (ex-info "bone track targets unknown bone" {:target target})))
                  (bone-track-target bone-id channel axis)
                  (update-in result [:pose/bones bone-id channel]
                             (fn [values]
                               (assoc (vec (or values (get defaults channel)))
                                      (axis-index axis) (sample t time)))))
                result))
            {:pose/bones {}} (:timeline/tracks timeline))))

(defn evaluate-skeleton
  "Evaluate animated pose and return GPU-ready bone world matrices."
  [skeleton timeline time]
  (bone-world-matrices skeleton (evaluate-skeleton-pose skeleton timeline time)))

(defn- matrix-inverse
  "Portable Gauss-Jordan inverse for a column-major 4x4 matrix."
  [m]
  (let [rows (mapv (fn [r]
                     (vec (concat (map #(nth m (+ (* % 4) r)) (range 4))
                                  (map #(if (= r %) 1.0 0.0) (range 4))))) (range 4))]
    (loop [a rows col 0]
      (if (= col 4)
        (vec (for [c (range 4) r (range 4)] (get-in a [r (+ 4 c)])))
        (let [pivot-row (apply max-key #(abs* (get-in a [% col])) (range col 4))
              pivot (get-in a [pivot-row col])]
          (when (< (abs* pivot) 1.0e-10)
            (throw (ex-info "non-invertible bind matrix" {:matrix m})))
          (let [a (assoc a col (nth a pivot-row) pivot-row (nth a col))
                normalized (mapv #(/ % pivot) (nth a col))
                a (assoc a col normalized)
                a (reduce (fn [rows r]
                            (if (= r col) rows
                              (let [factor (get-in rows [r col])]
                                (assoc rows r (mapv - (nth rows r) (mapv #(* factor %) normalized))))))
                          a (range 4))]
            (recur a (inc col))))))))

(defn bone-skinning-matrices
  "Return matrices in skeleton order as animatedWorld × inverseBindWorld.
  Rest pose therefore evaluates to identity, while animated pose produces
  deformation matrices suitable for kami.webgpu.mesh joint palettes."
  [skeleton pose]
  (let [rest-world (bone-world-matrices skeleton (pose {}))
        animated-world (bone-world-matrices skeleton pose)]
    (mapv (fn [{:bone/keys [id]}]
            (mat4-mul (get animated-world id) (matrix-inverse (get rest-world id))))
          (:skeleton/bones skeleton))))

(defn evaluate-skinning
  "Evaluate bone tracks and return ordered GPU skinning matrices."
  [skeleton timeline time]
  (bone-skinning-matrices skeleton (evaluate-skeleton-pose skeleton timeline time)))

(defn pose-constraint
  "Create an ordered skeletal pose constraint. Supported kinds:
  :copy-translation {:target bone-id :influence 0..1}
  :limit-rotation {:min [xyz] :max [xyz]}."
  [id kind bone-id options]
  (when-not (#{:copy-translation :limit-rotation} kind)
    (throw (ex-info "unsupported pose constraint" {:kind kind})))
  (when-let [influence (:influence options)]
    (when-not (<= 0 influence 1) (throw (ex-info "constraint influence must be within [0,1]" {:influence influence}))))
  (when (= kind :limit-rotation)
    (when-not (and (= 3 (count (:min options))) (= 3 (count (:max options)))
                   (every? true? (map <= (:min options) (:max options))))
      (throw (ex-info "invalid rotation limit" {:options options}))))
  {:constraint/id id :constraint/kind kind :constraint/bone bone-id :constraint/options options
   :constraint/enabled? true})

(defn apply-pose-constraints
  "Apply constraints in vector order to local pose channels. Missing pose
  channels start from rest values; disabled constraints are preserved/no-op."
  [skeleton pose constraints]
  (let [bones (into {} (map (juxt :bone/id identity) (:skeleton/bones skeleton)))
        local (fn [result id] (merge (:bone/rest (bones id)) (get-in result [:pose/bones id])))]
    (reduce
     (fn [result {:constraint/keys [kind bone options enabled?] :as constraint}]
       (if (false? enabled?) result
         (do
           (when-not (bones bone) (throw (ex-info "constraint bone not found" {:constraint constraint :bone bone})))
           (case kind
             :copy-translation
             (let [target (:target options) _ (when-not (bones target) (throw (ex-info "constraint target not found" {:target target})))
                   influence (:influence options 1.0) from (:translation (local result bone)) to (:translation (local result target))]
               (assoc-in result [:pose/bones bone :translation] (mapv #(+ %1 (* influence (- %2 %1))) from to)))
             :limit-rotation
             (let [rotation (:rotation (local result bone)) minimum (:min options) maximum (:max options)]
               (assoc-in result [:pose/bones bone :rotation] (mapv #(max %2 (min %3 %1)) rotation minimum maximum)))
             result))))
     pose constraints)))

(defn evaluate-constrained-skinning
  "Evaluate timeline tracks, ordered pose constraints, then inverse-bind skinning."
  [skeleton timeline time constraints]
  (bone-skinning-matrices skeleton
                          (apply-pose-constraints skeleton (evaluate-skeleton-pose skeleton timeline time) constraints)))

(defn solve-two-bone-ik
  "Solve a planar XY two-bone chain whose rest bones point along +X.
  Returns root/mid Z rotations plus reached joint/tip positions. Targets
  outside the chain range are clamped while preserving target direction."
  [{:keys [root length-a length-b target elbow]
    :or {root [0 0] elbow :positive}}]
  (when-not (and (pos? length-a) (pos? length-b) (= 2 (count root)) (= 2 (count target))
                 (#{:positive :negative} elbow))
    (throw (ex-info "invalid two-bone IK input" {:length-a length-a :length-b length-b :root root :target target :elbow elbow})))
  (let [[rx ry] root [tx ty] target dx (- tx rx) dy (- ty ry)
        requested (#?(:clj Math/sqrt :cljs js/Math.sqrt) (+ (* dx dx) (* dy dy)))
        minimum (+ (#?(:clj Math/abs :cljs js/Math.abs) (- length-a length-b)) 1.0e-9)
        maximum (- (+ length-a length-b) 1.0e-9) distance (max minimum (min maximum requested))
        direction (if (< requested 1.0e-9) 0.0 (#?(:clj Math/atan2 :cljs js/Math.atan2) dy dx))
        clamp #(max -1.0 (min 1.0 %))
        shoulder-offset (#?(:clj Math/acos :cljs js/Math.acos)
                         (clamp (/ (+ (* length-a length-a) (* distance distance) (- (* length-b length-b)))
                                   (* 2 length-a distance))))
        internal (#?(:clj Math/acos :cljs js/Math.acos)
                  (clamp (/ (+ (* length-a length-a) (* length-b length-b) (- (* distance distance)))
                            (* 2 length-a length-b))))
        sign (if (= elbow :positive) 1.0 -1.0) pi-value #?(:clj Math/PI :cljs js/Math.PI)
        root-angle (+ direction (* sign shoulder-offset)) mid-angle (* (- sign) (- pi-value internal))
        joint [(+ rx (* length-a (#?(:clj Math/cos :cljs js/Math.cos) root-angle)))
               (+ ry (* length-a (#?(:clj Math/sin :cljs js/Math.sin) root-angle)))]
        world-mid (+ root-angle mid-angle)
        tip [(+ (first joint) (* length-b (#?(:clj Math/cos :cljs js/Math.cos) world-mid)))
             (+ (second joint) (* length-b (#?(:clj Math/sin :cljs js/Math.sin) world-mid)))]]
    {:ik/root-rotation root-angle :ik/mid-rotation mid-angle :ik/joint joint :ik/tip tip
     :ik/requested-distance requested :ik/solved-distance distance
     :ik/clamped? (not= requested distance) :ik/elbow elbow}))

(defn two-bone-ik-pose
  "Convert a planar IK solution to sparse Z-rotation pose channels."
  [root-bone mid-bone solution]
  (pose {root-bone {:rotation [0 0 (:ik/root-rotation solution)]}
         mid-bone {:rotation [0 0 (:ik/mid-rotation solution)]}}))
