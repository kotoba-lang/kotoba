(ns openaccess.query
  "Pure query functions over the simplified OpenAccess design model,
  composing `openaccess.shape`, `openaccess.design`, and
  `openaccess.library`."
  (:require [openaccess.design :as design]
            [openaccess.library :as library]
            [openaccess.shape :as shape]))

(defn bounding-box
  "Union bounding box `[x1 y1 x2 y2]` of every shape's own bbox (per
  `shape/shape-bbox`) in `design`'s `:shapes`, or `nil` if it has none."
  [{:keys [shapes]}]
  (when (seq shapes)
    (let [bboxes (map shape/shape-bbox shapes)]
      [(apply min (map #(nth % 0) bboxes))
       (apply min (map #(nth % 1) bboxes))
       (apply max (map #(nth % 2) bboxes))
       (apply max (map #(nth % 3) bboxes))])))

(defn shapes-on-layer
  "The subset of `design`'s `:shapes` whose `:layer` is `layer`."
  [{:keys [shapes]} layer]
  (filterv #(= layer (:layer %)) shapes))

(defn- transform-shape
  "Return `shape` (from a child view) with its geometry carried through
  `design/instance-transform-point` for `inst`, i.e. re-expressed in the
  parent design's coordinate system. `:rect` is transformed corner-wise
  and its `:bbox` re-normalized (a rotation/reflection can swap which
  corner is min/max); `:polygon`/`:path` are transformed vertex-wise."
  [inst shape]
  (case (:kind shape)
    :rect (let [[x1 y1 x2 y2] (:bbox shape)
                [tx1 ty1] (design/instance-transform-point inst [x1 y1])
                [tx2 ty2] (design/instance-transform-point inst [x2 y2])]
            (assoc shape :bbox [(min tx1 tx2) (min ty1 ty2)
                                 (max tx1 tx2) (max ty1 ty2)]))
    (assoc shape :points
           (mapv #(design/instance-transform-point inst %) (:points shape)))))

(defn flatten-instances
  "One-level flatten of `design`'s `:instances`: for each instance, look
  up its referenced cell view (`:cell-ref` + `:view-ref`) in `lib`, take
  that view's own `:shapes` (via `:content-ref`), transform each shape
  into `design`'s coordinate system via `transform-shape`, and return
  the combined flat shape vector. Instances found within the child
  view are not themselves recursed into (one level only); instances
  whose cell/view cannot be resolved in `lib` contribute no shapes."
  [lib design]
  (vec
   (mapcat
    (fn [inst]
      (let [child-view (library/find-cell-view lib (:cell-ref inst) (:view-ref inst))
            child-shapes (get-in child-view [:content-ref :shapes])]
        (map #(transform-shape inst %) child-shapes)))
    (:instances design))))
