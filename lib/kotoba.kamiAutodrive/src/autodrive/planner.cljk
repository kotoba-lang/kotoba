(ns autodrive.planner
  "Global path planning: A* over the inflated occupancy grid, returned as a
  world-coordinate polyline.

  Restored from the deleted `kami-autodrive` Rust crate
  (kotoba-lang/kami-engine, PR #82), ADR-2607010930.

  The original crate called out to `kami-pathfind::astar_grid`. A* itself is
  portable pure logic (grid search, no hardware coupling), so it is ported
  inline here (`astar-grid`) rather than excluded, keeping the crate
  zero-dependency."
  (:require [autodrive.geom :as g]
            [autodrive.perception :as perc]))

;; ─────────────────────────────── A* ───────────────────────────────
;;
;; Open set is a Clojure `sorted-set` of `[f-score node]` pairs — a plain,
;; portable priority-queue substitute (no platform-specific interop), so this
;; runs identically on the JVM and in ClojureScript.

(defn- heuristic [[ax ay] [bx by]]
  ;; Octile distance — admissible for 8-connected grid movement.
  (let [dx (Math/abs (- ax bx)) dy (Math/abs (- ay by))]
    (+ (max dx dy) (* (- (Math/sqrt 2.0) 1.0) (min dx dy)))))

(def ^:private neighbor-offsets
  (for [dy [-1 0 1] dx [-1 0 1] :when (not (and (zero? dx) (zero? dy)))]
    [dx dy]))

(defn astar-grid
  "A* search over `cost-grid` (`[y][x]`, `0` = wall, `>0` = traversable cost)
  from `start` to `goal` (each `[x y]`). Returns a vector of `[x y]` cells
  from `start` to `goal` inclusive, or nil if unreachable."
  [cost-grid start goal]
  (let [h (count cost-grid)
        w (if (pos? h) (count (first cost-grid)) 0)
        walkable? (fn [[x y]]
                    (and (>= x 0) (>= y 0) (< x w) (< y h)
                         (pos? (nth (nth cost-grid y) x))))]
    (when (and (walkable? start) (walkable? goal))
      (loop [open (sorted-set [(heuristic start goal) start])
             g-score {start 0.0}
             came-from {}]
        (if (empty? open)
          nil
          (let [[_ current] (first open)
                open (disj open (first open))]
            (if (= current goal)
              (loop [c current path (list c)]
                (if-let [p (came-from c)]
                  (recur p (cons p path))
                  (vec path)))
              (let [[cx cy] current
                    nbrs (for [[dx dy] neighbor-offsets
                               :let [nx (+ cx dx) ny (+ cy dy)]
                               :when (walkable? [nx ny])
                               ;; Disallow cutting a diagonal between two
                               ;; orthogonal walls.
                               :when (or (zero? dx) (zero? dy)
                                         (and (walkable? [(+ cx dx) cy])
                                              (walkable? [cx (+ cy dy)])))]
                           [nx ny])
                    step-cost (fn [[nx ny]]
                                (let [diag? (and (not= cx nx) (not= cy ny))]
                                  (* (if diag? (Math/sqrt 2.0) 1.0) (nth (nth cost-grid ny) nx))))
                    [g-score' came-from' open']
                    (reduce
                     (fn [[gs cf op] n]
                       (let [tentative (+ (get gs current) (step-cost n))]
                         (if (< tentative (get gs n ##Inf))
                           [(assoc gs n tentative) (assoc cf n current)
                            (conj op [(+ tentative (heuristic n goal)) n])]
                           [gs cf op])))
                     [g-score came-from open]
                     nbrs)]
                (recur open' g-score' came-from')))))))))

;; ─────────────────────────────── Planning ───────────────────────────────

(defn- segment-clear
  "Sample the segment `a..b` at sub-cell spacing; clear iff no sample lands on
  an occupied cell. Thin alias over `autodrive.perception/line-clear?`."
  [a b grid]
  (perc/line-clear? grid a b))

(defn- simplify
  "Line-of-sight shortcutting: greedily drop intermediate waypoints whose
  removal keeps the segment collision-free. Produces a sparse, drivable path."
  [pts grid]
  (if (<= (count pts) 2)
    (vec pts)
    (let [pts (vec pts)]
      (loop [out [(pts 0)] anchor 0 i 1]
        (if (>= i (count pts))
          out
          (if (or (= i (dec (count pts))) (not (segment-clear (pts anchor) (pts (inc i)) grid)))
            (recur (conj out (pts i)) i (inc i))
            (recur out anchor (inc i))))))))

(defn- smooth
  "Chaikin corner-cutting to round the sharp grid/LOS corners for smoother
  tracking. Each iteration is collision-validated against `grid`; if it would
  clip an obstacle the previous (safe) version is kept, so the result is
  never less safe than the input."
  [path grid iters]
  (loop [cur (vec path) i 0]
    (if (or (>= i iters) (< (count cur) 3))
      cur
      (let [next (loop [acc [(cur 0)] w 0]
                   (if (>= (inc w) (count cur))
                     (conj acc (peek cur))
                     (let [a (cur w) b (cur (inc w))]
                       (recur (conj acc (g/lerp2 a b 0.25) (g/lerp2 a b 0.75)) (inc w)))))]
        (if (every? (fn [[a b]] (segment-clear a b grid))
                     (map vector next (rest next)))
          (recur next (inc i))
          cur)))))

(defn plan
  "Plan a collision-free path from `start` to `goal` over `grid`.

  `grid` should already be configuration-space inflated (see
  `autodrive.perception/inflated`). Start/goal are snapped to the nearest
  free cell. Returns world-frame waypoints (cell centres), line-of-sight
  simplified, or nil if no path exists."
  [grid start goal]
  (when-let [s (perc/nearest-free grid start)]
    (when-let [gg (perc/nearest-free grid goal)]
      (let [cost (perc/to-cost-grid grid)]
        (when-let [cells (astar-grid cost s gg)]
          (let [pts (mapv (fn [[x y]] (perc/cell->world grid x y)) cells)]
            (smooth (simplify pts grid) grid 2)))))))
