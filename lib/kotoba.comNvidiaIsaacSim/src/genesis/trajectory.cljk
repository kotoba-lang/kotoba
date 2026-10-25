(ns genesis.trajectory
  "Joint-space trajectory generators — smooth motion between configurations.

  Standard robotics primitives: cubic and quintic polynomial trajectories
  between two joint vectors with matching boundary derivatives, and a
  min-jerk shortcut (quintic with zero boundary accelerations). Plus a
  waypoint sequencer that strings polynomial segments end-to-end.

  Every trajectory here is a map with `:duration`, `:dof`, and can be
  sampled with `sample` -> `[q qdot qddot]` (clamped to [0, duration]).

  References:
    - Spong et al., Robot Modeling and Control §5 (trajectory planning).
    - Flash & Hogan 1985 (minimum-jerk).

  Restored from kotoba-lang/kami-engine `kami-genesis/src/trajectory.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math/data). The original Rust file's
  final test, `controller_tracks_trajectory_to_target`, was an
  integration test that drove `genesis.controllers` through a
  `kami_articulated`-parsed cartpole URDF via `World`; that URDF-driven
  World integration is out of scope here (see README), so this restoration
  substitutes a self-contained smoke test using `genesis.cartpole`
  directly instead (see test suite)."
  )

(defmulti duration :kind)
(defmulti dof :kind)
(defmulti sample (fn [traj _t] (:kind traj)))

;; ── Cubic polynomial: a0 + a1*t + a2*t^2 + a3*t^3 ─────────────────────────

(defn cubic-polynomial-trajectory
  [q0 qf qd0 qdf duration]
  (assert (= (count q0) (count qf) (count qd0) (count qdf)))
  (assert (> duration 0.0) "trajectory duration must be positive")
  (let [t duration t2 (* t t) t3 (* t2 t)
        coeffs (mapv (fn [q0i qfi qd0i qdfi]
                        [q0i qd0i
                         (/ (- (* 3.0 (- qfi q0i)) (* (+ (* 2.0 qd0i) qdfi) t)) t2)
                         (/ (+ (* 2.0 (- q0i qfi)) (* (+ qd0i qdfi) t)) t3)])
                      q0 qf qd0 qdf)]
    {:kind :cubic :q0 q0 :qf qf :qd0 qd0 :qdf qdf :duration duration :coeffs coeffs}))

(defn cubic-stop-to-stop [q0 qf duration]
  (let [zeros (vec (repeat (count q0) 0.0))]
    (cubic-polynomial-trajectory q0 qf zeros zeros duration)))

(defmethod duration :cubic [t] (:duration t))
(defmethod dof :cubic [t] (count (:q0 t)))
(defmethod sample :cubic [{:keys [duration coeffs]} t]
  (let [t (max 0.0 (min duration t))]
    (reduce
      (fn [[q qd qdd] [a0 a1 a2 a3]]
        [(conj q (+ a0 (* a1 t) (* a2 t t) (* a3 t t t)))
         (conj qd (+ a1 (* 2.0 a2 t) (* 3.0 a3 t t)))
         (conj qdd (+ (* 2.0 a2) (* 6.0 a3 t)))])
      [[] [] []] coeffs)))

;; ── Quintic polynomial (boundary pos + vel + accel) ───────────────────────

(defn quintic-polynomial-trajectory
  [q0 qf qd0 qdf qdd0 qddf duration]
  (assert (apply = (map count [q0 qf qd0 qdf qdd0 qddf])))
  (assert (> duration 0.0))
  (let [t duration t2 (* t t) t3 (* t2 t) t4 (* t3 t) t5 (* t4 t)
        coeffs (mapv (fn [q0i qfi qd0i qdfi qdd0i qddfi]
                        [q0i qd0i (/ qdd0i 2.0)
                         (/ (- (* 20.0 (- qfi q0i))
                               (* (+ (* 8.0 qdfi) (* 12.0 qd0i)) t)
                               (* (- (* 3.0 qdd0i) qddfi) t2))
                            (* 2.0 t3))
                         (/ (+ (* 30.0 (- q0i qfi))
                               (* (+ (* 14.0 qdfi) (* 16.0 qd0i)) t)
                               (* (- (* 3.0 qdd0i) (* 2.0 qddfi)) t2))
                            (* 2.0 t4))
                         (/ (- (* 12.0 (- qfi q0i))
                               (* 6.0 (+ qdfi qd0i) t)
                               (* (- qdd0i qddfi) t2))
                            (* 2.0 t5))])
                      q0 qf qd0 qdf qdd0 qddf)]
    {:kind :quintic :q0 q0 :qf qf :qd0 qd0 :qdf qdf :qdd0 qdd0 :qddf qddf :duration duration :coeffs coeffs}))

(defn min-jerk
  "Flash & Hogan 1985 minimum-jerk trajectory: quintic with all boundary
  velocities and accelerations zero."
  [q0 qf duration]
  (let [z (vec (repeat (count q0) 0.0))]
    (quintic-polynomial-trajectory q0 qf z z z z duration)))

(defmethod duration :quintic [t] (:duration t))
(defmethod dof :quintic [t] (count (:q0 t)))
(defmethod sample :quintic [{:keys [duration coeffs]} t]
  (let [t (max 0.0 (min duration t))
        t2 (* t t) t3 (* t2 t) t4 (* t3 t) t5 (* t4 t)]
    (reduce
      (fn [[q qd qdd] [c0 c1 c2 c3 c4 c5]]
        [(conj q (+ c0 (* c1 t) (* c2 t2) (* c3 t3) (* c4 t4) (* c5 t5)))
         (conj qd (+ c1 (* 2.0 c2 t) (* 3.0 c3 t2) (* 4.0 c4 t3) (* 5.0 c5 t4)))
         (conj qdd (+ (* 2.0 c2) (* 6.0 c3 t) (* 12.0 c4 t2) (* 20.0 c5 t3)))])
      [[] [] []] coeffs)))

;; ── Waypoint trajectory (sequence of cubic segments) ──────────────────────

(defn waypoint-trajectory
  "Sequence of joint waypoints with per-segment durations, joined into a
  continuous trajectory. Intermediate-waypoint velocities are centred
  differences (Catmull-Rom-style); endpoints get zero velocity."
  [waypoints segment-durations]
  (assert (>= (count waypoints) 2) "need at least 2 waypoints")
  (assert (= (count segment-durations) (dec (count waypoints))))
  (let [dof (count (first waypoints))
        n (count waypoints)
        vels (vec (for [k (range n)]
                    (if (and (> k 0) (< k (dec n)))
                      (let [dt-left (nth segment-durations (dec k))
                            dt-right (nth segment-durations k)]
                        (mapv (fn [wnext wprev] (/ (- wnext wprev) (+ dt-left dt-right)))
                              (nth waypoints (inc k)) (nth waypoints (dec k))))
                      (vec (repeat dof 0.0)))))
        [segments cum-t]
        (reduce
          (fn [[segs cum acc] k]
            (let [seg (cubic-polynomial-trajectory (nth waypoints k) (nth waypoints (inc k))
                                                     (nth vels k) (nth vels (inc k)) (nth segment-durations k))
                  acc' (+ acc (nth segment-durations k))]
              [(conj segs seg) (conj cum acc') acc']))
          [[] [0.0] 0.0]
          (range (dec n)))]
    {:kind :waypoint :segments segments :cum-t cum-t :dof dof}))

(defmethod duration :waypoint [t] (last (:cum-t t)))
(defmethod dof :waypoint [t] (:dof t))
(defmethod sample :waypoint [{:keys [segments cum-t] :as traj} t]
  (let [dur (duration traj)
        t (max 0.0 (min dur t))
        seg-idx (or (first (keep-indexed (fn [k _] (when (<= t (nth cum-t (inc k))) k)) segments))
                    (dec (count segments)))
        t-local (- t (nth cum-t seg-idx))]
    (sample (nth segments seg-idx) t-local)))
