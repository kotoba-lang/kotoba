;; etzhayyim.kotoba.query — a Datalog subset over the live EAVT triple set.
;;
;; Supports the access patterns the religious-corp actors actually use:
;;   {:find  [?sym ...]
;;    :in    [?param ...]          ; optional positional inputs
;;    :where [[?e :attr ?v]        ; data pattern (e a v); _ = wildcard
;;            [?e :other const]    ; constants bind/filter
;;            [(pred ?x ?y)]]}     ; predicate clause (allowlisted fns)
;;
;; Symbols beginning with ? are logic vars; _ is an ignored wildcard; anything
;; else is a constant. Joins are nested-loop over partially-bound clauses —
;; correct and adequate for a reference engine; kotoba-kqe is the production
;; arrangement-join path.

(ns etzhayyim.kotoba.query
  (:require [kotoba.lang.text :as str]
            [etzhayyim.kotoba.datom :as d]))

(defn- lvar? [x] (and (symbol? x) (str/starts-with? (name x) "?")))
(defn- wildcard? [x] (= '_ x))

;; Allowlisted predicate fns usable in [(pred ...)] clauses.
(def ^:private predicates
  {'=  =, 'not= not=, '<  <, '>  >, '<= <=, '>= >=
   'contains? (fn [coll x] (boolean (some #{x} coll)))
   'includes? (fn [s sub] (and (string? s) (str/includes? s (str sub))))
   'starts-with? (fn [s p] (and (string? s) (str/starts-with? s (str p))))})

(defn- resolve-term
  "Resolve a clause term against the current binding map. Logic vars resolve to
   their bound value or ::unbound; wildcards to ::wildcard; constants to self."
  [term binds]
  (cond
    (wildcard? term) ::wildcard
    (lvar? term)     (get binds term ::unbound)
    :else            term))

(defn- match-pattern
  "Given a data pattern [e a v] and the current bindings, return the seq of
   extended binding maps produced by unifying the pattern against `triples`."
  [triples [pe pa pv] binds]
  (let [re (resolve-term pe binds)
        ra (resolve-term pa binds)
        rv (resolve-term pv binds)]
    (for [[te ta tv] triples
          :when (and (or (#{::unbound ::wildcard} re) (= re te))
                     (or (#{::unbound ::wildcard} ra) (= ra ta))
                     (or (#{::unbound ::wildcard} rv) (= rv tv)))]
      (cond-> binds
        (and (lvar? pe) (= ::unbound re)) (assoc pe te)
        (and (lvar? pa) (= ::unbound ra)) (assoc pa ta)
        (and (lvar? pv) (= ::unbound rv)) (assoc pv tv)))))

(defn- apply-predicate
  "Filter bindings through a [(pred arg ...)] clause. Unbound vars => drop."
  [[expr] binds]
  (let [[pf & args] expr
        f (predicates pf)]
    (when (nil? f)
      (throw (ex-info (str "unsupported predicate: " pf
                           " (allowlist: " (keys predicates) ")")
                      {:pred pf})))
    (let [vals (map #(resolve-term % binds) args)]
      (if (some #{::unbound ::wildcard} vals)
        false
        (boolean (apply f vals))))))

(defn- predicate-clause? [clause]
  (and (vector? clause) (= 1 (count clause)) (list? (first clause))))

(defn- not-clause? [c] (and (seq? c) (= 'not (first c))))
(defn- or-clause?  [c] (and (seq? c) (= 'or (first c))))
(defn- and-clause? [c] (and (seq? c) (= 'and (first c))))

(defn- step
  "Advance the seq of binding maps through one where-clause. Besides data
   patterns and [(pred …)] predicates, supports:
     (not <clause>)         negation-as-failure: keep bindings the clause can't extend
     (or  <clause> …)       disjunction: union of bindings each branch satisfies
     (and <clause> …)       conjunction (mainly as an `or` branch)"
  [triples binds-seq clause]
  (cond
    (not-clause? clause)
    (let [inner (second clause)]
      (filter (fn [b] (empty? (step triples [b] inner))) binds-seq))

    (or-clause? clause)
    (->> binds-seq
         (mapcat (fn [b] (mapcat (fn [br] (step triples [b] br)) (rest clause))))
         distinct)

    (and-clause? clause)
    (reduce (partial step triples) binds-seq (rest clause))

    (predicate-clause? clause)
    (filter #(apply-predicate clause %) binds-seq)

    :else
    (mapcat #(match-pattern triples clause %) binds-seq)))

;; ── aggregates (Datomic-style :find grouping) ──
(def ^:private aggregates
  {'count          count
   'count-distinct (fn [xs] (count (distinct xs)))
   'sum            (fn [xs] (reduce + 0 xs))
   'min            (fn [xs] (when (seq xs) (apply min xs)))
   'max            (fn [xs] (when (seq xs) (apply max xs)))
   'avg            (fn [xs] (when (seq xs) (/ (reduce + 0 xs) (count xs))))
   'distinct       (fn [xs] (vec (distinct xs)))})

(defn- agg-element? [el] (and (seq? el) (contains? aggregates (first el))))

(defn- aggregate-result
  "Group `solved` bindings by the non-aggregate find vars, then apply each
   aggregate over its group (Datomic semantics)."
  [find solved]
  (let [group-vars (vec (filter symbol? find))
        groups (group-by (fn [b] (mapv b group-vars)) solved)]
    (into #{}
          (for [[gkey rows] groups
                :let [gmap (zipmap group-vars gkey)]]
            (mapv (fn [el]
                    (if (agg-element? el)
                      (let [[afn avar] el]
                        ((aggregates afn) (map #(get % avar) rows)))
                      (get gmap el)))
                  find)))))

(defn q
  "Run a Datalog query over `live` (a set/seq of [e a v] triples).
   `inputs` bind positional :in vars. Returns a set of result tuples (vectors
   in :find order). :find may contain aggregate forms — (count ?e), (sum ?x),
   (min ?x), (max ?x), (avg ?x), (count-distinct ?e), (distinct ?x) — which
   group by the remaining (non-aggregate) find vars."
  [query live & inputs]
  (let [{:keys [find in where]} query
        triples (vec live)
        init    (if (seq in)
                  [(zipmap in inputs)]
                  [{}])
        solved  (reduce (partial step triples) init where)]
    (if (some agg-element? find)
      (aggregate-result find solved)
      (->> solved
           (map (fn [b] (mapv #(get b %) find)))
           (into #{})))))

(defn q1
  "Convenience: first column of the first result row, or nil."
  [query live & inputs]
  (some-> (apply q query live inputs) first first))
