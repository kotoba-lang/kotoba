(ns kotoba.ontology-viz.semantic
  "Semantic UI contract (`noun.verb` operations and machine-readable schema),
  fail-closed read-only SQL/SPARQL parsing & execution (with PREFIX expansion,
  full RDF predicate IRIs, typed/language literals, algebraEdn, scannedRows,
  total scan budgets, and basis/visibility enforcement), plus Yataverse PR #83
  operation adapter (`invoke-yataverse`)."
  (:require [clojure.edn :as edn]
            [clojure.string :as str]
            [kotoba.ontology-viz.escape :as esc]
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
     :summary "Validate and execute a bounded read-only SPARQL SELECT/ASK query (or EDN/JSON algebra) over projected ontology triples with PREFIX expansion and SERVICE/LOAD remote fetch disabled."
     :read-only true
     :idempotent true
     :input-schema {:type "object"
                    :oneOf [{:required ["sparql"]} {:required ["query"]} {:required ["algebraEdn"]} {:required ["algebra"]}]
                    :properties {:sparql {:type "string" :description "Read-only SPARQL SELECT or ASK query (no SERVICE/LOAD/UPDATE)"}
                                 :query {:type "string" :description "Alias of sparql for Yataverse PR #83 interop"}
                                 :algebraEdn {:type "string" :description "kotoba.sparql / Yataverse EDN algebra string using :pattern composition"}
                                 :algebra {:type "object" :description "JSON/map SPARQL algebra object"}
                                 :form {:type "string" :enum ["select" "ask"]}
                                 :basisCid {:type "string"}
                                 :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                 :allowedSources {:type "array" :items {:type "string"}}
                                 :limit {:type "integer" :minimum 1 :maximum 500 :default 100}}}
     :output-schema {:type "object"
                     :required ["dialect" "form" "algebra-edn"]
                     :properties {:dialect {:const "sparql-readonly-v1"}
                                  :form {:type "string" :enum ["select" "ask"]}
                                  :boolean {:type "boolean"}
                                  :vars {:type "array" :items {:type "string"}}
                                  :row-count {:type "integer"}
                                  :algebra-edn {:type "string"}
                                  :bindings {:type "array"}}}}]})

(def yataverse-semantic-schema
  "Yataverse PR #83-aligned Semantic UI operations schema (`yataverse.ontology.operations/v1`)
  for graph-level execution, accurately advertising accepted inputs and lowercase SPARQL forms."
  {:schema yv/yataverse-operations-schema
   :graphSchema yv/yataverse-graph-schema
   :protocol "noun.verb"
   :readOnly true
   :operations
   [{:operation "ontology.graph"
     :noun "ontology"
     :verb "graph"
     :readOnly true
     :idempotent true
     :summary "Project or filter a canonical yataverse.ontology.graph/v1 model with fresh canonical DAG-CBOR graphCid."
     :inputSchema {:type "object"
                   :additionalProperties false
                   :properties {:basisCid {:type "string"}
                                :maxNodes {:type "integer" :minimum 1 :maximum 500}
                                :includeRdfSubjects {:type "boolean"}
                                :activeLayers {:type ["array" "null"] :items {:type "string"}}
                                :layers {:type ["array" "null"] :items {:type "string"}}
                                :kinds {:type "array" :items {:type "string" :enum valid-kind-names}}
                                :query {:type "string"}
                                :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                :allowedSources {:type "array" :items {:type "string"}}
                                :visibility {:type "object"}}}
     :outputSchema {:type "object"
                    :required ["schema" "version" "basisCid" "graphCid" "nodeCount" "meta" "layers" "nodes" "edges" "joins" "coverage"]}}
    {:operation "ontology.inspect"
     :noun "ontology"
     :verb "inspect"
     :readOnly true
     :idempotent true
     :summary "Inspect graph-level object types, connectors, tables, joins, or a single node (honest graph-only scope)."
     :inputSchema {:type "object"
                   :additionalProperties false
                   :properties {:basisCid {:type "string"}
                                :node-id {:type "string"}
                                :cid {:type "string"}
                                :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                :allowedSources {:type "array" :items {:type "string"}}
                                :visibility {:type "object"}}}
     :outputSchema {:type "object"
                    :required ["basisCid" "schema" "inspectionScope" "snapshotClosureVerified" "blockCids"]}}
    {:operation "ontology.view"
     :noun "ontology"
     :verb "view"
     :readOnly true
     :idempotent true
     :summary "Render Yataverse graph viewModel alongside optional standalone SVG and self-contained interactive HTML."
     :inputSchema {:type "object"
                   :additionalProperties false
                   :properties {:basisCid {:type "string"}
                                :format {:type "string" :enum ["json" "svg" "html" "all"] :default "all"}
                                :title {:type "string"}
                                :maxNodes {:type "integer" :minimum 1 :maximum 500}
                                :includeRdfSubjects {:type "boolean"}
                                :activeLayers {:type ["array" "null"] :items {:type "string"}}
                                :layers {:type ["array" "null"] :items {:type "string"}}
                                :kinds {:type "array" :items {:type "string" :enum valid-kind-names}}
                                :query {:type "string"}
                                :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                :allowedSources {:type "array" :items {:type "string"}}
                                :visibility {:type "object"}}}
     :outputSchema {:type "object"
                    :required ["basisCid" "semanticSchema" "viewModel"]}}
    {:operation "ontology.query_sql"
     :noun "ontology"
     :verb "query_sql"
     :readOnly true
     :idempotent true
     :summary "Execute a bounded read-only SQL SELECT query over ontology tables with basis pinning and visibility enforcement."
     :inputSchema {:type "object"
                   :additionalProperties false
                   :anyOf [{:required ["query"]} {:required ["sql"]}]
                   :properties {:basisCid {:type "string"}
                                :query {:type "string"}
                                :sql {:type "string"}
                                :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                :allowedSources {:type "array" :items {:type "string"}}
                                :visibility {:type "object"}
                                :limit {:type "integer" :minimum 1 :maximum 500}
                                :limits {:type "object"}}}
     :outputSchema {:type "object"
                    :required ["basisCid" "columns" "rows" "rowCount" "scannedRows" "readOnly"]}}
    {:operation "ontology.query_sparql"
     :noun "ontology"
     :verb "query_sparql"
     :readOnly true
     :idempotent true
     :summary "Execute a bounded read-only SPARQL query (or kotoba.sparql EDN / JSON algebra) with basis pinning and visibility enforcement."
     :inputSchema {:type "object"
                   :additionalProperties false
                   :oneOf [{:required ["query"]} {:required ["sparql"]} {:required ["algebraEdn"]} {:required ["algebra"]}]
                   :properties {:basisCid {:type "string"}
                                :query {:type "string"}
                                :sparql {:type "string"}
                                :algebraEdn {:type "string"}
                                :algebra {:type "object"}
                                :form {:type "string" :enum ["select" "ask"]}
                                :jurisdiction {:description "Optional jurisdiction visibility filter"}
                                :allowedSources {:type "array" :items {:type "string"}}
                                :visibility {:type "object"}
                                :limit {:type "integer" :minimum 1 :maximum 500}
                                :limits {:type "object"}}}
     :outputSchema {:type "object"
                    :required ["basisCid" "form" "algebraEdn" "readOnly"]
                    :properties {:form {:type "string" :enum ["select" "ask"]}
                                 :boolean {:type "boolean"}
                                 :variables {:type "array"}
                                 :bindings {:type "array"}
                                 :rowCount {:type "integer"}
                                 :algebraEdn {:type "string"}}}}]})

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

(defn- extract-visible-attr-values
  "Extract attribute values from visible `:entity` nodes for native value-matching
  join re-evaluation after visibility/maxNodes filtering."
  [entity-nodes]
  (reduce
   (fn [[obs-global obs-typed] n]
     (let [otype (or (get-in n [:provenance :type])
                     (get-in n [:meta "ontology/type"]))
           attrs (merge (or (:attributes n) {})
                        (into {} (map (fn [[k v]] [(str k) v])) (or (:meta n) {})))]
       (reduce-kv
        (fn [[og ot] k val]
          (let [ks (str k)
                vals (if (sequential? val) val [val])]
            [(update og ks (fnil into []) vals)
             (if otype
               (update ot [(str otype) ks] (fnil into []) vals)
               ot)]))
        [obs-global obs-typed]
        attrs)))
   [{} {}]
   entity-nodes))

(defn- recompute-visible-joins
  "Recompute join counts, coverage, and type-level join edge metadata strictly
  from the visible `kept-nodes` and `kept-edges` so visibility/truncation
  filtering never leaks restricted counts or collapses native value-matching joins."
  [joins kept-nodes kept-edges]
  (let [kept-ids (set (map :id kept-nodes))
        entity-nodes (filter #(= :entity (:kind %)) kept-nodes)
        type-counts (frequencies
                     (keep (fn [n]
                             (or (get-in n [:provenance :type])
                                 (get-in n [:meta "ontology/type"])))
                           entity-nodes))
        join-inst-edges (filter #(= :join-instance (:kind %)) kept-edges)
        [obs-global obs-typed] (extract-visible-attr-values entity-nodes)
        recomputed-joins
        (vec
         (keep
          (fn [j]
            (let [fn-id (:from-node j)
                  tn-id (:to-node j)]
              (when (and (contains? kept-ids fn-id)
                         (contains? kept-ids tn-id))
                (let [jname (or (:name j) (:id j))
                      ltype (or (:from-type j)
                                (when (and (string? fn-id) (str/starts-with? fn-id "type:"))
                                  (subs fn-id 5)))
                      rtype (or (:to-type j)
                                (when (and (string? tn-id) (str/starts-with? tn-id "type:"))
                                  (subs tn-id 5)))
                      matching-edges (filter #(= (:label %) jname) join-inst-edges)
                      native-value-join? (and (nil? (:join-kind j))
                                              (string? (:from-attr j))
                                              (str/starts-with? (:from-attr j) ":")
                                              (string? (:to-attr j))
                                              (str/starts-with? (:to-attr j) ":"))]
                  (if (and native-value-join? (empty? matching-edges))
                    ;; Re-evaluate native Kotoba value-matching join strictly on visible entities
                    (let [re-eval (g/evaluate-join
                                   (cond-> {:id (:id j)
                                            :from-node fn-id
                                            :to-node tn-id
                                            :from-attr (keyword (subs (:from-attr j) 1))
                                            :to-attr (keyword (subs (:to-attr j) 1))
                                            :match-rule (or (:match-rule j) :exact)
                                            :on-ambiguous (or (:on-ambiguous j) :error)
                                            :cardinality (or (:cardinality j) :many-to-one)
                                            :exclude (or (:exclude j) [])}
                                     ltype (assoc :from-type ltype)
                                     rtype (assoc :to-type rtype)
                                     (:mapping j) (assoc :mapping (:mapping j))
                                     (:description j) (assoc :description (:description j)))
                                   obs-global
                                   obs-typed)]
                      (merge j re-eval))
                    ;; Yataverse-style edge-backed join: recount strictly from visible entities & join-instance edges
                    (let [lcnt (get type-counts ltype 0)
                          rcnt (get type-counts rtype 0)
                          matched-left (count (distinct (map :source matching-edges)))
                          matched-rows (count matching-edges)
                          unmatched (max 0 (- lcnt matched-left))
                          cov (when (pos? lcnt)
                                (/ (double matched-left) (double lcnt)))
                          status (cond
                                   (zero? lcnt) :schema-only
                                   (= matched-left lcnt) :full
                                   (pos? matched-left) :partial
                                   :else :unmatched)]
                      (assoc j
                             :total-source-count lcnt
                             :eligible-count lcnt
                             :right-count rcnt
                             :matched-count matched-left
                             :matched-rows matched-rows
                             :unmatched-count unmatched
                             :excluded-count 0
                             :coverage cov
                             :status status
                             :matched-pairs []
                             :unmatched-values []
                             :excluded-values [])))))))
          joins))
        joins-by-name (into {} (map (juxt #(or (:name %) (:id %)) identity)) recomputed-joins)
        joins-by-id (into {} (map (juxt :id identity)) recomputed-joins)
        updated-edges
        (mapv
         (fn [e]
           (if (= :join (:kind e))
             (let [jname (or (get-in e [:metadata "joinName"])
                             (get-in e [:metadata :join-id])
                             (:id e))
                   j (or (get joins-by-name jname)
                         (get joins-by-id jname))]
               (if j
                 (let [mrows (or (:matched-rows j) (:matched-count j) 0)
                       cov-ratio (if (some? (:coverage j))
                                   (let [s (esc/round-int (* (double (:coverage j)) 1000.0))]
                                     (if (zero? (rem s 1000)) (quot s 1000) (/ s 1000.0)))
                                   0)]
                   (update e :metadata
                           (fn [m]
                             (cond-> (or m {})
                               (contains? m "matchedRows") (assoc "matchedRows" mrows)
                               (contains? m "coverageRatio") (assoc "coverageRatio" cov-ratio)
                               (contains? m :matched-count) (assoc :matched-count (:matched-count j))
                               (contains? m :coverage) (assoc :coverage (:coverage j))))))
                 e))
             e))
         kept-edges)]
    [recomputed-joins updated-edges]))

(defn apply-visibility
  "Enforce `:basisCid`/`:basis` pin and `:allowedSources` / `:jurisdiction`
  visibility constraints (top-level or nested under `:visibility`) fail-closed,
  recomputing `:joins`, type-level join edge metadata, and coverage strictly
  over visible nodes.

  Crucially:
  - Explicit `:allowedSources []` denies ALL nodes (fail-closed -> 0 nodes/edges/joins).
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
            raw-kept-edges (vec (filter #(and (contains? kept-ids (:source %))
                                              (contains? kept-ids (:target %)))
                                        (:edges graph)))
            [kept-joins kept-edges] (recompute-visible-joins (:joins graph) kept-nodes raw-kept-edges)
            kept-layers (g/build-layers kept-nodes)
            updated (-> graph
                        (assoc :nodes kept-nodes
                               :edges kept-edges
                               :layers kept-layers
                               :joins kept-joins)
                        (update :basis (fn [b]
                                         (-> b
                                             (dissoc :graph-cid :stats :coverage :yataverse-layers)
                                             (assoc :graph-cid-verification :absent
                                                    :node-count (count kept-nodes)
                                                    :edge-count (count kept-edges)
                                                    :layer-count (count kept-layers)
                                                    :join-count (count kept-joins))))))]
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

(defn- constant-term-matches?
  "Strict RDF term comparison: NEVER falls back to bare lexical matching on
  typed (`^^<dt>`) or language-tagged (`@lang`) literals."
  [pat actual]
  (let [actual-s (str actual)
        pat-clean (canonical-node-term pat)]
    (or (= pat actual-s)
        (= pat-clean actual-s))))

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

(defn- edn-escape-str [s]
  (str "\""
       (-> (str s)
           (str/replace "\\" "\\\\")
           (str/replace "\"" "\\\"")
           (str/replace "\n" "\\n")
           (str/replace "\r" "\\r")
           (str/replace "\t" "\\t"))
       "\""))

(defn- term->edn-str
  "Serialize a SPARQL term into Yataverse `ontology-sparql.mjs` / `kotoba.sparql`
  RDF term map EDN (`?var`, `{:rdf/type :iri :value \"...\"}`, or
  `{:rdf/type :literal :value \"...\" [:datatype ...] [:language ...]}`)."
  [term-info]
  (let [kind (:kind term-info)
        val (:value term-info)]
    (case kind
      :var val
      :iri (str "{:rdf/type :iri :value " (edn-escape-str val) "}")
      :bnode (str "{:rdf/type :bnode :value " (edn-escape-str val) "}")
      :literal (str "{:rdf/type :literal :value " (edn-escape-str val)
                    (when-let [dt (:datatype term-info)]
                      (str " :datatype " (edn-escape-str dt)))
                    (when-let [lg (:language term-info)]
                      (str " :language " (edn-escape-str lg)))
                    "}")
      (edn-escape-str val))))

(defn- parse-sparql-term-info
  "Parse a SPARQL token into both its matching string (`:match`) and its
  Yataverse-compatible RDF term descriptor (`:kind`, `:value`, `:datatype`, `:language`)."
  [tok prefix-map]
  (cond
    (str/starts-with? tok "?")
    {:kind :var :value tok :match tok}

    (and (str/starts-with? tok "<") (str/ends-with? tok ">") (>= (count tok) 2))
    (let [iri (subs tok 1 (dec (count tok)))]
      {:kind :iri :value iri :match iri})

    (str/starts-with? tok "_:")
    {:kind :bnode :value tok :match tok}

    (str/starts-with? tok "\"")
    (if-let [[_ lex suffix] (re-matches #"^\"([^\"]*)\"(.*)$" tok)]
      (cond
        (str/blank? suffix)
        {:kind :literal :value lex :match lex}

        (str/starts-with? suffix "@")
        (let [lang (subs suffix 1)]
          {:kind :literal :value lex :language lang :match (str lex "@" lang)})

        (str/starts-with? suffix "^^")
        (let [dt-raw (subs suffix 2)
              dt-exp (expand-sparql-term dt-raw prefix-map)]
          {:kind :literal :value lex :datatype dt-exp :match (str lex "^^<" dt-exp ">")})

        :else {:kind :literal :value tok :match tok})
      {:kind :literal :value tok :match tok})

    (str/includes? tok ":")
    (let [idx (str/index-of tok ":")
          pfx (subs tok 0 idx)
          local (subs tok (inc idx))]
      (if-let [base (get prefix-map pfx)]
        (let [iri (str base local)]
          {:kind :iri :value iri :match iri})
        {:kind :iri :value tok :match tok}))

    :else
    {:kind :iri :value tok :match tok}))

(defn- build-algebra-edn
  "Build a deterministic `kotoba.sparql` / Yataverse PR #83-compatible EDN
  algebra string using `:pattern` composition and explicit RDF term maps
  (`{:rdf/type :iri :value \"...\"}`, `{:rdf/type :literal ...}`), consumable
  directly by Yataverse `executeSparql(snapshot, { edn })`."
  [form term-patterns proj-vars limit-n]
  (let [pats-str (str/join " "
                           (map (fn [tp]
                                  (str "[" (str/join " " (map term->edn-str tp)) "]"))
                                term-patterns))
        bgp (str "{:sparql/op :bgp :patterns [" pats-str "]}")]
    (if (= form "ask")
      bgp
      (let [proj (str "{:sparql/op :project :vars [" (str/join " " proj-vars) "] :pattern " bgp "}")]
        (if limit-n
          (str "{:sparql/op :slice :offset 0 :limit " limit-n " :pattern " proj "}")
          proj)))))

(defn- algebra-term->info [t]
  (cond
    (symbol? t) {:kind :var :value (name t) :match (name t)}
    (string? t) (if (sparql-var? t)
                  {:kind :var :value t :match t}
                  {:kind :iri :value t :match t})
    (map? t)
    (let [rt (or (:rdf/type t) (:rdfType t) (get t "rdfType") (get t "rdf/type"))
          rt-name (if (keyword? rt) (name rt) (str rt))
          val (or (:value t) (get t "value"))
          lang (or (:language t) (get t "language"))
          dt (or (:datatype t) (get t "datatype"))]
      (cond
        (= rt-name "iri") {:kind :iri :value (str val) :match (str val)}
        (or (= rt-name "blank") (= rt-name "bnode")) {:kind :bnode :value (str val) :match (str val)}
        (= rt-name "literal")
        (cond
          lang {:kind :literal :value (str val) :language (str lang) :match (str val "@" lang)}
          dt (let [dt-s (if (map? dt) (str (or (:value dt) (get dt "value"))) (str dt))]
               {:kind :literal :value (str val) :datatype dt-s :match (str val "^^<" dt-s ">")})
          :else {:kind :literal :value (str val) :match (str val)})
        :else (v/fail! :invalid-sparql-algebra (str "unsupported RDF term map in SPARQL algebra: " (pr-str t)) {:term t})))
    :else (v/fail! :invalid-sparql-algebra (str "unsupported term in SPARQL algebra: " (pr-str t)) {:term t})))

(defn- extract-algebra-spec
  "Normalize a parsed EDN (`{:sparql/op ... :pattern ...}`) or Yataverse JSON
  (`{:op ... :pattern ...}`) SPARQL algebra tree into
  `{:form \"select\"|\"ask\" :patterns [[s p o] ...] :term-patterns [[...] ...] :vars [...] :limit n}`."
  ([node] (extract-algebra-spec node 0 nil nil nil))
  ([node depth form-acc vars-acc limit-acc]
   (when (> depth 16)
     (v/fail! :max-depth-exceeded "SPARQL algebra nesting depth exceeded 16" {:depth depth}))
   (when-not (map? node)
     (v/fail! :invalid-sparql-algebra "SPARQL algebra node must be a map" {:node node}))
   (let [raw-op (or (:sparql/op node) (:op node) (get node "op"))
         op-str (if (keyword? raw-op) (name raw-op) (str raw-op))
         inner (or (:pattern node) (get node "pattern"))]
     (case op-str
       "bgp"
       (let [pats (or (:patterns node) (get node "patterns"))]
         (when-not (and (sequential? pats) (seq pats))
           (v/fail! :invalid-sparql-algebra "BGP algebra requires non-empty :patterns vector" {:node node}))
         (let [term-pats (mapv (fn [p]
                                 (when-not (and (sequential? p) (= 3 (count p)))
                                   (v/fail! :invalid-sparql-algebra "each BGP pattern must have 3 terms [s p o]" {:pattern p}))
                                 (mapv algebra-term->info p))
                               pats)]
           {:form (or form-acc "select")
            :term-patterns term-pats
            :patterns (mapv #(mapv :match %) term-pats)
            :vars vars-acc
            :limit limit-acc}))

       "project"
       (let [raw-vars (or (:vars node) (get node "vars"))
             vs (when (sequential? raw-vars)
                  (mapv (fn [v]
                          (let [s (if (symbol? v) (name v) (str v))]
                            (when-not (sparql-var? s)
                              (v/fail! :invalid-sparql-algebra (str "invalid projected variable: " s) {:var v}))
                            s))
                        raw-vars))]
         (extract-algebra-spec inner (inc depth) (or form-acc "select") vs limit-acc))

       "slice"
       (let [raw-lim (or (:limit node) (get node "limit"))
             raw-off (or (:offset node) (get node "offset"))
             _ (when (and (some? raw-off) (not= 0 raw-off))
                 (v/fail! :unsupported-sparql-clause "non-zero OFFSET is not supported in read-only slice" {:offset raw-off}))
             lim (when (some? raw-lim)
                   (parse-bounded-positive-int! raw-lim max-query-limit :slice/limit :invalid-sparql))]
         (extract-algebra-spec inner (inc depth) form-acc vars-acc (if limit-acc (min limit-acc (or lim limit-acc)) lim)))

       "ask"
       (extract-algebra-spec inner (inc depth) "ask" [] limit-acc)

       (v/fail! :unsupported-sparql-clause
                (str "unsupported SPARQL algebra operator: " op-str)
                {:op op-str})))))

(defn- parse-triple-pattern-infos [where-body prefix-map]
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
       (mapv #(parse-sparql-term-info % prefix-map) tokens))
     all-clauses)))

(defn- parse-algebra-edn! [edn-str]
  (when-not (and (string? edn-str) (not (str/blank? edn-str)))
    (v/fail! :invalid-sparql-algebra "algebraEdn must be a non-empty string" {:algebraEdn edn-str}))
  (when (> (count edn-str) 2048)
    (v/fail! :invalid-sparql-algebra "algebraEdn exceeds 2048 character safety bound" {:length (count edn-str)}))
  (let [parsed (try
                 (edn/read-string edn-str)
                 (catch #?(:clj Exception :cljs :default) e
                   (v/fail! :invalid-sparql-algebra
                            (str "failed to parse algebraEdn: " #?(:clj (.getMessage e) :cljs (.-message e)))
                            {:algebraEdn edn-str})))]
    (v/assert-no-forbidden-wire-keys! parsed)
    parsed))

(defn query-sparql
  "Validate and execute a bounded read-only SPARQL SELECT or ASK BGP query
  (accepting SPARQL text via `:sparql`/`:query`, EDN algebra via `:algebraEdn`,
  or JSON/map algebra via `:algebra`) against the projected graph triples,
  expanding PREFIX declarations, enforcing basis/visibility constraints, and
  returning Yataverse PR #83-compatible lowercase `:form` (`\"select\"`/`\"ask\"`),
  `:boolean` for ASK, and `:pattern`-composed RDF-term-map `:algebra-edn`."
  [graph-or-yv params]
  (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                  (apply-visibility params))
        raw-sparql (or (:sparql params) (:query params))
        _ (when (and (some? (:sparql params)) (some? (:query params)))
            (v/fail! :invalid-sparql-arguments "provide only one of :sparql or :query" {}))
        raw-edn (:algebraEdn params)
        raw-alg (:algebra params)
        provided (+ (if (some? raw-sparql) 1 0)
                    (if (some? raw-edn) 1 0)
                    (if (some? raw-alg) 1 0))
        _ (when-not (= 1 provided)
            (v/fail! :invalid-sparql-arguments
                     "provide exactly one of :sparql/:query, :algebraEdn, or :algebra"
                     {:provided provided}))
        param-limit (if (contains? params :limit)
                      (parse-bounded-positive-int! (:limit params) max-query-limit :limit :invalid-sparql)
                      100)
        scan-budget (if-let [ms (get-in params [:limits :maxScanSteps])]
                      (parse-bounded-positive-int! ms max-sparql-scan-steps :limits/maxScanSteps :invalid-sparql)
                      max-sparql-scan-steps)
        triples (graph->triples graph)]
    (if (some? raw-sparql)
      (let [clean (validate-sparql-readonly! raw-sparql)
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
        (if ask-m
          (let [term-pats (parse-triple-pattern-infos (second ask-m) prefix-map)
                patterns (mapv #(mapv :match %) term-pats)
                solutions (eval-bgp-fail-closed patterns triples scan-budget)
                hit? (boolean (seq solutions))]
            {:dialect "sparql-readonly-v1"
             :form "ask"
             :boolean hit?
             :vars []
             :row-count (if hit? 1 0)
             :algebra-edn (build-algebra-edn "ask" term-pats [] nil)
             :bindings []})
          (let [[_ select-head where-body sparql-limit-str] sel-m
                effective-limit (if sparql-limit-str
                                  (min param-limit
                                       (parse-bounded-positive-int! sparql-limit-str max-query-limit :sparql/limit :invalid-sparql))
                                  param-limit)
                term-pats (parse-triple-pattern-infos where-body prefix-map)
                patterns (mapv #(mapv :match %) term-pats)
                solutions (eval-bgp-fail-closed patterns triples scan-budget)
                proj-vars (if (= "*" (str/trim select-head))
                            (vec (sort (distinct (mapcat keys solutions))))
                            (vec (re-seq #"\?[A-Za-z0-9_]+" select-head)))
                limited (vec (take effective-limit (map #(select-keys % proj-vars) solutions)))]
            {:dialect "sparql-readonly-v1"
             :form "select"
             :vars proj-vars
             :row-count (count limited)
             :algebra-edn (build-algebra-edn "select" term-pats proj-vars effective-limit)
             :bindings limited})))
      ;; Execute EDN or map algebra directly (Yataverse PR #83 interop)
      (let [alg-node (if (some? raw-edn) (parse-algebra-edn! raw-edn) raw-alg)
            _ (when (some? raw-alg) (v/assert-no-forbidden-wire-keys! raw-alg))
            spec (extract-algebra-spec alg-node)
            form (let [f (or (:form params) (:form spec) "select")]
                   (str/lower-case (if (keyword? f) (name f) (str f))))
            term-pats (:term-patterns spec)
            patterns (:patterns spec)
            solutions (eval-bgp-fail-closed patterns triples scan-budget)]
        (if (= form "ask")
          (let [hit? (boolean (seq solutions))]
            {:dialect "sparql-readonly-v1"
             :form "ask"
             :boolean hit?
             :vars []
             :row-count (if hit? 1 0)
             :algebra-edn (build-algebra-edn "ask" term-pats [] nil)
             :bindings []})
          (let [effective-limit (if (:limit spec) (min param-limit (:limit spec)) param-limit)
                proj-vars (if (seq (:vars spec))
                            (:vars spec)
                            (vec (sort (distinct (mapcat keys solutions)))))
                limited (vec (take effective-limit (map #(select-keys % proj-vars) solutions)))]
            {:dialect "sparql-readonly-v1"
             :form "select"
             :vars proj-vars
             :row-count (count limited)
             :algebra-edn (build-algebra-edn "select" term-pats proj-vars effective-limit)
             :bindings limited}))))))

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

(def ^:private max-yataverse-graph-nodes 500)

(def ^:private yv-layer->kotoba-filter-layer
  {"connector" "connector"
   "object-type" "ontology"
   "fact" "instance"
   "rdf-subject" "rdf"
   "ipld" "ipld"
   "attribute" "attribute"})

(defn- resolve-layer-filter-param
  "Resolve `:layers` / `:activeLayers` (or string equivalents). Returns
  `[present? normalized-vec]`.
  - `nil` / omitted => `[false nil]` (show all layers, matching Yataverse `activeLayers: null`).
  - Explicit empty `[]` => `[true []]` (0 nodes / 0 edges)."
  [params map-yv-names?]
  (let [raw-l (if (contains? params :layers) (:layers params) (get params "layers"))
        raw-al (if (contains? params :activeLayers) (:activeLayers params) (get params "activeLayers"))
        has-l? (some? raw-l)
        has-al? (some? raw-al)]
    (when (and has-l? has-al? (not= (vec raw-l) (vec raw-al)))
      (v/fail! :invalid-input "provide consistent :layers / :activeLayers values" {:layers raw-l :activeLayers raw-al}))
    (cond
      (or has-l? has-al?)
      (let [raw (if has-al? raw-al raw-l)]
        (when-not (and (sequential? raw) (every? #(or (string? %) (keyword? %)) raw))
          (v/fail! :invalid-active-layers "layers/activeLayers must be a sequence of layer ID strings" {:layers raw}))
        (let [strs (mapv #(if (keyword? %) (name %) %) raw)
              mapped (if map-yv-names?
                       (mapv #(get yv-layer->kotoba-filter-layer % %) strs)
                       strs)]
          [true mapped]))
      :else [false nil])))

(defn- apply-include-rdf-param [graph params]
  (let [has-rdf? (or (contains? params :includeRdfSubjects) (contains? params "includeRdfSubjects"))
        val (if (contains? params :includeRdfSubjects) (:includeRdfSubjects params) (get params "includeRdfSubjects"))]
    (if-not (and has-rdf? (some? val))
      graph
      (do
        (when-not (boolean? val)
          (v/fail! :invalid-input "includeRdfSubjects must be a boolean" {:includeRdfSubjects val}))
        (if val
          graph
          (let [kept-nodes (vec (remove #(= "rdf" (:layer %)) (:nodes graph)))
                kept-ids (set (map :id kept-nodes))
                raw-edges (vec (filter #(and (contains? kept-ids (:source %))
                                             (contains? kept-ids (:target %)))
                                       (:edges graph)))
                [kept-joins kept-edges] (recompute-visible-joins (:joins graph) kept-nodes raw-edges)
                kept-layers (g/build-layers kept-nodes)]
            (if (= (count kept-nodes) (count (:nodes graph)))
              graph
              (g/layout-graph
               (-> graph
                   (assoc :nodes kept-nodes :edges kept-edges :layers kept-layers :joins kept-joins)
                   (update :basis (fn [b]
                                    (-> b
                                        (dissoc :graph-cid :stats :coverage :yataverse-layers)
                                        (assoc :graph-cid-verification :absent
                                               :node-count (count kept-nodes)
                                               :edge-count (count kept-edges)
                                               :layer-count (count kept-layers)
                                               :join-count (count kept-joins))))))
               (select-keys (:layout graph) [:direction :node-width :node-height :col-gap :row-gap :pad-x :pad-y])))))))))

(defn- apply-max-nodes-bound [graph params]
  (let [raw-max (if (contains? params :maxNodes) (:maxNodes params) (get params "maxNodes"))]
    (if (nil? raw-max)
      graph
      (let [bound (parse-bounded-positive-int! raw-max max-yataverse-graph-nodes :maxNodes :invalid-limit)
            orig-nodes (:nodes graph)]
        (if (<= (count orig-nodes) bound)
          graph
          (let [kept-nodes (vec (take bound orig-nodes))
                kept-ids (set (map :id kept-nodes))
                raw-kept-edges (vec (filter #(and (contains? kept-ids (:source %))
                                                  (contains? kept-ids (:target %)))
                                            (:edges graph)))
                [kept-joins kept-edges] (recompute-visible-joins (:joins graph) kept-nodes raw-kept-edges)
                kept-layers (g/build-layers kept-nodes)
                updated (-> graph
                            (assoc :nodes kept-nodes
                                   :edges kept-edges
                                   :layers kept-layers
                                   :joins kept-joins)
                            (update :basis (fn [b]
                                             (-> b
                                                 (dissoc :graph-cid :stats :coverage :yataverse-layers)
                                                 (assoc :truncated true
                                                        :graph-cid-verification :absent
                                                        :node-count (count kept-nodes)
                                                        :edge-count (count kept-edges)
                                                        :layer-count (count kept-layers)
                                                        :join-count (count kept-joins))))))]
            (g/layout-graph updated (select-keys (:layout graph) [:direction :node-width :node-height :col-gap :row-gap :pad-x :pad-y]))))))))

(defn- apply-graph-filters
  "Apply `:includeRdfSubjects`, `:layers` / `:activeLayers` (explicit `[]` -> 0
  nodes/0 edges/0 joins, `nil` -> all layers), `:kinds`, `:query`, and optional
  `:maxNodes`, recomputing joins, edge metadata, and `truncated` consistently."
  [graph params map-yv-names?]
  (let [g0 (apply-include-rdf-param graph params)
        [has-layers? norm-layers] (resolve-layer-filter-param params map-yv-names?)
        has-kinds? (some? (:kinds params))
        has-query? (not (str/blank? (:query params)))
        filtered (if (or has-layers? has-kinds? has-query?)
                   (let [f0 (g/filter-graph g0
                                            (cond-> (select-keys params [:kinds :query])
                                              has-layers? (assoc :layers norm-layers))
                                            {:verify-graph-cid-fn yv/verify-normalized-graph-cid!})
                         [kept-joins kept-edges] (recompute-visible-joins (:joins f0) (:nodes f0) (:edges f0))]
                     (-> f0
                         (assoc :joins kept-joins :edges kept-edges)
                         (assoc-in [:basis :join-count] (count kept-joins))
                         (assoc-in [:basis :edge-count] (count kept-edges))))
                   g0)]
    (apply-max-nodes-bound filtered params)))

(defn invoke
  "Dispatch a Semantic UI `noun.verb` operation locally against a validated
  `ontology.graph/v1` (or Yataverse `yataverse.ontology.graph/v1`) graph.

  Distinguishes `nil` from explicit empty `layers: []` / `activeLayers: []` /
  `kinds: []` so clearing all layers returns 0 nodes / 0 edges identically to
  the HTML viewer."
  ([graph-or-yv op params] (invoke graph-or-yv op params {}))
  ([graph-or-yv op params {:keys [render-html-fn]}]
   (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                   (apply-visibility params))]
     (case op
       "ontology.inspect"
       (inspect-node graph params)

       "ontology.graph"
       (apply-graph-filters graph params false)

       "ontology.view"
       (let [fmt (str/lower-case (str (or (:format params) "svg")))
             filtered (apply-graph-filters graph params false)
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

(defn- yataverse-graph-inspection
  "Build an honest graph-level inspection payload for `ontology.inspect` when
  operating on a standalone graph (no full snapshot block closure verified).
  Never fabricates snapshot schema or snapshot block closure CIDs."
  [graph yv-graph]
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
        block-cids (if (:graphCid yv-graph)
                     {:graph (:graphCid yv-graph)}
                     {})]
    {:basisCid (:basisCid yv-graph)
     :schema yv/yataverse-graph-schema
     :inspectionScope "graph-only"
     :snapshotClosureVerified false
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

(def ^:private allowed-yataverse-op-params
  {"ontology.graph"
   #{"basisCid" "basis" "maxNodes" "includeRdfSubjects" "activeLayers" "layers"
     "kinds" "query" "jurisdiction" "allowedSources" "visibility"}
   "ontology.inspect"
   #{"basisCid" "basis" "node-id" "cid" "jurisdiction" "allowedSources" "visibility"}
   "ontology.view"
   #{"basisCid" "basis" "format" "title" "maxNodes" "includeRdfSubjects" "activeLayers"
     "layers" "kinds" "query" "jurisdiction" "allowedSources" "visibility"}
   "ontology.query_sql"
   #{"basisCid" "basis" "query" "sql" "limit" "limits" "jurisdiction" "allowedSources" "visibility"}
   "ontology.query_sparql"
   #{"basisCid" "basis" "query" "sparql" "algebraEdn" "algebra" "form" "limit" "limits"
     "jurisdiction" "allowedSources" "visibility"}})

(defn- validate-yataverse-op-params! [op params]
  (when-not (map? (or params {}))
    (v/fail! :invalid-input "operation params must be a map" {:operation op}))
  (when-let [allowed (get allowed-yataverse-op-params op)]
    (doseq [k (keys (or params {}))]
      (let [ks (if (keyword? k) (name k) (str k))]
        (when-not (contains? allowed ks)
          (v/fail! :unsupported-operation-param
                   (str "unsupported parameter " (pr-str ks) " for " op)
                   {:operation op :param ks :allowed (vec (sort allowed))}))))))

(defn invoke-yataverse
  "Yataverse PR #83 operation adapter: accepts a Kotoba `ontology.graph/v1` OR
  Yataverse `yataverse.ontology.graph/v1` graph, enforces `:basisCid` pin,
  `:jurisdiction`/`:allowedSources` visibility, `:activeLayers`/`:layers`
  (explicit `[]` -> 0 nodes/0 edges; `nil`/omitted -> all layers), `:maxNodes`,
  and `:includeRdfSubjects`, refuses unknown or unsupported snapshot-only
  parameters (`:carBase64`, `:apiBase`, etc.) fail-closed, and returns
  Yataverse's `yataverse.ontology.operations/v1` envelope."
  ([graph-or-yv op params] (invoke-yataverse graph-or-yv op params {}))
  ([graph-or-yv op params {:keys [render-html-fn]}]
   (validate-yataverse-op-params! op params)
   (let [graph (-> (svg/normalize-and-validate-graph graph-or-yv)
                   (apply-visibility params))
         yv-graph (yv/->yataverse-graph graph)
         basis-cid (:basisCid yv-graph)
         result
         (case op
           "ontology.graph"
           (let [filtered (apply-graph-filters graph params true)]
             (yv/->yataverse-graph filtered))

           "ontology.inspect"
           (if (or (:node-id params) (:cid params))
             (assoc (inspect-node graph params)
                    :basisCid basis-cid
                    :schema yv/yataverse-graph-schema
                    :inspectionScope "graph-only"
                    :snapshotClosureVerified false
                    :blockCids (if (:graphCid yv-graph) {:graph (:graphCid yv-graph)} {}))
             (yataverse-graph-inspection graph yv-graph))

           "ontology.view"
           (let [fmt (str/lower-case (str (or (:format params) "all")))
                 _ (when-not (contains? #{"json" "svg" "html" "all"} fmt)
                     (v/fail! :invalid-format
                              (str "expected json|svg|html|all, got: " fmt)
                              {:format fmt :allowed ["json" "svg" "html" "all"]}))
                 filtered (apply-graph-filters graph params true)
                 filtered-yv (yv/->yataverse-graph filtered)
                 opts (select-keys params [:title])
                 inspection (yataverse-graph-inspection filtered filtered-yv)
                 view-model {:basisCid basis-cid
                             :schema yv/yataverse-graph-schema
                             :inspectionScope "graph-only"
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
             (if (= "ask" (:form res))
               {:basisCid basis-cid
                :form "ask"
                :boolean (:boolean res)
                :algebraEdn (:algebra-edn res)
                :readOnly true}
               {:basisCid basis-cid
                :form "select"
                :variables (:vars res)
                :bindings (:bindings res)
                :rowCount (:row-count res)
                :algebraEdn (:algebra-edn res)
                :readOnly true}))

           (v/fail! :unknown-operation
                    (str "unknown Semantic UI operation: " op)
                    {:operation op :allowed operation-names}))]
     {:ok true
      :operation op
      :schemaVersion yv/yataverse-operations-schema
      :basisCid basis-cid
      :result result})))
