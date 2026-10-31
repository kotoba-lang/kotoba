(ns kami.eizo.compositor.roto
  "Roto/mask data model: an ordered polygon (vector of [x y] points,
  straight edges only in v0 — bezier handles are a documented future
  extension, not implemented here) plus a point-in-polygon test.

  point-in-polygon? uses the standard ray-casting algorithm (cast a
  ray from the point to +infinity along x and count edge crossings;
  odd count = inside) so it is correct for non-convex polygons, not
  just convex ones.")

(defn point-in-polygon?
  "True if [x y] is inside `polygon` (a vector of [x y] points,
  implicitly closed — the edge from the last point back to the first
  is included). Ray-casting algorithm."
  [polygon [x y]]
  (let [n (count polygon)]
    (loop [i 0 j (dec n) inside? false]
      (if (>= i n)
        inside?
        (let [[xi yi] (nth polygon i)
              [xj yj] (nth polygon j)
              crosses? (and (not= (> yi y) (> yj y))
                            (< x (+ xi (* (/ (- xj xi) (- yj yi)) (- y yi)))))]
          (recur (inc i) i (if crosses? (not inside?) inside?)))))))

(defn make-polygon
  "Constructs a polygon from a sequence of [x y] points. Requires at
  least 3 points; returns nil otherwise (caller should treat nil as
  invalid, mirroring the shape-validating-constructor convention used
  by kami-ongaku-notation/kami-ongaku-project)."
  [points]
  (when (>= (count points) 3)
    (vec points)))
