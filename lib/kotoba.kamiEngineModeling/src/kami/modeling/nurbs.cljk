(ns kami.modeling.nurbs
  "Portable validated NURBS curve/surface evaluation and tessellation. The
  values are exact-authoring contracts; tessellation is a derived mesh."
  (:require [kami.modeling :as modeling]))

(defn- finite-number? [x]
  (and (number? x) #?(:clj (Double/isFinite (double x)) :cljs (js/Number.isFinite x))))
(defn- nondecreasing? [xs] (every? (fn [[a b]] (<= a b)) (partition 2 1 xs)))

(defn curve
  [{:keys [degree knots control-points weights] :as spec}]
  (let [n (count control-points) weights (or weights (vec (repeat n 1.0)))]
    (when-not (and (integer? degree) (pos? degree) (> n degree)
                   (= (count knots) (+ n degree 1)) (= n (count weights))
                   (every? #(and (= 3 (count %)) (every? finite-number? %)) control-points)
                   (every? #(and (finite-number? %) (pos? %)) weights)
                   (every? finite-number? knots) (nondecreasing? knots)
                   (< (nth knots degree) (nth knots n)))
      (throw (ex-info "invalid NURBS curve" {:spec spec})))
    {:nurbs/kind :curve :nurbs/degree degree :nurbs/knots (vec knots)
     :nurbs/control-points (mapv vec control-points) :nurbs/weights (vec weights)
     :nurbs/domain [(nth knots degree) (nth knots n)]}))

(defn- basis [i degree knots u last-index]
  (if (zero? degree)
    (if (or (and (<= (nth knots i) u) (< u (nth knots (inc i))))
            (and (= u (last knots)) (= i last-index))) 1.0 0.0)
    (let [left-den (- (nth knots (+ i degree)) (nth knots i))
          right-den (- (nth knots (+ i degree 1)) (nth knots (inc i)))
          left (if (zero? left-den) 0.0 (* (/ (- u (nth knots i)) left-den)
                                           (basis i (dec degree) knots u last-index)))
          right (if (zero? right-den) 0.0 (* (/ (- (nth knots (+ i degree 1)) u) right-den)
                                             (basis (inc i) (dec degree) knots u last-index)))]
      (+ left right))))

(defn evaluate-curve [{:nurbs/keys [degree knots control-points weights domain] :as c} u]
  (when-not (= :curve (:nurbs/kind c)) (throw (ex-info "expected NURBS curve" {})))
  (when-not (and (finite-number? u) (<= (first domain) u (second domain)))
    (throw (ex-info "parameter outside curve domain" {:u u :domain domain})))
  (let [last-index (dec (count control-points))
        weighted (mapv (fn [i]
                         (* (nth weights i) (basis i degree knots u last-index)))
                       (range (count control-points)))
        denominator (reduce + weighted)]
    (when (zero? denominator) (throw (ex-info "zero rational basis denominator" {:u u})))
    (mapv (fn [axis]
            (/ (reduce + (map-indexed (fn [i point] (* (nth weighted i) (nth point axis))) control-points))
               denominator)) (range 3))))

(defn surface [{:keys [u-degree v-degree u-knots v-knots control-net weights] :as spec}]
  (let [rows (count control-net) columns (count (first control-net))
        weights (or weights (mapv (fn [_] (vec (repeat columns 1.0))) (range rows)))]
    (when-not (and (pos? rows) (pos? columns) (every? #(= columns (count %)) control-net)
                   (= rows (count weights)) (every? #(= columns (count %)) weights))
      (throw (ex-info "invalid rectangular NURBS control net" {:spec spec})))
    ;; Validate each parametric direction through the curve constructor.
    (curve {:degree u-degree :knots u-knots :control-points (first control-net) :weights (first weights)})
    (curve {:degree v-degree :knots v-knots :control-points (mapv first control-net) :weights (mapv first weights)})
    {:nurbs/kind :surface :nurbs/u-degree u-degree :nurbs/v-degree v-degree
     :nurbs/u-knots (vec u-knots) :nurbs/v-knots (vec v-knots)
     :nurbs/control-net (mapv #(mapv vec %) control-net) :nurbs/weights (mapv vec weights)
     :nurbs/u-domain [(nth u-knots u-degree) (nth u-knots columns)]
     :nurbs/v-domain [(nth v-knots v-degree) (nth v-knots rows)]}))

(defn evaluate-surface [{:nurbs/keys [u-degree v-degree u-knots v-knots control-net weights
                                      u-domain v-domain] :as s} u v]
  (when-not (= :surface (:nurbs/kind s)) (throw (ex-info "expected NURBS surface" {})))
  (when-not (and (<= (first u-domain) u (second u-domain))
                 (<= (first v-domain) v (second v-domain)))
    (throw (ex-info "parameter outside surface domain" {:u u :v v})))
  (let [rows (count control-net) columns (count (first control-net))
        terms (for [j (range rows) i (range columns)]
                (let [b (* (basis i u-degree u-knots u (dec columns))
                           (basis j v-degree v-knots v (dec rows))
                           (get-in weights [j i]))]
                  [b (get-in control-net [j i])]))
        denominator (reduce + (map first terms))]
    (when (zero? denominator) (throw (ex-info "zero rational surface denominator" {:u u :v v})))
    (mapv (fn [axis] (/ (reduce + (map (fn [[b p]] (* b (nth p axis))) terms)) denominator)) (range 3))))

(defn tessellate-surface [s u-segments v-segments]
  (when-not (and (integer? u-segments) (integer? v-segments) (pos? u-segments) (pos? v-segments))
    (throw (ex-info "surface segment counts must be positive" {})))
  (let [[u0 u1] (:nurbs/u-domain s) [v0 v1] (:nurbs/v-domain s)
        point (fn [j i] (evaluate-surface s (+ u0 (* (/ i u-segments) (- u1 u0)))
                                           (+ v0 (* (/ j v-segments) (- v1 v0)))))
        vertices (vec (for [j (range (inc v-segments)) i (range (inc u-segments))] (point j i)))
        index (fn [j i] (+ i (* j (inc u-segments))))
        faces (vec (for [j (range v-segments) i (range u-segments)]
                     [(index j i) (index j (inc i)) (index (inc j) (inc i)) (index (inc j) i)]))]
    (assoc (modeling/mesh vertices faces) :mesh/source {:kind :nurbs-surface
                                                        :u-segments u-segments :v-segments v-segments})))

(defn trim-loop
  "Closed polygonal loop in surface parameter space. Curved p-curves can be
  adaptively sampled into this canonical portable representation."
  [id points orientation]
  (when-not (and (uuid? id) (<= 3 (count points))
                 (every? #(and (vector? %) (= 2 (count %)) (every? number? %)) points)
                 (#{:outer :inner} orientation))
    (throw (ex-info "invalid NURBS trim loop" {:id id :orientation orientation})))
  {:trim/id id :trim/points (vec points) :trim/orientation orientation})

(defn trimmed-surface [surface outer-loop inner-loops]
  (when-not (and (= :surface (:nurbs/kind surface)) (= :outer (:trim/orientation outer-loop))
                 (every? #(= :inner (:trim/orientation %)) inner-loops))
    (throw (ex-info "trimmed surface requires one outer and zero-or-more inner loops" {})))
  {:nurbs/kind :trimmed-surface :trim/surface surface :trim/outer outer-loop :trim/inner (vec inner-loops)})

(defn- point-on-segment? [[px py] [ax ay] [bx by] tolerance]
  (let [cross (- (* (- px ax) (- by ay)) (* (- py ay) (- bx ax)))
        dot-product (+ (* (- px ax) (- bx ax)) (* (- py ay) (- by ay)))
        length2 (+ (* (- bx ax) (- bx ax)) (* (- by ay) (- by ay)))]
    (and (<= (#?(:clj Math/abs :cljs js/Math.abs) cross) tolerance)
         (<= (- tolerance) dot-product (+ length2 tolerance)))))

(defn point-in-trim?
  ([loop point] (point-in-trim? loop point 1.0e-9))
  ([{:trim/keys [points]} [x y :as point] tolerance]
   (let [segments (map vector points (concat (rest points) [(first points)]))
         crosses? (fn [[[xi yi] [xj yj]]]
                    (and (not= (> yi y) (> yj y))
                         (< x (+ xi (/ (* (- xj xi) (- y yi)) (- yj yi))))))]
     (if (some (fn [[a b]] (point-on-segment? point a b tolerance)) segments)
       true
       (odd? (count (filter crosses? segments)))))))

(defn inside-trim? [{:trim/keys [outer inner]} uv]
  (and (point-in-trim? outer uv) (not-any? #(point-in-trim? % uv) inner)))

(defn tessellate-trimmed-surface [trimmed u-segments v-segments]
  (when-not (= :trimmed-surface (:nurbs/kind trimmed))
    (throw (ex-info "expected trimmed NURBS surface" {})))
  (let [surface (:trim/surface trimmed) [u0 u1] (:nurbs/u-domain surface) [v0 v1] (:nurbs/v-domain surface)
        uv (fn [j i] [(+ u0 (* (/ i u-segments) (- u1 u0)))
                      (+ v0 (* (/ j v-segments) (- v1 v0)))])
        vertices (vec (for [j (range (inc v-segments)) i (range (inc u-segments))]
                        (let [[u v] (uv j i)] (evaluate-surface surface u v))))
        index (fn [j i] (+ i (* j (inc u-segments))))
        cells (for [j (range v-segments) i (range u-segments)
                    :let [center-uv (mapv #(/ (+ %1 %2) 2.0) (uv j i) (uv (inc j) (inc i)))]
                    :when (inside-trim? trimmed center-uv)]
                [(index j i) (index j (inc i)) (index (inc j) (inc i)) (index (inc j) i)])]
    (assoc (modeling/mesh vertices (vec cells))
           :mesh/source {:kind :trimmed-nurbs-surface :trim/outer (get-in trimmed [:trim/outer :trim/id])
                         :trim/inner (mapv :trim/id (:trim/inner trimmed))
                         :u-segments u-segments :v-segments v-segments})))
