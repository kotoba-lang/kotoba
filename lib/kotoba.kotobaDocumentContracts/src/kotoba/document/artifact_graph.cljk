(ns kotoba.document.artifact-graph
  "Domain-neutral dependency graph for deterministic derived document artifacts.")

(def schema-version 1)

(defn- dependency-closure [graph targets]
  (loop [pending (vec targets) result #{}]
    (if-let [id (peek pending)]
      (if (contains? result id)
        (recur (pop pending) result)
        (let [spec (get graph id)]
          (if spec
            (recur (into (pop pending) (:depends-on spec)) (conj result id))
            (recur (pop pending) result))))
      result)))

(defn build-order
  "Validate a graph and return a stable topological order for the requested
  targets. Dependencies absent from the graph are source artifact ids."
  ([graph] (build-order graph (keys graph)))
  ([graph targets]
   (doseq [id targets]
     (when-not (contains? graph id)
       (throw (ex-info "artifact target is not defined" {:artifact/id id}))))
   (let [required (dependency-closure graph targets)
         permanent (atom #{})
         temporary (atom #{})
         result (atom [])]
     (letfn [(visit [id stack]
               (when (contains? @temporary id)
                 (throw (ex-info "artifact dependency cycle"
                                 {:artifact/id id :artifact/cycle (conj stack id)})))
               (when-not (contains? @permanent id)
                 (swap! temporary conj id)
                 (doseq [dependency (sort-by str (:depends-on (graph id)))
                         :when (contains? required dependency)]
                   (visit dependency (conj stack id)))
                 (swap! temporary disj id)
                 (swap! permanent conj id)
                 (swap! result conj id)))]
       (doseq [id (sort-by str targets)] (visit id []))
       @result))))

(defn state
  "Create a reusable artifact state. Source tokens must change whenever the
  corresponding source value changes."
  ([] (state {} {}))
  ([values tokens]
   {:artifact.graph/schema-version schema-version
    :artifact.graph/values values :artifact.graph/tokens tokens
    :artifact.graph/journal []}))

(defn rebuild
  "Build requested artifacts in dependency order. Unchanged nodes reuse their
  prior values. A rebuilt dependency forces all consumers to rebuild. Builders
  receive dependency values plus all source values and already-built artifacts.

  Graph node: `{:depends-on [...], :version any, :build (fn [context] value)}`.
  Options: `:targets`, `:source-tokens`, and explicit `:invalidate` ids."
  ([graph sources previous]
   (rebuild graph sources previous {}))
  ([graph sources previous {:keys [targets source-tokens invalidate]
                            :or {targets (keys graph) source-tokens {} invalidate #{}}}]
   (let [order (build-order graph targets)
         source-ids (set (mapcat #(or (:depends-on (graph %)) []) order))
         missing (remove #(or (contains? graph %) (contains? sources %)) source-ids)]
     (when (seq missing)
       (throw (ex-info "artifact graph references missing sources"
                       {:artifact/missing-sources (set missing)})))
     (let [initial-values (merge (:artifact.graph/values previous) sources)
           initial-tokens (merge (:artifact.graph/tokens previous) source-tokens)
           result
           (reduce
            (fn [{:keys [values tokens rebuilt journal] :as accumulator} id]
              (let [{:keys [depends-on version build]} (graph id)
                    dependency-token (mapv #(get tokens %) depends-on)
                    token [version dependency-token]
                    stale? (or (contains? invalidate id)
                               (not (contains? values id))
                               (not= token (get tokens id))
                               (some rebuilt depends-on))]
                (if stale?
                  (let [dependency-values (into {} (map #(vector % (get values %)) depends-on))
                        value (build {:artifact/id id
                                      :dependencies dependency-values
                                      :sources sources :artifacts values})]
                    (assoc accumulator
                           :values (assoc values id value)
                           :tokens (assoc tokens id token)
                           :rebuilt (conj rebuilt id)
                           :journal (conj journal {:artifact/id id :status :rebuilt})))
                  (assoc accumulator :journal
                         (conj journal {:artifact/id id :status :reused})))))
            {:values initial-values :tokens initial-tokens :rebuilt #{} :journal []}
            order)]
       {:artifact.graph/schema-version schema-version
        :artifact.graph/values (:values result)
        :artifact.graph/tokens (:tokens result)
        :artifact.graph/rebuilt (:rebuilt result)
        :artifact.graph/journal (:journal result)}))))
