(ns kami-app-giemon-factory.factory
  "The `Factory` scene model, ported from `scene.rs`'s `Factory` struct and
  its `impl` block.

  In the original Rust, `Factory::load()` deserialized
  `70-tools/e7m-sim/scenes/giemon-factory-r0/factory.scene.json` via serde.
  That JSON is not present anywhere in this monorepo checkout (confirmed
  absent by a tree search of the source commit before this port began), so
  this namespace does not port a `load` — callers supply the parsed factory
  map (e.g. from EDN/JSON of their own).

  A factory map uses namespaced `:factory/...` keys mirroring the Rust struct
  fields 1:1 (kebab-case): `:factory/name`, `:factory/bbox-m` (`[min-x min-y
  max-x max-y]`), `:factory/site-bbox-m` (optional, same shape),
  `:factory/walls`, `:factory/columns`, `:factory/beams`, `:factory/zones`,
  `:factory/machines`, `:factory/conveyors`, `:factory/cells`,
  `:factory/agvs`, `:factory/service-nodes`, `:factory/utilities`,
  `:factory/fixtures`, `:factory/site-pavements`, `:factory/site-greens`,
  `:factory/site-structures`, `:factory/site-posts` — the last 8 default to
  `[]` when absent, matching serde's `#[serde(default)]`.

  Excluded: `Factory::load` (serde/`include_str!` I/O), `wall_obstacles` /
  `column_obstacles` / `machine_obstacles` still port (they were pure), but
  their Rust return type `kami_genesis::Obstacle::Aabb` is represented here
  as a plain `{:min [x y z] :max [x y z]}` map (no `kami_genesis` port
  exists).")

(defn- field
  "Default-aware accessor: coll-fields default to `[]`, matching serde's
  `#[serde(default)]` on the MEP/外構 fields."
  [f k]
  (get f k []))

(defn center
  "Plan-centre `[x y z]` of the building bbox (z is always 0 — mirrors the
  Rust `Vec3::new(.., .., 0.0)`)."
  [f]
  (let [[x0 y0 x1 y1] (:factory/bbox-m f)]
    [(* 0.5 (+ x0 x1)) (* 0.5 (+ y0 y1)) 0.0]))

(defn site-extent
  "The full site footprint to cover with ground: `:factory/site-bbox-m` if
  present, else the building bbox padded out by 12m each side."
  [f]
  (or (:factory/site-bbox-m f)
      (let [[x0 y0 x1 y1] (:factory/bbox-m f)]
        [(- x0 12.0) (- y0 12.0) (+ x1 12.0) (+ y1 12.0)])))

(defn wall-obstacles
  "Perimeter/partition walls -> AABB collision volumes (z = 0 .. height)."
  [f]
  (mapv (fn [{:keys [aabb height]}]
          (let [[x0 y0 x1 y1] aabb]
            {:min [x0 y0 0.0] :max [x1 y1 height]}))
        (field f :factory/walls)))

(defn column-obstacles
  "Structural columns -> AABB collision volumes (square section, z = 0..h)."
  [f]
  (mapv (fn [{:keys [x y w height]}]
          {:min [(- x (* w 0.5)) (- y (* w 0.5)) 0.0]
           :max [(+ x (* w 0.5)) (+ y (* w 0.5)) height]})
        (field f :factory/columns)))

(defn machine-obstacles
  "Production machines -> AABB collision volumes (footprint x height)."
  [f]
  (mapv (fn [{:keys [aabb height]}]
          (let [[x0 y0 x1 y1] aabb]
            {:min [x0 y0 0.0] :max [x1 y1 height]}))
        (field f :factory/machines)))

(defn agv-obstacles
  "Everything an AGV can hit: walls + columns + machines."
  [f]
  (vec (concat (wall-obstacles f) (column-obstacles f) (machine-obstacles f))))

(defn- aabb-center [[x0 y0 x1 y1]]
  [(* 0.5 (+ x0 x1)) (* 0.5 (+ y0 y1))])

(defn element-xy
  "Plan-position `[x y]` of a render element id -- for placing a construction
  robot at a step's work zone. Returns `nil` for unknown ids."
  [f id]
  (let [c (center f)]
    (cond
      (or (= id "floor") (= id "ground"))
      [(first c) (second c)]

      :else
      (or (some #(when (= (:id %) id) [(:x %) (:y %)]) (field f :factory/columns))
          (some #(when (= (:id %) id)
                   (let [[y0 y1] (:span-y %)]
                     [(:x %) (* 0.5 (+ y0 y1))]))
                (field f :factory/beams))
          (some #(when (= (:id %) id) (aabb-center (:aabb %))) (field f :factory/walls))
          (some #(when (= (:id %) id) (aabb-center (:rect %))) (field f :factory/zones))
          (some #(when (= (:id %) id) (aabb-center (:aabb %))) (field f :factory/machines))
          (some #(when (= (:id %) id) (aabb-center (:aabb %)))
                (concat (field f :factory/service-nodes) (field f :factory/site-structures)))
          (some #(when (= (:id %) id) (aabb-center (:rect %)))
                (concat (field f :factory/site-pavements) (field f :factory/site-greens)))
          (some #(when (= (:id %) id) [(:x %) (:y %)]) (field f :factory/site-posts))
          (some #(when (= (:id %) id) [(nth (:pos %) 0) (nth (:pos %) 1)]) (field f :factory/cells))
          (some #(when (= (:id %) id) [(nth (:pos %) 0) (nth (:pos %) 1)]) (field f :factory/agvs))
          ;; polyline / multi-point elements: midpoint of first/last point
          (some #(when (and (= (:id %) id) (seq (:path %)))
                   (let [a (first (:path %)) b (last (:path %))]
                     [(* 0.5 (+ (first a) (first b))) (* 0.5 (+ (second a) (second b)))]))
                (field f :factory/utilities))
          (some #(when (and (= (:id %) id) (seq (:path %)))
                   (let [a (first (:path %)) b (last (:path %))]
                     [(* 0.5 (+ (first a) (first b))) (* 0.5 (+ (second a) (second b)))]))
                (field f :factory/conveyors))
          (some #(when (and (= (:id %) id) (seq (:points %)))
                   (let [pts (:points %) n (count pts)]
                     [(/ (reduce + (map first pts)) n) (/ (reduce + (map second pts)) n)]))
                (field f :factory/fixtures))))))

(defn step-center
  "Work-zone centre `[x y]` of a construction step from its revealed ids."
  [f reveals]
  (let [pts (keep #(element-xy f %) reveals)]
    (if (seq pts)
      [(/ (reduce + (map first pts)) (count pts))
       (/ (reduce + (map second pts)) (count pts))]
      (let [c (center f)] [(first c) (second c)]))))

(defn element-ids
  "The set of every element id in the factory (inlined from the Rust test
  suite's `order_is_contiguous_and_reveals_resolve`, which builds this exact
  set to validate that a construction order only reveals real elements)."
  [f]
  (into #{"ground" "floor"}
        (map :id)
        (concat (field f :factory/walls) (field f :factory/columns)
                (field f :factory/beams) (field f :factory/zones)
                (field f :factory/machines) (field f :factory/conveyors)
                (field f :factory/cells) (field f :factory/agvs)
                (field f :factory/service-nodes) (field f :factory/utilities)
                (field f :factory/fixtures) (field f :factory/site-pavements)
                (field f :factory/site-greens) (field f :factory/site-structures)
                (field f :factory/site-posts))))
