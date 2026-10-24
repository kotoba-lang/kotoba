(ns innen.core
  "Graph construction, indexing, and historical slicing for 因縁 records.

   A graph is a plain map -- no records, no mutation -- so it round-trips
   through EDN and can be handed straight to `innen.tx/->tx` for Datomic /
   DataScript, or to any of the pure algorithms in `innen.algo`:

     {:innen/nodes    {node-id node-map}
      :innen/edges    [edge-map ...]
      :innen/out      {node-id [edge ...]}   ; edges where node is the DEPENDENT
      :innen/in       {node-id [edge ...]}   ; edges where node is the DEPENDENCY
      :innen/problems [...]                   ; from innen.schema, kept with the graph
      :innen/as-of    \"2026-07-25\"}

   `graph` is fail-closed: schema `:error` problems abort construction, because
   the whole point of the record is that a query result can be traced back to a
   checkable source. `graph*` is the escape hatch for tooling that needs to
   inspect a bad batch (an ingest script reporting what it rejected); it keeps
   the problems attached and still refuses to index the offending edges."
  (:require [innen.schema :as schema]
            [innen.time :as t]))

(defn- index-edges [edges]
  (reduce (fn [acc e]
            (-> acc
                (update-in [:out (:innen.edge/from e)] (fnil conj []) e)
                (update-in [:in (:innen.edge/to e)] (fnil conj []) e)))
          {:out {} :in {}}
          edges))

(defn graph*
  "Build a graph, tolerating bad input: nodes/edges with `:error` problems are
   EXCLUDED from the indexes but their problems are reported. Returns
   `{:innen/... :innen/rejected {:nodes [...] :edges [...]}}`."
  [{:keys [nodes edges as-of source]}]
  (let [node-probs (mapcat schema/node-problems nodes)
        edge-probs (mapcat schema/edge-problems edges)
        bad-node-id? (->> (schema/errors node-probs)
                          (keep #(get-in % [:innen/node :innen.node/id]))
                          set)
        good-nodes (remove #(bad-node-id? (:innen.node/id %)) nodes)
        by-id (into {} (map (juxt :innen.node/id identity)) good-nodes)
        bad-edge? (->> (schema/errors edge-probs)
                       (keep :innen/edge)
                       set)
        good-edges (vec (remove bad-edge? edges))
        ;; An edge pointing at a node this batch does not define is a real
        ;; problem to report, but NOT a reason to drop the edge: a partial
        ;; ingest legitimately references nodes another corpus file defines.
        dangling (for [e good-edges
                       [dir id] [[:from (:innen.edge/from e)] [:to (:innen.edge/to e)]]
                       :when (not (contains? by-id id))]
                   {:innen/severity :warn
                    :innen/code :edge/dangling-ref
                    :innen/message (str "edge " dir " references undefined node " id)
                    :innen/edge e})
        {:keys [out in]} (index-edges good-edges)]
    {:innen/nodes by-id
     :innen/edges good-edges
     :innen/out out
     :innen/in in
     :innen/as-of as-of
     :innen/source source
     :innen/problems (vec (concat node-probs edge-probs dangling))
     :innen/rejected {:nodes (vec (remove #(contains? by-id (:innen.node/id %)) nodes))
                      :edges (vec (filter bad-edge? edges))}}))

(defn graph
  "Build a graph, refusing to proceed if anything is inadmissible. Throws with
   the full problem list -- callers that want partial results use `graph*`."
  [input]
  (let [g (graph* input)
        errs (schema/errors (:innen/problems g))]
    (when (seq errs)
      (throw (ex-info (str "innen.core/graph: " (count errs) " inadmissible node(s)/edge(s); "
                           "use graph* to inspect, or fix the sourcing")
                      {:innen/errors errs})))
    (dissoc g :innen/rejected)))

(defn node [g id] (get-in g [:innen/nodes id]))
(defn nodes [g] (vals (:innen/nodes g)))
(defn edges [g] (:innen/edges g))

(defn node-ids [g] (set (keys (:innen/nodes g))))

(defn- edge-matches? [{:keys [kinds necessity confidence min-confidence]} e]
  (let [rank {:documented 3 :attested 2 :contested 1 :estimate 1}]
    (and (or (nil? kinds) (contains? (set kinds) (:innen.edge/kind e)))
         (or (nil? necessity) (contains? (set necessity) (:innen.edge/necessity e)))
         (or (nil? confidence) (contains? (set confidence) (:innen.edge/confidence e)))
         (or (nil? min-confidence)
             (>= (get rank (:innen.edge/confidence e) 0) (get rank min-confidence 0))))))

(defn dependency-edges
  "Edges on which `id` depends (id is the `from`), optionally filtered by
   `{:kinds #{...} :necessity #{...} :confidence #{...} :min-confidence :attested}`."
  ([g id] (dependency-edges g id nil))
  ([g id opts] (filterv (partial edge-matches? opts) (get-in g [:innen/out id] []))))

(defn dependent-edges
  "Edges of things that depend on `id` (id is the `to`)."
  ([g id] (dependent-edges g id nil))
  ([g id opts] (filterv (partial edge-matches? opts) (get-in g [:innen/in id] []))))

(defn dependencies
  "Node ids `id` directly depends on."
  ([g id] (dependencies g id nil))
  ([g id opts] (mapv :innen.edge/to (dependency-edges g id opts))))

(defn dependents
  "Node ids that directly depend on `id`."
  ([g id] (dependents g id nil))
  ([g id opts] (mapv :innen.edge/from (dependent-edges g id opts))))

(defn as-of
  "Slice the graph at a historical `date`: keep only edges whose
   `:innen.edge/valid` interval contains that date, and only nodes whose
   `:innen.node/existed` interval contains it.

   `:basis` picks how an item with NO stated interval is treated, and the
   difference is large enough that it is an explicit argument rather than a
   default nobody notices:

   * `:any` (default) -- keep it. It claims no interval, so no slice can honestly
     exclude it. Inflated wherever the record is undated: measured on the first
     real corpus, `(as-of g \"1700\")` kept 303 nodes, including present-day
     Delaware registrations that state no founding date.
   * `:stated` -- keep only what actually states an interval covering the date.
     The honest answer to \"what can this record say about that era\". On that
     same corpus: 8 nodes and 0 edges for 1700.
   * `:stated-or-endpoint` -- an undated EDGE counts as holding at the date when
     both of its endpoints are dated and existed then. This is a real reading,
     not a guess: the record says the relation exists and says when both parties
     existed, so the window in which it could have held is derived from stated
     facts. Nodes still need their own dates.

   `(as-of g \"1750\")` is the dependency graph as it stood in 1750, not today's
   graph with old rows filtered out by hand."
  ([g date] (as-of g date nil))
  ([g date {:keys [basis] :or {basis :any}}]
   (let [strict? (not= basis :any)
         keep-node? (fn [n]
                     (if-let [iv (:innen.node/existed n)]
                       (t/within? iv date)
                       (not strict?)))
        dated-node? (fn [id]
                      (when-let [n (get-in g [:innen/nodes id])]
                        (when-let [iv (:innen.node/existed n)]
                          (t/within? iv date))))
        keep-edge? (fn [e]
                     (if-let [iv (:innen.edge/valid e)]
                       (t/within? iv date)
                       (case basis
                         :any true
                         :stated false
                         :stated-or-endpoint (boolean (and (dated-node? (:innen.edge/from e))
                                                           (dated-node? (:innen.edge/to e)))))))
        ns* (filterv keep-node? (nodes g))
        kept-ids (set (map :innen.node/id ns*))
        es (filterv (fn [e]
                      (and (keep-edge? e)
                           ;; an edge cannot hold in a year when one of its
                           ;; endpoints did not exist, even if the edge itself
                           ;; states a wider interval
                           (or (not (contains? (node-ids g) (:innen.edge/from e)))
                               (contains? kept-ids (:innen.edge/from e)))
                           (or (not (contains? (node-ids g) (:innen.edge/to e)))
                               (contains? kept-ids (:innen.edge/to e)))))
                    (edges g))
        {:keys [out in]} (index-edges es)]
    (assoc g
           :innen/nodes (into {} (map (juxt :innen.node/id identity)) ns*)
           :innen/edges es
           :innen/out out
           :innen/in in
           :innen/slice-at date
           :innen/slice-basis basis))))

(defn merge-graphs
  "Union two graphs. Node collisions on the same `:innen.node/id` keep the
   FIRST graph's node and report the collision, so an ingest can never quietly
   overwrite a hand-verified node with a scraped one."
  [a b]
  (let [collisions (for [[id n] (:innen/nodes b)
                         :let [existing (get-in a [:innen/nodes id])]
                         :when (and existing (not= existing n))]
                     {:innen/severity :warn
                      :innen/code :graph/node-collision
                      :innen/message (str "node " id " defined differently in both graphs; kept the first")
                      :innen/node n})
        nodes* (merge (:innen/nodes b) (:innen/nodes a))
        edges* (into (vec (:innen/edges a)) (:innen/edges b))
        {:keys [out in]} (index-edges edges*)]
    {:innen/nodes nodes*
     :innen/edges edges*
     :innen/out out
     :innen/in in
     :innen/as-of (or (:innen/as-of a) (:innen/as-of b))
     :innen/problems (vec (concat (:innen/problems a) (:innen/problems b) collisions))}))

(defn stats
  "Shape of the record: counts by node kind, edge kind, necessity, confidence.
   Used by the loop's report so growth is visible per cycle."
  [g]
  {:innen/node-count (count (:innen/nodes g))
   :innen/edge-count (count (:innen/edges g))
   :innen/by-node-kind (frequencies (map :innen.node/kind (nodes g)))
   :innen/by-edge-kind (frequencies (map :innen.edge/kind (edges g)))
   :innen/by-necessity (frequencies (map :innen.edge/necessity (edges g)))
   :innen/by-confidence (frequencies (map :innen.edge/confidence (edges g)))
   :innen/earliest-valid-from (->> (edges g)
                                   (keep (comp :from :innen.edge/valid))
                                   (sort-by t/lower-key)
                                   first)
   :innen/warnings (count (schema/warnings (:innen/problems g)))})
