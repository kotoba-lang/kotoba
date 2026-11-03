(ns kami.modeling.feature-graph
  "Typed, deterministic dependency graph for CAD features and DCC modifiers."
  (:require [kami.modeling.document :as document]))

(def geometry-types #{:mesh :brep :curve :surface :assembly :scalar :any})

(defn node [id kind input-type output-type dependencies parameters evaluator]
  (when-not (and (uuid? id) (keyword? kind) (geometry-types input-type) (geometry-types output-type)
                 (every? uuid? dependencies) (ifn? evaluator))
    (throw (ex-info "invalid feature node" {:id id :kind kind})))
  {:feature/id id :feature/kind kind :feature/input-type input-type :feature/output-type output-type
   :feature/dependencies (vec dependencies) :feature/parameters parameters
   :feature/enabled? true :feature/evaluator evaluator})

(defn graph [nodes outputs]
  {:graph/nodes (into {} (map (juxt :feature/id identity) nodes)) :graph/outputs (vec outputs)})

(defn validation-errors [graph]
  (let [nodes (:graph/nodes graph) errors (transient []) add! #(conj! errors %)]
    (doseq [[id n] nodes dep (:feature/dependencies n)]
      (if-let [source (get nodes dep)]
        (when-not (or (= :any (:feature/input-type n)) (= :any (:feature/output-type source))
                      (= (:feature/input-type n) (:feature/output-type source)))
          (add! {:error :type-mismatch :node id :dependency dep
                 :expected (:feature/input-type n) :actual (:feature/output-type source)}))
        (add! {:error :missing-dependency :node id :dependency dep})))
    (doseq [id (:graph/outputs graph)]
      (when-not (contains? nodes id) (add! {:error :missing-output :node id})))
    (letfn [(visit [id visiting visited]
              (cond (visiting id) [visited [{:error :dependency-cycle :node id}]]
                    (visited id) [visited []]
                    :else (reduce (fn [[seen errs] dep]
                                    (let [[seen' errs'] (visit dep (conj visiting id) seen)]
                                      [seen' (into errs errs')]))
                                  [(conj visited id) []] (filter nodes (:feature/dependencies (get nodes id))))))]
      (let [[_ cycle-errors] (reduce (fn [[visited errs] id]
                                      (let [[visited' found] (visit id #{} visited)]
                                        [visited' (into errs found)])) [#{} []] (keys nodes))]
        (doseq [e (distinct cycle-errors)] (add! e))))
    (persistent! errors)))

(defn valid-graph? [graph] (empty? (validation-errors graph)))

(defn- cache-key [node dependency-keys]
  (document/revision-id {:node (:feature/id node) :kind (:feature/kind node)
                         :parameters (:feature/parameters node) :enabled? (:feature/enabled? node)
                         :dependencies dependency-keys}))

(defn evaluate
  "Evaluate requested outputs. Cache entries contain value and last-valid value;
  failures are data and never erase the last valid preview."
  ([graph] (evaluate graph {}))
  ([graph cache]
   (let [errors (validation-errors graph)]
     (when (seq errors) (throw (ex-info "invalid feature graph" {:errors errors})))
     (let [state (atom {:cache cache :visiting #{}})]
       (letfn [(run [id]
                 (let [node (get-in graph [:graph/nodes id])]
                   (when (contains? (:visiting @state) id) (throw (ex-info "feature cycle" {:node id})))
                   (swap! state update :visiting conj id)
                   (let [deps (mapv run (:feature/dependencies node))
                         dep-keys (mapv :evaluation/cache-key deps)
                         key (cache-key node dep-keys)
                         cached (get-in @state [:cache id])
                         result (if (= key (:evaluation/cache-key cached))
                                  (assoc cached :evaluation/cache-hit? true)
                                  (if (false? (:feature/enabled? node))
                                    {:evaluation/node id :evaluation/status :disabled
                                     :evaluation/value (:evaluation/value (first deps))
                                     :evaluation/cache-key key :evaluation/cache-hit? false}
                                    (try
                                      (let [value ((:feature/evaluator node) (mapv :evaluation/value deps)
                                                   (:feature/parameters node))]
                                        {:evaluation/node id :evaluation/status :ok :evaluation/value value
                                         :evaluation/last-valid value :evaluation/cache-key key
                                         :evaluation/cache-hit? false})
                                      (catch #?(:clj Exception :cljs :default) e
                                        {:evaluation/node id :evaluation/status :failed
                                         :evaluation/error {:message #?(:clj (.getMessage e) :cljs (.-message e))
                                                            :data (ex-data e)}
                                         :evaluation/value (:evaluation/last-valid cached)
                                         :evaluation/last-valid (:evaluation/last-valid cached)
                                         :evaluation/cache-key key :evaluation/cache-hit? false}))))]
                     (swap! state assoc-in [:cache id] result)
                     (swap! state update :visiting disj id)
                     result)))]
         (let [outputs (mapv run (:graph/outputs graph))]
           {:evaluation/outputs outputs :evaluation/cache (:cache @state)
            :evaluation/status (if (some #(= :failed (:evaluation/status %)) (vals (:cache @state)))
                                 :failed :ok)}))))))

(defn update-parameters [graph id parameters]
  (when-not (get-in graph [:graph/nodes id]) (throw (ex-info "feature node not found" {:id id})))
  (assoc-in graph [:graph/nodes id :feature/parameters] parameters))
(defn set-enabled [graph id enabled?] (assoc-in graph [:graph/nodes id :feature/enabled?] (boolean enabled?)))
