(ns kotoba.sarutahiko-factory.factory
  "Factory layout data model — ported from `scene.rs`'s `Factory` struct
  and its pure geometry methods (`center`, `site_extent`,
  `wall_obstacles`, `column_obstacles`, `machine_obstacles`,
  `carrier_deck`, `element_xy`, `agv_obstacles`).

  A `factory` is a plain EDN map with (mostly optional, default `[]`)
  vector-of-map fields:

    :factory/name           string
    :factory/bbox-m         [min-x min-y max-x max-y]
    :factory/site-bbox-m    [min-x min-y max-x max-y] or nil (defaults to
                             `bbox-m` padded by 12.0 m on every side)
    :factory/walls          [{:id :aabb [x0 y0 x1 y1] :height} ...]
    :factory/columns        [{:id :x :y :w :height} ...]
    :factory/beams          [{:id :x :span-y [y0 y1] :section :z} ...]
    :factory/zones          [{:id :label :rect [x0 y0 x1 y1] :tint [r g b]} ...]
    :factory/machines       [{:id :kind :aabb [x0 y0 x1 y1] :height} ...]
    :factory/conveyors      [{:id :path [[x y] ...] :width} ...]
    :factory/cells          [{:id :urdf :pos [x y z] :yaw} ...]
    :factory/agvs           [{:id :pos [x y z] :yaw :size [x y z] :mass} ...]
    :factory/loaders        [{:id :kind :pos :yaw :size :mass :payload
                               :payload-mass :pick [x y] :drop [x y]
                               :deck-z :vehicle} ...]  (see `.loader`)
    :factory/service-nodes  [{:id :kind :aabb [x0 y0 x1 y1] :height} ...]
    :factory/utilities      [{:id :kind :path [[x y] ...] :z :width} ...]
    :factory/fixtures       [{:id :kind :size :points [[x y z] ...]} ...]
    :factory/site-pavements [{:id :kind :rect [x0 y0 x1 y1]} ...]
    :factory/site-greens    [{:id :kind :rect [x0 y0 x1 y1]} ...]
    :factory/site-structures[{:id :kind :aabb [x0 y0 x1 y1] :height} ...]
    :factory/site-posts     [{:id :kind :x :y :height} ...]

  All functions are pure: no I/O, no resource loading. Callers get a
  `factory` map from wherever they like — in this repo, from
  `kotoba.sarutahiko-factory.fixtures/factory` (a synthetic test fixture,
  see the README; the real upstream `sarutahiko-factory-r0` scene JSON is
  unavailable in this checkout).

  Unported (host-adapter, stays Rust+wgpu): `static_boxes` (mesh-building)
  and everything that consumes it — id-tagged unit-box render geometry and
  colour lookup tables have no meaning outside a renderer.")

;; ── obstacles ──────────────────────────────────────────────────────────────

(defn- aabb->obstacle
  "`[x0 y0 x1 y1]` footprint + `height` → an `:obstacle/min` `:obstacle/max`
  AABB from z=0 to z=`height`."
  [[x0 y0 x1 y1] height]
  {:obstacle/min [x0 y0 0.0]
   :obstacle/max [x1 y1 height]})

(defn wall-obstacles
  "Perimeter/partition walls → AABB collision volumes (z = 0..height)."
  [factory]
  (mapv #(aabb->obstacle (:aabb %) (:height %)) (:factory/walls factory)))

(defn column-obstacles
  "Structural columns → AABB collision volumes (square section, z = 0..h)."
  [factory]
  (mapv (fn [{:keys [x y w height]}]
          (let [h2 (* 0.5 w)]
            {:obstacle/min [(- x h2) (- y h2) 0.0]
             :obstacle/max [(+ x h2) (+ y h2) height]}))
        (:factory/columns factory)))

(defn machine-obstacles
  "Production machines → AABB collision volumes (footprint × height)."
  [factory]
  (mapv #(aabb->obstacle (:aabb %) (:height %)) (:factory/machines factory)))

(defn carrier-deck
  "The deck of the named carrier machine as an obstacle capped at `deck-z`
  (so a lowered truck payload settles physically onto it). `nil` for
  unknown ids."
  [factory id deck-z]
  (when-let [m (first (filter #(= id (:id %)) (:factory/machines factory)))]
    (aabb->obstacle (:aabb m) deck-z)))

(defn agv-obstacles
  "Everything an AGV can hit: walls + columns + machines."
  [factory]
  (into (wall-obstacles factory)
        (concat (column-obstacles factory) (machine-obstacles factory))))

;; ── geometry ───────────────────────────────────────────────────────────────

(defn center
  "Plan-view centre `[x y 0.0]` of `:factory/bbox-m`."
  [factory]
  (let [[x0 y0 x1 y1] (:factory/bbox-m factory)]
    [(* 0.5 (+ x0 x1)) (* 0.5 (+ y0 y1)) 0.0]))

(defn site-extent
  "The full site footprint `[x0 y0 x1 y1]` to cover with ground: explicit
  `:factory/site-bbox-m` if present, else `:factory/bbox-m` padded 12.0 m."
  [factory]
  (or (:factory/site-bbox-m factory)
      (let [[x0 y0 x1 y1] (:factory/bbox-m factory)]
        [(- x0 12.0) (- y0 12.0) (+ x1 12.0) (+ y1 12.0)])))

;; ── id lookups ─────────────────────────────────────────────────────────────

(defn- aabb-center [[x0 y0 x1 y1]] [(* 0.5 (+ x0 x1)) (* 0.5 (+ y0 y1))])

(defn- path-endpoint-mid [path]
  (when (seq path)
    (let [[ax ay] (first path)
          [bx by] (last path)]
      [(* 0.5 (+ ax bx)) (* 0.5 (+ ay by))])))

(defn- points-mean [points]
  (when (seq points)
    (let [n (count points)]
      [(/ (reduce + (map first points)) n)
       (/ (reduce + (map second points)) n)])))

(defn element-xy
  "Plan-position `[x y]` of a render-element `id`, searching every
  sub-collection the way `Factory::element_xy` did. `nil` for unknown ids."
  [factory id]
  (cond
    (#{"floor" "ground"} id)
    (let [[cx cy] (center factory)] [cx cy])

    :else
    (or (some #(when (= id (:id %)) [(:x %) (:y %)]) (:factory/columns factory))
        (some #(when (= id (:id %))
                 [(:x %) (* 0.5 (+ (first (:span-y %)) (second (:span-y %))))])
              (:factory/beams factory))
        (some #(when (= id (:id %)) (aabb-center (:aabb %))) (:factory/walls factory))
        (some #(when (= id (:id %)) (aabb-center (:rect %))) (:factory/zones factory))
        (some #(when (= id (:id %)) (aabb-center (:aabb %))) (:factory/machines factory))
        (some #(when (= id (:id %)) (aabb-center (:aabb %)))
              (concat (:factory/service-nodes factory) (:factory/site-structures factory)))
        (some #(when (= id (:id %)) (aabb-center (:rect %)))
              (concat (:factory/site-pavements factory) (:factory/site-greens factory)))
        (some #(when (= id (:id %)) [(:x %) (:y %)]) (:factory/site-posts factory))
        (some #(when (= id (:id %)) (let [[x y] (:pos %)] [x y])) (:factory/cells factory))
        (some #(when (= id (:id %)) (let [[x y] (:pos %)] [x y])) (:factory/agvs factory))
        (some #(when (= id (:id %)) (let [[x y] (:pos %)] [x y])) (:factory/loaders factory))
        (some #(when (and (= id (:id %)) (seq (:path %))) (path-endpoint-mid (:path %)))
              (:factory/utilities factory))
        (some #(when (and (= id (:id %)) (seq (:path %))) (path-endpoint-mid (:path %)))
              (:factory/conveyors factory))
        (some #(when (and (= id (:id %)) (seq (:points %))) (points-mean (:points %)))
              (:factory/fixtures factory)))))

(defn element-ids
  "The set of every render-element id in the factory (`\"ground\"` and
  `\"floor\"` plus every sub-collection's `:id`) — used to validate that a
  construction order's `:step/reveals` only names real elements."
  [factory]
  (into #{"ground" "floor"}
        (map :id)
        (concat (:factory/walls factory) (:factory/columns factory)
                 (:factory/beams factory) (:factory/zones factory)
                 (:factory/machines factory) (:factory/conveyors factory)
                 (:factory/cells factory) (:factory/agvs factory)
                 (:factory/loaders factory) (:factory/service-nodes factory)
                 (:factory/utilities factory) (:factory/fixtures factory)
                 (:factory/site-pavements factory) (:factory/site-greens factory)
                 (:factory/site-structures factory) (:factory/site-posts factory))))
