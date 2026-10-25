(ns genesis.ik
  "Damped-least-squares (DLS) inverse-kinematics solver.

  Iteratively computes a joint configuration `q` such that a named link
  reaches a target pose in world frame, using the planar Jacobian.

  Update rule:
      dq = J^T (J J^T + lambda^2 I)^-1 . e
      q  <- q + step-size . dq
  where `e = target - current-pose` is the 3-vector (dx, dz, dtheta_y)
  reduced to the planar plane.

  Mirrors the public API surface of
  `omni.isaac.motion_generation.LulaKinematicsSolver.compute_inverse_kinematics`
  (Isaac Sim 4.x) at the level of inputs/outputs.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/ik.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.jacobian :as jac]))

(defn default-options []
  {:tol 1e-3 :max-iters 200 :damping-lambda 0.05 :step-size 0.5 :include-orientation? false})

;; ── Forward kinematics + planar Jacobian per topology ──────────────────

(defn cartpole-pose [x theta link]
  (case link
    "world" {:x 0.0 :z 0.0 :theta-y 0.0}
    "cart" {:x x :z 0.0 :theta-y 0.0}
    "pole_link" {:x (+ x (* 0.25 (Math/sin theta))) :z (* 0.25 (Math/cos theta)) :theta-y theta}
    nil))

(defn dp-pose [q1 q2 {:keys [l1 l2]} link]
  (case link
    "world" {:x 0.0 :z 0.0 :theta-y 0.0}
    "link1" {:x (* (* l1 0.5) (Math/sin q1)) :z (- (* (* l1 0.5) (Math/cos q1))) :theta-y q1}
    "link2" {:x (+ (* l1 (Math/sin q1)) (* (* l2 0.5) (Math/sin (+ q1 q2))))
             :z (- (- (* l1 (Math/cos q1))) (* (* l2 0.5) (Math/cos (+ q1 q2))))
             :theta-y (+ q1 q2)}
    "link2_tip" {:x (+ (* l1 (Math/sin q1)) (* l2 (Math/sin (+ q1 q2))))
                 :z (- (- (* l1 (Math/cos q1))) (* l2 (Math/cos (+ q1 q2))))
                 :theta-y (+ q1 q2)}
    nil))

(defn- planar-chain-com-pose [q k {:keys [n lengths]}]
  (loop [i 0 theta-cum 0.0 pjx 0.0 pjz 0.0]
    (let [theta-cum (+ theta-cum (nth q i))]
      (if (= i k)
        (let [lc (* (nth lengths i) 0.5)]
          {:x (+ pjx (* lc (Math/sin theta-cum))) :z (- pjz (* lc (Math/cos theta-cum))) :theta-y theta-cum})
        (let [l (nth lengths i)]
          (recur (inc i) theta-cum (+ pjx (* l (Math/sin theta-cum))) (- pjz (* l (Math/cos theta-cum)))))))))

(defn- jac->planar [j]
  (let [{:keys [rows]} j n (count (first rows))]
    (vec (for [c (range n)] [(get-in rows [0 c]) (get-in rows [2 c]) (get-in rows [4 c])]))))

;; Backends: map from :pose-fn / :jac-fn / :dof

(defn- cartpole-backend [cfg link-name]
  {:link-pose (fn [q] (cartpole-pose (nth q 0) (nth q 1) link-name))
   :planar-jacobian (fn [q] (when-let [j (jac/cartpole-link-jacobian (nth q 1) link-name cfg)] (jac->planar j)))
   :dof 2})

(defn- dp-backend [cfg link-name]
  {:link-pose (fn [q] (dp-pose (nth q 0) (nth q 1) cfg link-name))
   :planar-jacobian
   (fn [q]
     (if (= link-name "link2_tip")
       (let [q1 (nth q 0) q2 (nth q 1)
             s1 (Math/sin q1) c1 (Math/cos q1)
             s12 (Math/sin (+ q1 q2)) c12 (Math/cos (+ q1 q2))
             l1 (:l1 cfg) l2 (:l2 cfg)]
         [[(+ (* l1 c1) (* l2 c12)) (+ (* l1 s1) (* l2 s12)) 1.0]
          [(* l2 c12) (* l2 s12) 1.0]])
       (when-let [j (jac/dp-link-jacobian (nth q 0) (nth q 1) link-name cfg)] (jac->planar j))))
   :dof 2})

(defn- planar-chain-backend [cfg link-index]
  {:link-pose (fn [q] (planar-chain-com-pose q link-index cfg))
   :planar-jacobian (fn [q] (when-let [j (jac/planar-chain-link-jacobian q link-index cfg)] (jac->planar j)))
   :dof (:n cfg)})

;; ── Solver core ───────────────────────────────────────────────────────────

(defn- solve-dls [jac3xn err3 lambda]
  (let [n (count jac3xn)
        a (vec (for [r (range 3)]
                 (vec (for [c (range 3)]
                        (+ (reduce + (for [k (range n)] (* (get-in jac3xn [k r]) (get-in jac3xn [k c]))))
                           (if (= r c) (* lambda lambda) 0.0))))))
        det (- (+ (* (get-in a [0 0]) (- (* (get-in a [1 1]) (get-in a [2 2])) (* (get-in a [1 2]) (get-in a [2 1]))))
                   (* (get-in a [0 2]) (- (* (get-in a [1 0]) (get-in a [2 1])) (* (get-in a [1 1]) (get-in a [2 0])))))
                (* (get-in a [0 1]) (- (* (get-in a [1 0]) (get-in a [2 2])) (* (get-in a [1 2]) (get-in a [2 0])))))]
    (if (< (Math/abs det) 1e-12)
      (vec (repeat n 0.0))
      (let [inv-det (/ 1.0 det)
            inv [[(* inv-det (- (* (get-in a [1 1]) (get-in a [2 2])) (* (get-in a [1 2]) (get-in a [2 1]))))
                  (* inv-det (- (- (* (get-in a [0 1]) (get-in a [2 2])) (* (get-in a [0 2]) (get-in a [2 1])))))
                  (* inv-det (- (* (get-in a [0 1]) (get-in a [1 2])) (* (get-in a [0 2]) (get-in a [1 1]))))]
                 [(* inv-det (- (- (* (get-in a [1 0]) (get-in a [2 2])) (* (get-in a [1 2]) (get-in a [2 0])))))
                  (* inv-det (- (* (get-in a [0 0]) (get-in a [2 2])) (* (get-in a [0 2]) (get-in a [2 0]))))
                  (* inv-det (- (- (* (get-in a [0 0]) (get-in a [1 2])) (* (get-in a [0 2]) (get-in a [1 0])))))]
                 [(* inv-det (- (* (get-in a [1 0]) (get-in a [2 1])) (* (get-in a [1 1]) (get-in a [2 0]))))
                  (* inv-det (- (- (* (get-in a [0 0]) (get-in a [2 1])) (* (get-in a [0 1]) (get-in a [2 0])))))
                  (* inv-det (- (* (get-in a [0 0]) (get-in a [1 1])) (* (get-in a [0 1]) (get-in a [1 0]))))]]
            y (vec (for [r (range 3)] (reduce + (map * (nth inv r) err3))))]
        (vec (for [k (range n)] (reduce + (map * (nth jac3xn k) y))))))))

(defn- pose-error [target current include-orientation?]
  (let [e-x (- (:x target) (:x current))
        e-z (- (:z target) (:z current))
        e-th (if include-orientation?
               (let [e (- (:theta-y target) (:theta-y current))
                     two-pi (* 2.0 Math/PI)]
                 (loop [e e]
                   (cond (> e Math/PI) (recur (- e two-pi))
                         (< e (- Math/PI)) (recur (+ e two-pi))
                         :else e)))
               0.0)]
    [e-x e-z e-th]))

(defn- norm3 [[a b c]] (Math/sqrt (+ (* a a) (* b b) (* c c))))

(defn- run-dls [{:keys [link-pose planar-jacobian]} q-init target {:keys [tol max-iters damping-lambda step-size include-orientation?]}]
  (loop [q (vec q-init) iters 0 converged? false final-err ##Inf]
    (if (>= iters max-iters)
      {:q q :converged? converged? :iters iters :final-error final-err}
      (if-let [pose (link-pose q)]
        (let [err (pose-error target pose include-orientation?)
              err-norm (norm3 err)]
          (if (< err-norm tol)
            {:q q :converged? true :iters iters :final-error err-norm}
            (if-let [jac3xn (planar-jacobian q)]
              (let [dq (solve-dls jac3xn err damping-lambda)
                    q' (vec (map (fn [qi dqi] (+ qi (* step-size dqi))) q dq))]
                (recur q' (inc iters) false err-norm))
              {:q q :converged? false :iters iters :final-error err-norm})))
        {:q q :converged? converged? :iters iters :final-error final-err}))))

;; ── Public entry points ───────────────────────────────────────────────────

(defn solve-ik-cartpole [cfg link-name q-init target opts]
  (run-dls (cartpole-backend cfg link-name) q-init target opts))

(defn solve-ik-dp [cfg link-name q-init target opts]
  (run-dls (dp-backend cfg link-name) q-init target opts))

(defn solve-ik-planar-chain [cfg link-index q-init target opts]
  (run-dls (planar-chain-backend cfg link-index) q-init target opts))
