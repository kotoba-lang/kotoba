(ns kotoba.ontology-viz.yataverse-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]))

(defn- refusal-reason [f]
  (try
    (f)
    ::no-throw
    (catch #?(:clj clojure.lang.ExceptionInfo
              :cljs :default) e
      (:reason (ex-data e)))))

;; Exact seeded fixture captured from Yataverse PR #83
;; (`createDefaultOntologySnapshot()` -> `buildOntologyGraph(snap)`).
(def yataverse-pr83-fixture
  {"schema" "yataverse.ontology.graph/v1"
   "version" 1
   "basisCid" "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em"
   "id" "yataverse-seeded-kotoba-ontology"
   "stats" {"objectTypes" 2 "connectors" 3 "facts" 4 "quads" 34 "joins" 1}
   "layers" [{"id" "connector" "label" "Connectors" "order" 0 "nodeCount" 3}
             {"id" "object-type" "label" "Object Types" "order" 1 "nodeCount" 2}
             {"id" "fact" "label" "Facts (Provenance-Tagged)" "order" 2 "nodeCount" 4}]
   "nodes" [{"id" "connector:jp.agencies" "label" "jp.agencies" "kind" "connector" "layer" "connector"
             "meta" {"name" "Japan Public Agency Registry" "objectType" "agency" "status" "implemented"}}
            {"id" "connector:jp.geps" "label" "jp.geps" "kind" "connector" "layer" "connector"
             "meta" {"name" "GEPS 落札実績オープンデータ" "objectType" "tender" "status" "implemented"
                     "repo" "https://github.com/kotoba-lang/goyoukiki"}}
            {"id" "connector:jp.kkj" "label" "jp.kkj" "kind" "connector" "layer" "connector"
             "meta" {"name" "kkj.go.jp 官公需情報ポータル 検索API" "objectType" "tender" "status" "implemented"
                     "repo" "https://github.com/kotoba-lang/goyoukiki"}}
            {"id" "type:agency" "label" "agency" "kind" "object-type" "layer" "object-type"
             "meta" {"name" "Procurement Agency" "requiredAttributes" ["jurisdiction" "name"] "key" ["name"]}}
            {"id" "type:tender" "label" "tender" "kind" "object-type" "layer" "object-type"
             "meta" {"name" "Procurement Tender / Opportunity" "requiredAttributes" ["status"] "key" ["status"]}}
            {"id" "fact:agency:ag-digital" "label" "agency:ag-digital" "kind" "fact" "layer" "fact"
             "meta" {"id" "ag-digital" "ontology/type" "agency" "ontology/source" "jp.agencies"
                     "name" "Digital Agency" "jurisdiction" "jp-national"}}
            {"id" "fact:agency:ag-tokyo" "label" "agency:ag-tokyo" "kind" "fact" "layer" "fact"
             "meta" {"id" "ag-tokyo" "ontology/type" "agency" "ontology/source" "jp.agencies"
                     "name" "Tokyo Metropolitan Government" "jurisdiction" "jp-tokyo"}}
            {"id" "fact:tender:geps-2026-042" "label" "tender:geps-2026-042" "kind" "fact" "layer" "fact"
             "meta" {"id" "geps-2026-042" "ontology/type" "tender" "ontology/source" "jp.geps"
                     "ontology/fetched-at" "2026-11-27T00:00:00Z" "ontology/confidence" 0.92
                     "status" "awarded" "title" "Municipal Open-Data Catalog Federation"
                     "jurisdiction" "jp-tokyo" "amount" 8500000}}
            {"id" "fact:tender:kkj-2026-001" "label" "tender:kkj-2026-001" "kind" "fact" "layer" "fact"
             "meta" {"id" "kkj-2026-001" "ontology/type" "tender" "ontology/source" "jp.kkj"
                     "ontology/fetched-at" "2026-11-27T00:00:00Z" "ontology/confidence" 0.96
                     "status" "open" "title" "Content-Addressed Archive Gateway Pilot"
                     "jurisdiction" "jp-national" "amount" 12000000}}]
   "edges" [{"id" "e1" "from" "connector:jp.agencies" "to" "type:agency" "label" "produces" "kind" "provenance"
             "meta" {"connectorId" "jp.agencies" "objectType" "agency"}}
            {"id" "e2" "from" "connector:jp.geps" "to" "type:tender" "label" "produces" "kind" "provenance"
             "meta" {"connectorId" "jp.geps" "objectType" "tender"}}
            {"id" "e3" "from" "connector:jp.kkj" "to" "type:tender" "label" "produces" "kind" "provenance"
             "meta" {"connectorId" "jp.kkj" "objectType" "tender"}}
            {"id" "e4" "from" "type:tender" "to" "type:agency" "label" "tender_with_agency (agency_id=id)" "kind" "join"
             "meta" {"joinName" "tender_with_agency" "kind" "inner" "matchedRows" 2 "coverageRatio" 1}}
            {"id" "e5" "from" "fact:agency:ag-digital" "to" "type:agency" "label" "ontology/type" "kind" "instance"
             "meta" {"source" "jp.agencies"}}
            {"id" "e6" "from" "fact:agency:ag-digital" "to" "connector:jp.agencies" "label" "ontology/source" "kind" "provenance"
             "meta" {"source" "jp.agencies"}}
            {"id" "e7" "from" "fact:agency:ag-tokyo" "to" "type:agency" "label" "ontology/type" "kind" "instance"
             "meta" {"source" "jp.agencies"}}
            {"id" "e8" "from" "fact:agency:ag-tokyo" "to" "connector:jp.agencies" "label" "ontology/source" "kind" "provenance"
             "meta" {"source" "jp.agencies"}}
            {"id" "e9" "from" "fact:tender:geps-2026-042" "to" "type:tender" "label" "ontology/type" "kind" "instance"
             "meta" {"source" "jp.geps"}}
            {"id" "e10" "from" "fact:tender:geps-2026-042" "to" "connector:jp.geps" "label" "ontology/source" "kind" "provenance"
             "meta" {"source" "jp.geps"}}
            {"id" "e11" "from" "fact:tender:kkj-2026-001" "to" "type:tender" "label" "ontology/type" "kind" "instance"
             "meta" {"source" "jp.kkj"}}
            {"id" "e12" "from" "fact:tender:kkj-2026-001" "to" "connector:jp.kkj" "label" "ontology/source" "kind" "provenance"
             "meta" {"source" "jp.kkj"}}
            {"id" "e13" "from" "fact:tender:geps-2026-042" "to" "fact:agency:ag-tokyo" "label" "tender_with_agency" "kind" "join-instance"
             "meta" {"leftKey" "agency_id" "rightKey" "id"}}
            {"id" "e14" "from" "fact:tender:kkj-2026-001" "to" "fact:agency:ag-digital" "label" "tender_with_agency" "kind" "join-instance"
             "meta" {"leftKey" "agency_id" "rightKey" "id"}}]
   "joins" [{"name" "tender_with_agency"
             "leftType" "tender"
             "rightType" "agency"
             "leftKey" "agency_id"
             "rightKey" "id"
             "kind" "inner"
             "leftCount" 2
             "rightCount" 2
             "matchedLeft" 2
             "matchedRows" 2
             "coverageRatio" 1}]
   "coverage" {"byConnector" {"jp.agencies" 2 "jp.geps" 1 "jp.kkj" 1}
               "byObjectType" {"agency" 2 "tender" 2}
               "byJurisdiction" {"jp-national" 2 "jp-tokyo" 2}
               "totalJoins" 1
               "totalMatchedJoinRows" 2}
   "truncated" false})

(deftest yataverse-pr83-roundtrip-and-rendering-test
  (testing "detects Yataverse PR #83 graph and converts cleanly to Kotoba ontology.graph/v1"
    (is (true? (ov/yataverse-graph? yataverse-pr83-fixture)))
    (let [kg (ov/<-yataverse-graph yataverse-pr83-fixture)]
      (is (= "ontology.graph/v1" (:schema/version kg)))
      (is (= "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em"
             (get-in kg [:basis :root-cid])))
      (is (= 9 (count (:nodes kg))))
      (is (= 14 (count (:edges kg))))
      (is (= 1 (count (:joins kg))))
      (is (= :syntax-only (get-in kg [:basis :cid-verification])))
      ;; Round-trip back to Yataverse wire format
      (let [yv (ov/->yataverse-graph kg)]
        (is (= "yataverse.ontology.graph/v1" (:schema yv)))
        (is (= 1 (:version yv)))
        (is (= "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em" (:basisCid yv)))
        (is (= 9 (count (:nodes yv))))
        (is (= 14 (count (:edges yv))))
        (is (every? #(and (string? (:from %)) (string? (:to %)) (map? (:meta %))) (:edges yv)))
        (is (every? #(and (string? (:id %)) (integer? (:nodeCount %))) (:layers yv)))
        (is (= "tender_with_agency" (get-in yv [:joins 0 :name])))
        (is (= 2 (get-in yv [:joins 0 :matchedRows])))
        (is (= 1 (get-in yv [:joins 0 :coverageRatio])))
        (is (= 2 (get-in yv [:coverage "totalMatchedJoinRows"]))))))

  (testing "direct rendering and Semantic UI ops work on raw Yataverse PR #83 fixture"
    (let [svg (ov/render-svg yataverse-pr83-fixture {:title "Yataverse Seeded"})
          html (ov/render-html yataverse-pr83-fixture {:title "Yataverse Seeded"})
          ins (ov/invoke yataverse-pr83-fixture "ontology.inspect" {:node-id "type:tender"})
          vw (ov/invoke yataverse-pr83-fixture "ontology.view" {:format "svg" :title "YV View"})]
      (is (str/includes? svg "data-node-id=\"fact:tender:kkj-2026-001\""))
      (is (str/includes? svg "tender_with_agency"))
      (is (str/includes? html "data-screen-state="))
      (is (str/includes? html "tender_with_agency"))
      (is (true? (:found ins)))
      (is (= 1 (count (:joins ins))))
      (is (= "svg" (:format vw)))
      (is (str/includes? (:content vw) "YV View"))))

  (testing "Yataverse operation adapter returns yataverse.ontology.operations/v1 envelopes"
    (let [g-res (ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph" {})
          i-res (ov/invoke-yataverse yataverse-pr83-fixture "ontology.inspect" {})
          v-res (ov/invoke-yataverse yataverse-pr83-fixture "ontology.view" {:format "all" :title "YV All"})
          s-res (ov/invoke-yataverse yataverse-pr83-fixture "ontology.query_sql"
                                     {:query "SELECT id, kind FROM nodes WHERE layer = 'connector'"})
          q-res (ov/invoke-yataverse yataverse-pr83-fixture "ontology.query_sparql"
                                     {:query "SELECT ?s ?o WHERE { ?s rdf:type ?o } LIMIT 5"})]
      (is (true? (:ok g-res)))
      (is (= "yataverse.ontology.operations/v1" (:schemaVersion g-res)))
      (is (= "yataverse.ontology.graph/v1" (get-in g-res [:result :schema])))
      (is (= 2 (count (get-in i-res [:result :objectTypes]))))
      (is (= 3 (count (get-in i-res [:result :connectors]))))
      (is (some? (get-in v-res [:result :viewModel])))
      (is (string? (get-in v-res [:result :svg])))
      (is (string? (get-in v-res [:result :html])))
      (is (= 3 (get-in s-res [:result :rowCount])))
      (is (= 5 (get-in q-res [:result :rowCount]))))))

(deftest yataverse-negative-validation-test
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph {"schema" "wrong/v1" "version" 1}))))
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph {"schema" "yataverse.ontology.graph/v1" "version" 2}))))
  (is (= :invalid-cid
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "basisCid" "baaaaaaaaaaaaaaaaaaaaaaaa")))))
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "nodes" [{"id" "n1" "kind" "unknown-kind"}]))))))
