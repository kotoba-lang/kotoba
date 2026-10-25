(ns genesis.double-pendulum
  "2-link planar revolute serial chain (double pendulum) — extends beyond
  Cartpole topology toward general robot arms.

  Equations from Spong, Hutchinson & Vidyasagar \"Robot Modeling and
  Control\" (planar 2-link manipulator, revolute-revolute, gravity along
  -z, motion confined to the xz plane with both axes along world y).
  Uniform-density rods assumed (lc = l/2, I = m*l^2/12).

  Restored from kotoba-lang/kami-engine
  `kami-genesis/src/double_pendulum.rs` (deleted PR #82) as
  zero-dependency portable CLJC. Per ADR-2607010930. Ported 1:1
  (fully portable pure math/data)."
  )

(defn default-config
  "Matches kami-engine fixtures/double_pendulum/double_pendulum.urdf."
  []
  {:m1 1.0 :m2 1.0 :l1 1.0 :l2 1.0
   :gravity 9.81 :effort-limit 50.0
   :dt (/ 1.0 240.0)}) ;; 240 Hz physics

(defn default-state []
  {:q1 0.0 :q2 0.0 :q1-dot 0.0 :q2-dot 0.0})

(defn clamp [v lo hi] (max lo (min hi v)))

(defn mass-matrix
  "[m11 m12 m22] — the 2x2 symmetric manipulator mass matrix M(q) at this
  q2 (m11/m12/m22 depend only on q2, not q1, for this planar 2-link
  geometry). Public: genesis.double-pendulum-joint-limits builds a joint-
  space constraint on this same M(q) (ADR-2607110900 M3)."
  [{:keys [m1 m2 l1 l2]} q2]
  (let [lc1 (* l1 0.5) lc2 (* l2 0.5)
        i1 (/ (* m1 l1 l1) 12.0) i2 (/ (* m2 l2 l2) 12.0)
        c2 (Math/cos q2)
        m11 (+ (* m1 lc1 lc1)
               (* m2 (+ (* l1 l1) (* lc2 lc2) (* 2.0 l1 lc2 c2)))
               i1 i2)
        m12 (+ (* m2 (+ (* lc2 lc2) (* l1 lc2 c2))) i2)
        m22 (+ (* m2 lc2 lc2) i2)]
    [m11 m12 m22]))

(defn step
  "Semi-implicit Euler step with `tau = [tau1 tau2]` (joint torques)."
  [{:keys [q1 q2 q1-dot q2-dot]} [tau1 tau2] {:keys [m1 m2 l1 l2 gravity effort-limit dt] :as cfg}]
  (let [t1 (clamp tau1 (- effort-limit) effort-limit)
        t2 (clamp tau2 (- effort-limit) effort-limit)
        lc1 (* l1 0.5) lc2 (* l2 0.5)
        s2 (Math/sin q2)
        s1 (Math/sin q1)
        s12 (Math/sin (+ q1 q2))
        [m11 m12 m22] (mass-matrix cfg q2)
        h (* -1.0 m2 l1 lc2 s2)
        c1 (* h q2-dot (+ (* 2.0 q1-dot) q2-dot))
        c2 (* -1.0 h q1-dot q1-dot)
        g1 (+ (* (+ (* m1 lc1) (* m2 l1)) gravity s1)
              (* m2 lc2 gravity s12))
        g2 (* m2 lc2 gravity s12)
        b1 (- t1 c1 g1)
        b2 (- t2 c2 g2)
        det (- (* m11 m22) (* m12 m12))
        q1-acc (/ (- (* m22 b1) (* m12 b2)) det)
        q2-acc (/ (+ (* -1.0 m12 b1) (* m11 b2)) det)
        q1-dot' (+ q1-dot (* dt q1-acc))
        q1' (+ q1 (* dt q1-dot'))
        q2-dot' (+ q2-dot (* dt q2-acc))
        q2' (+ q2 (* dt q2-dot'))]
    {:q1 q1' :q2 q2' :q1-dot q1-dot' :q2-dot q2-dot'}))

(defn energy
  "Total mechanical energy — validates energy conservation under zero
  torque (semi-implicit Euler conserves energy approximately)."
  [{:keys [q1 q2 q1-dot q2-dot]} {:keys [m1 m2 l1 l2 gravity] :as cfg}]
  (let [lc1 (* l1 0.5) lc2 (* l2 0.5)
        [m11 m12 m22] (mass-matrix cfg q2)
        q1d q1-dot q2d q2-dot
        ke (* 0.5 (+ (* m11 q1d q1d) (* 2.0 m12 q1d q2d) (* m22 q2d q2d)))
        z1 (* -1.0 lc1 (Math/cos q1))
        z2 (- (* -1.0 l1 (Math/cos q1)) (* lc2 (Math/cos (+ q1 q2))))
        pe (+ (* m1 gravity z1) (* m2 gravity z2))]
    (+ ke pe)))
