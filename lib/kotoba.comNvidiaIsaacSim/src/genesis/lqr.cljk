(ns genesis.lqr
  "Linear Quadratic Regulator (LQR) controller for the Cartpole around its
  upright equilibrium (theta = 0).

  Build pipeline:
    1. Finite-difference the nonlinear Cartpole `genesis.cartpole/step`
       formula at the origin state to recover the discrete-time
       linearisation matrices A (4x4) and B (4x1).
    2. Solve the Discrete Algebraic Riccati Equation (DARE) by fixed-point
       iteration.
    3. Optimal state-feedback gain K = (R + B^T P B)^-1 B^T P A.
    4. Control law: u(s) = -K . (s - s_target), clamped to +/-max-effort.

  Restored from kotoba-lang/kami-engine `kami-genesis/src/lqr.rs`
  (deleted PR #82) as zero-dependency portable CLJC. Per ADR-2607010930.
  Ported 1:1 (fully portable pure math)."
  (:require [genesis.cartpole :as cartpole]))

(defn default-weights []
  {:q-diag [1.0 0.1 100.0 1.0] :r 0.1})

(defn clamp [v lo hi] (max lo (min hi v)))

;; 4-vectors and 4x4 matrices as plain Clojure vectors (row-major).

(defn- state->arr [{:keys [x x-dot theta theta-dot]}] [x x-dot theta theta-dot])
(defn- arr->state [[x x-dot theta theta-dot]] {:x x :x-dot x-dot :theta theta :theta-dot theta-dot})

(defn- mat4-mul [x y]
  (vec (for [i (range 4)] (vec (for [j (range 4)]
                                  (reduce + (for [k (range 4)] (* (get-in x [i k]) (get-in y [k j])))))))))
(defn- mat4-transpose [x] (vec (for [j (range 4)] (vec (for [i (range 4)] (get-in x [i j]))))))
(defn- mat4-diag [d] (vec (for [i (range 4)] (vec (for [j (range 4)] (if (= i j) (nth d i) 0.0))))))
(defn- mat4-add [x y] (vec (map (fn [r1 r2] (vec (map + r1 r2))) x y)))
(defn- mat4-sub [x y] (vec (map (fn [r1 r2] (vec (map - r1 r2))) x y)))
(defn- mat4-max-abs [x] (reduce max (map #(reduce max (map (fn [v] (Math/abs v)) %)) x)))
(defn- outer4 [b c] (vec (for [i (range 4)] (vec (for [j (range 4)] (* (nth b i) (nth c j)))))))
(defn- rowmat4 [r m] (vec (for [j (range 4)] (reduce + (for [k (range 4)] (* (nth r k) (get-in m [k j])))))))
(defn- matcol4 [m c] (vec (for [i (range 4)] (reduce + (for [k (range 4)] (* (get-in m [i k]) (nth c k)))))))
(defn- dot4 [a b] (reduce + (map * a b)))

(defn- linearize-cartpole [cfg eps]
  (let [s0 (cartpole/default-state)
        step-one (fn [s action] (cartpole/step s action cfg))
        a (vec (for [j (range 4)]
                 (let [s0-arr (state->arr s0)
                       s-plus (assoc s0-arr j (+ (nth s0-arr j) eps))
                       s-minus (assoc s0-arr j (- (nth s0-arr j) eps))
                       n-p (state->arr (step-one (arr->state s-plus) 0.0))
                       n-m (state->arr (step-one (arr->state s-minus) 0.0))]
                   (mapv (fn [np nm] (/ (- np nm) (* 2.0 eps))) n-p n-m))))
        ;; a is currently column-major (a[j] = column j); transpose to rows.
        a-rows (vec (for [i (range 4)] (vec (for [j (range 4)] (get-in a [j i])))))
        n-plus (state->arr (step-one s0 eps))
        n-minus (state->arr (step-one s0 (- eps)))
        b (mapv (fn [np nm] (/ (- np nm) (* 2.0 eps))) n-plus n-minus)]
    [a-rows b]))

(defn- solve-dare [a b {:keys [q-diag r]} tol max-iters]
  (let [q (mat4-diag q-diag)
        a-t (mat4-transpose a)]
    (loop [p q iters 0]
      (if (>= iters max-iters)
        [p iters ##Inf]
        (let [pa (mat4-mul p a)
              pb (matcol4 p b)
              btpa (rowmat4 b pa)
              btpb (dot4 b pb)
              scalar-inv (/ 1.0 (+ r btpb))
              outer-scaled (vec (map (fn [row] (mapv #(* % scalar-inv) row)) (outer4 pb btpa)))
              atpa (mat4-mul a-t pa)
              atpb-outer (mat4-mul a-t outer-scaled)
              p-new (mat4-add q (mat4-sub atpa atpb-outer))
              delta (mat4-max-abs (mat4-sub p-new p))]
          (if (< delta tol)
            [p-new (inc iters) delta]
            (recur p-new (inc iters))))))))

(defn- compute-gain [a b p r]
  (let [pa (mat4-mul p a)
        pb (matcol4 p b)
        btpa (rowmat4 b pa)
        btpb (dot4 b pb)
        scalar-inv (/ 1.0 (+ r btpb))]
    (mapv #(* scalar-inv %) btpa)))

(defn build
  "Build an LQR controller for the given cartpole config + weights."
  [cfg weights]
  (let [[a b] (linearize-cartpole cfg 1e-3)
        [p iters residual] (solve-dare a b weights 1e-6 1000)
        gain (compute-gain a b p (:r weights))]
    {:gain gain :max-effort (:force-mag cfg) :dare-iters iters :dare-residual residual}))

(defn control
  "Compute control input u = clamp(-K . s, +/-max-effort)."
  [{:keys [gain max-effort]} s]
  (let [s-vec (state->arr s)
        u (- (reduce + (map * gain s-vec)))]
    (clamp u (- max-effort) max-effort)))
