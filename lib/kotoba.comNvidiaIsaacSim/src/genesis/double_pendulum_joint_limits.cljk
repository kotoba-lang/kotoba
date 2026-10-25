(ns genesis.double-pendulum-joint-limits
  "Joint-angle limits for genesis.double-pendulum, unified into the same
  effective-mass + sequential-impulse constraint structure
  genesis.rigid-body uses for Cartesian contact (ADR-2607110900 M3),
  instead of a naive independent clamp-and-zero per joint.

  A one-sided joint-limit constraint uses the exact same 'effective mass
  along a direction, then velocity-level impulse' math as a contact
  normal constraint — just in *joint space* (direction = a unit basis
  vector e_i selecting one generalized coordinate) instead of Cartesian
  space (direction = a contact normal), with the manipulator mass matrix
  M(q) — already real and ported in genesis.double-pendulum — standing
  in for the point-mass/inertia effective-mass computation.

  Concretely: for joint i's limit constraint, effective inverse mass
  w_i = e_i^T M(q)^-1 e_i (a diagonal entry of M^-1), and the impulse
  lambda = -(1+e)*qdot_i / w_i changes BOTH q1-dot and q2-dot via
  lambda * (column i of M^-1) — not just qdot_i in isolation. The M12
  cross term is what makes this a real coupled constraint rather than a
  clamp: a naive per-joint clamp would leave the other joint's velocity
  untouched, silently violating the coupled equations of motion.

  Does not modify genesis.double-pendulum/step (the unconstrained
  integrator) — this is a post-step constraint-resolution pass composed
  on top of it, same shape as ADR-2607110900 M2's contact resolution
  being separate from free-body integration."
  (:require [genesis.double-pendulum :as dp]))

(defn ->limits
  [{:keys [q1-lower q1-upper q2-lower q2-upper restitution baumgarte slop]
    :or {q1-lower ##-Inf q1-upper ##Inf
         q2-lower ##-Inf q2-upper ##Inf
         restitution 0.0 baumgarte 0.15 slop 1.0e-3}}]
  {:q1 [q1-lower q1-upper] :q2 [q2-lower q2-upper]
   :restitution restitution :baumgarte baumgarte :slop slop})

(defn- inv-mass-2x2
  "M(q)^-1 as {:i11 :i12 :i22} (symmetric, so i21 = i12)."
  [cfg q2]
  (let [[m11 m12 m22] (dp/mass-matrix cfg q2)
        det (- (* m11 m22) (* m12 m12))]
    {:i11 (/ m22 det) :i12 (/ (- m12) det) :i22 (/ m11 det)}))

(defn- joint-impulse
  "lambda for a one-sided constraint on a joint whose current velocity is
  `qdot` and whose own effective inverse mass is `w` (a diagonal M^-1
  entry). Same restitution formula as genesis.rigid-body/resolve-contact."
  [qdot w restitution]
  (/ (* (- (+ 1.0 restitution)) qdot) w))

(defn- baumgarte-delta [q limit-q direction baumgarte slop]
  (let [overshoot (* direction (- q limit-q))] ;; positive iff violating
    (* (- direction) baumgarte (max 0.0 (- overshoot slop)))))

(defn resolve-limits
  "One constraint-resolution pass after an unconstrained genesis.double-
  pendulum/step. `state` is that step's output; `limits` is a ->limits
  map. Returns an updated state with joint limits enforced (velocity
  impulse + Baumgarte position correction), or `state` unchanged if
  neither joint is violating its limit."
  [{:keys [q1 q2 q1-dot q2-dot] :as state} cfg limits]
  (let [{:keys [restitution baumgarte slop]} limits
        [q1-lower q1-upper] (:q1 limits)
        [q2-lower q2-upper] (:q2 limits)
        {:keys [i11 i12 i22]} (inv-mass-2x2 cfg q2)
        violating? (fn [q qdot lower upper]
                     (cond (and (> q upper) (pos? qdot)) :upper
                           (and (< q lower) (neg? qdot)) :lower
                           :else nil))
        v1 (violating? q1 q1-dot q1-lower q1-upper)
        v2 (violating? q2 q2-dot q2-lower q2-upper)
        ;; joint 1's constraint impulse (if any), applied to both DOFs via M^-1
        [q1-dot q2-dot]
        (if v1
          (let [lambda (joint-impulse q1-dot i11 restitution)]
            [(+ q1-dot (* lambda i11)) (+ q2-dot (* lambda i12))])
          [q1-dot q2-dot])
        ;; joint 2's constraint impulse (if any) — Gauss-Seidel: reads the
        ;; just-updated q1-dot/q2-dot, same sequential-impulse style as
        ;; genesis.rigid-body/resolve-contacts.
        [q1-dot q2-dot]
        (if v2
          (let [lambda (joint-impulse q2-dot i22 restitution)]
            [(+ q1-dot (* lambda i12)) (+ q2-dot (* lambda i22))])
          [q1-dot q2-dot])
        q1' (if v1
              (+ q1 (baumgarte-delta q1 (if (= v1 :upper) q1-upper q1-lower)
                                     (if (= v1 :upper) 1.0 -1.0) baumgarte slop))
              q1)
        q2' (if v2
              (+ q2 (baumgarte-delta q2 (if (= v2 :upper) q2-upper q2-lower)
                                     (if (= v2 :upper) 1.0 -1.0) baumgarte slop))
              q2)]
    (if (or v1 v2)
      {:q1 q1' :q2 q2' :q1-dot q1-dot :q2-dot q2-dot}
      state)))

(defn step
  "genesis.double-pendulum/step followed by one resolve-limits pass — the
  limit-aware drop-in replacement for dp/step."
  [state tau cfg limits]
  (resolve-limits (dp/step state tau cfg) cfg limits))
