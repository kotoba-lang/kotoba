(ns pathfind
  "KAMI Pathfind — A* grid pathfinding (for tilemaps) + NavMesh point
  location (for open 3D worlds). Designed for NPC navigation in
  kami-game. Restored from the legacy kami-engine/kami-pathfind Rust
  crate (deleted in kotoba-lang/kami-engine PR #82 'Remove Rust
  workspace from kami-engine') as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. A
  grid position is `[x y]`. A cost grid is a vector-of-vectors
  `grid[y][x]`, 0 = wall, 1-255 = traversal cost.")

(defn grid-pos [x y] [x y])

(defn- heuristic
  "Octile distance heuristic (matches diagonal move cost 14, orthogonal 10)."
  [[ax ay] [bx by]]
  (let [dx (Math/abs (- ax bx)) dy (Math/abs (- ay by))
        mn (min dx dy) mx (max dx dy)]
    (+ (* 14 mn) (* 10 (- mx mn)))))

(def ^:private directions
  [[-1 0] [1 0] [0 -1] [0 1] [-1 -1] [1 -1] [-1 1] [1 1]])

(defn- reconstruct [came-from start goal]
  (loop [path (list goal) current goal]
    (if (= current start)
      (vec path)
      (let [prev (get came-from current)]
        (recur (conj path prev) prev)))))

(defn astar-grid
  "A* pathfinding on a 2D `grid` (`grid[y][x]`, 0 = wall) from `start` to
  `goal` (both `[x y]`). Returns the path as a vector of `[x y]`
  positions (inclusive of start/goal), or nil if unreachable."
  [grid start goal]
  (let [h (count grid)
        w (if (pos? h) (count (first grid)) 0)]
    (if (zero? w)
      nil
      (loop [open [{:pos start :g 0 :f (heuristic start goal)}]
             g-score {start 0}
             came-from {}
             closed #{}]
        (if (empty? open)
          nil
          (let [min-idx (reduce (fn [best i] (if (< (:f (nth open i)) (:f (nth open best))) i best))
                                 0 (range 1 (count open)))
                current (nth open min-idx)
                open (into (subvec open 0 min-idx) (subvec open (inc min-idx)))]
            (cond
              (= (:pos current) goal)
              (reconstruct came-from start goal)

              (closed (:pos current))
              (recur open g-score came-from closed)

              :else
              (let [closed (conj closed (:pos current))
                    [cx cy] (:pos current)
                    [open g-score came-from]
                    (reduce
                     (fn [[open g-score came-from] [dx dy]]
                       (let [nx (+ cx dx) ny (+ cy dy)]
                         (if (or (< nx 0) (< ny 0) (>= nx w) (>= ny h))
                           [open g-score came-from]
                           (let [np [nx ny]]
                             (if (closed np)
                               [open g-score came-from]
                               (let [cost (long (nth (nth grid ny) nx))]
                                 (if (zero? cost)
                                   [open g-score came-from]
                                   (let [move-cost (* (if (and (not= dx 0) (not= dy 0)) 14 10) cost)
                                         ng (+ (:g current) move-cost)]
                                     (if (< ng (get g-score np #?(:clj Long/MAX_VALUE :cljs js/Number.MAX_SAFE_INTEGER)))
                                       [(conj open {:pos np :g ng :f (+ ng (heuristic np goal))})
                                        (assoc g-score np ng)
                                        (assoc came-from np (:pos current))]
                                       [open g-score came-from])))))))))
                     [open g-score came-from]
                     directions)]
                (recur open g-score came-from closed)))))))))

;; ── NavMesh ──────────────────────────────────────

(defn nav-triangle [vertices neighbors center cost]
  {:vertices vertices :neighbors neighbors :center center :cost cost})

(defn nav-mesh
  "A fresh, empty NavMesh."
  []
  {:triangles []})

(defn add-triangle [mesh tri] (update mesh :triangles conj tri))

(defn- sign [[p1x p1y] [p2x p2y] [p3x p3y]]
  (- (* (- p1x p3x) (- p2y p3y)) (* (- p2x p3x) (- p1y p3y))))

(defn- point-in-triangle? [p [v0 v1 v2]]
  (let [d1 (sign p v0 v1) d2 (sign p v1 v2) d3 (sign p v2 v0)
        neg (or (< d1 0.0) (< d2 0.0) (< d3 0.0))
        pos (or (> d1 0.0) (> d2 0.0) (> d3 0.0))]
    (not (and neg pos))))

(defn locate
  "Index of the triangle in `mesh` containing point `p` (`[x y]`), or
  nil if none."
  [mesh p]
  (let [tris (:triangles mesh)
        n (count tris)]
    (loop [i 0]
      (cond
        (= i n) nil
        (point-in-triangle? p (:vertices (nth tris i))) i
        :else (recur (inc i))))))
