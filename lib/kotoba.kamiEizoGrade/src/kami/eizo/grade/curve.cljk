(ns kami.eizo.grade.curve
  "Per-channel tone curves: control points evaluated with monotone cubic
   Hermite interpolation (Fritsch-Carlson tangent limiting), the same
   family of interpolant used by real grading tools' curve widgets so
   that monotonic control-point data never produces overshoot/undershoot
   between points (plain Catmull-Rom does not give that guarantee; plain
   linear does but looks faceted — monotone Hermite gets both smoothness
   and the guarantee)."
  (:require [kami.eizo.grade.mathutil :as m]))

(defn curve
  "`points` is a seq of [x y] pairs, x in ascending order (not enforced
   here structurally, but `sorted?` below checks it). Returns a curve
   value that pre-computes Fritsch-Carlson tangents once."
  [points]
  (let [pts (vec (sort-by first points))
        n (count pts)
        xs (mapv first pts)
        ys (mapv second pts)]
    {:kami.eizo.grade/type :curve
     :points pts
     :tangents (when (>= n 2)
                 (let [secants (mapv (fn [i]
                                        (let [dx (- (xs (inc i)) (xs i))]
                                          (if (zero? dx) 0.0 (/ (- (ys (inc i)) (ys i)) dx))))
                                      (range (dec n)))
                       raw-m (mapv (fn [i]
                                     (cond
                                       (zero? i) (secants 0)
                                       (= i (dec n)) (secants (dec (count secants)))
                                       :else (/ (+ (secants (dec i)) (secants i)) 2.0)))
                                   (range n))]
                   ;; Fritsch-Carlson monotonicity limiting over each secant interval
                   (loop [i 0 m raw-m]
                     (if (>= i (count secants))
                       m
                       (let [s (secants i)]
                         (if (zero? s)
                           (recur (inc i) (assoc m i 0.0 (inc i) 0.0))
                           (let [a (/ (m i) s)
                                 b (/ (m (inc i)) s)
                                 a (if (neg? a) 0.0 a)
                                 b (if (neg? b) 0.0 b)
                                 mag2 (+ (* a a) (* b b))]
                             (if (> mag2 9.0)
                               (let [t (/ 3.0 (m/sqrt mag2))]
                                 (recur (inc i) (assoc m i (* t a s) (inc i) (* t b s))))
                               (recur (inc i) (assoc m i (* a s) (inc i) (* b s)))))))))))}))

(defn- clamp01 [x] (max 0.0 (min 1.0 (double x))))

(defn eval-curve
  "Evaluate the curve at `x`. Values outside the control-point range clamp
   to the nearest endpoint's y (flat extrapolation, matching standard NLE
   curve-widget behavior)."
  [{:keys [points tangents]} x]
  (let [n (count points)]
    (cond
      (zero? n) x
      (= n 1) (second (points 0))
      (<= x (first (points 0))) (second (points 0))
      (>= x (first (points (dec n)))) (second (points (dec n)))
      :else
      (let [i (loop [i 0]
                (if (>= x (first (points (inc i)))) (recur (inc i)) i))
            [x0 y0] (points i) [x1 y1] (points (inc i))
            m0 (tangents i) m1 (tangents (inc i))
            dx (- x1 x0)
            t (if (zero? dx) 0.0 (/ (- x x0) dx))
            t2 (* t t) t3 (* t2 t)
            h00 (+ (* 2 t3) (* -3 t2) 1)
            h10 (+ t3 (* -2 t2) t)
            h01 (+ (* -2 t3) (* 3 t2))
            h11 (- t3 t2)]
        (clamp01 (+ (* h00 y0) (* h10 dx m0) (* h01 y1) (* h11 dx m1)))))))
