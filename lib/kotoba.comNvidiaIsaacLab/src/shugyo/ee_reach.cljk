(ns shugyo.ee-reach
  "`VectorizedEeReachEnv` — an end-effector **Cartesian** reach task — port of
  the original crate's `ee_reach_env.rs`. Built on `shugyo.reach`'s URDF-chain
  parsing + forward kinematics (reused directly — kept DRY rather than
  duplicating the chain/FK code).

  Duck-typing note (on top of `shugyo.reach`'s FK/dynamics duck-typing):

    - **`kami_sensor_sim::ContactSensor`** — never restored as a kotoba-lang
      repo. The original test usage is a simple point-goal proximity sensor
      (`in_contact ⟺ ‖ee - goal‖ < contact_radius`), so `ee-in-contact?`
      reimplements exactly that — a genuine (if minimal) contact sensor, not
      a no-op stub — returning `{:in-contact? bool :contact-normal unit-vec}`
      (the unit vector from ee toward goal; a finite fallback `[0 0 1]` when
      the two points coincide, matching the `contact_normal.is_finite()`
      assertion the original test makes).
    - **`solve_ik_to_goals`** (originally a damped-least-squares call into
      `kami_genesis`'s batched IK solver) — reimplemented here as numeric
      Jacobian-transpose-style damped least-squares IK against a
      finite-difference Jacobian of `shugyo.reach/forward-kinematics`
      (perturb each joint by ε, measure the tool-point displacement). Generic
      to any chain length; genuinely solves the IK per env (not a
      lookup/oracle), iterating `iters` times with damping `lambda`."
  (:require [shugyo.lcg :as lcg]
            [shugyo.reach :as reach]
            [shugyo.traits :as t]))

;; ---------------------------------------------------------------------------
;; Contact sensor duck-type (see namespace docstring)
;; ---------------------------------------------------------------------------

(defn ee-in-contact?
  "`{:in-contact? bool :contact-normal [x y z]}` — a minimal point-goal
  proximity sensor. `contact-radius <= 0` disables contact entirely (pure
  positioning task)."
  [ee goal contact-radius]
  (let [d (reach/v- ee goal)
        dist (reach/v-norm d)
        in-contact? (and (> contact-radius 0.0) (< dist contact-radius))
        normal (if (< dist 1e-9) [0.0 0.0 1.0] (reach/v-scale d (/ -1.0 dist)))]
    {:in-contact? in-contact? :contact-normal normal}))

;; ---------------------------------------------------------------------------
;; Numeric damped-least-squares IK via finite-difference Jacobian of FK
;; ---------------------------------------------------------------------------

(defn- finite-diff-jacobian
  "3xN Jacobian of the tool-point position w.r.t. joint angles `q`, via
  central finite differences (`eps` radians)."
  [chain link-name tool-offset q eps]
  (let [ndof (:ndof chain)
        f (fn [qv] (reach/tool-world-pos chain qv link-name tool-offset))]
    (vec
     (for [d (range ndof)]
       (let [q+ (update q d + eps)
             q- (update q d - eps)
             p+ (f q+) p- (f q-)]
         (reach/v-scale (reach/v- p+ p-) (/ 1.0 (* 2.0 eps))))))))

(defn solve-ik-point
  "Damped-least-squares IK: solve `q` such that `tool-world-pos chain q
  link-name tool-offset` reaches `goal`, starting from `q0`, iterating
  `iters` times with damping `lambda`."
  [chain link-name tool-offset goal q0 iters lambda]
  (let [ndof (:ndof chain)]
    (loop [i 0 q q0]
      (if (= i iters)
        q
        (let [p (reach/tool-world-pos chain q link-name tool-offset)
              err (reach/v- goal p)
              ;; Column-major NxD Jacobian (rows = joints, each a 3-vector).
              jac (finite-diff-jacobian chain link-name tool-offset q 1e-4)
              ;; Jacobian-transpose step, damped: dq_d = alpha * J_d . err
              ;; with a small adaptive step so it behaves like a damped
              ;; least-squares update without a full matrix solve.
              alpha (/ 1.0 (+ lambda (reduce + 0.0 (map #(reach/v-dot % %) jac))))
              dq (mapv (fn [jd] (* alpha (reach/v-dot jd err))) jac)]
          (recur (inc i) (mapv + q dq)))))))

;; ---------------------------------------------------------------------------
;; ReachCfg helper (reuse `shugyo.reach/reach-cfg-default`)
;; ---------------------------------------------------------------------------

(defn- zero-joint-state [ndof]
  {:q (vec (repeat ndof 0.0)) :qdot (vec (repeat ndof 0.0))})

;; ---------------------------------------------------------------------------
;; VectorizedEeReachEnv
;; ---------------------------------------------------------------------------

(defn- tool-world [chain q ee-link tool-offset]
  (reach/tool-world-pos chain q ee-link tool-offset))

(deftype VectorizedEeReachEnvT
    [chain num-envs-n ee-link cfg
     states-atom goals-atom ref-q-atom dof-scales-atom steps-atom rngs-atom noise-rng-atom]
  t/VecRLEnv
  (num-envs [_] num-envs-n)
  (observation-dim-per-env [_] (+ (* 2 (:ndof chain)) 6 (if (:observe-contact? cfg) 1 0)))
  (action-dim-per-env [_] (:ndof chain))
  (reset-all! [this base-seed]
    (let [ndof (:ndof chain)]
      (when (some? base-seed)
        (clojure.core/reset! noise-rng-atom (lcg/lcg-new (bit-xor base-seed 0xA5A51234))))
      (let [g (:gravity-dr cfg) m (:mass-dr cfg)]
        (clojure.core/reset!
         dof-scales-atom
         (if (or g m)
           (reach/randomize-physics (bit-xor (or base-seed 0) 0xD12) num-envs-n g m)
           (vec (repeat num-envs-n {:gravity-scale 1.0 :mass-scale 1.0})))))
      (dotimes [e num-envs-n]
        (when (some? base-seed)
          (clojure.core/swap! rngs-atom assoc e (lcg/lcg-new (+ base-seed e)))))
      (let [rngs @rngs-atom
            ref-pairs (mapv (fn [e]
                               (loop [d 0 st (nth rngs e) acc (transient [])]
                                 (if (= d ndof)
                                   [(persistent! acc) st]
                                   (let [[v st'] (lcg/next-signed st)]
                                     (recur (inc d) st' (conj! acc (* v (:goal-range cfg))))))))
                             (range num-envs-n))
            ref-q (vec (mapcat first ref-pairs))]
        (clojure.core/reset! rngs-atom (mapv second ref-pairs))
        (clojure.core/reset! ref-q-atom ref-q)
        ;; FK at the reference config gives the reachable Cartesian goal.
        (clojure.core/reset!
         goals-atom
         (vec (mapcat (fn [e]
                        (tool-world chain (subvec ref-q (* e ndof) (* (inc e) ndof))
                                    ee-link (:tool-offset cfg)))
                      (range num-envs-n)))))
      ;; Episode starts from the zero pose.
      (clojure.core/reset! states-atom (vec (repeat num-envs-n (zero-joint-state ndof))))
      (clojure.core/reset! steps-atom (vec (repeat num-envs-n 0))))
    (t/observations-flat this))
  (step-all! [this actions]
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
                   (let [tgt (subvec actions (* e ndof) (* (inc e) ndof))]
                     (loop [k 0 s state]
                       (if (= k (:decimation cfg)) s (recur (inc k) (reach/step-chain chain s tgt (opts-of e)))))))
                 (range num-envs-n) states)))
        (clojure.core/swap! steps-atom #(mapv inc %))
        (let [obs-all-clean (t/observations-flat this)
              obs-all (if (> (:obs-noise-std cfg) 0.0)
                        (let [std (:obs-noise-std cfg)]
                          (loop [i 0 st @noise-rng-atom acc (transient [])]
                            (if (= i (count obs-all-clean))
                              (do (clojure.core/reset! noise-rng-atom st) (persistent! acc))
                              (let [[nz st'] (lcg/next-signed st)]
                                (recur (inc i) st' (conj! acc (+ (nth obs-all-clean i) (* nz std))))))))
                        obs-all-clean)
              od (t/observation-dim-per-env this)
              states @states-atom
              goals @goals-atom]
          (mapv (fn [e]
                  (let [q (:q (nth states e))
                        ee (tool-world chain q ee-link (:tool-offset cfg))
                        goal (subvec goals (* e 3) (* (inc e) 3))
                        d (reach/v- ee goal)
                        sq (reach/v-dot d d)
                        act (subvec actions (* e ndof) (* (inc e) ndof))
                        act-sq (reduce + 0.0 (map #(* % %) act))
                        {:keys [in-contact?]} (ee-in-contact? ee goal (:contact-radius cfg))
                        bonus (if in-contact? (:contact-bonus cfg) 0.0)
                        reward (+ (- (- sq) (* (:action-penalty cfg) act-sq)) bonus)]
                    (t/step-result (subvec obs-all (* e od) (* (inc e) od))
                                    reward
                                    (< (reach/v-norm d) (:goal-tol cfg))
                                    (>= (nth @steps-atom e) (:max-steps cfg)))))
                (range num-envs-n))))))
  (observations-flat [_]
    (let [ndof (:ndof chain)
          states @states-atom
          goals @goals-atom]
      (vec
       (mapcat
        (fn [e]
          (let [{:keys [q qdot]} (nth states e)
                ee (tool-world chain q ee-link (:tool-offset cfg))
                goal (subvec goals (* e 3) (* (inc e) 3))
                d (reach/v- goal ee)
                touch (when (:observe-contact? cfg)
                        [(if (:in-contact? (ee-in-contact? ee goal (:contact-radius cfg))) 1.0 0.0)])]
            (concat q qdot ee d touch)))
        (range num-envs-n))))))

(defn vectorized-ee-reach-env-new
  "Build `num-envs` copies of the serial revolute chain in `urdf-text`;
  `ee-link` is the end-effector link whose (tool-offset-shifted) world
  position is the reach target."
  [num-envs urdf-text ee-link cfg]
  (when (zero? num-envs) (throw (ex-info "num-envs must be > 0" {})))
  (let [chain (reach/parse-urdf-chain urdf-text)]
    (when (zero? (:ndof chain)) (throw (ex-info "articulation has no actuated DOF" {})))
    (when (nil? (reach/link-pose chain (vec (repeat (:ndof chain) 0.0)) ee-link))
      (throw (ex-info (str "end-effector link '" ee-link "' not found") {})))
    (->VectorizedEeReachEnvT
     chain num-envs ee-link cfg
     (atom (vec (repeat num-envs (zero-joint-state (:ndof chain)))))
     (atom (vec (repeat (* num-envs 3) 0.0)))
     (atom (vec (repeat (* num-envs (:ndof chain)) 0.0)))
     (atom (vec (repeat num-envs {:gravity-scale 1.0 :mass-scale 1.0})))
     (atom (vec (repeat num-envs 0)))
     (atom (mapv #(lcg/lcg-new %) (range num-envs)))
     (atom (lcg/lcg-new 0x9E3779B9)))))

;; Extra (non-protocol) accessors mirroring the Rust inherent-impl surface.

(defn goals [^VectorizedEeReachEnvT env] @(.-goals-atom env))
(defn reference-joint-solution [^VectorizedEeReachEnvT env] @(.-ref-q-atom env))

(defn set-cartesian-goals!
  "Override the per-env Cartesian goals with user-specified world targets
  (`[num-envs, 3]`). Invalidates `reference-joint-solution` as an IK
  reference (no longer generated by FK sampling)."
  [^VectorizedEeReachEnvT env targets]
  (assert (= (count targets) (* (.-num-envs-n env) 3)) "goal shape [num-envs, 3]")
  (clojure.core/reset! (.-goals-atom env) (vec targets)))

(defn solve-ik-to-goals
  "Solve per-env IK for the current Cartesian goals; returns the
  `[num-envs, n-dof]` joint targets."
  [^VectorizedEeReachEnvT env iters lambda]
  (let [chain (.-chain env)
        ndof (:ndof chain)
        ee-link (.-ee-link env)
        cfg (.-cfg env)
        goals @(.-goals-atom env)
        n (.-num-envs-n env)]
    (vec
     (mapcat
      (fn [e]
        (solve-ik-point chain ee-link (:tool-offset cfg)
                         (subvec goals (* e 3) (* (inc e) 3))
                         (vec (repeat ndof 0.0)) iters lambda))
      (range n)))))
