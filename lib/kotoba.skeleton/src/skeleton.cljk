(ns skeleton
  "KAMI Skeleton — glTF-compatible skeletal animation: bone hierarchy,
  keyframe interpolation (linear/step/cubic-spline), pose blending/
  cross-fade, CCD inverse kinematics, anatomical joint constraints, and
  bone-name retargeting. Restored from the legacy kami-engine/
  kami-skeleton Rust crate (deleted in kotoba-lang/kami-engine PR #82
  'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root). Ledger class
  `:port-to-CLJC-domain-interpreter` (90-docs/migration/
  clj-wgsl-ledger.edn) — GPU skinning (consuming the joint-matrix
  buffer this namespace produces) stays native/WGSL; this namespace
  owns the animation math and pose evaluation itself.

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU."
  (:require [skeleton.math :as m]))

;; ── Bone / Skeleton ──────────────────────────────
;; Bone: {:name :parent (index or nil) :local-position (Vec3)
;;        :local-rotation (Quat) :local-scale (Vec3) :inverse-bind (Mat4)}
;; Skeleton: {:bones [Bone ...]}

(defn bone [{:keys [name parent local-position local-rotation local-scale inverse-bind]}]
  {:name name :parent parent :local-position local-position :local-rotation local-rotation
   :local-scale local-scale :inverse-bind (or inverse-bind m/mat4-identity)})

(defn skeleton [bones] {:bones (vec bones)})

;; ── Keyframes / tracks / clips ───────────────────

(def interpolations #{:linear :step :cubic-spline})

(defn interpolation-by-name [name]
  (case name
    "step" :step
    ("cubic" "cubicspline" "cubic-spline") :cubic-spline
    :linear))

(defn keyframe [{:keys [time position rotation scale]}]
  {:time time :position position :rotation rotation :scale scale})

(defn bone-track
  ([bone-index keyframes] (bone-track bone-index keyframes :linear))
  ([bone-index keyframes interpolation]
   {:bone-index bone-index :keyframes (vec keyframes) :interpolation interpolation}))

(defn with-interpolation [track interp] (assoc track :interpolation interp))

(defn animation-clip [{:keys [name duration tracks looping]}]
  {:name name :duration duration :tracks (vec tracks) :looping looping})

(defn retarget
  "Retarget `clip` from `source` skeleton to `target` skeleton by bone
  name: each track's source bone index resolves to its name in
  `source`, then matches the same-named bone in `target`. Tracks with
  no name match in `target` are dropped."
  [clip source target]
  (let [target-index (fn [name] (some (fn [[i b]] (when (= (:name b) name) i))
                                       (map-indexed vector (:bones target))))
        tracks (keep
                (fn [t]
                  (when-let [name (:name (get (:bones source) (:bone-index t)))]
                    (when-let [ti (target-index name)]
                      (bone-track ti (:keyframes t) (:interpolation t)))))
                (:tracks clip))]
    (animation-clip {:name (:name clip) :duration (:duration clip) :tracks tracks :looping (:looping clip)})))

;; ── Keyframe interpolation ───────────────────────

(defn- kf-pos [k] (or (:position k) m/vec3-zero))
(defn- kf-rot [k] (or (:rotation k) m/quat-identity))
(defn- kf-scl [k] (or (:scale k) m/vec3-one))

(defn- catmull-rom [p0 p1 p2 p3 t]
  (let [t2 (* t t) t3 (* t2 t)]
    (m/vec3-scale
     (m/vec3+ (m/vec3+ (m/vec3-scale p1 2.0)
                        (m/vec3-scale (m/vec3- p2 p0) t))
              (m/vec3+ (m/vec3-scale (m/vec3+ (m/vec3-scale p0 2.0)
                                               (m/vec3+ (m/vec3-scale p1 -5.0)
                                                        (m/vec3+ (m/vec3-scale p2 4.0) (m/vec3-scale p3 -1.0))))
                                     t2)
                       (m/vec3-scale (m/vec3+ (m/vec3-scale p0 -1.0)
                                               (m/vec3+ (m/vec3-scale p1 3.0)
                                                        (m/vec3+ (m/vec3-scale p2 -3.0) p3)))
                                     t3)))
     0.5)))

(defn- interpolate-track
  "Returns `[position rotation scale]` for `track` at `time`."
  [track time]
  (let [kfs (:keyframes track)]
    (cond
      (empty? kfs) [m/vec3-zero m/quat-identity m/vec3-one]

      (or (= 1 (count kfs)) (<= time (:time (first kfs))))
      (let [k (first kfs)] [(kf-pos k) (kf-rot k) (kf-scl k)])

      (>= time (:time (peek kfs)))
      (let [k (peek kfs)] [(kf-pos k) (kf-rot k) (kf-scl k)])

      :else
      (let [n (count kfs)
            i (loop [i 0] (if (and (< i (dec n)) (< (:time (nth kfs (inc i))) time)) (recur (inc i)) i))
            a (nth kfs i) b (nth kfs (inc i))
            t (/ (- time (:time a)) (- (:time b) (:time a)))]
        (case (:interpolation track)
          :step [(kf-pos a) (kf-rot a) (kf-scl a)]

          :linear
          [(m/vec3-lerp (kf-pos a) (kf-pos b) t)
           (m/quat-slerp (kf-rot a) (kf-rot b) t)
           (m/vec3-lerp (kf-scl a) (kf-scl b) t)]

          :cubic-spline
          (let [p0p (kf-pos (nth kfs (max 0 (dec i)))) p3p (kf-pos (nth kfs (min (dec n) (+ i 2))))
                pos (catmull-rom p0p (kf-pos a) (kf-pos b) p3p t)
                p0s (kf-scl (nth kfs (max 0 (dec i)))) p3s (kf-scl (nth kfs (min (dec n) (+ i 2))))
                scl (catmull-rom p0s (kf-scl a) (kf-scl b) p3s t)
                te (* t t (- 3.0 (* 2.0 t)))
                rot (m/quat-slerp (kf-rot a) (kf-rot b) te)]
            [pos rot scl]))))))

;; ── Pose evaluation ──────────────────────────────

(defn- track-for-bone [clip i] (some (fn [t] (when (= (:bone-index t) i) t)) (:tracks clip)))

(defn- local-trs
  "Per-bone local `[position rotation scale]` for `clip` at `time` (rest
  pose where no track for that bone)."
  [sk clip time]
  (mapv
   (fn [i b]
     (if-let [track (track-for-bone clip i)]
       (interpolate-track track time)
       [(:local-position b) (:local-rotation b) (:local-scale b)]))
   (range) (:bones sk)))

(defn- locals->world [sk locals]
  (let [n (count (:bones sk))]
    (loop [i 0 world (vec (repeat n nil))]
      (if (= i n)
        world
        (let [[pos rot scl] (nth locals i)
              l (m/mat4-from-scale-rotation-translation scl rot pos)
              parent (:parent (nth (:bones sk) i))
              w (if parent (m/mat4-mul (nth world parent) l) l)]
          (recur (inc i) (assoc world i w)))))))

(defn evaluate
  "World transform matrices for all bones of `sk` at `clip`/`time`."
  [sk clip time]
  (locals->world sk (local-trs sk clip time)))

(defn- rest-world [sk]
  (locals->world sk (mapv (fn [b] [(:local-position b) (:local-rotation b) (:local-scale b)]) (:bones sk))))

(defn evaluate-blend
  "Blend several clips into one pose and return world matrices. `layers`
  is a seq of `[clip time weight]`; weights are normalised.
  Translation/scale blend by weighted average, rotation by weighted
  nlerp (hemisphere-aligned). Empty/zero-weight input -> the skeleton's
  rest pose."
  [sk layers]
  (let [n (count (:bones sk))
        total (reduce + (map (fn [[_ _ w]] (max 0.0 w)) layers))]
    (if (or (zero? n) (<= total 0.0))
      (rest-world sk)
      (let [per-layer (for [[clip time w] layers :when (> w 0.0)]
                         [(local-trs sk clip time) (/ w total)])
            locals
            (mapv
             (fn [i]
               (let [[pos acc scl _reference]
                     (reduce
                      (fn [[pos acc scl reference] [trs w]]
                        (let [[p r s] (nth trs i)
                              r (if (and reference (< (m/quat-dot reference r) 0.0)) (m/quat-neg r) r)
                              reference (or reference r)]
                          [(m/vec3+ pos (m/vec3-scale p w))
                           (m/quat-add acc (m/quat-scale r w))
                           (m/vec3+ scl (m/vec3-scale s w))
                           reference]))
                      [m/vec3-zero [0.0 0.0 0.0 0.0] m/vec3-zero nil]
                      per-layer)
                     rot (if (> (m/quat-length-squared acc) 1e-12) (m/quat-normalize acc) m/quat-identity)]
                 [pos rot scl]))
             (range n))]
        (locals->world sk locals)))))

(defn evaluate-crossfade
  "Cross-fade from `from` to `to` by `alpha` in [0,1] (0 = all `from`)."
  [sk from from-time to to-time alpha]
  (let [a (max 0.0 (min 1.0 alpha))]
    (evaluate-blend sk [[from from-time (- 1.0 a)] [to to-time a]])))

;; ── CCD inverse kinematics ───────────────────────

(defn solve-ik-ccd
  "Solve `chain` (bone indices root -> effector) with CCD IK so the tip
  reaches `target` (world space). Returns `[[bone-index rotation] ...]`
  for every bone in the chain except the effector."
  [sk chain target iterations threshold]
  (let [n (count (:bones sk))]
    (if (or (< (count chain) 2) (some #(>= % n) chain))
      []
      (let [bones (:bones sk)
            pos (mapv :local-position bones)
            scl (mapv :local-scale bones)
            world-of (fn [local-rot]
                       (loop [i 0 world (vec (repeat n nil))]
                         (if (= i n)
                           world
                           (let [l (m/mat4-from-scale-rotation-translation (nth scl i) (nth local-rot i) (nth pos i))
                                 parent (:parent (nth bones i))
                                 w (if parent (m/mat4-mul (nth world parent) l) l)]
                             (recur (inc i) (assoc world i w))))))
            effector (peek chain)
            joints (vec (butlast chain))]
        (loop [iter 0 local-rot (mapv :local-rotation bones)]
          (if (or (>= iter (max 1 iterations))
                  (< (m/vec3-distance (m/mat4-translation (nth (world-of local-rot) effector)) target) threshold))
            (mapv (fn [b] [b (nth local-rot b)]) joints)
            (recur (inc iter)
                   (reduce
                    (fn [local-rot bone-i]
                      (let [world (world-of local-rot)
                            bpos (m/mat4-translation (nth world bone-i))
                            to-eff (m/vec3- (m/mat4-translation (nth world effector)) bpos)
                            to-tgt (m/vec3- target bpos)]
                        (if (or (< (m/vec3-length to-eff) 1e-6) (< (m/vec3-length to-tgt) 1e-6))
                          local-rot
                          (let [delta (m/quat-from-rotation-arc (m/vec3-normalize to-eff) (m/vec3-normalize to-tgt))
                                new-world-rot (m/quat-normalize (m/quat-mul delta (m/mat4-rotation (nth world bone-i))))
                                parent (:parent (nth bones bone-i))
                                parent-rot (if parent (m/mat4-rotation (nth world parent)) m/quat-identity)]
                            (assoc local-rot bone-i
                                   (m/quat-normalize (m/quat-mul (m/quat-inverse parent-rot) new-world-rot)))))))
                    local-rot
                    (reverse joints)))))))))

;; ── Anatomical joint constraints ─────────────────

(defn joint-constraint [min-xyz max-xyz] {:min min-xyz :max max-xyz})

(defn- quat-to-euler-xyz [[x y z w]]
  (let [sinr-cosp (* 2.0 (+ (* w x) (* y z)))
        cosr-cosp (- 1.0 (* 2.0 (+ (* x x) (* y y))))
        roll (Math/atan2 sinr-cosp cosr-cosp)
        sinp (* 2.0 (- (* w y) (* z x)))
        pitch (if (>= (Math/abs sinp) 1.0) (* (/ Math/PI 2.0) (if (neg? sinp) -1.0 1.0)) (Math/asin sinp))
        siny-cosp (* 2.0 (+ (* w z) (* x y)))
        cosy-cosp (- 1.0 (* 2.0 (+ (* y y) (* z z))))
        yaw (Math/atan2 siny-cosp cosy-cosp)]
    [roll pitch yaw]))

(defn- euler-xyz->quat [x y z]
  (m/quat-mul (m/quat-mul (m/quat-from-rotation-z z) (m/quat-from-rotation-y y)) (m/quat-from-rotation-x x)))

(defn constraint-clamp
  "Clamp a quaternion `rotation` to `constraint`'s Euler XYZ limits."
  [constraint rotation]
  (let [[x y z] (quat-to-euler-xyz rotation)
        [minx miny minz] (:min constraint)
        [maxx maxy maxz] (:max constraint)
        cx (max minx (min maxx x))
        cy (max miny (min maxy y))
        cz (max minz (min maxz z))]
    (euler-xyz->quat cx cy cz)))

(defn default-humanoid-constraints
  "`[bone-name joint-constraint]` pairs covering standard VRM humanoid
  skeleton bones. Values derived from orthopedic range-of-motion
  references."
  []
  (let [d (/ Math/PI 180.0)]
    [["head" (joint-constraint [(* -60.0 d) (* -80.0 d) (* -40.0 d)] [(* 60.0 d) (* 80.0 d) (* 40.0 d)])]
     ["neck" (joint-constraint [(* -30.0 d) (* -45.0 d) (* -30.0 d)] [(* 30.0 d) (* 45.0 d) (* 30.0 d)])]
     ["spine" (joint-constraint [(* -30.0 d) (* -30.0 d) (* -20.0 d)] [(* 30.0 d) (* 30.0 d) (* 20.0 d)])]
     ["chest" (joint-constraint [(* -15.0 d) (* -15.0 d) (* -10.0 d)] [(* 15.0 d) (* 15.0 d) (* 10.0 d)])]
     ["hips" (joint-constraint [(* -30.0 d) (* -30.0 d) (* -15.0 d)] [(* 30.0 d) (* 30.0 d) (* 15.0 d)])]
     ["leftUpperArm" (joint-constraint [(* -60.0 d) (* -45.0 d) (* -30.0 d)] [(* 90.0 d) (* 90.0 d) (* 180.0 d)])]
     ["rightUpperArm" (joint-constraint [(* -60.0 d) (* -90.0 d) (* -180.0 d)] [(* 90.0 d) (* 45.0 d) (* 30.0 d)])]
     ["leftLowerArm" (joint-constraint [(* -5.0 d) 0.0 (* -5.0 d)] [(* 5.0 d) (* 145.0 d) (* 5.0 d)])]
     ["rightLowerArm" (joint-constraint [(* -5.0 d) (* -145.0 d) (* -5.0 d)] [(* 5.0 d) 0.0 (* 5.0 d)])]
     ["leftUpperLeg" (joint-constraint [(* -30.0 d) (* -45.0 d) (* -20.0 d)] [(* 120.0 d) (* 30.0 d) (* 45.0 d)])]
     ["rightUpperLeg" (joint-constraint [(* -30.0 d) (* -30.0 d) (* -45.0 d)] [(* 120.0 d) (* 45.0 d) (* 20.0 d)])]
     ["leftLowerLeg" (joint-constraint [(* -140.0 d) (* -5.0 d) (* -5.0 d)] [0.0 (* 5.0 d) (* 5.0 d)])]
     ["rightLowerLeg" (joint-constraint [(* -140.0 d) (* -5.0 d) (* -5.0 d)] [0.0 (* 5.0 d) (* 5.0 d)])]]))

(defn build-humanoid-constraints
  "`[bone-index joint-constraint]` pairs for bones of `sk` found by name
  in `default-humanoid-constraints`."
  [sk]
  (vec
   (keep
    (fn [[name constraint]]
      (when-let [idx (some (fn [[i b]] (when (= (:name b) name) i)) (map-indexed vector (:bones sk)))]
        [idx constraint]))
    (default-humanoid-constraints))))

(defn evaluate-constrained
  "Like `evaluate`, but applies `constraints` (`[[bone-index constraint]
  ...]`) to each animated bone's rotation before computing world
  transforms."
  [sk clip time constraints]
  (let [locals (mapv
                (fn [i [pos rot scl]]
                  (if-let [[_ c] (some (fn [[bi c]] (when (= bi i) [bi c])) constraints)]
                    [pos (constraint-clamp c rot) scl]
                    [pos rot scl]))
                (range) (local-trs sk clip time))]
    (locals->world sk locals)))

;; ── GPU joint matrices ───────────────────────────

(defn- joint-matrices-from-world [sk world]
  (mapv (fn [b w] (m/mat4-mul w (:inverse-bind b))) (:bones sk) world))

(defn joint-matrices
  "World * inverse-bind matrices for GPU skinning upload."
  [sk clip time]
  (joint-matrices-from-world sk (evaluate sk clip time)))

(defn joint-matrices-constrained
  [sk clip time constraints]
  (joint-matrices-from-world sk (evaluate-constrained sk clip time constraints)))
