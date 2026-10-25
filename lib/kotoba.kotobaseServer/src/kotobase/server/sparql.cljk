(ns kotobase.server.sparql
  "Deprecated compiled-query compatibility parser for IEngine adapters.

  The canonical server handler uses `kotobase.server.sparql-protocol`; this
  namespace remains only for separately versioned adapters that execute the
  compiled-query shape through `kotobase.server.query-exec`.

  SPARQL SUBSET -> the compiled-query shape `kotobase.server.query-exec`
  executes over the map-form Datalog engine (ADR-2607172500's
  `graph.sparql` surface; ADR-2607250100 axis 4, depth pass 2026-07-25).

  Supported, and ONLY this -- an HONEST SUBSET (each unsupported form is
  rejected loudly with the supported grammar in the error, never silently
  misread):

    SELECT ?v ... | SELECT * | SELECT (COUNT(?x) AS ?c) [?v ...]
      aggregates: COUNT | SUM | MIN | MAX | AVG
    WHERE { t . t
            OPTIONAL { t . t }        (left outer join)
            FILTER(?v op lit) }       (op: = != < <= > >=)
    GROUP BY ?v ...
    LIMIT n

    term := ?var | <iri> | \"string\" | 'string' | integer | decimal

  When aggregates are present, every bare SELECT variable must appear in
  GROUP BY (no silent first-of-group). Numeric FILTER comparison applies
  when both sides parse as numbers; lexicographic otherwise -- values are
  stored as wire strings (`tx-edn->quads` stringification), and <iri>/
  quoted/number literals compile to that stored-string form.

  Not supported (rejected): PREFIX/BASE, UNION, GRAPH, ORDER BY,
  DISTINCT, HAVING, property paths, blank nodes, language tags, ^^typed
  literals, subqueries, BIND, VALUES, CONSTRUCT/ASK/DESCRIBE, nested
  OPTIONAL, expressions beyond a single `?var op literal` in FILTER."
  (:require [kotoba.lang.text :as str]))

(def grammar-help
  "supported: SELECT ?v ...|*|(COUNT(?x) AS ?c) WHERE { s p o . OPTIONAL { s p o } FILTER(?v op lit) } | { t } UNION { t } [GROUP BY ?v] [ORDER BY ?v|DESC(?v)] [LIMIT n]; ops: = != < <= > >=; aggs: COUNT SUM MIN MAX AVG")

(defn- fail [msg near]
  (throw (ex-info (str "sparql-subset: " msg " (near: " (pr-str near) "). " grammar-help)
                  {:sparql-subset true})))

(def ^:private token-re
  #"<[^>=\s][^>\s]*>|\"[^\"]*\"|'[^']*'|\?[A-Za-z_][A-Za-z0-9_]*|-?[0-9]+(?:\.[0-9]+)?|\{|\}|\(|\)|\.|!=|<=|>=|=|<|>|[^\s{}()]+")

(defn- tokenize [s] (vec (re-seq token-re s)))

(defn- variable? [t] (str/starts-with? t "?"))

(def ^:private ops {"=" := "!=" :not= "<" :< "<=" :<= ">" :> ">=" :>=})
(def ^:private aggs {"COUNT" :count "SUM" :sum "MIN" :min "MAX" :max "AVG" :avg})

(defn- term->value [t]
  (cond
    (and (str/starts-with? t "<") (str/ends-with? t ">")) (subs t 1 (dec (count t)))
    (and (str/starts-with? t "\"") (str/ends-with? t "\"")) (subs t 1 (dec (count t)))
    (and (str/starts-with? t "'") (str/ends-with? t "'")) (subs t 1 (dec (count t)))
    (re-matches #"-?[0-9]+(?:\.[0-9]+)?" t) t
    :else (fail "unsupported term" t)))

(defn- term->pattern [t]
  (if (variable? t) (symbol t) (term->value t)))

(defn- upper [t] (str/upper (str t)))

(defn- parse-triples
  "Triples separated by '.', stopping when stop? matches. -> [ts patterns]"
  [ts stop?]
  (loop [ts ts current [] acc []]
    (cond
      (empty? ts) (fail "block never closed" "end of query")
      (stop? (first ts))
      (let [acc (if (seq current)
                  (if (= 3 (count current)) (conj acc current)
                      (fail "pattern must have exactly 3 terms" current))
                  acc)]
        [ts acc])
      (= "." (first ts))
      (if (= 3 (count current))
        (recur (rest ts) [] (conj acc current))
        (fail "pattern must have exactly 3 terms" current))
      :else
      (if (= 3 (count current))
        (fail "pattern must have exactly 3 terms (missing '.'?)" (first ts))
        (recur (rest ts) (conj current (term->pattern (first ts))) acc)))))

(defn- parse-where-body
  "After WHERE '{': patterns / OPTIONAL blocks / FILTERs until '}'.
  -> [ts where optionals filters]"
  [ts]
  (loop [ts ts where [] optionals [] filters []]
    (cond
      (empty? ts) (fail "WHERE never closed with }" "end of query")
      (= "}" (first ts)) [(vec (rest ts)) where optionals filters]
      (= "OPTIONAL" (upper (first ts)))
      (let [ts (rest ts)]
        (when-not (= "{" (first ts)) (fail "OPTIONAL must open with {" (first ts)))
        (let [[ts patterns] (parse-triples (rest ts) #(= "}" %))]
          (when (empty? patterns) (fail "OPTIONAL block needs at least one pattern" "{}"))
          (recur (vec (rest ts)) where (conj optionals patterns) filters)))
      (= "FILTER" (upper (first ts)))
      (let [[_ open v op lit close & more] ts]
        (when-not (= "(" open) (fail "FILTER must open with (" open))
        (when-not (and v (variable? v)) (fail "FILTER needs ?var op literal" v))
        (when-not (contains? ops op) (fail "unsupported FILTER operator" op))
        (when-not (and lit (not (contains? #{")" "(" "{" "}"} lit))) (fail "FILTER literal expected" lit))
        (when-not (= ")" close) (fail "FILTER must close with )" close))
        (recur (vec more) where optionals
               (conj filters {:var (symbol v) :op (get ops op) :value (term->value lit)})))
      (= "." (first ts)) (recur (rest ts) where optionals filters)
      (= "{" (first ts))
      ;; braced group chain: { t... } UNION { t... } [UNION { t... }]* --
      ;; stored via a sentinel in `where` meta below (returned separately).
      (let [[ts branches]
            (loop [ts ts branches []]
              (if (= "{" (first ts))
                (let [[ts patterns] (parse-triples (rest ts) #(= "}" %))]
                  (when (empty? patterns) (fail "UNION branch needs at least one pattern" "{}"))
                  (let [ts (vec (rest ts))]
                    (if (and (seq ts) (= "UNION" (upper (first ts))))
                      (recur (vec (rest ts)) (conj branches patterns))
                      [ts (conj branches patterns)])))
                (fail "UNION must be followed by a { } group" (first ts))))]
        (when (< (count branches) 2) (fail "a braced group must be part of a UNION chain" "{ }"))
        (recur ts (vary-meta where assoc ::unions branches) optionals filters))
      :else
      (let [[ts patterns] (parse-triples ts #(or (= "}" %) (= "OPTIONAL" (upper %)) (= "FILTER" (upper %)) (= "{" %)))]
        (recur ts (into where patterns) optionals filters)))))

(defn- parse-select
  "-> [ts find-items star?]; find item = ?var symbol or {:agg :var :as}."
  [ts]
  (loop [ts ts acc [] star? false]
    (cond
      (empty? ts) (fail "missing WHERE" "end of query")
      (= "WHERE" (upper (first ts))) [(vec (rest ts)) acc star?]
      (= "*" (first ts)) (recur (rest ts) acc true)
      (variable? (first ts)) (recur (rest ts) (conj acc (symbol (first ts))) star?)
      (= "(" (first ts))
      (let [[_ agg open v close as c close2 & more] ts]
        (when-not (contains? aggs (upper agg)) (fail "unsupported aggregate" agg))
        (when-not (= "(" open) (fail "aggregate needs (?var)" open))
        (when-not (and v (variable? v)) (fail "aggregate needs a ?var" v))
        (when-not (= ")" close) (fail "aggregate needs (?var)" close))
        (when-not (= "AS" (upper as)) (fail "aggregate needs AS ?alias" as))
        (when-not (and c (variable? c)) (fail "aggregate alias must be a ?var" c))
        (when-not (= ")" close2) (fail "aggregate must close with )" close2))
        (recur (vec more) (conj acc {:agg (get aggs (upper agg)) :var (symbol v) :as (symbol c)}) star?))
      :else (fail "only ?vars, * or (AGG(?v) AS ?a) allowed in SELECT" (first ts)))))

(defn parse
  "SPARQL subset text -> compiled query for kotobase.server.query-exec.
  Throws ex-info {:sparql-subset true} on anything outside the subset."
  [text]
  (let [ts (tokenize (str text))]
    (when (empty? ts) (fail "empty query" ""))
    (when-not (= "SELECT" (upper (first ts))) (fail "must start with SELECT" (first ts)))
    (let [[ts find-items star?] (parse-select (vec (rest ts)))
          _ (when (and (empty? find-items) (not star?)) (fail "SELECT needs ?vars, * or aggregates" "WHERE"))
          _ (when-not (= "{" (first ts)) (fail "WHERE must open with {" (first ts)))
          [ts where optionals filters] (parse-where-body (vec (rest ts)))
          unions (::unions (meta where))
          _ (when (and (seq unions) (seq where))
              (fail "mixing bare triples with a UNION chain in one WHERE is unsupported" "UNION"))
          _ (when (and (empty? where) (empty? unions))
              (fail "WHERE needs at least one triple pattern outside OPTIONAL" "{}"))
          [ts order-by']
          (if (and (seq ts) (= "ORDER" (upper (first ts))))
            (do (when-not (= "BY" (upper (second ts))) (fail "ORDER must be followed by BY" (second ts)))
                (loop [ts (vec (drop 2 ts)) acc []]
                  (cond
                    (and (seq ts) (variable? (first ts)))
                    (recur (vec (rest ts)) (conj acc {:var (symbol (first ts)) :dir :asc}))
                    (and (seq ts) (contains? #{"ASC" "DESC"} (upper (first ts)))
                         (= "(" (second ts)) (variable? (nth ts 2 "")) (= ")" (nth ts 3 nil)))
                    (recur (vec (drop 4 ts))
                           (conj acc {:var (symbol (nth ts 2)) :dir (if (= "DESC" (upper (first ts))) :desc :asc)}))
                    :else (if (empty? acc) (fail "ORDER BY needs ?var / ASC(?var) / DESC(?var)" (first ts)) [ts acc]))))
            [ts []])
          [ts group-by']
          (if (and (seq ts) (= "GROUP" (upper (first ts))))
            (do (when-not (= "BY" (upper (second ts))) (fail "GROUP must be followed by BY" (second ts)))
                (loop [ts (vec (drop 2 ts)) acc []]
                  (if (and (seq ts) (variable? (first ts)))
                    (recur (vec (rest ts)) (conj acc (symbol (first ts))))
                    (if (empty? acc) (fail "GROUP BY needs at least one ?var" (first ts)) [ts acc]))))
            [ts []])
          [ts order-by']
          (if (and (empty? order-by') (seq ts) (= "ORDER" (upper (first ts))))
            (do (when-not (= "BY" (upper (second ts))) (fail "ORDER must be followed by BY" (second ts)))
                (loop [ts (vec (drop 2 ts)) acc []]
                  (cond
                    (and (seq ts) (variable? (first ts)))
                    (recur (vec (rest ts)) (conj acc {:var (symbol (first ts)) :dir :asc}))
                    (and (seq ts) (contains? #{"ASC" "DESC"} (upper (first ts)))
                         (= "(" (second ts)) (variable? (nth ts 2 "")) (= ")" (nth ts 3 nil)))
                    (recur (vec (drop 4 ts))
                           (conj acc {:var (symbol (nth ts 2)) :dir (if (= "DESC" (upper (first ts))) :desc :asc)}))
                    :else (if (empty? acc) (fail "ORDER BY needs ?var / ASC(?var) / DESC(?var)" (first ts)) [ts acc]))))
            [ts order-by'])
          limit
          (cond
            (empty? ts) nil
            (and (= "LIMIT" (upper (first ts))) (= 2 (count ts)) (re-matches #"[0-9]+" (second ts)))
            #?(:clj (Long/parseLong (second ts))
               :cljs (js/parseInt (second ts) 10))
            :else (fail "only GROUP BY / ORDER BY / LIMIT allowed after }" (first ts)))
          all-vars (vec (distinct (concat (filter symbol? (mapcat identity where))
                                          (mapcat (fn [ps] (filter symbol? (mapcat identity ps))) (or unions []))
                                          (mapcat (fn [ps] (filter symbol? (mapcat identity ps))) optionals))))
          find-items (if star? (vec (concat all-vars find-items)) find-items)
          bare-vars (filterv symbol? find-items)
          agg-items (filterv map? find-items)]
      (doseq [v bare-vars]
        (when-not (some #{v} all-vars)
          (fail "SELECT variable not bound in WHERE/OPTIONAL" (str v))))
      (doseq [{:keys [var]} agg-items]
        (when-not (some #{var} all-vars)
          (fail "aggregate variable not bound in WHERE/OPTIONAL" (str var))))
      (doseq [f filters]
        (when-not (some #{(:var f)} all-vars)
          (fail "FILTER variable not bound in WHERE/OPTIONAL" (str (:var f)))))
      (when (and (seq agg-items) (seq bare-vars))
        (doseq [v bare-vars]
          (when-not (some #{v} group-by')
            (fail "with aggregates, every bare SELECT var must be in GROUP BY" (str v)))))
      (doseq [{:keys [var]} order-by']
        (when-not (or (some #{var} (filterv symbol? find-items))
                      (some (fn [it] (and (map? it) (= var (:as it)))) find-items))
          (fail "ORDER BY var must be projected in SELECT" (str var))))
      (cond-> {:find find-items :where (vec where)}
        (seq unions) (assoc :unions unions)
        (seq order-by') (assoc :order-by order-by')
        (seq optionals) (assoc :optionals optionals)
        (seq filters) (assoc :filters filters)
        (seq group-by') (assoc :group-by group-by')
        limit (assoc :limit limit)))))
