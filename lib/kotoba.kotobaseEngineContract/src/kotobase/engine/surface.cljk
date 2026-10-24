(ns kotobase.engine.surface
  "Layer ownership for public database operations.

  IEngine owns physical state transitions and primitive scans. Datomic-shaped
  query semantics may be implemented above those primitives, but provider
  diagnostics, materialized projections, archives, and chain anchors are
  deliberately separate contracts. This table prevents a rollout adapter from
  treating every similarly named endpoint as a portable engine operation.")

(def operation-layers
  {:engine-state
   #{:transact :snapshot :restore :scan :history :checkpoint :maintain}

   :semantic-query
   #{:datoms :seek-datoms :index-range :q :sparql :cypher :pull :pull-many
     :index-pull :entity :entid :ident :as-of :since :basis-t :tx :tx-range
     :log :sync}

   :provider-diagnostics
   #{:db-stats}

   :projection
   #{:define-view :refresh-view :view}

   :archive
   #{:archive-put :archive-get :archive-list}

   :anchor
   #{:anchor-checkpoint :anchor-receipt :verify-anchor}})

(defn operation-layer [operation]
  (some (fn [[layer operations]]
          (when (contains? operations operation) layer))
        operation-layers))

(defn engine-operation? [operation]
  (= :engine-state (operation-layer operation)))

(defn portable-read-operation?
  "True only for reads whose result is independent of physical layout.
  `db-stats` and `view` intentionally return false: the former describes one
  provider, while the latter belongs to a separately versioned projection
  subsystem with its own definition and source-commit barrier."
  [operation]
  (or (contains? #{:scan :history} operation)
      (= :semantic-query (operation-layer operation))))

(defn validate-operation-layers
  ([] (validate-operation-layers operation-layers))
  ([layers]
   (let [memberships (reduce-kv
                      (fn [acc layer operations]
                        (reduce #(update %1 %2 (fnil conj #{}) layer)
                                acc operations))
                      {} layers)
         duplicates (into {} (filter (fn [[_ owners]] (> (count owners) 1)))
                          memberships)]
     (when (seq duplicates)
       (throw (ex-info "operations must have exactly one owning layer"
                       {:type :kotobase.engine/ambiguous-operation-layer
                        :duplicates duplicates})))
     layers)))

(validate-operation-layers)
