(ns genesis.controllers
  "ArticulationController — PD / velocity / effort control surface.

  Mirrors `isaacsim.core.api.controllers.ArticulationController` (Isaac
  Sim 4.x). Takes an `ArticulationAction` map that may specify any
  combination of `:joint-positions` (PD target), `:joint-velocities` (PD
  damping target), or `:joint-efforts` (direct + feedforward), and
  computes per-step torques.

      tau_i = kp_i . (q_target_i - q_i)
            + kd_i . (qdot_target_i - qdot_i)
            + tau_ff_i

  Adaptation from the original Rust: `ArticulationController::apply_action`
  took `&mut Articulation` (a `genesis.world`-owned, URDF-driven handle)
  and mutated it in place. That `World`/`Articulation` integration depends
  on the `kami_articulated` URDF-parsing crate, which is out of scope for
  this restoration (see README / `genesis.world`). Here `compute-torques`
  is a pure function of `(q, qdot, action, controller)` returning the
  clamped torque vector — callers apply it to whatever state representation
  they use (e.g. `genesis.cartpole`/`genesis.double-pendulum`/
  `genesis.planar-chain` states via their own `step` fns). This preserves
  the PD/velocity/effort control law and clamping 1:1.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/controllers.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930."
  )

(defn action-positions [targets] {:joint-positions targets :joint-velocities nil :joint-efforts nil})
(defn action-velocities [targets] {:joint-positions nil :joint-velocities targets :joint-efforts nil})
(defn action-efforts [targets] {:joint-positions nil :joint-velocities nil :joint-efforts targets})
(defn action-empty [dof] {:joint-positions nil :joint-velocities nil :joint-efforts (vec (repeat dof 0.0))})

(defn new-controller
  "Create with uniform gains."
  [dof kp kd max-effort]
  {:kps (vec (repeat dof kp)) :kds (vec (repeat dof kd)) :max-efforts (vec (repeat dof max-effort))
   :last-action nil :last-torques (vec (repeat dof 0.0))})

(defn set-gains [ctrl kps kds] (assert (= (count kps) (count kds))) (assoc ctrl :kps kps :kds kds))
(defn set-max-efforts [ctrl max-efforts] (assoc ctrl :max-efforts max-efforts))
(defn get-gains [{:keys [kps kds]}] [kps kds])
(defn get-max-efforts [{:keys [max-efforts]}] max-efforts)
(defn get-applied-action [{:keys [last-action]}] last-action)
(defn get-last-torques [{:keys [last-torques]}] last-torques)

(defn clamp [v lo hi] (max lo (min hi v)))

(defn compute-torques
  "Compute torques from `action` given current joint state `q`/`qdot`,
  clamp to `max-efforts`, and return `[torques ctrl']` where `ctrl'` has
  `:last-action`/`:last-torques` updated for `get-applied-action`/
  `get-last-torques`."
  [{:keys [kps kds max-efforts] :as ctrl} q qdot action]
  (let [dof (count q)
        _ (assert (= (count kps) dof))
        _ (assert (= (count kds) dof))
        pos-active? (some? (:joint-positions action))
        tau0 (vec (repeat dof 0.0))
        tau1 (if-let [pos (:joint-positions action)]
               (mapv (fn [tau kp p qi] (+ tau (* kp (- p qi)))) tau0 kps pos q)
               tau0)
        tau2 (cond
               (:joint-velocities action)
               (mapv (fn [tau kd v qd] (+ tau (* kd (- v qd)))) tau1 kds (:joint-velocities action) qdot)
               pos-active?
               (mapv (fn [tau kd qd] (+ tau (* kd (- 0.0 qd)))) tau1 kds qdot)
               :else tau1)
        tau3 (if-let [eff (:joint-efforts action)]
               (mapv + tau2 eff)
               tau2)
        tau-clamped (mapv (fn [tau lim] (clamp tau (- lim) lim)) tau3 max-efforts)]
    [tau-clamped (assoc ctrl :last-action action :last-torques tau-clamped)]))
