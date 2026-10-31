(ns cae.nonlinear
  "Browser-portable extensions: tabulated material data and a contact FEM kernel."
  (:require [cae.solver :as solver]))

(defn- interp [table x]
  (let [rows (sort-by first table) x (double x)]
    (cond (<= x (ffirst rows)) (second (first rows))
          (>= x (first (last rows))) (second (last rows))
          :else (let [[[x0 y0] [x1 y1]] (first (filter (fn [[[a] [b]]] (<= a x b)) (partition 2 1 rows)))]
                  (+ y0 (* (/ (- x x0) (- x1 x0)) (- y1 y0)))))))

(defmethod solver/solve :material-table [{:keys [temperature-K properties query-temperature-K]}]
  (when-not (seq temperature-K) (throw (ex-info "temperature-K table is required" {})))
  (let [q (double (or query-temperature-K (first temperature-K)))]
   {:solver :material-table :temperature-K q
   :properties (into {} (for [[k table] properties] [k (interp table q)]))
   :fidelity :tabulated-reference :status :screening-only}))

(defmethod solver/solve :nonlinear-contact [{:keys [force-N area-m2 thickness-m youngs-modulus-Pa contact-stiffness-N-m max-iterations tolerance-m]}]
  (let [f (double force-N) a (double area-m2) t (double thickness-m) e (double youngs-modulus-Pa) k (double contact-stiffness-N-m) it (long (or max-iterations 50)) tol (double (or tolerance-m 1e-9))
        ;; penalty contact: displacement is solved by Newton iteration for F = k*max(u-gap,0)+EAu/t
        ea (/ (* e a) t) u (loop [u (/ f (+ ea k)) n 0] (let [r (- (* ea u) (* k (max u 0.0)) f) d (+ ea (if (pos? u) k 0.0)) next (- u (/ r d))] (if (or (< (Math/abs r) (* tol (max 1.0 f))) (>= n it)) next (recur next (inc n)))))]
    {:solver :nonlinear-contact :displacement-m u :contact-force-N (* k (max u 0.0)) :stress-Pa (* e (/ u t)) :iterations it :converged? (< (Math/abs (- (* ea u) (* k (max u 0.0)) f)) (* tol (max 1.0 f))) :fidelity :nonlinear-reference :status :screening-only}))
