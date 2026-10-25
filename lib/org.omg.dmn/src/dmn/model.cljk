(ns dmn.model
  "DMN-as-EDN: a plain-data representation of a Decision Requirements Graph (DRG),
  each decision carrying a decision table. No I/O, no third-party deps — portable
  .cljc (JVM, ClojureScript, SCI).

  A DRG is a map keyed by namespaced `:dmn/*` keys. Decisions are id-keyed for
  O(1) lookup; topology comes from :dmn/requires edges, not document order:

    {:dmn/id \"drg\"
     :dmn/decisions
     {\"approve\" {:dmn/id \"approve\" :dmn/name \"Approve\"
                  :dmn/hit-policy :unique
                  :dmn/requires [\"risk\"]
                  :dmn/inputs  [{:dmn/id \"i1\" :dmn/label \"age\" :dmn/expr \"age\"}]
                  :dmn/outputs [{:dmn/id \"o1\" :dmn/label \"approved\"}]
                  :dmn/rules   [{:dmn/id \"r1\" :dmn/when [\"> 18\"] :dmn/then [true]}]}}}")

(def hit-policies
  "Allowed hit-policy values for a decision table."
  #{:unique :first :priority :any :collect :rule-order})

;; --- builder (threadable, graph-centric) ---

(defn drg
  "A fresh, empty decision requirements graph."
  [id]
  {:dmn/id id :dmn/decisions {}})

(defn decision
  "A bare decision map (to be attached via `add-decision`). opts: {:name :hit-policy :requires}."
  ([id] (decision id nil))
  ([id opts]
   (cond-> {:dmn/id id
            :dmn/hit-policy (get opts :hit-policy :unique)
            :dmn/requires   (vec (get opts :requires []))
            :dmn/inputs     []
            :dmn/outputs    []
            :dmn/rules      []}
     (:name opts) (assoc :dmn/name (:name opts)))))

(defn add-decision
  "Attach `dec-map` (built via `decision`) into `graph`."
  [graph dec-map]
  (assoc-in graph [:dmn/decisions (:dmn/id dec-map)] dec-map))

(defn add-input
  "Append an input column to decision `dec-id` in `graph`. opts: {:label :expr}."
  ([graph dec-id id] (add-input graph dec-id id nil))
  ([graph dec-id id opts]
   (update-in graph [:dmn/decisions dec-id :dmn/inputs]
              conj (cond-> {:dmn/id id}
                     (:label opts) (assoc :dmn/label (:label opts))
                     (:expr  opts) (assoc :dmn/expr  (:expr  opts))))))

(defn add-output
  "Append an output column to decision `dec-id` in `graph`. opts: {:label}."
  ([graph dec-id id] (add-output graph dec-id id nil))
  ([graph dec-id id opts]
   (update-in graph [:dmn/decisions dec-id :dmn/outputs]
              conj (cond-> {:dmn/id id}
                     (:label opts) (assoc :dmn/label (:label opts))))))

(defn add-rule
  "Append a rule to decision `dec-id`. `when-cells` and `then-cells` are vectors
  aligned positionally with the decision's inputs and outputs respectively."
  [graph dec-id rule-id when-cells then-cells]
  (update-in graph [:dmn/decisions dec-id :dmn/rules]
             conj {:dmn/id rule-id :dmn/when (vec when-cells) :dmn/then (vec then-cells)}))

(defn requires
  "Declare that decision `dec-id` depends on `dep-ids` (a seq of decision ids).
  Appends (deduplicates) to any existing :dmn/requires."
  [graph dec-id dep-ids]
  (update-in graph [:dmn/decisions dec-id :dmn/requires]
             (fn [existing] (vec (distinct (concat existing dep-ids))))))

;; --- queries ---

(defn decisions    [graph]        (vals (:dmn/decisions graph)))
(defn decision-by-id [graph id]  (get-in graph [:dmn/decisions id]))
(defn inputs  [graph dec-id]     (get-in graph [:dmn/decisions dec-id :dmn/inputs]))
(defn outputs [graph dec-id]     (get-in graph [:dmn/decisions dec-id :dmn/outputs]))
(defn rules   [graph dec-id]     (get-in graph [:dmn/decisions dec-id :dmn/rules]))

(defn topo-order
  "Return decision ids in topological order (dependencies before dependants),
  starting from `dec-id` and its transitive :dmn/requires. Deterministic (ids are
  sorted at each Kahn step). Throws via ex-info on a cycle."
  [graph dec-id]
  (let [all (:dmn/decisions graph)
        ;; collect all transitive ids reachable from dec-id
        reachable
        (loop [frontier [dec-id] visited #{}]
          (if-let [cur (first frontier)]
            (if (contains? visited cur)
              (recur (rest frontier) visited)
              (let [deps (get-in all [cur :dmn/requires] [])]
                (recur (concat (rest frontier) deps) (conj visited cur))))
            visited))
        nodes (select-keys all reachable)
        ;; in-degree: count of dependencies within the reachable set
        in-deg (reduce (fn [m id]
                         (assoc m id
                                (count (filter reachable
                                               (get-in nodes [id :dmn/requires] [])))))
                       {}
                       reachable)
        result
        (loop [queue (sort (filter #(zero? (get in-deg %)) reachable))
               deg   in-deg
               out   []]
          (if-let [cur (first queue)]
            (let [;; nodes within reachable that list cur as a dependency
                  dependants (filter (fn [id]
                                       (some #{cur} (get-in nodes [id :dmn/requires] [])))
                                     reachable)
                  deg'      (reduce (fn [d dep] (update d dep dec)) deg dependants)
                  new-zeros (sort (filter #(zero? (get deg' %)) dependants))]
              (recur (concat (rest queue) new-zeros) deg' (conj out cur)))
            out))]
    (if (= (count result) (count reachable))
      result
      (throw (ex-info "DMN DRG contains a cycle"
                      {:dmn/error :cycle :dmn/ids (vec reachable)})))))
