(ns openaccess.shape
  "Simplified OpenAccess geometric shapes.

  Three shape kinds, each plain EDN tagged by `:kind`:

    rect    := {:kind :rect    :layer keyword? :bbox [x1 y1 x2 y2]}
    polygon := {:kind :polygon :layer keyword? :points [[x y] ...]}
    path    := {:kind :path    :layer keyword? :width number?
                :points [[x y] ...]}

  `:bbox`/point coordinates are plain numbers (no fixed-point/DBU scaling,
  no arcs, no donuts — the real OpenAccess `oaShape` hierarchy supports
  far more primitives than this restoration models).")

(defn rect
  "Construct a `:rect` shape on `layer` with axis-aligned bounding box
  `bbox` (`[x1 y1 x2 y2]`)."
  [layer bbox]
  {:kind :rect :layer layer :bbox bbox})

(defn polygon
  "Construct a `:polygon` shape on `layer` from vertex `points`
  (`[[x y] ...]`)."
  [layer points]
  {:kind :polygon :layer layer :points points})

(defn path
  "Construct a `:path` (routed wire) shape on `layer` with centerline
  `points` (`[[x y] ...]`) and stroke `width`."
  [layer width points]
  {:kind :path :layer layer :width width :points points})

(defn- points-bbox
  "Axis-aligned bounding box `[x1 y1 x2 y2]` of `points` (`[[x y] ...]`),
  i.e. the min/max independently over each axis."
  [points]
  (let [xs (map first points)
        ys (map second points)]
    [(apply min xs) (apply min ys) (apply max xs) (apply max ys)]))

(defn shape-bbox
  "Compute the axis-aligned bounding box `[x1 y1 x2 y2]` of `shape`.

  - `:rect`    — the shape's own `:bbox`.
  - `:polygon` — the min/max of `:points` over each axis.
  - `:path`    — the min/max of `:points` over each axis, expanded by
    half of `:width` on every side (approximating the drawn stroke
    around the centerline)."
  [{:keys [kind bbox points width]}]
  (case kind
    :rect bbox
    :polygon (points-bbox points)
    :path (let [[x1 y1 x2 y2] (points-bbox points)
                h (/ width 2)]
            [(- x1 h) (- y1 h) (+ x2 h) (+ y2 h)])))
