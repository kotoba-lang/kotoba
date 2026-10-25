(ns pcb.route
  "Grid-based maze autorouting — Lee's algorithm (C. Y. Lee, \"An
  Algorithm for Path Connections and Its Applications\", IRE
  Transactions on Electronic Computers, 1961): breadth-first wave
  propagation over a grid from a source cell, tracing back the shortest
  obstacle-avoiding path once the target is reached. This is the
  textbook maze-routing algorithm every PCB autorouter historically
  started from (rip-up/reroute, channel routing, and Steiner-tree
  variants all build on it); this implements the base algorithm, not
  those refinements.

  `route-net` connects every `pcb.layout/pad` sharing one `:net-id`
  (across all placed footprints, with footprint rotation applied to pad
  positions); multi-pin nets are joined via a Manhattan-distance minimum
  spanning tree (not a true rectilinear Steiner tree — MST is the
  standard, simpler approximation), then each MST edge is maze-routed in
  turn.

  Honest scope:
  - Single-layer routing only — no via insertion to escape a fully
    boxed-in net (a real autorouter falls back to a different layer;
    this one just fails that net, see `route-all`'s `:failed`).
  - Grid-quantized, 4-connected (rectilinear) paths, not 45°/arc corner
    styles a production tool would apply as a post-process.
  - Sequential net ordering (net N's trace becomes an obstacle for net
    N+1) — not simultaneous or rip-up-and-reroute, so routing order can
    determine whether a later net finds a path at all."
  (:require [pcb.layout :as layout]))

;; ─────────────────────────── geometry helpers ───────────────────────────

(defn- deg->rad [d] (/ (* d Math/PI) 180.0))

(defn- rotate-point
  "Rotate `[x y]` by `degrees` counter-clockwise about the origin."
  [[x y] degrees]
  (let [r (deg->rad degrees)
        c (Math/cos r) s (Math/sin r)]
    [(- (* x c) (* y s)) (+ (* x s) (* y c))]))

(defn- pad-radius-mm
  "A circumscribing-circle radius for `pad`'s `:size` (the pad's own
  physical extent, not its clearance) — half the size vector's length,
  which is exact for a round pad and a (safe, slightly conservative)
  over-estimate for rect/oblong ones. `nil`/missing `:size` -> 0.0 (a
  pad with no declared footprint geometry blocks nothing beyond its
  center point plus clearance)."
  [pad]
  (if-let [[w h] (:size pad)]
    (/ (Math/sqrt (+ (* w w) (* h h))) 2.0)
    0.0))

(defn footprint-pad-positions
  "Every pad on `footprint`, as `{:net-id :absolute [x y] :radius-mm r}`
  — the pad's own `:center` rotated by the footprint's `:rotation`
  (degrees, CCW) then translated by the footprint's `[x y]`, plus its
  own physical radius (see pad-radius-mm — obstacle-building needs this;
  pcb.layout never applies this transform anywhere itself, DRC checks
  trace/via geometry only, never footprint pad geometry — so this is
  new, not a refactor of existing logic)."
  [footprint]
  (mapv (fn [p]
          {:net-id (:net-id p)
           :footprint-id (:id footprint)
           :radius-mm (pad-radius-mm p)
           :absolute (let [[rx ry] (rotate-point (:center p) (:rotation footprint))]
                       [(+ rx (:x footprint)) (+ ry (:y footprint))])})
        (:pads footprint)))

(defn- all-pad-positions [layout]
  (mapcat footprint-pad-positions (:footprints layout)))

(defn- outline-bounds
  "`[[minx miny] [maxx maxy]]` from a board outline given as a seq of
  `[x y]` points (a polygon, or just the two corners of a rectangle —
  either way the bounding box is the same computation; pcb.layout never
  constrains `:outline`'s shape beyond \"points\")."
  [outline]
  (let [xs (map first outline) ys (map second outline)]
    [[(apply min xs) (apply min ys)] [(apply max xs) (apply max ys)]]))

;; ─────────────────────────────── grid ───────────────────────────────

(defn- mm->cell [pitch [minx miny] [x y]]
  [(long (Math/round (/ (- x minx) pitch))) (long (Math/round (/ (- y miny) pitch)))])

(defn- cell->mm [pitch [minx miny] [col row]]
  [(+ minx (* col pitch)) (+ miny (* row pitch))])

(defn- grid-dims [pitch [minx miny] [maxx maxy]]
  [(inc (long (Math/round (/ (- maxx minx) pitch))))
   (inc (long (Math/round (/ (- maxy miny) pitch))))])

(defn- disc-blocked-cells
  "Every grid cell within `radius-mm` of `center-mm` (a filled disc,
  clearance margin around an obstacle point)."
  [pitch origin [ncols nrows] center-mm radius-mm]
  (let [[ccol crow] (mm->cell pitch origin center-mm)
        r-cells (long (Math/ceil (/ radius-mm pitch)))]
    (for [dc (range (- r-cells) (inc r-cells))
          dr (range (- r-cells) (inc r-cells))
          :let [col (+ ccol dc) row (+ crow dr)]
          :when (and (<= 0 col) (< col ncols) (<= 0 row) (< row nrows)
                     (<= (Math/sqrt (+ (* dc dc) (* dr dr))) (/ radius-mm pitch)))]
      [col row])))

(defn- segment-blocked-cells
  "Grid cells within `radius-mm` of the polyline `points-mm` — used to
  turn an already-routed trace into an obstacle for later nets."
  [pitch origin dims points-mm radius-mm]
  (mapcat (fn [p] (disc-blocked-cells pitch origin dims p radius-mm))
          points-mm))

(defn- build-obstacle-set
  "Blocked cells: every pad NOT in `own-net-id` (its own physical extent
  -- pad-radius-mm, from :size -- PLUS the DRC min-clearance and half
  the routing trace width; a pad isn't a point), the board edge itself
  (a 1-cell-thick border, since a trace should not run exactly on the
  outline), and every already-routed trace/via (clearance likewise)."
  [layout pitch origin dims own-net-id trace-width]
  (let [cfg (:drc-config layout)
        clearance (+ (:min-clearance cfg) (/ trace-width 2.0))
        [ncols nrows] dims
        pad-obstacles
        (mapcat (fn [{:keys [net-id absolute radius-mm]}]
                  (when (not= net-id own-net-id)
                    (disc-blocked-cells pitch origin dims absolute (+ radius-mm clearance))))
                (all-pad-positions layout))
        trace-obstacles
        (mapcat (fn [trace]
                   (when (not= (:net-id trace) own-net-id)
                     (segment-blocked-cells pitch origin dims (:points trace)
                                            (+ clearance (/ (:width trace) 2.0)))))
                (:traces layout))
        via-obstacles
        (mapcat (fn [via]
                   (when (not= (:net-id via) own-net-id)
                     (disc-blocked-cells pitch origin dims [(:x via) (:y via)]
                                         (+ clearance (/ (:outer-diameter via) 2.0)))))
                (:vias layout))
        border (concat (for [c (range ncols)] [c 0]) (for [c (range ncols)] [c (dec nrows)])
                       (for [r (range nrows)] [0 r]) (for [r (range nrows)] [(dec ncols) r]))]
    (into #{} (concat pad-obstacles trace-obstacles via-obstacles border))))

;; ─────────────────────────── Lee's algorithm ───────────────────────────

(defn- trace-back
  "Walk `came-from` (cell -> predecessor-or-nil) from `cur` back to the
  root, returning the path root-to-cur."
  [came-from cur]
  (loop [path (list cur) at cur]
    (let [prev (get came-from at)]
      (if (nil? prev)
        (vec path)
        (recur (cons prev path) prev)))))

(defn maze-route-cells
  "Lee's algorithm: BFS shortest 4-connected path from `src` to `dst`
  over a `[ncols nrows]` grid, avoiding `blocked` cells (src/dst are
  exempted even if `blocked` — a pad's own clearance disc shouldn't wall
  it off from its own trace). Returns a vector of cells from src to dst
  inclusive, or nil if unreachable."
  [[ncols nrows] blocked src dst]
  (if (= src dst)
    [src]
    (let [neighbors (fn [[c r]] [[(inc c) r] [(dec c) r] [c (inc r)] [c (dec r)]])
          in-bounds? (fn [[c r]] (and (<= 0 c) (< c ncols) (<= 0 r) (< r nrows)))
          free? (fn [cell] (or (= cell src) (= cell dst) (not (blocked cell))))]
      ;; plain-vector FIFO (front-index + conj-at-end), not
      ;; clojure.lang.PersistentQueue, so this stays cljs-portable --
      ;; subvec/nth-by-index is O(1), so this is still a proper queue,
      ;; not an O(n^2) shift.
      (loop [frontier [src]
             front 0
             came-from {src nil}]
        (if (>= front (count frontier))
          nil
          (let [cur (nth frontier front)]
            (if (= cur dst)
              (trace-back came-from cur)
              (let [next-cells (filter #(and (in-bounds? %) (free? %) (not (contains? came-from %)))
                                        (neighbors cur))
                    came-from' (reduce (fn [m c] (assoc m c cur)) came-from next-cells)
                    frontier' (reduce conj frontier next-cells)]
                (recur frontier' (inc front) came-from')))))))))

(defn- simplify-collinear
  "Drop interior points where the path doesn't change direction —
  turns N grid-hop points into just the corners, without altering the
  path's shape."
  [points]
  (if (< (count points) 3)
    (vec points)
    (let [dir (fn [[x0 y0] [x1 y1]] [(- x1 x0) (- y1 y0)])]
      (loop [out [(first points)] prev (first points) rest-pts (rest points)]
        (cond
          (empty? rest-pts) out
          (= 1 (count rest-pts)) (conj out (first rest-pts))
          :else
          (let [cur (first rest-pts) nxt (second rest-pts)]
            (if (= (dir prev cur) (dir cur nxt))
              (recur out prev (rest rest-pts))
              (recur (conj out cur) cur (rest rest-pts)))))))))

;; ─────────────────────── MST over a net's pads ───────────────────────

(defn- manhattan [[ax ay] [bx by]] (+ (Math/abs (- bx ax)) (Math/abs (- by ay))))

(defn- mst-edges
  "Prim's algorithm: minimum spanning tree edges (index pairs) over
  `points`, Manhattan distance. `points` has >= 2 elements."
  [points]
  (let [n (count points)]
    (loop [in-tree #{0} edges []]
      (if (= n (count in-tree))
        edges
        (let [[_best-d best-i best-j]
              (reduce (fn [[bd bi bj] i]
                        (reduce (fn [[bd bi bj] j]
                                  (if (contains? in-tree j)
                                    [bd bi bj]
                                    (let [d (manhattan (nth points i) (nth points j))]
                                      (if (< d bd) [d i j] [bd bi bj]))))
                                [bd bi bj] (range n)))
                      [##Inf nil nil] (vec in-tree))]
          (recur (conj in-tree best-j) (conj edges [best-i best-j])))))))

;; ───────────────────────────────── API ─────────────────────────────────

(def ^:const default-grid-pitch-mm 0.25)

(defn route-net
  "Route every pad with `net-id` in `layout` (across all footprints).
  Returns `[status layout']` — `status` is `:ok` (0 or 1 pad, nothing to
  route, or all pads connected), `:routed`, or `:unrouted` (fewer than 2
  pads found, or the maze router couldn't connect every MST edge — in
  that case `layout'` is unchanged, not partially routed). `opts`:
  `:grid-pitch-mm` (default 0.25), `:trace-width` (default the layout's
  `drc-config` min-trace-width), `:layer` (default `:front`)."
  [layout net-id & [{:keys [grid-pitch-mm trace-width layer]
                     :or {grid-pitch-mm default-grid-pitch-mm layer :front}}]]
  (let [trace-width (or trace-width (:min-trace-width (:drc-config layout)))
        pads (filterv #(= net-id (:net-id %)) (all-pad-positions layout))]
    (cond
      (< (count pads) 2) [:ok layout]
      :else
      (let [origin (first (outline-bounds (:outline (:board layout))))
            dims (grid-dims grid-pitch-mm origin (second (outline-bounds (:outline (:board layout)))))
            points (mapv :absolute pads)
            edges (mst-edges points)]
        (loop [remaining edges layout layout]
          (if (empty? remaining)
            [:routed layout]
            (let [[i j] (first remaining)
                  blocked (build-obstacle-set layout grid-pitch-mm origin dims net-id trace-width)
                  src (mm->cell grid-pitch-mm origin (nth points i))
                  dst (mm->cell grid-pitch-mm origin (nth points j))
                  cell-path (maze-route-cells dims blocked src dst)]
              (if (nil? cell-path)
                [:unrouted layout]
                (let [mm-path (simplify-collinear (mapv #(cell->mm grid-pitch-mm origin %) cell-path))
                      [_id layout] (layout/route-trace layout net-id mm-path trace-width layer)]
                  (recur (rest remaining) layout))))))))))

(defn route-all
  "Route every distinct net-id present on `layout`'s placed footprint
  pads, in ascending net-id order (so routing order is deterministic).
  Returns `{:layout layout' :routed [net-id ...] :failed [net-id ...]}`
  — a net in `:failed` left `layout'` unchanged for that net (see
  route-net); it does not stop routing the rest."
  [layout & [opts]]
  (let [net-ids (->> (all-pad-positions layout) (keep :net-id) distinct sort)]
    (reduce (fn [{:keys [layout] :as acc} net-id]
              (let [[status layout'] (route-net layout net-id opts)]
                (case status
                  :unrouted (update acc :failed conj net-id)
                  (-> acc (assoc :layout layout') (update :routed conj net-id)))))
            {:layout layout :routed [] :failed []}
            net-ids)))
