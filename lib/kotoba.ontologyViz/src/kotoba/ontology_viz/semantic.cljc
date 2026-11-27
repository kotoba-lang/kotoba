(ns kotoba.ontology-viz.semantic
  "Semantic UI contract (`noun.verb` operations and machine-readable schema)
  plus fail-closed local read-only query/inspect execution for Yataverse and
  Kotoba ontology apps."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]))

(def contract-version "kotoba.semantic-ui/v1")

(def operation-names
  ["ontology.inspect"
   "ontology.graph"
   "ontology.view"
   "ontology.query_sql"
   "ontology.query_sparql"])

(def schema
  "Machine-readable Semantic UI schema declaring the five ontology `noun.verb`
  operations compatible with Yataverse and Kotoba hosts."
  {:schema/version contract-version
   :namespace "ontology"
   :read-only true
   :remote-fetch false
   :operations
   [{:name "ontology.inspect"
     :noun "ontology"
     :verb "inspect"
     :summary "Inspect a single ontology node (object type, connector, attribute, entity, RDF resource, or IPLD CID) with adjacent edges and join coverage."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :properties {:node-id {:type "string" :description "Canonical node ID (e.g. type:tender, connector:jp.kkj, ipld:bafy...)"}
                                 :cid {:type "string" :description "Optional IPLD CIDv1 to inspect directly"}}
                    :anyOf [{:required ["node-id"]} {:required ["cid"]}]}
     :output-schema {:type "object"
                     :required ["found" "node" "incoming" "outgoing" "joins"]
                     :properties {:found {:type "boolean"}
                                  :node {:type ["object" "null"]}
                                  :incoming {:type "array"}
                                  :outgoing {:type "array"}
                                  :joins {:type "array"}}}}
    {:name "ontology.graph"
     :noun "ontology"
     :verb "graph"
     :summary "Return the normalized ontology.graph/v1 projection (nodes, edges, layers, joins, basis) with optional layer/kind/search filters."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :properties {:layers {:type "array" :items {:type "string"}}
                                 :kinds {:type "array" :items {:type "string"}}
                                 :query {:type "string"}}}
     :output-schema {:type "object"
                     :required ["schema/version" "schema/kind" "basis" "layers" "nodes" "edges" "joins"]
                     :properties {:schema/version {:const "ontology.graph/v1"}
                                  :schema/kind {:const "ontology.graph"}}}}
    {:name "ontology.view"
     :noun "ontology"
     :verb "view"
     :summary "Render the ontology graph as a zero-dependency standalone SVG or self-contained interactive HTML viewer."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :properties {:format {:type "string" :enum ["svg" "html"] :default "svg"}
                                 :title {:type "string"}
                                 :layers {:type "array" :items {:type "string"}}
                                 :query {:type "string"}}}
     :output-schema {:type "object"
                     :required ["format" "content-type" "content"]
                     :properties {:format {:type "string" :enum ["svg" "html"]}
                                  :content-type {:type "string"}
                                  :content {:type "string"}}}}
    {:name "ontology.query_sql"
     :noun "ontology"
     :verb "query_sql"
     :summary "Validate and execute a bounded read-only SQL SELECT query over projected ontology tables (nodes, edges, joins, layers)."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :required ["sql"]
                    :properties {:sql {:type "string" :description "Read-only SELECT query against nodes, edges, joins, or layers"}
                                 :limit {:type "integer" :minimum 1 :maximum 500 :default 100}}}
     :output-schema {:type "object"
                     :required ["dialect" "table" "columns" "row-count" "rows"]
                     :properties {:dialect {:const "sql-readonly-v1"}
                                  :table {:type "string"}
                                  :columns {:type "array" :items {:type "string"}}
                                  :row-count {:type "integer"}
                                  :rows {:type "array"}}}}
    {:name "ontology.query_sparql"
     :noun "ontology"
     :verb "query_sparql"
     :summary "Validate and execute a bounded read-only SPARQL SELECT/ASK query over projected ontology triples with SERVICE/LOAD remote fetch disabled."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :required ["sparql"]
                    :properties {:sparql {:type "string" :description "Read-only SPARQL SELECT or ASK query (no SERVICE/LOAD/UPDATE)"}
                                 :limit {:type "integer" :minimum 1 :maximum 500 :default 100}}}
     :output-schema {:type "object"
                     :required ["dialect" "form" "vars" "row-count" "bindings"]
                     :properties {:dialect {:const "sparql-readonly-v1"}
                                  :form {:type "string" :enum ["SELECT" "ASK"]}
                                  :vars {:type "array" :items {:type "string"}}
                                  :row-count {:type "integer"}
                                  :bindings {:type "array"}}}}]})

(defn- ci-re
  "Compile a case-insensitive dotall regex portably across JVM, bb, nbb, and CLJS."
  [pattern]
  #?(:clj (re-pattern (str "(?is)" pattern))
     :cljs (js/RegExp. pattern "is")))

;; ── Fail-closed SQL validation & bounded local executor ──────────────────────

(def ^:private forbidden-sql-re
  (ci-re "\\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|ATTACH|DETACH|COPY|PRAGMA|EXEC|EXECUTE|CALL|GRANT|REVOKE|VACUUM)\\b"))

(def ^:private select-head-re (ci-re "^SELECT\\s+"))

(def ^:private select-shape-re
  (ci-re "^SELECT\\s+(.+?)\\s+FROM\\s+([A-Za-z_][A-Za-z0-9_]*)(?:\\s+WHERE\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*'([^']*)')?(?:\\s+LIMIT\\s+(\\d+))?$"))

(defn validate-sql-readonly!
  "Fail closed unless `sql` is a single read-only SELECT statement without
  stacked semicolons, comments hiding payloads, or DDL/DML keywords."
  [sql]
  (when-not (and (string? sql) (not (str/blank? sql)))
    (v/fail! :invalid-sql "SQL query must be a non-empty string" {:sql sql}))
  (when (> (count sql) 2048)
    (v/fail! :invalid-sql "SQL query exceeds 2048 character safety bound" {:length (count sql)}))
  (let [trimmed (str/trim sql)
        no-trailing-semi (str/replace trimmed #";\s*$" "")]
    (when (str/includes? no-trailing-semi ";")
      (v/fail! :unsafe-sql "stacked SQL statements are forbidden" {:sql sql}))
    (when (or (str/includes? no-trailing-semi "--")
              (str/includes? no-trailing-semi "/*"))
      (v/fail! :unsafe-sql "SQL comments are forbidden in read-only contract" {:sql sql}))
    (when (re-find forbidden-sql-re no-trailing-semi)
      (v/fail! :unsafe-sql "mutating or administrative SQL keywords are forbidden" {:sql sql}))
    (when-not (re-find select-head-re no-trailing-semi)
      (v/fail! :unsafe-sql "only SELECT statements are permitted" {:sql sql}))
    no-trailing-semi))

(defn- table-rows [graph table-name]
  (case (str/lower-case table-name)
    "nodes" (mapv (fn [n]
                    {"id" (:id n)
                     "label" (:label n)
                     "kind" (name (or (:kind n) :node))
                     "layer" (:layer n)
                     "cid" (:cid n)})
                  (:nodes graph))
    "edges" (mapv (fn [e]
                    {"id" (:id e)
                     "source" (:source e)
                     "target" (:target e)
                     "label" (:label e)
                     "kind" (name (or (:kind e) :edge))
                     "layer" (:layer e)})
                  (:edges graph))
    "joins" (mapv (fn [j]
                    {"id" (:id j)
                     "from_attr" (:from-attr j)
                     "to_attr" (:to-attr j)
                     "match_rule" (name (or (:match-rule j) :exact))
                     "coverage" (:coverage j)
                     "status" (name (or (:status j) :schema-only))
                     "matched_count" (:matched-count j)
                     "unmatched_count" (:unmatched-count j)
                     "excluded_count" (:excluded-count j)})
                  (:joins graph))
    "layers" (mapv (fn [l]
                     {"id" (:id l)
                      "label" (:label l)
                      "order" (:order l)
                      "node_count" (:node-count l)})
                   (:layers graph))
    (v/fail! :unknown-sql-table
             (str "unknown ontology SQL table: " table-name)
             {:table table-name :allowed ["nodes" "edges" "joins" "layers"]})))

(defn query-sql
  "Validate and execute a bounded read-only SELECT query over `nodes`, `edges`,
  `joins`, or `layers` of a normalized `ontology.graph/v1`."
  [graph {:keys [sql limit] :or {limit 100}}]
  (let [clean (validate-sql-readonly! sql)
        bounded-limit (if (and (integer? limit) (pos? limit)) (min limit 500) 100)
        m (re-matches select-shape-re clean)]
    (when-not m
      (v/fail! :unsupported-sql-shape
               "supported read-only shape: SELECT <cols|*> FROM <nodes|edges|joins|layers> [WHERE <col> = '<val>'] [LIMIT <n>]"
               {:sql clean}))
    (let [[_ cols-raw table where-col where-val sql-limit-str] m
          rows (table-rows graph table)
          filtered (if where-col
                     (filterv #(= (str (get % (str/lower-case where-col))) where-val) rows)
                     rows)
          effective-limit (if sql-limit-str
                            (min bounded-limit #?(:clj (Integer/parseInt sql-limit-str)
                                                  :cljs (js/parseInt sql-limit-str 10)))
                            bounded-limit)
          limited (vec (take effective-limit filtered))
          cols (if (= "*" (str/trim cols-raw))
                 (if-let [first-row (first rows)]
                   (vec (sort (keys first-row)))
                   [])
                 (mapv #(str/lower-case (str/trim %)) (str/split cols-raw #",")))
          projected (if (= "*" (str/trim cols-raw))
                      limited
                      (mapv #(select-keys % cols) limited))]
      {:dialect "sql-readonly-v1"
       :table (str/lower-case table)
       :columns cols
       :row-count (count projected)
       :rows projected})))

;; ── Fail-closed SPARQL validation & bounded local executor ───────────────────

(def ^:private forbidden-sparql-re
  (ci-re "(?:\\b(?:SERVICE|LOAD|INSERT|DELETE|DROP|CLEAR|CREATE|ADD|MOVE|COPY|SILENT)\\b|\\bFROM\\s+NAMED\\b|\\bFROM\\s+<https?:)"))

(def ^:private sparql-prefix-select-ask-re
  (ci-re "^(?:PREFIX\\s+[A-Za-z0-9_-]*:\\s*<[^>]+>\\s*)*(SELECT|ASK)\\b"))

(def ^:private sparql-prefix-strip-re
  (ci-re "^(?:PREFIX\\s+[A-Za-z0-9_-]*:\\s*<[^>]+>\\s*)*"))

(def ^:private sparql-ask-head-re (ci-re "^ASK\\b"))
(def ^:private sparql-where-body-re (ci-re "\\{([^}]*)\\}"))
(def ^:private sparql-select-vars-re (ci-re "^SELECT\\s+(.*?)\\s+WHERE\\b"))

(defn validate-sparql-readonly!
  "Fail closed unless `sparql` is a read-only SELECT or ASK query with no
  SERVICE/LOAD remote federation or SPARQL Update clauses."
  [sparql]
  (when-not (and (string? sparql) (not (str/blank? sparql)))
    (v/fail! :invalid-sparql "SPARQL query must be a non-empty string" {:sparql sparql}))
  (when (> (count sparql) 2048)
    (v/fail! :invalid-sparql "SPARQL query exceeds 2048 character safety bound" {:length (count sparql)}))
  (let [trimmed (str/trim sparql)]
    (when (re-find forbidden-sparql-re trimmed)
      (v/fail! :remote-fetch-forbidden
               "SPARQL SERVICE/LOAD/remote FROM and UPDATE operations are forbidden (offline read-only)"
               {:sparql trimmed}))
    (when-not (re-find sparql-prefix-select-ask-re trimmed)
      (v/fail! :unsafe-sparql "only read-only SELECT or ASK SPARQL queries are permitted" {:sparql trimmed}))
    trimmed))

(defn- graph->triples [graph]
  (concat
   (for [n (:nodes graph)]
     [(:id n) "rdf:type" (name (or (:kind n) :node))])
   (for [n (:nodes graph)]
     [(:id n) "rdfs:label" (:label n)])
   (for [n (:nodes graph) :when (:cid n)]
     [(:id n) "ipld:cid" (:cid n)])
   (for [n (:nodes graph)]
     [(:id n) "kotoba:layer" (:layer n)])
   (for [e (:edges graph)]
     [(:source e) (:label e) (:target e)])))

(defn- sparql-var? [tok]
  (and (string? tok) (str/starts-with? tok "?")))

(defn- unquote-sparql-term [tok]
  (cond
    (and (str/starts-with? tok "\"") (str/ends-with? tok "\"") (>= (count tok) 2))
    (subs tok 1 (dec (count tok)))
    (and (str/starts-with? tok "<") (str/ends-with? tok ">") (>= (count tok) 2))
    (subs tok 1 (dec (count tok)))
    :else tok))

(defn- match-sparql-term [pat actual bindings]
  (if (sparql-var? pat)
    (if (contains? bindings pat)
      (when (= (get bindings pat) actual) bindings)
      (assoc bindings pat actual))
    (when (= (unquote-sparql-term pat) (str actual))
      bindings)))

(defn- parse-triple-patterns [where-body]
  (let [raw-tokens (re-seq #"\"[^\"]*\"|<[^>]+>|\?[A-Za-z0-9_]+|[^\s]+" where-body)
        {:keys [clauses cur]}
        (reduce
         (fn [{:keys [clauses cur]} tok]
           (cond
             (= tok ".")
             {:clauses (if (seq cur) (conj clauses cur) clauses)
              :cur []}

             (and (> (count tok) 1)
                  (str/ends-with? tok ".")
                  (not (str/starts-with? tok "\""))
                  (not (str/starts-with? tok "<")))
             (let [next-cur (conj cur (subs tok 0 (dec (count tok))))]
               {:clauses (conj clauses next-cur)
                :cur []})

             :else
             {:clauses clauses
              :cur (conj cur tok)}))
         {:clauses [] :cur []}
         raw-tokens)
        all-clauses (if (seq cur) (conj clauses cur) clauses)]
    (when (empty? all-clauses)
      (v/fail! :invalid-sparql "SPARQL graph pattern must contain at least one triple pattern"
               {:where where-body}))
    (mapv
     (fn [tokens]
       (when-not (= 3 (count tokens))
         (v/fail! :invalid-sparql
                  (str "expected triple pattern (s p o), got: " (str/join " " tokens))
                  {:tokens tokens}))
       (vec tokens))
     all-clauses)))

(defn query-sparql
  "Validate and execute a bounded read-only SPARQL SELECT or ASK BGP query
  against the projected graph triples."
  [graph {:keys [sparql limit] :or {limit 100}}]
  (let [clean (validate-sparql-readonly! sparql)
        bounded-limit (if (and (integer? limit) (pos? limit)) (min limit 500) 100)
        body-only (str/trim (str/replace clean sparql-prefix-strip-re ""))
        ask? (boolean (re-find sparql-ask-head-re body-only))
        where-m (re-find sparql-where-body-re body-only)]
    (when-not where-m
      (v/fail! :invalid-sparql "SPARQL query must include a { ... } graph pattern" {:sparql clean}))
    (let [patterns (parse-triple-patterns (second where-m))
          triples (graph->triples graph)
          solutions (reduce
                     (fn [bs [ps pp po]]
                       (vec
                        (take (* bounded-limit 4)
                              (for [b bs
                                    [ts tp to] triples
                                    :let [b1 (some->> b
                                                      (match-sparql-term ps ts)
                                                      (match-sparql-term pp tp)
                                                      (match-sparql-term po to))]
                                    :when b1]
                                b1))))
                     [{}]
                     patterns)]
      (if ask?
        {:dialect "sparql-readonly-v1"
         :form "ASK"
         :vars []
         :ask (boolean (seq solutions))
         :row-count (if (seq solutions) 1 0)
         :bindings []}
        (let [select-head (second (re-find sparql-select-vars-re body-only))
              proj-vars (if (or (nil? select-head) (= "*" (str/trim select-head)))
                          (vec (sort (distinct (mapcat keys solutions))))
                          (vec (re-seq #"\?[A-Za-z0-9_]+" select-head)))
              limited (vec (take bounded-limit (map #(select-keys % proj-vars) solutions)))]
          {:dialect "sparql-readonly-v1"
           :form "SELECT"
           :vars proj-vars
           :row-count (count limited)
           :bindings limited})))))

;; ── Node Inspection & Operation Dispatch ─────────────────────────────────────

(defn inspect-node
  "Inspect a node by `:node-id` or `:cid`, returning adjacent edges and joins."
  [graph {:keys [node-id cid]}]
  (let [cid-str (when (some? cid) (v/extract-cid cid))
        target (cond
                 node-id (first (filter #(= (:id %) node-id) (:nodes graph)))
                 cid-str (first (filter #(= (:cid %) cid-str) (:nodes graph)))
                 :else (v/fail! :invalid-input "ontology.inspect requires :node-id or :cid" {}))]
    (if-not target
      {:found false :node nil :incoming [] :outgoing [] :joins []}
      (let [nid (:id target)
            incoming (filterv #(= (:target %) nid) (:edges graph))
            outgoing (filterv #(= (:source %) nid) (:edges graph))
            joins (filterv #(or (= (:from-node %) nid) (= (:to-node %) nid)) (:joins graph))]
        {:found true
         :node target
         :incoming incoming
         :outgoing outgoing
         :joins joins}))))

(defn invoke
  "Dispatch a Semantic UI `noun.verb` operation locally against a normalized
  graph. Accepts optional `render-html-fn` (supplied by `kotoba.ontology-viz`
  facade to avoid circular requires) when invoking `ontology.view` with
  `:format \"html\"`."
  ([graph op params] (invoke graph op params {}))
  ([graph op params {:keys [render-html-fn]}]
   (case op
     "ontology.inspect"
     (inspect-node graph params)

     "ontology.graph"
     (if (or (seq (:layers params)) (seq (:kinds params)) (not (str/blank? (:query params))))
       (g/filter-graph graph params)
       graph)

     "ontology.view"
     (let [fmt (str/lower-case (str (or (:format params) "svg")))
           filtered (if (or (seq (:layers params)) (not (str/blank? (:query params))))
                      (g/filter-graph graph params)
                      graph)
           opts (select-keys params [:title])]
       (case fmt
         "svg" {:format "svg"
                :content-type "image/svg+xml"
                :content (svg/render-svg filtered opts)}
         "html" (if render-html-fn
                  {:format "html"
                   :content-type "text/html; charset=utf-8"
                   :content (render-html-fn filtered opts)}
                  (v/fail! :renderer-unavailable
                           "HTML renderer not wired; call kotoba.ontology-viz/invoke for ontology.view html"
                           {:format fmt}))
         (v/fail! :invalid-format
                  (str "unsupported ontology.view format: " fmt)
                  {:format fmt :allowed ["svg" "html"]})))

     "ontology.query_sql"
     (query-sql graph params)

     "ontology.query_sparql"
     (query-sparql graph params)

     (v/fail! :unknown-operation
              (str "unknown Semantic UI operation: " op)
              {:operation op :allowed operation-names}))))
