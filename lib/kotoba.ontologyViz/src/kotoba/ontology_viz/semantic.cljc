(ns kotoba.ontology-viz.semantic
  "Semantic UI contract (`noun.verb` operations and machine-readable schema),
  fail-closed read-only SQL/SPARQL parsing & execution (with PREFIX expansion,
  full RDF predicate IRIs, typed/language literals, algebraEdn, scannedRows,
  total scan budgets, and basis/visibility enforcement), plus Yataverse PR #83
  operation adapter (`invoke-yataverse`)."
  (:require [clojure.string :as str]
            [kotoba.ontology-viz.graph :as g]
            [kotoba.ontology-viz.svg :as svg]
            [kotoba.ontology-viz.validate :as v]
            [kotoba.ontology-viz.yataverse :as yv]))

(def contract-version "kotoba.semantic-ui/v1")

(def operation-names
  ["ontology.inspect"
   "ontology.graph"
   "ontology.view"
   "ontology.query_sql"
   "ontology.query_sparql"])

(def valid-kind-names
  (vec (sort (map name v/valid-node-kinds))))

(def schema
  "Machine-readable Semantic UI schema declaring the five ontology `noun.verb`
  operations compatible with Kotoba hosts and adaptable to Yataverse PR #83."
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
                                 :cid {:type "string" :description "Optional IPLD CIDv1 to inspect directly"}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter (string or string[])"}
                                 :allowedSources {:type "array" :items {:type "string"}}}
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
     :summary "Return the normalized ontology.graph/v1 projection (nodes, edges, layers, joins, basis) with optional layer/kind/search/visibility filters."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :properties {:layers {:type "array" :items {:type "string"}}
                                 :kinds {:type "array" :items {:type "string" :enum valid-kind-names}}
                                 :query {:type "string"}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                 :allowedSources {:type "array" :items {:type "string"}}}}
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
                                 :kinds {:type "array" :items {:type "string" :enum valid-kind-names}}
                                 :query {:type "string"}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                 :allowedSources {:type "array" :items {:type "string"}}}}
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
                    :anyOf [{:required ["sql"]} {:required ["query"]}]
                    :properties {:sql {:type "string" :description "Read-only SELECT query against nodes, edges, joins, or layers"}
                                 :query {:type "string" :description "Alias of sql for Yataverse PR #83 interop"}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                 :allowedSources {:type "array" :items {:type "string"}}
                                 :limit {:type "integer" :minimum 1 :maximum 500 :default 100}}}
     :output-schema {:type "object"
                     :required ["dialect" "table" "columns" "row-count" "scanned-rows" "rows"]
                     :properties {:dialect {:const "sql-readonly-v1"}
                                  :table {:type "string"}
                                  :columns {:type "array" :items {:type "string"}}
                                  :row-count {:type "integer"}
                                  :scanned-rows {:type "integer"}
                                  :rows {:type "array"}}}}
    {:name "ontology.query_sparql"
     :noun "ontology"
     :verb "query_sparql"
     :summary "Validate and execute a bounded read-only SPARQL SELECT/ASK query over projected ontology triples with PREFIX expansion and SERVICE/LOAD remote fetch disabled."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :anyOf [{:required ["sparql"]} {:required ["query"]}]
                    :properties {:sparql {:type "string" :description "Read-only SPARQL SELECT or ASK query (no SERVICE/LOAD/UPDATE)"}
                                 :query {:type "string" :description "Alias of sparql for Yataverse PR #83 interop"}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                 :allowedSources {:type "array" :items {:type "string"}}
                                 :limit {:type "integer" :minimum 1 :maximum 500 :default 100}}}
     :output-schema {:type "object"
                     :required ["dialect" "form" "vars" "row-count" "algebra-edn" "bindings"]
                     :properties {:dialect {:const "sparql-readonly-v1"}
                                  :form {:type "string" :enum ["SELECT" "ASK"]}
                                  :vars {:type "array" :items {:type "string"}}
                                  :row-count {:type "integer"}
                                  :algebra-edn {:type "string"}
                                  :bindings {:type "array"}}}}]})

(def yataverse-semantic-schema
  "Yataverse PR #83-aligned Semantic UI operations schema (`yataverse.ontology.operations/v1`)."
  {:schema yv/yataverse-operations-schema
   :snapshotSchema "yataverse.ontology.snapshot/v1"
   :graphSchema yv/yataverse-graph-schema
   :protocol "noun.verb"
   :readOnly true
   :operations
   (mapv (fn [op]
           {:operation (:name op)
            :noun (:noun op)
            :verb (:verb op)
            :readOnly (:read-only op)
            :idempotent (:idempotent op)
            :summary (:summary op)
            :inputSchema (:input-schema op)
            :outputSchema (:output-schema op)})
         (:operations schema))})

;; ── Basis Pin & Visibility Enforcement (Fail-Closed) ─────────────────────────

(defn- assert-basis-pin! [graph params]
  (let [basis-param (or (:basis params) (get params "basis"))
        expected-cid (or (:basisCid params)
                         (get params "basisCid")
                         (when (map? basis-param)
                           (or (:basisCid basis-param)
                               (:root-cid basis-param)
                               (:cid basis-param)
                               (get basis-param "basisCid")
                               (get basis-param "cid"))))]
    (when expected-cid
      (v/extract-cid expected-cid)
      (let [actual-cid (get-in graph [:basis :root-cid])]
        (when (not= expected-cid actual-cid)
          (v/fail! :basis-cid-mismatch
                   (str "basisCid mismatch: expected " expected-cid ", got " (pr-str actual-cid))
                   {:expected expected-cid :actual actual-cid}))))))

(defn- node-source [node]
  (or (get-in node [:provenance :source])
      (get-in node [:provenance :connector-id])
      (get-in node [:meta "ontology/source"])
      (when (= :connector (:kind node))
        (if (str/starts-with? (:id node) "connector:")
          (subs (:id node) 10)
          (:id node)))))

(defn- node-jurisdiction [node]
  (or (get-in node [:meta "jurisdiction"])
      (get-in node [:attributes "jurisdiction"])
      (get-in node [:attributes ":jurisdiction"])
      (get-in node [:attributes ":jurisdiction/code"])))

(defn- extract-visibility-field
  "Look up visibility field `kw` / `s` in top-level `params` or nested `:visibility` / `\"visibility\"` map.
  Returns `[present? value]` so explicit `[]` or `nil` is never confused with absent."
  [params kw s]
  (let [vis (or (:visibility params) (get params "visibility"))]
    (cond
      (contains? params kw) [true (get params kw)]
      (contains? params s) [true (get params s)]
      (and (map? vis) (contains? vis kw)) [true (get vis kw)]
      (and (map? vis) (contains? vis s)) [true (get vis s)]
      :else [false nil])))

(defn apply-visibility
  "Enforce `:basisCid`/`:basis` pin and `:allowedSources` / `:jurisdiction`
  visibility constraints (top-level or nested under `:visibility`) fail-closed.

  Crucially:
  - Explicit `:allowedSources []` denies ALL nodes (fail-closed -> 0 nodes/edges).
  - Explicit `:jurisdiction []` denies ALL jurisdiction-bearing nodes (and facts)."
  [graph params]
  (assert-basis-pin! graph params)
  (let [[has-sources? raw-sources] (extract-visibility-field params :allowedSources "allowedSources")
        [has-jur? raw-jur] (extract-visibility-field params :jurisdiction "jurisdiction")]
    (if-not (or has-sources? has-jur?)
      graph
      (let [allowed-sources (when has-sources?
                              (when-not (or (sequential? raw-sources) (set? raw-sources))
                                (v/fail! :invalid-visibility "allowedSources must be a sequence or set" {:allowedSources raw-sources}))
                              (set (map str raw-sources)))
            allowed-jurs (when has-jur?
                           (cond
                             (string? raw-jur) #{raw-jur}
                             (keyword? raw-jur) #{(name raw-jur)}
                             (or (sequential? raw-jur) (set? raw-jur)) (set (map str raw-jur))
                             :else (v/fail! :invalid-visibility "jurisdiction must be string or sequence" {:jurisdiction raw-jur})))
            visible-node? (fn [n]
                            (let [src-ok? (if-not has-sources?
                                            true
                                            (if (empty? allowed-sources)
                                              false
                                              (let [s (node-source n)]
                                                (if (some? s)
                                                  (contains? allowed-sources (str s))
                                                  true))))
                                  jur-ok? (if-not has-jur?
                                            true
                                            (if (empty? allowed-jurs)
                                              false
                                              (let [j (node-jurisdiction n)]
                                                (if (some? j)
                                                  (contains? allowed-jurs (str j))
                                                  (not= :entity (:kind n))))))]
                              (and src-ok? jur-ok?)))
            kept-nodes (vec (filter visible-node? (:nodes graph)))
            kept-ids (set (map :id kept-nodes))
            kept-edges (vec (filter #(and (contains? kept-ids (:source %))
                                          (contains? kept-ids (:target %)))
                                    (:edges graph)))
            kept-layers (g/build-layers kept-nodes)
            updated (-> graph
                        (assoc :nodes kept-nodes
                               :edges kept-edges
                               :layers kept-layers)
                        (update :basis (fn [b]
                                         (-> b
                                             (dissoc :graph-cid :stats :coverage :yataverse-layers)
                                             (assoc :graph-cid-verification :absent
                                                    :node-count (count kept-nodes)
                                                    :edge-count (count kept-edges)
                                                    :layer-count (count kept-layers))))))]
        (g/layout-graph updated (select-keys (:layout graph) [:direction :node-width :node-height :col-gap :row-gap :pad-x :pad-y]))))))

;; ── Portable regex & safe bounded integer parsing ────────────────────────────

(defn- ci-re
  "Compile a case-insensitive dotall regex portably across JVM, bb, nbb, and CLJS."
  [pattern]
  #?(:clj (re-pattern (str "(?is)" pattern))
     :cljs (js/RegExp. pattern "is")))

(def ^:private max-query-limit 500)
(def ^:private max-sparql-intermediate 10000)
(def ^:private max-sparql-scan-steps 100000)

(defn- parse-bounded-positive-int!
  "Strictly parse a positive integer string or integer within [1, max-val]
  portably across JVM Clojure, Babashka, and nbb."
  [raw max-val field reason]
  (let [n (cond
            (integer? raw) raw
            (and (string? raw) (re-matches #"^[0-9]{1,9}$" raw))
            (reduce (fn [acc ch]
                      (+ (* acc 10) (- #?(:clj (int ch) :cljs (.charCodeAt ch 0)) 48)))
                    0
                    raw)
            :else
            (v/fail! reason
                     (str field " must be a positive integer in [1, " max-val "], got: " (pr-str raw))
                     {:field field :value raw :max max-val}))]
    (when-not (<= 1 n max-val)
      (v/fail! reason
               (str field " (" n ") is outside permitted range [1, " max-val "]")
               {:field field :value n :min 1 :max max-val}))
    n))

(defn- extract-query-string! [params primary-key alias-key reason]
  (let [p1 (get params primary-key)
        p2 (get params alias-key)]
    (when (and (some? p1) (some? p2))
      (v/fail! reason
               (str "provide only one of " primary-key " or " alias-key)
               {:keys [primary-key alias-key]}))
    (or p1 p2)))

;; ── Fail-closed SQL validation & bounded local executor ──────────────────────

(def ^:private forbidden-sql-re
  (ci-re "\\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|ATTACH|DETACH|COPY|PRAGMA|EXEC|EXECUTE|CALL|GRANT|REVOKE|VACUUM)\\b"))

(def ^:private select-head-re (ci-re "^SELECT\\s+"))

(def ^:private select-shape-re
  (ci-re "^SELECT\\s+(.+?)\\s+FROM\\s+([A-Za-z_][A-Za-z0-9_]*)(?:\\s+WHERE\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*'([^']*)')?(?:\\s+LIMIT\\s+([0-9]+))?$"))

(def ^:private table-column-schemas
  {"nodes"  #{"id" "label" "kind" "layer" "cid"}
   "edges"  #{"id" "source" "target" "label" "kind" "layer"}
   "joins"  #{"id" "from_attr" "to_attr" "match_rule" "coverage" "status"
              "matched_count" "unmatched_count" "excluded_count"}
   "layers" #{"id" "label" "order" "node_count"}})

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

(defn- parse-sql-columns! [cols-raw table-name]
  (let [allowed (get table-column-schemas table-name)
        trimmed (str/trim cols-raw)]
    (if (= "*" trimmed)
      (vec (sort allowed))
      (let [parts (map str/trim (str/split trimmed #","))]
        (when (some str/blank? parts)
          (v/fail! :unsupported-sql-shape "empty column in SELECT list" {:columns cols-raw}))
        (mapv
         (fn [col]
           (when-not (re-matches #"^[A-Za-z_][A-Za-z0-9_]*$" col)
             (v/fail! :unsupported-sql-shape
                      (str "unsupported SQL column expression or alias: " col)
                      {:column col}))
           (let [lc (str/lower-case col)]
             (when-not (contains? allowed lc)
               (v/fail! :unknown-sql-column
                        (str "unknown column " (pr-str lc) " on table " (pr-str table-name))
                        {:table table-name :column lc :allowed (vec (sort allowed))}))
             lc))
         parts)))))

(defn query-sql
  "Validate and execute a bounded read-only SELECT query over `nodes`, `edges`,
  `joins`, or `layers` of a validated `ontology.graph/v1` (or Yataverse graph)
  after enforcing basis pin and visibility filters."
  [graph-or-yv params]
  (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                  (apply-visibility params))
        sql (extract-query-string! params :sql :query :invalid-sql)
        clean (validate-sql-readonly! sql)
        param-limit (if (contains? params :limit)
                      (parse-bounded-positive-int! (:limit params) max-query-limit :limit :invalid-sql)
                      100)
        m (re-matches select-shape-re clean)]
    (when-not m
      (v/fail! :unsupported-sql-shape
               "supported read-only shape: SELECT <cols|*> FROM <nodes|edges|joins|layers> [WHERE <col> = '<val>'] [LIMIT <n>]"
               {:sql clean}))
    (let [[_ cols-raw table-raw where-col-raw where-val sql-limit-str] m
          table (str/lower-case table-raw)
          rows (table-rows graph table)
          scanned-rows (count rows)
          cols (parse-sql-columns! cols-raw table)
          where-col (when where-col-raw
                      (let [wc (str/lower-case where-col-raw)
                            allowed (get table-column-schemas table)]
                        (when-not (contains? allowed wc)
                          (v/fail! :unknown-sql-column
                                   (str "unknown WHERE column " (pr-str wc) " on table " (pr-str table))
                                   {:table table :column wc :allowed (vec (sort allowed))}))
                        wc))
          effective-limit (if sql-limit-str
                            (min param-limit
                                 (parse-bounded-positive-int! sql-limit-str max-query-limit :sql/limit :invalid-sql))
                            param-limit)
          filtered (if where-col
                     (filterv #(= (str (get % where-col)) where-val) rows)
                     rows)
          limited (vec (take effective-limit filtered))
          projected (mapv #(select-keys % cols) limited)]
      {:dialect "sql-readonly-v1"
       :table table
       :columns cols
       :row-count (count projected)
       :scanned-rows scanned-rows
       :rows projected})))

;; ── Fail-closed SPARQL with PREFIX Expansion, Full RDF Triples & Algebra EDN ─

(def ^:private forbidden-sparql-re
  (ci-re "(?:\\b(?:SERVICE|LOAD|INSERT|DELETE|DROP|CLEAR|CREATE|ADD|MOVE|COPY|SILENT)\\b|\\bFROM\\s+NAMED\\b|\\bFROM\\s+<https?:)"))

(def ^:private sparql-prefix-one-re
  (ci-re "^PREFIX\\s+([A-Za-z0-9_-]*):\\s*<([^>]+)>\\s*"))

(def ^:private sparql-select-full-re
  (ci-re "^SELECT\\s+(\\*|(?:\\?[A-Za-z0-9_]+(?:\\s+\\?[A-Za-z0-9_]+)*))\\s+(?:WHERE\\s*)?\\{([^{}]*)\\}(?:\\s+LIMIT\\s+([0-9]+))?$"))

(def ^:private sparql-ask-full-re
  (ci-re "^ASK\\s*(?:WHERE\\s*)?\\{([^{}]*)\\}$"))

(def ^:private unsupported-sparql-modifier-re
  (ci-re "\\b(OPTIONAL|UNION|FILTER|GRAPH|BIND|VALUES|ORDER\\s+BY|GROUP\\s+BY|HAVING|OFFSET|MINUS|SUBSELECT|CONSTRUCT|DESCRIBE)\\b"))

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
    trimmed))

(def ^:private default-sparql-prefixes
  {"rdf"  "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
   "rdfs" "http://www.w3.org/2000/01/rdf-schema#"
   "xsd"  "http://www.w3.org/2001/XMLSchema#"})

(defn- parse-prefixes
  "Extract all leading `PREFIX p: <iri>` declarations into `[prefix-map remainder]`,
  seeded with standard `rdf:`, `rdfs:`, and `xsd:` prefixes (overridable by query)."
  [query-str]
  (loop [rem (str/trim query-str)
         pmap default-sparql-prefixes]
    (if-let [m (re-find sparql-prefix-one-re rem)]
      (let [[full pfx iri] m]
        (recur (str/trim (subs rem (count full)))
               (assoc pmap pfx iri)))
      [pmap rem])))

(defn- expand-sparql-term
  "Expand a SPARQL token using declared `prefix-map`:
  - `?var` -> unchanged
  - `<iri>` -> `iri`
  - `\"lit\"` / `\"lit\"@lang` / `\"lit\"^^<dt>` -> normalized lexical/typed string
  - `pfx:local` when `pfx` is declared in `prefix-map` -> `(str (get prefix-map pfx) local)`
  - otherwise unchanged token."
  [tok prefix-map]
  (cond
    (str/starts-with? tok "?") tok

    (and (str/starts-with? tok "<") (str/ends-with? tok ">") (>= (count tok) 2))
    (subs tok 1 (dec (count tok)))

    (str/starts-with? tok "\"")
    (if-let [[_ lex suffix] (re-matches #"^\"([^\"]*)\"(.*)$" tok)]
      (cond
        (str/blank? suffix) lex
        (str/starts-with? suffix "@") (str lex suffix)
        (str/starts-with? suffix "^^")
        (let [dt-raw (subs suffix 2)
              dt-exp (expand-sparql-term dt-raw prefix-map)]
          (str lex "^^<" dt-exp ">"))
        :else tok)
      tok)

    (str/includes? tok ":")
    (let [idx (str/index-of tok ":")
          pfx (subs tok 0 idx)
          local (subs tok (inc idx))]
      (if-let [base (get prefix-map pfx)]
        (str base local)
        tok))

    :else tok))

(defn- strip-attr-graph-suffix [k]
  (let [s (str k)]
    (if-let [[_ base] (re-matches #"^(.+?) \[[^\]]+\]$" s)]
      base
      s)))

(defn- strip-literal-decorations [s]
  (cond
    (re-matches #"^(.+)\^\^<[^>]+>$" s) (second (re-matches #"^(.+)\^\^<[^>]+>$" s))
    (re-matches #"^(.+)@[A-Za-z0-9-]+$" s) (second (re-matches #"^(.+)@[A-Za-z0-9-]+$" s))
    :else nil))

(defn- canonical-node-term [node-id]
  (if (and (string? node-id) (str/starts-with? node-id "rdf:"))
    (subs node-id 4)
    (str node-id)))

(defn- graph->triples
  "Project graph nodes, edges (using full `:predicate-iri` when present), and
  node attributes (preserving typed/language-tagged RDF literals and
  multi-valued vectors) into a deduplicated canonical triple stream."
  [graph]
  (let [rdf-type-iri "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
        rdfs-label-iri "http://www.w3.org/2000/01/rdf-schema#label"
        node-base
        (for [n (:nodes graph)
              :let [s (or (get-in n [:attributes :iri])
                          (canonical-node-term (:id n)))]
              t (concat
                 [[s rdf-type-iri (name (or (:kind n) :node))]
                  [s rdfs-label-iri (:label n)]
                  [s "kotoba:layer" (:layer n)]]
                 (when (:cid n) [[s "ipld:cid" (:cid n)]]))]
          t)
        node-attrs
        (for [n (:nodes graph)
              :let [s (or (get-in n [:attributes :iri])
                          (canonical-node-term (:id n)))]
              [k v] (:attributes n)
              :when (and (some? v) (not= k :iri))
              :let [pred-full (strip-attr-graph-suffix (if (keyword? k)
                                                         (if (namespace k) (str ":" (namespace k) "/" (name k)) (str ":" (name k)))
                                                         (str k)))
                    vals (if (sequential? v) v [v])]
              val vals]
          [s pred-full (str val)])
        edge-triples
        (for [e (:edges graph)
              :let [s (canonical-node-term (:source e))
                    o (canonical-node-term (:target e))
                    p (or (get-in e [:metadata :predicate-iri]) (:label e))]]
          [s p o])]
    (vec (distinct (concat node-base node-attrs edge-triples)))))

(defn- sparql-var? [tok]
  (and (string? tok) (str/starts-with? tok "?")))

(defn- constant-term-matches? [pat actual]
  (let [actual-s (str actual)
        pat-clean (canonical-node-term pat)]
    (or (= pat actual-s)
        (= pat-clean actual-s)
        (when-let [bare (strip-literal-decorations actual-s)]
          (= pat bare)))))

(defn- match-sparql-term [pat actual bindings]
  (if (sparql-var? pat)
    (if (contains? bindings pat)
      (when (= (get bindings pat) actual) bindings)
      (assoc bindings pat actual))
    (when (constant-term-matches? pat actual)
      bindings)))

(defn- parse-triple-patterns [where-body prefix-map]
  (when (re-find unsupported-sparql-modifier-re where-body)
    (v/fail! :unsupported-sparql-clause
             "unsupported SPARQL clause inside graph pattern (only flat BGP triple patterns are supported)"
             {:where where-body}))
  (let [raw-tokens (re-seq #"\"[^\"]*\"(?:\^\^(?:<[^>]+>|[A-Za-z0-9_-]*:[A-Za-z0-9_.-]+)|@[A-Za-z0-9-]+)?|<[^>]+>|\?[A-Za-z0-9_]+|[^\s]+" where-body)
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
       (mapv #(expand-sparql-term % prefix-map) tokens))
     all-clauses)))

(defn- eval-bgp-fail-closed
  "Evaluate all BGP triple patterns enforcing BOTH intermediate solution count
  (`max-sparql-intermediate`) AND total candidate scan step budget
  (`max-sparql-scan-steps`), failing closed rather than silently truncating."
  [patterns triples scan-budget]
  (let [steps (volatile! 0)]
    (reduce
     (fn [bs [ps pp po]]
       (let [out (transient [])]
         (doseq [b bs
                 [ts tp to] triples]
           (let [s (vswap! steps inc)]
             (when (> s scan-budget)
               (v/fail! :sparql-scan-limit-exceeded
                        (str "SPARQL scan steps exceeded bound (" scan-budget ")")
                        {:limit scan-budget :pattern [ps pp po]})))
           (when-let [b1 (some->> b
                                  (match-sparql-term ps ts)
                                  (match-sparql-term pp tp)
                                  (match-sparql-term po to))]
             (conj! out b1)
             (when (> (count out) max-sparql-intermediate)
               (v/fail! :sparql-solution-limit-exceeded
                        (str "SPARQL intermediate BGP solution count exceeded bound (" max-sparql-intermediate ")")
                        {:limit max-sparql-intermediate :pattern [ps pp po]}))))
         (persistent! out)))
     [{}]
     patterns)))

(defn- build-algebra-edn
  "Build a deterministic `kotoba.sparql`-compatible EDN algebra string."
  [form patterns proj-vars limit-n]
  (let [bgp {:sparql/op :bgp
             :patterns (mapv (fn [[s p o]]
                               [(if (sparql-var? s) (symbol s) s)
                                (if (sparql-var? p) (symbol p) p)
                                (if (sparql-var? o) (symbol o) o)])
                             patterns)}]
    (pr-str
     (if (= form "ASK")
       {:sparql/op :ask :child bgp}
       (let [proj {:sparql/op :project
                   :vars (mapv symbol proj-vars)
                   :child bgp}]
         (if limit-n
           {:sparql/op :slice :offset 0 :limit limit-n :child proj}
           proj))))))

(defn query-sparql
  "Validate and execute a bounded read-only SPARQL SELECT or ASK BGP query
  against the projected graph triples, expanding PREFIX declarations,
  enforcing basis/visibility constraints, and consuming the entire query
  fail-closed."
  [graph-or-yv params]
  (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                  (apply-visibility params))
        sparql (extract-query-string! params :sparql :query :invalid-sparql)
        clean (validate-sparql-readonly! sparql)
        param-limit (if (contains? params :limit)
                      (parse-bounded-positive-int! (:limit params) max-query-limit :limit :invalid-sparql)
                      100)
        scan-budget (if-let [ms (get-in params [:limits :maxScanSteps])]
                      (parse-bounded-positive-int! ms max-sparql-scan-steps :limits/maxScanSteps :invalid-sparql)
                      max-sparql-scan-steps)
        [prefix-map body-only] (parse-prefixes clean)
        ask-m (re-matches sparql-ask-full-re body-only)
        sel-m (when-not ask-m (re-matches sparql-select-full-re body-only))]
    (when (and (nil? ask-m) (nil? sel-m))
      (if (re-find unsupported-sparql-modifier-re body-only)
        (v/fail! :unsupported-sparql-clause
                 "unsupported SPARQL clause or trailing modifier (supported: PREFIX*, SELECT <vars|*> [WHERE] { <bgp> } [LIMIT n], ASK [WHERE] { <bgp> })"
                 {:sparql clean})
        (v/fail! :unsafe-sparql
                 "invalid or unsupported read-only SPARQL query syntax"
                 {:sparql clean})))
    (let [triples (graph->triples graph)]
      (if ask-m
        (let [patterns (parse-triple-patterns (second ask-m) prefix-map)
              solutions (eval-bgp-fail-closed patterns triples scan-budget)]
          {:dialect "sparql-readonly-v1"
           :form "ASK"
           :vars []
           :ask (boolean (seq solutions))
           :row-count (if (seq solutions) 1 0)
           :algebra-edn (build-algebra-edn "ASK" patterns [] nil)
           :bindings []})
        (let [[_ select-head where-body sparql-limit-str] sel-m
              effective-limit (if sparql-limit-str
                                (min param-limit
                                     (parse-bounded-positive-int! sparql-limit-str max-query-limit :sparql/limit :invalid-sparql))
                                param-limit)
              patterns (parse-triple-patterns where-body prefix-map)
              solutions (eval-bgp-fail-closed patterns triples scan-budget)
              proj-vars (if (= "*" (str/trim select-head))
                          (vec (sort (distinct (mapcat keys solutions))))
                          (vec (re-seq #"\?[A-Za-z0-9_]+" select-head)))
              limited (vec (take effective-limit (map #(select-keys % proj-vars) solutions)))]
          {:dialect "sparql-readonly-v1"
           :form "SELECT"
           :vars proj-vars
           :row-count (count limited)
           :algebra-edn (build-algebra-edn "SELECT" patterns proj-vars effective-limit)
           :bindings limited})))))

;; ── Node Inspection & Operation Dispatch ─────────────────────────────────────

(defn inspect-node
  "Inspect a node by `:node-id` or `:cid` after enforcing basis/visibility."
  [graph-or-yv {:keys [node-id cid] :as params}]
  (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                  (apply-visibility params))
        cid-str (when (some? cid) (v/extract-cid cid))
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

(defn- has-graph-filter? [params]
  (or (some? (:layers params))
      (some? (:kinds params))
      (not (str/blank? (:query params)))))

(defn invoke
  "Dispatch a Semantic UI `noun.verb` operation locally against a validated
  `ontology.graph/v1` (or Yataverse `yataverse.ontology.graph/v1`) graph.

  Distinguishes `nil` from explicit empty `layers: []` / `kinds: []` so
  clearing all layers returns 0 nodes / 0 edges identically to the HTML viewer."
  ([graph-or-yv op params] (invoke graph-or-yv op params {}))
  ([graph-or-yv op params {:keys [render-html-fn]}]
   (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                   (apply-visibility params))]
     (case op
       "ontology.inspect"
       (inspect-node graph params)

       "ontology.graph"
       (if (has-graph-filter? params)
         (g/filter-graph graph params)
         graph)

       "ontology.view"
       (let [fmt (str/lower-case (str (or (:format params) "svg")))
             filtered (if (has-graph-filter? params)
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
                {:operation op :allowed operation-names})))))

;; ── Yataverse PR #83 Operation Adapter ───────────────────────────────────────

(defn- yataverse-snapshot-inspection [graph yv-graph]
  (let [object-types (mapv (fn [n]
                             {:id (if (str/starts-with? (:id n) "type:") (subs (:id n) 5) (:id n))
                              :name (or (get-in n [:meta "name"]) (:label n))
                              :requiredAttributes (or (get-in n [:meta "requiredAttributes"])
                                                      (vec (sort (keys (:attributes n)))))
                              :key (or (:keys n) (get-in n [:meta "key"]) [])})
                           (filter #(= :object-type (:kind %)) (:nodes graph)))
        connectors (mapv (fn [n]
                           {:id (if (str/starts-with? (:id n) "connector:") (subs (:id n) 10) (:id n))
                            :name (or (get-in n [:meta "name"]) (:label n))
                            :objectType (or (get-in n [:meta "objectType"])
                                            (get-in n [:attributes :object-type]))
                            :status (or (get-in n [:meta "status"])
                                        (get-in n [:provenance :status])
                                        "unknown")})
                         (filter #(= :connector (:kind %)) (:nodes graph)))
        block-cids (cond-> {}
                     (:basisCid yv-graph) (assoc :root (:basisCid yv-graph))
                     (:graphCid yv-graph) (assoc :graph (:graphCid yv-graph)))]
    {:basisCid (:basisCid yv-graph)
     :schema (:schema yv-graph)
     :id (:id yv-graph)
     :blockCids block-cids
     :stats (:stats yv-graph)
     :objectTypes object-types
     :connectors connectors
     :joinMappings (:joins yv-graph)
     :tables [{:name "nodes" :rowCount (count (:nodes graph)) :columns (vec (sort (get table-column-schemas "nodes")))}
              {:name "edges" :rowCount (count (:edges graph)) :columns (vec (sort (get table-column-schemas "edges")))}
              {:name "joins" :rowCount (count (:joins graph)) :columns (vec (sort (get table-column-schemas "joins")))}
              {:name "layers" :rowCount (count (:layers graph)) :columns (vec (sort (get table-column-schemas "layers")))}]}))

(defn invoke-yataverse
  "Yataverse PR #83 operation adapter: accepts a Kotoba `ontology.graph/v1` OR
  Yataverse `yataverse.ontology.graph/v1` graph, enforces `:basisCid` pin and
  `:jurisdiction`/`:allowedSources` visibility, dispatches `ontology.graph`,
  `ontology.inspect` (with `blockCids`), `ontology.view` (aligned `viewModel` &
  `yataverse.ontology.operations/v1` `semanticSchema`), `ontology.query_sql`
  (with `scannedRows`), and `ontology.query_sparql` (with `algebraEdn`), and
  returns Yataverse's `yataverse.ontology.operations/v1` envelope."
  ([graph-or-yv op params] (invoke-yataverse graph-or-yv op params {}))
  ([graph-or-yv op params {:keys [render-html-fn]}]
   (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                   (apply-visibility params))
         yv-graph (yv/->yataverse-graph graph)
         basis-cid (:basisCid yv-graph)
         result
         (case op
           "ontology.graph"
           (let [filtered (if (has-graph-filter? params)
                            (g/filter-graph graph params)
                            graph)]
             (yv/->yataverse-graph filtered))

           "ontology.inspect"
           (if (or (:node-id params) (:cid params))
             (assoc (inspect-node graph params)
                    :basisCid basis-cid
                    :blockCids (cond-> {}
                                 basis-cid (assoc :root basis-cid)
                                 (:graphCid yv-graph) (assoc :graph (:graphCid yv-graph))))
             (yataverse-snapshot-inspection graph yv-graph))

           "ontology.view"
           (let [fmt (str/lower-case (str (or (:format params) "all")))
                 _ (when-not (contains? #{"json" "svg" "html" "all"} fmt)
                     (v/fail! :invalid-format
                              (str "expected json|svg|html|all, got: " fmt)
                              {:format fmt :allowed ["json" "svg" "html" "all"]}))
                 filtered (if (has-graph-filter? params)
                            (g/filter-graph graph params)
                            graph)
                 filtered-yv (yv/->yataverse-graph filtered)
                 opts (select-keys params [:title])
                 inspection (yataverse-snapshot-inspection filtered filtered-yv)
                 view-model {:basisCid basis-cid
                             :schema yv/yataverse-graph-schema
                             :id (:id filtered-yv)
                             :stats (:stats filtered-yv)
                             :inspection inspection
                             :graph filtered-yv
                             :operations (mapv (fn [o]
                                                 {:operation (:operation o)
                                                  :noun (:noun o)
                                                  :verb (:verb o)
                                                  :readOnly (:readOnly o)})
                                               (:operations yataverse-semantic-schema))}]
             (cond-> {:basisCid basis-cid
                      :semanticSchema yataverse-semantic-schema
                      :viewModel view-model}
               (or (= fmt "svg") (= fmt "all"))
               (assoc :svg (svg/render-svg filtered opts))

               (or (= fmt "html") (= fmt "all"))
               (assoc :html (if render-html-fn
                              (render-html-fn filtered opts)
                              (v/fail! :renderer-unavailable
                                       "HTML renderer not wired; call kotoba.ontology-viz/invoke-yataverse"
                                       {:format fmt})))))

           "ontology.query_sql"
           (let [res (query-sql graph params)]
             {:basisCid basis-cid
              :columns (:columns res)
              :rows (:rows res)
              :rowCount (:row-count res)
              :scannedRows (:scanned-rows res)
              :readOnly true})

           "ontology.query_sparql"
           (let [res (query-sparql graph params)]
             (cond-> {:basisCid basis-cid
                      :form (:form res)
                      :variables (:vars res)
                      :bindings (:bindings res)
                      :rowCount (:row-count res)
                      :algebraEdn (:algebra-edn res)
                      :readOnly true}
               (contains? res :ask) (assoc :ask (:ask res))))

           (v/fail! :unknown-operation
                    (str "unknown Semantic UI operation: " op)
                    {:operation op :allowed operation-names}))]
     {:ok true
      :operation op
      :schemaVersion yv/yataverse-operations-schema
      :basisCid basis-cid
      :result result})))
