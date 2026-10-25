(ns brep.polygon
  "Portable planar polygon triangulation shared by STEP, IFC, BREP and CAD.
  Supports concave outer rings and multiple non-touching inner rings."
  (:require [brep.config :as config]))

(defn- cross [[ax ay] [bx by] [cx cy]]
  (- (* (- bx ax) (- cy ay)) (* (- by ay) (- cx ax))))

(defn- signed-area [points]
  (/ (reduce + (map (fn [[[ax ay] [bx by]]] (- (* ax by) (* bx ay)))
                    (partition 2 1 (conj (vec points) (first points))))) 2.0))

(defn- oriented [vertices project ccw?]
  (let [area (signed-area (mapv project vertices))]
    (if (= ccw? (pos? area)) (vec vertices) (vec (reverse vertices)))))

(defn- point-in-triangle? [p a b c]
  (let [c1 (cross a b p) c2 (cross b c p) c3 (cross c a p)
        epsilon config/epsilon-point-merge]
    (and (>= c1 (- epsilon)) (>= c2 (- epsilon)) (>= c3 (- epsilon)))))

(defn- point-in-polygon? [[x y] points]
  (let [edges (partition 2 1 (conj (vec points) (first points)))
        crossings (filter true?
                          (map (fn [[[ax ay] [bx by]]]
                                 (and (not= (> ay y) (> by y))
                                      (< x (+ ax (* (/ (- y ay) (- by ay)) (- bx ax))))))
                               edges))]
    (odd? (count crossings))))

(defn- orientation [a b c]
  (let [value (cross a b c) epsilon config/epsilon-point-merge]
    (cond (> value epsilon) 1 (< value (- epsilon)) -1 :else 0)))

(defn- proper-intersection? [a b c d]
  (and (not= (orientation a b c) (orientation a b d))
       (not= (orientation c d a) (orientation c d b))))

(defn- visible-bridge? [outer holes project outer-index hole hole-index]
  (let [a (project (nth outer outer-index)) b (project (nth hole hole-index))
        midpoint (mapv #(/ % 2.0) (mapv + a b))
        outer-points (mapv project outer)
        hole-points (mapv #(mapv project %) holes)
        crosses-ring?
        (fn [ring ignored-index]
          (let [points (mapv project ring) n (count points)]
            (some (fn [i]
                    (when-not (or (= i ignored-index) (= (mod (inc i) n) ignored-index))
                      (proper-intersection? a b (nth points i) (nth points (mod (inc i) n)))))
                  (range n))))]
    (and (point-in-polygon? midpoint outer-points)
         (not-any? #(point-in-polygon? midpoint %) hole-points)
         (not (crosses-ring? outer outer-index))
         (not (crosses-ring? hole hole-index))
         (not-any? #(crosses-ring? % -1) (remove #{hole} holes)))))

(defn- bridge-hole [outer holes hole project]
  (let [hole-index (first (sort-by (fn [i]
                                     (let [[x y] (project (nth hole i))] [(- x) y]))
                                   (range (count hole))))
        hp (project (nth hole hole-index))
        candidates (filter #(visible-bridge? outer holes project % hole hole-index)
                           (range (count outer)))
        outer-index (first (sort-by (fn [i]
                                      (let [op (project (nth outer i)) delta (mapv - op hp)]
                                        (reduce + (map #(* % %) delta))))
                                    candidates))]
    (if (nil? outer-index)
      outer
      (let [hole-cycle (mapv #(nth hole (mod (+ hole-index %) (count hole)))
                             (range (count hole)))
            ov (nth outer outer-index) hv (nth hole hole-index)]
        (vec (concat (subvec outer 0 (inc outer-index))
                     hole-cycle [hv ov] (subvec outer (inc outer-index))))))))

(defn- ear-indices [vertices project]
  (let [points (mapv project vertices) n (count points)]
    (loop [ring (vec (range n)) triangles [] guard (* n n)]
      (cond
        (= 3 (count ring)) (into triangles ring)
        (or (< (count ring) 3) (zero? guard)) triangles
        :else
        (if-let [[ring-index a b c]
                 (first
                  (keep (fn [i]
                          (let [rn (count ring)
                                ia (nth ring (mod (dec i) rn)) ib (nth ring i)
                                ic (nth ring (mod (inc i) rn))
                                pa (nth points ia) pb (nth points ib) pc (nth points ic)]
                            (when (> (cross pa pb pc) config/epsilon-point-merge)
                              (when-not
                               (some (fn [candidate]
                                       (let [p (nth points candidate)]
                                         (and (not (#{ia ib ic} candidate))
                                              (not (#{pa pb pc} p))
                                              (point-in-triangle? p pa pb pc))))
                                     ring)
                               [i ia ib ic]))))
                        (range (count ring))))]
          (recur (into (subvec ring 0 ring-index) (subvec ring (inc ring-index)))
                 (into triangles [a b c]) (dec guard))
          triangles)))))

(defn triangulate-rings
  "Triangulate `[outer & holes]`. `project` maps each vertex to planar `[x y]`.
  Returns vertices (including bridge duplicates) and flat triangle indices."
  ([rings] (triangulate-rings rings identity))
  ([rings project]
   (if (or (empty? rings) (< (count (first rings)) 3))
     {:vertices [] :indices []}
     (let [outer (oriented (first rings) project true)
           holes (mapv #(oriented % project false) (rest rings))
           bridged (reduce (fn [polygon hole] (bridge-hole polygon holes hole project))
                           outer holes)]
       {:vertices bridged :indices (vec (ear-indices bridged project))}))))
