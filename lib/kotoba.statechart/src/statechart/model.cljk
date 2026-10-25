(ns statechart.model
  "Harel statecharts / SCXML-subset as EDN. Zero third-party deps — portable .cljc
  (JVM, ClojureScript, SCI). A chart is a plain namespaced-key map you can assoc,
  diff, store in Datomic, or generate; this namespace adds a threading-friendly
  builder and the structural queries an interpreter or validator needs.

  A chart:
    {:sc/id \"door\" :sc/initial \"closed\"
     :sc/states {\"closed\" {:sc/id \"closed\" :sc/type :atomic
                            :sc/on {\"OPEN\" [{:sc/target \"open\"}]}
                            :sc/entry [\"enterClosed\"] :sc/exit []}
                 \"open\"   {:sc/id \"open\" :sc/type :atomic
                            :sc/on {\"CLOSE\" [{:sc/target \"closed\"}]}
                            :sc/entry [] :sc/exit []}}}

  State types: :atomic (leaf), :compound (has :sc/initial + nested :sc/states),
  :parallel (all child regions active simultaneously), :final (terminal).
  Transitions: {:sc/target id :sc/cond guard-name :sc/actions [action-names]}.")

;; --- builder (all return plain maps; thread with add-state / on) ---

(defn chart
  "Create a root chart map."
  ([id initial] {:sc/id id :sc/initial initial :sc/states {}})
  ([id initial opts] (merge {:sc/id id :sc/initial initial :sc/states {}} opts)))

(defn state
  "Create an atomic state map."
  ([id] (state id nil))
  ([id opts]
   (merge {:sc/id id :sc/type :atomic :sc/on {} :sc/entry [] :sc/exit []} opts)))

(defn compound
  "Create a compound state map (has :sc/initial + nested :sc/states)."
  ([id initial] (compound id initial nil))
  ([id initial opts]
   (merge {:sc/id id :sc/type :compound :sc/initial initial
           :sc/states {} :sc/on {} :sc/entry [] :sc/exit []} opts)))

(defn parallel
  "Create a parallel state map (all child regions simultaneously active)."
  ([id] (parallel id nil))
  ([id opts]
   (merge {:sc/id id :sc/type :parallel
           :sc/states {} :sc/on {} :sc/entry [] :sc/exit []} opts)))

(defn add-state
  "Add a state map into parent's :sc/states (parent may be a chart or compound/parallel)."
  [parent s]
  (assoc-in parent [:sc/states (:sc/id s)] s))

(defn on
  "Add a transition map to a state map on `event`.
  transition: {:sc/target id :sc/cond guard-name :sc/actions [names]}."
  [s event transition]
  (update-in s [:sc/on event] (fnil conj []) transition))

;; --- queries ---

(defn all-states
  "Flat map of {id -> state} for ALL states in chart-or-state (recursive)."
  [chart-or-state]
  (letfn [(collect [states]
            (reduce (fn [acc [id s]]
                      (into (assoc acc id s) (collect (:sc/states s {}))))
                    {}
                    states))]
    (collect (:sc/states chart-or-state {}))))

(defn lookup
  "Find a state by id anywhere in the chart (recursive). nil if not found."
  [chart id]
  (get (all-states chart) id))

(defn atomic?   [s] (= :atomic   (:sc/type s)))
(defn compound? [s] (= :compound (:sc/type s)))
(defn parallel? [s] (= :parallel (:sc/type s)))
(defn final?    [s] (= :final    (:sc/type s)))

(defn- build-parent-map
  "Returns {child-id parent-id} for all states. Top-level states map to nil."
  [chart]
  (letfn [(recurse [parent-id states]
            (reduce (fn [acc [id s]]
                      (into (assoc acc id parent-id)
                            (recurse id (:sc/states s {}))))
                    {}
                    states))]
    (recurse nil (:sc/states chart {}))))

(defn ancestors
  "Sequence of ancestor state ids from immediate parent to outermost.
  Top-level states return []. Requires the root chart as first arg."
  [chart id]
  (let [pm (build-parent-map chart)]
    (loop [current id result []]
      (let [p (get pm current)]
        (if (nil? p)
          result
          (recur p (conj result p)))))))

(defn descendants
  "All descendant state ids of `id` (every nested state, recursive)."
  [chart id]
  (let [s (lookup chart id)]
    (keys (all-states s))))
