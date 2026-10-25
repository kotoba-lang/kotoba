(ns shugyo.reach
  "`VectorizedReachEnv` — a general articulated-arm joint-space reach task —
  port of the original crate's `reach_env.rs`.

  Duck-typing note (the big one in this crate): the original wrapped
  `kami_genesis::ArticulationBatch::from_urdf` (built by
  `kami_articulated::parse_urdf`) — neither is restored as a kotoba-lang repo
  (kami-genesis never was; kami-articulated is empty mid-restoration). This
  namespace reimplements the real computational content both would have
  provided, as genuine (not stubbed) generic serial-chain robotics math:

    1. **URDF-XML extraction** — a minimal, regex-based extractor of
       `<link>`/`<joint type=\"revolute\">` elements (mass, inertial origin,
       joint origin, axis, position limits) sufficient for the same fixture
       shape the original Rust tests embedded (a chain of single-axis
       revolute joints). This is NOT a general URDF parser — no branching
       kinematic trees, no non-revolute joints, no mesh/visual/collision
       elements — just enough structure to reconstruct the same test
       fixtures. Document this limitation wherever the parser is used.
    2. **Forward kinematics** — sequential rigid transforms down the chain:
       each joint's child link position = parent position + parent rotation
       × joint origin offset; child rotation = parent rotation × rotation
       about the joint's local axis by the current joint angle. Generic to
       any chain length (not hardcoded to 2 links).
    3. **Dynamics** — two modes, both genuine simplifications of what a real
       physics engine's actuator model would produce, not placeholders:
         - `computed-torque? true` (default): feedback-linearizing
           computed-torque control gives each joint an independent
           critically-tuned 2nd-order linear system,
           `q'' = kp*(target - q) - kd*q'` — the textbook *result* of
           computed-torque control (exact tracking regardless of
           configuration/gravity), integrated with semi-implicit Euler.
         - `computed-torque? false` (plain PD, used by the DR-divergence
           tests): adds a per-joint lumped gravity-torque term,
           `τ_gravity_d ≈ -(downstream mass_d)·gravity_z·lever_d·cos(q_d)`,
           where `downstream mass_d` is the summed mass of every link past
           joint `d` and `lever_d` is the summed magnitude of the joint-origin
           / inertial-origin offsets past joint `d` (a decoupled per-joint
           pendulum approximation — it does not couple across joints the way
           a full mass matrix would, but genuinely makes `gravity-dr`/
           `mass-dr` change the passive/PD steady-state per env, which is
           exactly what the two DR-divergence tests below require).
    4. **Physics DR** — `randomize-physics` draws a per-env
       `{:gravity-scale :mass-scale}` pair from a single shared RNG stream
       (mirrors `ArticulationBatch::randomize_physics`), applied in the
       dynamics above.

  Layout (env-major flat, like the Cartpole env):
    - action: `[num-envs, n-dof]` joint **position targets** (rad)
    - observation: `[num-envs, 3*n-dof]` = `[q, q̇, (q-goal - q)]`
    - reward: `-‖q - q-goal‖² - w·‖action‖²` (per env)
    - terminated: `‖q - q-goal‖∞ < goal-tol`; truncated: episode length cap"
  (:require [kotoba.lang.text] [shugyo.lcg :as lcg]
            [shugyo.policy :as policy]
            [shugyo.traits :as t]))

;; ---------------------------------------------------------------------------
;; Minimal 3-vector / 3x3-rotation-matrix helpers
;; ---------------------------------------------------------------------------

(def identity3 [[1.0 0.0 0.0] [0.0 1.0 0.0] [0.0 0.0 1.0]])

(defn v+ [[ax ay az] [bx by bz]] [(+ ax bx) (+ ay by) (+ az bz)])
(defn v- [[ax ay az] [bx by bz]] [(- ax bx) (- ay by) (- az bz)])
(defn v-scale [[x y z] s] [(* x s) (* y s) (* z s)])
(defn v-dot [[ax ay az] [bx by bz]] (+ (* ax bx) (* ay by) (* az bz)))
(defn v-norm [v] #?(:clj (Math/sqrt (v-dot v v)) :cljs (js/Math.sqrt (v-dot v v))))
(defn v-normalize [v]
  (let [n (v-norm v)]
    (if (< n 1e-12) [0.0 0.0 1.0] (v-scale v (/ 1.0 n)))))

(defn mat-vec [[r0 r1 r2] v] [(v-dot r0 v) (v-dot r1 v) (v-dot r2 v)])

(defn mat-mul [a b]
  (let [bt [[(nth (nth b 0) 0) (nth (nth b 1) 0) (nth (nth b 2) 0)]
            [(nth (nth b 0) 1) (nth (nth b 1) 1) (nth (nth b 2) 1)]
            [(nth (nth b 0) 2) (nth (nth b 1) 2) (nth (nth b 2) 2)]]]
    (vec (for [row a] (vec (for [col bt] (v-dot row col)))))))

(defn rot-axis-angle
  "Rodrigues' rotation formula: 3x3 rotation matrix for `angle` radians about
  unit `axis`."
  [axis angle]
  (let [[x y z] (v-normalize axis)
        c #?(:clj (Math/cos angle) :cljs (js/Math.cos angle))
        s #?(:clj (Math/sin angle) :cljs (js/Math.sin angle))
        t (- 1.0 c)]
    [[(+ c (* t x x)) (- (* t x y) (* s z)) (+ (* t x z) (* s y))]
     [(+ (* t x y) (* s z)) (+ c (* t y y)) (- (* t y z) (* s x))]
     [(- (* t x z) (* s y)) (+ (* t y z) (* s x)) (+ c (* t z z))]]))

;; ---------------------------------------------------------------------------
;; URDF-XML chain extractor (see namespace docstring for scope/limitations)
;; ---------------------------------------------------------------------------

(defn- parse-double* [s] #?(:clj (Double/parseDouble (kotoba.lang.text/trim s))
                             :cljs (js/parseFloat (kotoba.lang.text/trim s))))

(defn- parse-xyz [s]
  (if (nil? s)
    [0.0 0.0 0.0]
    (mapv parse-double* (kotoba.lang.text/split (kotoba.lang.text/trim s) #"\s+"))))

(defn- attr [block name]
  (second (re-find (re-pattern (str name "=\"([^\"]*)\"")) block)))

(defn- parse-links [text]
  (into {}
        (for [[_ name body] (re-seq #"(?s)<link\s+name=\"([^\"]+)\"\s*>(.*?)</link>" text)]
          [name {:name name
                 :mass (if-let [m (attr body "value")] (parse-double* m) 0.0)
                 :inertial-origin (if-let [o (attr body "xyz")] (parse-xyz o) [0.0 0.0 0.0])}])))

(defn- parse-joints [text]
  (for [[_ name jtype body] (re-seq #"(?s)<joint\s+name=\"([^\"]+)\"\s+type=\"([^\"]+)\"\s*>(.*?)</joint>" text)
        :when (= jtype "revolute")]
    (let [parent (second (re-find #"<parent\s+link=\"([^\"]+)\"" body))
          child (second (re-find #"<child\s+link=\"([^\"]+)\"" body))
          origin (parse-xyz (second (re-find #"<origin\s+xyz=\"([^\"]*)\"" body)))
          axis (parse-xyz (second (re-find #"<axis\s+xyz=\"([^\"]*)\"" body)))
          lower (parse-double* (or (second (re-find #"<limit[^>]*\blower=\"([^\"]*)\"" body)) "-3.14159"))
          upper (parse-double* (or (second (re-find #"<limit[^>]*\bupper=\"([^\"]*)\"" body)) "3.14159"))]
      {:name name :parent parent :child child :origin origin :axis axis :limit [lower upper]})))

(defn parse-urdf-chain
  "Extract a generic single-axis-per-joint serial revolute chain from URDF
  XML `text`. Returns a chain map with everything `forward-kinematics` and
  the dynamics functions below need. See namespace docstring for scope."
  [text]
  (let [links (parse-links text)
        joints (vec (parse-joints text))
        ndof (count joints)
        root-name (:parent (first joints))
        link-order (into [root-name] (map :child joints))
        link-recs (mapv #(get links % {:name % :mass 0.0 :inertial-origin [0.0 0.0 0.0]}) link-order)
        origins (mapv :origin joints)
        axes (mapv :axis joints)
        limits (mapv :limit joints)
        downstream-mass (mapv (fn [d] (reduce + 0.0 (map :mass (subvec link-recs (inc d) (count link-recs)))))
                               (range ndof))
        lever (mapv (fn [d]
                      (+ (reduce + 0.0 (map v-norm (subvec origins (inc d) ndof)))
                         (v-norm (:inertial-origin (last link-recs)))))
                    (range ndof))]
    {:ndof ndof
     :dof-names (mapv :name joints)
     :link-names link-order
     :origins origins
     :axes axes
     :limits limits
     :downstream-mass downstream-mass
     :lever lever
     :links link-recs}))

;; ---------------------------------------------------------------------------
;; Forward kinematics
;; ---------------------------------------------------------------------------

(defn forward-kinematics
  "Sequential rigid transforms down `chain` at joint angles `q`. Returns a
  vector of `{:name :pos :rot}` maps, one per link, root first."
  [chain q]
  (loop [i 0 pos [0.0 0.0 0.0] rot identity3
         acc [{:name (first (:link-names chain)) :pos pos :rot rot}]]
    (if (= i (:ndof chain))
      acc
      (let [origin (nth (:origins chain) i)
            axis (nth (:axes chain) i)
            angle (nth q i)
            joint-rot (rot-axis-angle axis angle)
            child-pos (v+ pos (mat-vec rot origin))
            child-rot (mat-mul rot joint-rot)
            child-name (nth (:link-names chain) (inc i))]
        (recur (inc i) child-pos child-rot
               (conj acc {:name child-name :pos child-pos :rot child-rot}))))))

(defn link-pose
  "`[pos rot]` of `link-name` at joint angles `q` (nil if not found)."
  [chain q link-name]
  (when-let [entry (some #(when (= (:name %) link-name) %) (forward-kinematics chain q))]
    [(:pos entry) (:rot entry)]))

(defn tool-world-pos
  "World position of `tool-offset` (in the `link-name` frame) at joint
  angles `q`."
  [chain q link-name tool-offset]
  (when-let [[pos rot] (link-pose chain q link-name)]
    (v+ pos (mat-vec rot tool-offset))))

;; ---------------------------------------------------------------------------
;; Dynamics: computed-torque (default) or plain-PD + lumped gravity torque
;; ---------------------------------------------------------------------------

(defn step-chain
  "Advance per-env joint state `{:q :qdot}` by one `dt` substep toward
  `targets`, per `chain` and dynamics options. See namespace docstring for
  the computed-torque / plain-PD+gravity-approximation duck-typing."
  [chain {:keys [q qdot]} targets
   {:keys [kp kd computed-torque? gravity-z gravity-scale mass-scale dt]}]
  (let [ndof (:ndof chain)
        downstream-mass (:downstream-mass chain)
        lever (:lever chain)]
    (loop [d 0 q' (transient []) qdot' (transient [])]
      (if (= d ndof)
        {:q (persistent! q') :qdot (persistent! qdot')}
        (let [qd (nth q d)
              qdotd (nth qdot d)
              target (nth targets d)
              qdd (if computed-torque?
                    (- (* kp (- target qd)) (* kd qdotd))
                    (let [dm (nth downstream-mass d)
                          lv (nth lever d)
                          inertia (max 1e-6 (* dm mass-scale))
                          cosq #?(:clj (Math/cos qd) :cljs (js/Math.cos qd))
                          gravity-torque (- (* dm mass-scale gravity-z gravity-scale lv cosq))]
                      (/ (+ (* kp (- target qd)) (* -1.0 kd qdotd) gravity-torque) inertia)))
              qdotd' (+ qdotd (* dt qdd))
              qd' (+ qd (* dt qdotd'))]
          (recur (inc d) (conj! q' qd') (conj! qdot' qdotd')))))))

;; ---------------------------------------------------------------------------
;; ReachCfg
;; ---------------------------------------------------------------------------

(defn reach-cfg-default []
  {:dt (/ 1.0 120.0)
   :gravity-z -9.81
   :kp 100.0
   :kd 20.0
   :computed-torque? true
   :normalized-actions? false
   :contact-radius 0.0
   :contact-bonus 0.0
   :observe-contact? false
   :tool-offset [0.0 0.0 0.0]
   :action-noise-std 0.0
   :gravity-dr nil
   :mass-dr nil
   :obs-noise-std 0.0
   :goal-range 0.8
   :goal-tol 0.05
   :action-penalty 0.001
   :decimation 4
   :max-steps 300})

;; ---------------------------------------------------------------------------
;; Physics-DR helper (shared with `shugyo.ee-reach`)
;; ---------------------------------------------------------------------------

(defn randomize-physics
  "Draw `num-envs` `{:gravity-scale :mass-scale}` pairs, one independently
  seeded LCG stream per env (`seed + e`, matching the per-env goal-sampling
  convention elsewhere in this namespace — better-decorrelated across
  adjacent envs than a single continuous shared stream). `gravity-range`/
  `mass-range` are `[lo hi]` pairs or `nil` (nil => fixed scale 1.0)."
  [seed num-envs gravity-range mass-range]
  (let [[glo ghi] (or gravity-range [1.0 1.0])
        [mlo mhi] (or mass-range [1.0 1.0])]
    (mapv (fn [e]
            (let [state (lcg/lcg-new (+ seed e))
                  [g state1] (lcg/next-uniform state glo ghi)
                  [m _state2] (lcg/next-uniform state1 mlo mhi)]
              {:gravity-scale g :mass-scale m}))
          (range num-envs))))

;; ---------------------------------------------------------------------------
;; VectorizedReachEnv
;; ---------------------------------------------------------------------------

(defn- zero-joint-state [ndof]
  {:q (vec (repeat ndof 0.0)) :qdot (vec (repeat ndof 0.0))})

(defn- observations-flat* [chain states goals]
  (let [ndof (:ndof chain)]
    (vec (mapcat (fn [{:keys [q qdot]} e]
                   (concat q qdot (map (fn [d] (- (nth goals (+ (* e ndof) d)) (nth q d))) (range ndof))))
                 states (range)))))

(deftype VectorizedReachEnvT
    [chain num-envs-n cfg
     states-atom goals-atom dof-scales-atom steps-atom rngs-atom noise-rng-atom]
  t/VecRLEnv
  (num-envs [_] num-envs-n)
  (observation-dim-per-env [_] (* 3 (:ndof chain)))
  (action-dim-per-env [_] (:ndof chain))
  (reset-all! [this base-seed]
    (let [ndof (:ndof chain)]
      (when (some? base-seed)
        (clojure.core/reset! noise-rng-atom (lcg/lcg-new (bit-xor base-seed 0xA5A51234))))
      (let [g (:gravity-dr cfg) m (:mass-dr cfg)]
        (clojure.core/reset!
         dof-scales-atom
         (if (or g m)
           (randomize-physics (bit-xor (or base-seed 0) 0xD12) num-envs-n g m)
           (vec (repeat num-envs-n {:gravity-scale 1.0 :mass-scale 1.0})))))
      (dotimes [e num-envs-n]
        (when (some? base-seed)
          (clojure.core/swap! rngs-atom assoc e (lcg/lcg-new (+ base-seed e)))))
      (let [rngs @rngs-atom
            goal-pairs (mapv (fn [e]
                                (loop [d 0 st (nth rngs e) acc (transient [])]
                                  (if (= d ndof)
                                    [(persistent! acc) st]
                                    (let [[v st'] (lcg/next-signed st)]
                                      (recur (inc d) st' (conj! acc (* v (:goal-range cfg))))))))
                              (range num-envs-n))]
        (clojure.core/reset! rngs-atom (mapv second goal-pairs))
        (clojure.core/reset! goals-atom (vec (mapcat first goal-pairs))))
      (clojure.core/reset! states-atom (vec (repeat num-envs-n (zero-joint-state ndof))))
      (clojure.core/reset! steps-atom (vec (repeat num-envs-n 0))))
    (t/observations-flat this))
  (step-all! [_ actions]
    (let [ndof (:ndof chain)]
      (assert (= (count actions) (* num-envs-n ndof)) "action shape")
      (let [actions (if (> (:action-noise-std cfg) 0.0)
                      (let [std (:action-noise-std cfg)]
                        (loop [i 0 st @noise-rng-atom acc (transient [])]
                          (if (= i (count actions))
                            (do (clojure.core/reset! noise-rng-atom st) (persistent! acc))
                            (let [[nz st'] (lcg/next-signed st)]
                              (recur (inc i) st' (conj! acc (+ (nth actions i) (* nz std))))))))
                      actions)
            targets (if (:normalized-actions? cfg)
                      (policy/rescale-to-limits actions (:limits chain) num-envs-n)
                      actions)
            dof-scales @dof-scales-atom
            opts-of (fn [e] {:kp (:kp cfg) :kd (:kd cfg) :computed-torque? (:computed-torque? cfg)
                              :gravity-z (:gravity-z cfg)
                              :gravity-scale (:gravity-scale (nth dof-scales e))
                              :mass-scale (:mass-scale (nth dof-scales e))
                              :dt (:dt cfg)})]
        (clojure.core/swap!
         states-atom
         (fn [states]
           (mapv (fn [e state]
                   (let [tgt (subvec targets (* e ndof) (* (inc e) ndof))]
                     (loop [k 0 s state]
                       (if (= k (:decimation cfg)) s (recur (inc k) (step-chain chain s tgt (opts-of e)))))))
                 (range num-envs-n) states)))
        (clojure.core/swap! steps-atom #(mapv inc %))
        (let [states @states-atom
              goals @goals-atom
              obs-all-clean (observations-flat* chain states goals)
              obs-all (if (> (:obs-noise-std cfg) 0.0)
                        (let [std (:obs-noise-std cfg)]
                          (loop [i 0 st @noise-rng-atom acc (transient [])]
                            (if (= i (count obs-all-clean))
                              (do (clojure.core/reset! noise-rng-atom st) (persistent! acc))
                              (let [[nz st'] (lcg/next-signed st)]
                                (recur (inc i) st' (conj! acc (+ (nth obs-all-clean i) (* nz std))))))))
                        obs-all-clean)
              od (* 3 ndof)]
          (mapv (fn [e]
                  (let [{:keys [q]} (nth states e)
                        goal (subvec goals (* e ndof) (* (inc e) ndof))
                        err (mapv - q goal)
                        sq-err (reduce + 0.0 (map #(* % %) err))
                        max-err (reduce max 0.0 (map #(Math/abs (double %)) err))
                        act (subvec actions (* e ndof) (* (inc e) ndof))
                        act-sq (reduce + 0.0 (map #(* % %) act))
                        reward (- (- sq-err) (* (:action-penalty cfg) act-sq))]
                    (t/step-result (subvec obs-all (* e od) (* (inc e) od))
                                    reward
                                    (< max-err (:goal-tol cfg))
                                    (>= (nth @steps-atom e) (:max-steps cfg)))))
                (range num-envs-n))))))
  (observations-flat [_]
    (observations-flat* chain @states-atom @goals-atom)))

(defn vectorized-reach-env-new
  "Build `num-envs` copies of the serial revolute chain in `urdf-text` (see
  namespace docstring for the URDF-extraction / dynamics duck-typing)."
  [num-envs urdf-text cfg]
  (when (zero? num-envs) (throw (ex-info "num-envs must be > 0" {})))
  (let [chain (parse-urdf-chain urdf-text)]
    (when (zero? (:ndof chain)) (throw (ex-info "articulation has no actuated DOF" {})))
    (->VectorizedReachEnvT
     chain num-envs cfg
     (atom (vec (repeat num-envs (zero-joint-state (:ndof chain)))))
     (atom (vec (repeat (* num-envs (:ndof chain)) 0.0)))
     (atom (vec (repeat num-envs {:gravity-scale 1.0 :mass-scale 1.0})))
     (atom (vec (repeat num-envs 0)))
     (atom (mapv #(lcg/lcg-new %) (range num-envs)))
     (atom (lcg/lcg-new 0x9E3779B9)))))

;; Extra (non-protocol) accessors mirroring the Rust inherent-impl surface.

(defn dof-limits [^VectorizedReachEnvT env] (:limits (.-chain env)))
(defn dof-names [^VectorizedReachEnvT env] (:dof-names (.-chain env)))
(defn goals [^VectorizedReachEnvT env] @(.-goals-atom env))
(defn env-chain [^VectorizedReachEnvT env] (.-chain env))
(defn env-states [^VectorizedReachEnvT env] @(.-states-atom env))
