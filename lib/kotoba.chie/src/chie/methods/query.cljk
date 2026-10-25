(ns chie.methods.query
  "chie 智慧 — knowledge-graph query interface over the AI-ecosystem graph (ADR-2606171200).

  Maturity / usability: the kotoba Datom EDN is a knowledge graph, not a flat list — this
  module exposes the practical observatory queries that prove it (the point of the Datalog
  substrate). All queries are pure graph traversals over the loaded {:nodes :edges}; nothing
  is stored, nothing mutates (N1). The 取-concentration queries reuse chie.methods.analyze so
  every answer is the same on-read integral the report uses — no second source of truth.

    node / label                  — a node map / its display label
    incident (id)                 — {:inbound :outbound} 縁 of a node
    funders-of (lab)              — :invests-in sources (capital) into a lab
    compute-suppliers-of (lab)    — :compute-deal sources (compute) into a lab
    governed-by (lab)             — :governs / :sets-standard sources (policy reach) over a node
    rounds-of (lab)               — :ai.invest/round nodes linked to a lab
    subsidiaries (parent)         — nodes that :organism/nests-in the parent
    concentration-in (axis)       — ranked accumulators on one axis (compute/capital/talent/policy)
    opening-worklist              — ranked :bond/opening-priority (who most needs OPENING)

  CONSTITUTIONAL: G1 — OPENING map, never a winner-rank; queries surface accumulation routed
  to opening, never a capability/forecast verdict (N3/G4). Persons only as public-role nodes."
  (:require [chie.methods.analyze :as analyze]))

(defn node [nodes id] (get nodes id))
(defn label [nodes id] (get-in nodes [id ":organism/label"] id))

(defn incident
  "All 縁 touching `id`, split by direction."
  [edges id]
  {:inbound  (filterv #(= id (get % ":en/to")) edges)
   :outbound (filterv #(= id (get % ":en/from")) edges)})

(defn- sources-by-kind
  "Source ids of edges of any kind in `kinds` whose :en/to = `dst`, sorted."
  [edges dst kinds]
  (sort (set (for [e edges
                   :when (and (contains? kinds (get e ":en/kind"))
                              (= dst (get e ":en/to")))]
               (get e ":en/from")))))

(defn funders-of          [edges lab] (sources-by-kind edges lab #{":invests-in"}))
(defn compute-suppliers-of [edges lab] (sources-by-kind edges lab #{":compute-deal"}))
(defn governed-by         [edges lab] (sources-by-kind edges lab #{":governs" ":sets-standard"}))

(defn rounds-of
  "Round nodes (:ai.invest/round) structurally linked to `lab` (round → lab :partners edge)."
  [nodes edges lab]
  (sort (set (for [e edges
                   :when (and (= ":partners" (get e ":en/kind"))
                              (= lab (get e ":en/to"))
                              (= ":ai.invest/round" (get-in nodes [(get e ":en/from") ":organism/kind"])))]
               (get e ":en/from")))))

(defn subsidiaries
  "Node ids that :organism/nests-in `parent`, sorted."
  [nodes parent]
  (sort (for [[nid n] nodes :when (= parent (get n ":organism/nests-in"))] nid)))

(defn concentration-in
  "Ranked [id label load] accumulators on one axis (reuses the analyze integral)."
  ([nodes edges axis] (concentration-in nodes edges axis 10))
  ([nodes edges axis limit]
   (let [res (analyze/analyze nodes edges)
         d (into {} (keep (fn [[nid m]] (when-let [v (get m axis)] [nid v]))
                          (:concentration res)))]
     (analyze/rank d nodes limit))))

(defn opening-worklist
  "Ranked [id label opening-priority] — the actionable 'who most needs OPENING' list."
  ([nodes edges] (opening-worklist nodes edges 10))
  ([nodes edges limit]
   (analyze/rank (:opening (analyze/analyze nodes edges)) nodes limit)))

;; ── cross-axis lenses (the 4th per-axis source lens + the multi-axis OPENING synthesis) ──────
(defn talent-sources-of
  "Source ids on the TALENT axis (:talent-flow edges) into `lab` — the 4th per-axis source lens,
  completing funders-of (capital) / compute-suppliers-of (compute) / governed-by (policy) so all
  four concentration axes have a who-feeds-this-node query."
  [edges lab] (sources-by-kind edges lab #{":talent-flow"}))

(def ^:private all-axes [:compute :capital :talent :policy])

(defn axis-profile
  "The per-axis 取-accumulation a single entity bears, as a COMPLETE {:compute :capital :talent
  :policy} map (0.0 on any axis it bears no accumulation). This is the cross-axis breakdown of one
  node's incident inbound load that the single-axis `concentration-in` cannot show. Factual (G2 —
  the edge integral computed on read), never a verdict (N3/G4)."
  [nodes edges id]
  (let [m (get-in (analyze/analyze nodes edges) [:concentration id] {})]
    (into {} (for [ax all-axes] [ax (double (get m ax 0.0))]))))

(defn multi-axis-chokepoints
  "The cross-axis OPENING lens: entities whose CLOSED 取-concentration spans the MOST axes at once.
  A node accumulating across compute AND capital AND policy is a higher SYSTEMIC opening priority
  than one dominating a single axis with a bigger number — which a per-axis ranking
  (`concentration-in`) cannot surface. Each axis load is openness-discounted (× the node's
  opening/total = 1−openness factor), so a fully-OPEN multi-axis accumulator scores breadth 0 and
  drops out (G1 — an open accumulator is never an opening target). Ranked
  [id label axis-breadth opening-load profile] by (breadth desc, opening-load desc). Routes to
  OPENING, never a winner-rank / capability-grade (G1/G4)."
  ([nodes edges] (multi-axis-chokepoints nodes edges 10))
  ([nodes edges limit]
   (let [{:keys [concentration total opening]} (analyze/analyze nodes edges)]
     (->> concentration
          (keep (fn [[id m]]
                  (let [t (get total id 0.0)
                        factor (if (pos? t) (/ (get opening id 0.0) t) 0.0)   ; = 1 − openness
                        open-axes (into {} (for [[ax v] m :let [ov (* v factor)] :when (> ov 0.0)]
                                             [ax ov]))]
                    (when (seq open-axes)
                      [id (label nodes id) (count open-axes)
                       (reduce + 0.0 (vals open-axes)) open-axes]))))
          (sort-by (fn [[_ _ breadth load _]] [(- breadth) (- load)]))
          (take limit)
          vec))))

#?(:clj
   (defn -main
     "CLI: a few example queries over the seed (file I/O at the edge)."
     [& argv]
     (let [here (-> *file* clojure.java.io/file .getParentFile .getParentFile .getParentFile .getParentFile)
           seed (clojure.java.io/file here "data" "seed.edn")
           {:keys [nodes edges]} (analyze/load-file* seed)
           lab (or (first argv) "ai.lab.openai")]
       (println (str "funders-of " lab ": " (funders-of edges lab)))
       (println (str "compute-suppliers-of " lab ": " (compute-suppliers-of edges lab)))
       (println (str "governed-by " lab ": " (governed-by edges lab)))
       (println (str "rounds-of " lab ": " (rounds-of nodes edges lab)))
       (println (str "opening-worklist (top 3): "
                     (mapv second (opening-worklist nodes edges 3))))
       0)))
