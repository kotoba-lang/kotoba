(ns cmmn.model
  "CMMN-as-EDN: a plain-data representation of a CMMN 1.1 case model, plus a
  builder and the queries a validator or executor needs.
  No I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  A case is a map keyed by namespaced `:cmmn/*` keys. Plan items are kept in
  an id-keyed map for O(1) lookup; entry/exit criteria (sentries) are vectors
  on each item:

    {:cmmn/id \"case\"
     :cmmn/items
     {\"t1\" {:cmmn/id \"t1\" :cmmn/type :human-task
             :cmmn/entry-criteria [{:cmmn/on \"m1\" :cmmn/event :occur}]
             :cmmn/exit-criteria []}
      \"m1\" {:cmmn/id \"m1\" :cmmn/type :milestone
             :cmmn/entry-criteria [{:cmmn/on \"t0\" :cmmn/event :complete}]}
      \"s1\" {:cmmn/id \"s1\" :cmmn/type :stage
             :cmmn/children [\"t1\"]}}}")

(def plan-item-types
  "All valid CMMN plan-item types."
  #{:human-task :process-task :stage :milestone :event-listener})

(def criterion-events
  "Valid sentry trigger events."
  #{:complete :occur :terminate})

;; --- builder ---

(defn entry
  "Return a sentry entry-criterion that watches `on` (item-id) for `event`.
  opts: :if-cond — optional guard condition string."
  [on event & {:keys [if-cond]}]
  (cond-> {:cmmn/on on :cmmn/event event}
    if-cond (assoc :cmmn/if if-cond)))

(defn exit
  "Return a sentry exit-criterion that watches `on` (item-id) for `event`."
  [on event]
  {:cmmn/on on :cmmn/event event})

(defn child
  "Return the child item id string (identity — provided for symmetry with entry/exit)."
  [id] id)

(defn item
  "Build a plan-item map for `id` of `type`.
  opts: :entry (vector of entry criteria), :exit (vector of exit criteria),
        :children (vector of child item ids — for stages)."
  [id type & {:keys [entry exit children]}]
  (cond-> {:cmmn/id             id
           :cmmn/type           type
           :cmmn/entry-criteria (or entry [])
           :cmmn/exit-criteria  (or exit [])}
    children (assoc :cmmn/children children)))

(defn case-model
  "Build a case map from `id` and zero or more item maps."
  [id & items]
  {:cmmn/id    id
   :cmmn/items (into {} (map (juxt :cmmn/id identity) items))})

;; --- queries ---

(defn get-item  [case-map item-id] (get-in case-map [:cmmn/items item-id]))
(defn all-items [case-map]         (vals (:cmmn/items case-map)))
(defn item-ids  [case-map]         (set (keys (:cmmn/items case-map))))

(defn items-of-type
  "All plan-items of the given type `t`."
  [case-map t]
  (filter #(= t (:cmmn/type %)) (all-items case-map)))
