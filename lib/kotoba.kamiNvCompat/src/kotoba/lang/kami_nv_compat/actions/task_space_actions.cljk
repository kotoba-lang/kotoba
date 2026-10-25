(ns kotoba.lang.kami-nv-compat.actions.task-space-actions
  "Task-space action wrappers — JVM port of src/actions/task-space-actions.ts.
  DifferentialInverseKinematicsAction, OperationalSpaceControllerAction,
  BinaryJointPositionAction, NonHolonomicAction. Each wraps a controller or
  kinematic model and dispatches effort via write-effort!. Wave 16d of
  ADR-2607020130."
  (:require [kotoba.lang.kami-nv-compat.actions.action-term :as at]
            [kotoba.lang.kami-nv-compat.actions.articulated-env :as ae]
            [kotoba.lang.kami-nv-compat.controllers.differential-ik :as dik]
            [kotoba.lang.kami-nv-compat.controllers.operational-space :as osc]))

;; ── DifferentialInverseKinematicsAction ───────────────────────────────────

(defn make-diff-ik-action
  "Differential IK action: target pose → joint DELTA → PD effort."
  [cfg]
  (let [controller-cfg (or (:controller-cfg cfg) (dik/make-default-differential-ik-cfg))
        controller (dik/differential-ik-controller controller-cfg)
        inferred (dik/action-dim controller)
        _ (when (and (some? (:action-dim cfg)) (not= (:action-dim cfg) inferred))
            (throw (ex-info "DiffIK: actionDim contradicts controller" {:cfg (:action-dim cfg) :inferred inferred})))
        state (at/make-action-term-state (assoc cfg :action-dim inferred))]
    {:term
     (reify at/IActionTerm
       (action-dim [_] (:action-dim state))
       (process-actions! [_ raw] (at/base-process-actions! state raw))
       (reset-term! [_] (at/base-reset! state) (dik/reset-controller! controller nil))
       (apply-actions! [_ env]
         (let [body-name (:body-name cfg)
               jacobian (ae/get-jacobian env body-name)
               [ee-pos ee-quat] (ae/get-ee-pose env body-name)
               q-full (ae/joint-positions env)
               dq-full (ae/joint-velocities env)
               joints (:joint-names cfg)
               q-arm (mapv #(if (< % (count q-full)) (q-full %) 0) joints)
               processed @(:processed-actions state)]
           (dik/set-command! controller processed {:ee-pos ee-pos :ee-quat ee-quat})
           (let [joint-delta (dik/compute controller {:ee-pos ee-pos :ee-quat ee-quat :jacobian jacobian})
                 p-gain (or (:p-gain cfg) 100.0)
                 d-gain (or (:d-gain cfg) 10.0)
                 torques (vec (for [slot (range (count joints))]
                                (let [joint (joints slot)
                                      target (+ (q-arm slot) (joint-delta slot))
                                      qj (if (< joint (count q-full)) (q-full joint) 0)
                                      dqj (if (< joint (count dq-full)) (dq-full joint) 0)
                                      tau (- (* p-gain (- target qj)) (* d-gain dqj))]
                                  [joint tau])))]
             (ae/write-effort! env torques false)))))
     :state state :controller controller}))

;; ── OperationalSpaceControllerAction ──────────────────────────────────────

(defn make-osc-action
  "OSC action: target wrench/pose → joint TORQUES (no PD layer)."
  [cfg]
  (let [controller-cfg (or (:controller-cfg cfg) (osc/make-default-osc-cfg))
        num-dof (count (:joint-names cfg))
        controller (osc/operational-space-controller controller-cfg 1 num-dof)
        inferred (osc/action-dim controller)
        _ (when (and (some? (:action-dim cfg)) (not= (:action-dim cfg) inferred))
            (throw (ex-info "OSC: actionDim contradicts controller" {:cfg (:action-dim cfg) :inferred inferred})))
        state (at/make-action-term-state (assoc cfg :action-dim inferred))]
    {:term
     (reify at/IActionTerm
       (action-dim [_] (:action-dim state))
       (process-actions! [_ raw] (at/base-process-actions! state raw))
       (reset-term! [_] (at/base-reset! state))
       (apply-actions! [_ env]
         (let [body-name (:body-name cfg)
               jacobian (ae/get-jacobian env body-name)
               [ee-pos ee-quat] (ae/get-ee-pose env body-name)
               [ee-lin-vel ee-ang-vel] (ae/get-ee-velocity env body-name)
               q-full (ae/joint-positions env)
               dq-full (ae/joint-velocities env)
               joints (:joint-names cfg)
               q-arm (mapv #(if (< % (count q-full)) (q-full %) 0) joints)
               dq-arm (mapv #(if (< % (count dq-full)) (dq-full %) 0) joints)
               processed @(:processed-actions state)
               gravity-torque (when (:gravity-compensation controller-cfg)
                                (ae/get-gravity-torque env body-name))
               ns-target (when (not= (:nullspace-control controller-cfg) "none")
                           (or (:nullspace-joint-targets cfg) q-arm))]
           (osc/set-command! controller processed {:ee-pos ee-pos :ee-quat ee-quat})
           (let [tau (osc/compute controller {:ee-pos ee-pos :ee-quat ee-quat
                                              :ee-lin-vel ee-lin-vel :ee-ang-vel ee-ang-vel
                                              :jacobian jacobian :joint-pos q-arm :joint-vel dq-arm
                                              :gravity-torque gravity-torque :nullspace-target-pos ns-target})]
             (ae/write-effort! env (mapv vector joints tau) false)))))
     :state state :controller controller}))

;; ── BinaryJointPositionAction ─────────────────────────────────────────────

(defn make-binary-joint-position-action
  "Binary open/close gripper: action[0] >= threshold → close."
  [cfg]
  (let [n (count (:joint-names cfg))]
    (when (not= n (count (:open-command cfg)))
      (throw (ex-info "open-command length must match joint-names" {:n n :got (count (:open-command cfg))})))
    (when (not= n (count (:close-command cfg)))
      (throw (ex-info "close-command length must match joint-names" {:n n :got (count (:close-command cfg))})))
    (let [state (at/make-action-term-state (assoc cfg :action-dim 1))
          is-close (atom false)]
      {:term
       (reify at/IActionTerm
         (action-dim [_] 1)
         (process-actions! [_ raw] (at/base-process-actions! state raw))
         (reset-term! [_] (at/base-reset! state) (reset! is-close false))
         (apply-actions! [_ env]
           (let [threshold (or (:threshold cfg) 0.0)
                 processed @(:processed-actions state)]
             (reset! is-close (>= (first processed) threshold))
             (let [target-pose (if @is-close (:close-command cfg) (:open-command cfg))
                   q (ae/joint-positions env)
                   dq (ae/joint-velocities env)
                   joints (:joint-names cfg)
                   p-gain (or (:p-gain cfg) 100.0)
                   d-gain (or (:d-gain cfg) 10.0)
                   torques (vec (for [slot (range n)]
                                  (let [joint (joints slot)
                                        target (target-pose slot)
                                        qj (if (< joint (count q)) (q joint) 0)
                                        dqj (if (< joint (count dq)) (dq joint) 0)
                                        tau (- (* p-gain (- target qj)) (* d-gain dqj))]
                                    [joint tau])))]
               (ae/write-effort! env torques false)))))
       :state state :is-close is-close})))

;; ── NonHolonomicAction (differential-drive mobile base) ───────────────────

(defn make-non-holonomic-action
  "Differential-drive: [v_x, omega_z] → wheel velocities → PD effort."
  [cfg]
  (when (not= 2 (count (:joint-names cfg)))
    (throw (ex-info "NonHolonomic: joint-names must be [leftWheel, rightWheel]" {:got (count (:joint-names cfg))})))
  (when (or (nil? (:wheel-radius cfg)) (<= (:wheel-radius cfg) 0))
    (throw (ex-info "NonHolonomic: wheel-radius must be > 0" {})))
  (when (or (nil? (:wheel-separation cfg)) (<= (:wheel-separation cfg) 0))
    (throw (ex-info "NonHolonomic: wheel-separation must be > 0" {})))
  (let [state (at/make-action-term-state (assoc cfg :action-dim 2))
        wheel-target (atom [0 0])]
    {:term
     (reify at/IActionTerm
       (action-dim [_] 2)
       (process-actions! [_ raw]
         (when (not= 2 (count raw))
           (throw (ex-info "NonHolonomic: expected 2 action elements" {:got (count raw)})))
         (at/base-process-actions! state raw))
       (reset-term! [_] (at/base-reset! state) (reset! wheel-target [0 0]))
       (apply-actions! [_ env]
         (let [processed @(:processed-actions state)
               v-x (processed 0)
               omega-z (processed 1)
               half-l (/ (:wheel-separation cfg) 2)
               r (:wheel-radius cfg)
               omega-left (/ (- v-x (* omega-z half-l)) r)
               omega-right (/ (+ v-x (* omega-z half-l)) r)]
           (reset! wheel-target [omega-left omega-right])
           (let [dq (ae/joint-velocities env)
                 [left-joint right-joint] (:joint-names cfg)
                 dq-left (if (< left-joint (count dq)) (dq left-joint) 0)
                 dq-right (if (< right-joint (count dq)) (dq right-joint) 0)
                 p-gain (or (:p-gain cfg) 10.0)
                 tau-left (* p-gain (- omega-left dq-left))
                 tau-right (* p-gain (- omega-right dq-right))]
             (ae/write-effort! env [[left-joint tau-left] [right-joint tau-right]] false)))))
     :state state :wheel-target wheel-target}))
