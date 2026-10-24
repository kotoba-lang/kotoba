(ns graph.data
  "Data model: transform haisen/systemofsystem JSON (from the `gftd` CLI) into a
  unified graph representation.

  Restored from `kami-engine/kami-graph/src/data.rs` (kotoba-lang/kami-engine,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as zero-dependency
  portable `.cljc`, per ADR-2607010930 (the clj-wgsl migration).

  The original Rust structs (`HaisenData`, `HaisenApp`, `HaisenEdge`, `HaisenStats`,
  `SoSData`, `SoSSystem`, `SoSInterface`, `SoSLayer`, `SoSStats`, `GraphData`,
  `GraphNode`, `GraphEdge`) used `serde::Deserialize` to parse JSON directly. Here
  we assume the JSON has already been parsed into plain Clojure maps with keyword
  keys (by whatever JSON reader the caller uses); this namespace only implements
  the `#[serde(default)]` field defaults (via `get` with a fallback) and the
  `to_graph` transform logic, ported 1:1.

  ## Shapes (plain maps, no records)

  - `GraphNode`  -> {:id :label :group :group-index :node-type :radius :x :y}
  - `GraphEdge`  -> {:from-idx :to-idx :edge-type :label}
  - `GraphData`  -> {:nodes [GraphNode...] :edges [GraphEdge...] :groups [string...]}
  - `HaisenApp`  -> {:nanoid :did :name :performer-type :runtime-type :project :x :y}
  - `HaisenEdge` -> {:from :to :edge-type :label}
  - `HaisenData` -> {:apps [HaisenApp...] :edges [HaisenEdge...] :infra [HaisenApp...]
                      :stats {:total-apps :total-edges :orphans}}
  - `SoSSystem`    -> {:id :system-type :app-count :deployed}
  - `SoSInterface` -> {:from :to :protocol :edge-count}
  - `SoSLayer`     -> {:name :systems}
  - `SoSData`      -> {:systems [...] :interfaces [...] :layers [...]
                        :stats {:total-systems :total-interfaces :total-apps
                                 :coupling-score :cohesion-score}}"
  (:require [kotoba.lang.text :as str]))

;; --- accessors with serde-style defaults -------------------------------

(defn- fget
  "Like `get` but treats blank string / nil the same (mirrors `#[serde(default)]`
  on String/number fields)."
  [m k default]
  (let [v (get m k default)]
    (if (nil? v) default v)))

(defn has-layout?
  "True if any app in `haisen-data` has a non-zero pre-computed (x,y) — i.e. the
  data came from `gftd haisen scan --layout`. Mirrors `HaisenData::has_layout`."
  [haisen-data]
  (boolean (some (fn [app]
                    (or (not= (fget app :x 0.0) 0.0)
                        (not= (fget app :y 0.0) 0.0)))
                  (:apps haisen-data))))

;; --- group interning (immutable HashMap<String,usize> equivalent) ------

(defn- ensure-group
  "Returns [idx groups' group-map'] — interns `g` into `groups`/`group-map`,
  reusing the existing index if already present. Mirrors the Rust closure
  `ensure_group`."
  [groups group-map g]
  (if-let [idx (get group-map g)]
    [idx groups group-map]
    (let [idx (count groups)]
      [idx (conj groups g) (assoc group-map g idx)])))

;; --- shorten-label -------------------------------------------------------

(defn shorten-label
  "Shorten a long node id into a display label. Ported 1:1 from `shorten_label`."
  [s]
  (cond
    (<= (count s) 16)
    s

    (str/starts-with? s "app.etzhayyim.apps.")
    (let [rest (subs s (count "app.etzhayyim.apps."))
          parts (str/split rest #"\.")]
      (if (> (count parts) 2)
        (str (nth parts 0) "." (nth parts 1) "..")
        rest))

    (str/starts-with? s "did:web:")
    (-> (subs s (count "did:web:"))
        (str/replace ".etzhayyim.com" ""))

    (str/starts-with? s "sql:")
    (subs s (count "sql:"))

    :else
    (str (subs s 0 14) "..")))

;; --- HaisenData -> GraphData --------------------------------------------

(defn haisen->graph
  "Transform `HaisenData` (apps/edges/infra) into a unified `GraphData`.
  Ported 1:1 from `HaisenData::to_graph`."
  [{:keys [apps infra edges] :as _haisen-data}]
  (let [apps (or apps [])
        infra (or infra [])
        edges (or edges [])

        ;; Apps
        [nodes id->idx groups group-map]
        (reduce
          (fn [[nodes id->idx groups group-map] app]
            (let [nanoid (fget app :nanoid "")
                  did (fget app :did "")
                  id (cond
                       (not (str/blank? nanoid)) nanoid
                       (not (str/blank? did)) did
                       :else nil)]
              (if (or (nil? id) (contains? id->idx id))
                [nodes id->idx groups group-map]
                (let [project (fget app :project "")
                      group (if (str/blank? project) "unknown" project)
                      [gi groups group-map] (ensure-group groups group-map group)
                      idx (count nodes)
                      name (fget app :name "")
                      label (if (str/blank? name) nanoid name)]
                  [(conj nodes {:id id
                                :label label
                                :group group
                                :group-index gi
                                :node-type (fget app :performer-type "")
                                :radius 6.0
                                :x (fget app :x 0.0)
                                :y (fget app :y 0.0)})
                   (assoc id->idx id idx)
                   groups group-map]))))
          [[] {} [] {}]
          apps)

        ;; Infra
        [nodes id->idx groups group-map]
        (reduce
          (fn [[nodes id->idx groups group-map] infra-app]
            (let [id (fget infra-app :name "")]
              (if (or (str/blank? id) (contains? id->idx id))
                [nodes id->idx groups group-map]
                (let [[gi groups group-map] (ensure-group groups group-map "infra")
                      idx (count nodes)]
                  [(conj nodes {:id id
                                :label id
                                :group "infra"
                                :group-index gi
                                :node-type "system"
                                :radius 10.0
                                :x (fget infra-app :x 0.0)
                                :y (fget infra-app :y 0.0)})
                   (assoc id->idx id idx)
                   groups group-map]))))
          [nodes id->idx groups group-map]
          infra)

        ;; Edges (ensure target nodes exist)
        [nodes id->idx groups _group-map graph-edges]
        (reduce
          (fn [[nodes id->idx groups group-map graph-edges] e]
            (let [to (:to e)
                  from (:from e)
                  [nodes id->idx groups group-map]
                  (if (contains? id->idx to)
                    [nodes id->idx groups group-map]
                    (let [[gi groups group-map] (ensure-group groups group-map "collection")
                          idx (count nodes)]
                      [(conj nodes {:id to
                                    :label (shorten-label to)
                                    :group "collection"
                                    :group-index gi
                                    :node-type "collection"
                                    :radius 3.0
                                    :x 0.0
                                    :y 0.0})
                       (assoc id->idx to idx)
                       groups group-map]))
                  fi (get id->idx from)
                  ti (get id->idx to)
                  graph-edges (if (and fi ti)
                                (let [edge-type (:edge-type e)
                                      label (fget e :label "")]
                                  (conj graph-edges {:from-idx fi
                                                      :to-idx ti
                                                      :edge-type edge-type
                                                      :label (if (str/blank? label) edge-type label)}))
                                graph-edges)]
              [nodes id->idx groups group-map graph-edges]))
          [nodes id->idx groups group-map []]
          edges)]
    {:nodes nodes :edges graph-edges :groups groups}))

;; --- SoSData -> GraphData ------------------------------------------------

(defn sos->graph
  "Transform `SoSData` (systems/interfaces/layers) into a unified `GraphData`.
  Ported 1:1 from `SoSData::to_graph`."
  [{:keys [systems interfaces layers] :as _sos-data}]
  (let [systems (or systems [])
        interfaces (or interfaces [])
        layers (or layers [])

        sys->layer (reduce (fn [acc layer]
                              (reduce (fn [acc sys] (assoc acc sys (:name layer)))
                                      acc (:systems layer)))
                            {} layers)

        [nodes id->idx groups group-map]
        (reduce
          (fn [[nodes id->idx groups group-map] sys]
            (if (contains? id->idx (:id sys))
              [nodes id->idx groups group-map]
              (let [layer (or (get sys->layer (:id sys)) (fget sys :system-type ""))
                    [gi groups group-map] (ensure-group groups group-map layer)
                    idx (count nodes)
                    app-count (fget sys :app-count 0)
                    r (* (Math/sqrt (double app-count)) 3.0)
                    radius (min 20.0 (max r 6.0))]
                [(conj nodes {:id (:id sys)
                              :label (:id sys)
                              :group layer
                              :group-index gi
                              :node-type (fget sys :system-type "")
                              :radius radius
                              :x 0.0
                              :y 0.0})
                 (assoc id->idx (:id sys) idx)
                 groups group-map])))
          [[] {} [] {}]
          systems)

        [nodes id->idx groups _group-map graph-edges]
        (reduce
          (fn [[nodes id->idx groups group-map graph-edges] iface]
            (let [[nodes id->idx groups group-map]
                  (reduce
                    (fn [[nodes id->idx groups group-map] ep]
                      (if (contains? id->idx ep)
                        [nodes id->idx groups group-map]
                        (let [[gi groups group-map] (ensure-group groups group-map "unknown")
                              idx (count nodes)]
                          [(conj nodes {:id ep
                                        :label ep
                                        :group "unknown"
                                        :group-index gi
                                        :node-type "project"
                                        :radius 6.0
                                        :x 0.0
                                        :y 0.0})
                           (assoc id->idx ep idx)
                           groups group-map])))
                    [nodes id->idx groups group-map]
                    [(:from iface) (:to iface)])
                  fi (get id->idx (:from iface))
                  ti (get id->idx (:to iface))
                  graph-edges (if (and fi ti)
                                (conj graph-edges {:from-idx fi
                                                    :to-idx ti
                                                    :edge-type (:protocol iface)
                                                    :label (:protocol iface)})
                                graph-edges)]
              [nodes id->idx groups group-map graph-edges]))
          [nodes id->idx groups group-map []]
          interfaces)]
    {:nodes nodes :edges graph-edges :groups groups}))
