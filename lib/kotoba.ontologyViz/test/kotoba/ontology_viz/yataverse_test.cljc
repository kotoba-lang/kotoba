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

;; Exact official reference fixture from Yataverse PR #83 (HEAD ef29596b):
;; `test/fixtures/ontology-graph-v1.json`.
(def yataverse-pr83-fixture
  {"schema" "yataverse.ontology.graph/v1"
   "version" 1
   "basisCid" "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em"
   "id" "yataverse-seeded-kotoba-ontology"
   "stats" {"objectTypes" 2 "connectors" 3 "facts" 4 "quads" 34 "joins" 1}
   "nodeCount" 9
   "meta" {"id" "yataverse-seeded-kotoba-ontology"
           "snapshotSchema" "yataverse.ontology.snapshot/v1"
           "stats" {"objectTypes" 2 "connectors" 3 "facts" 4 "quads" 34 "joins" 1}
           "nodeCount" 9
           "edgeCount" 14
           "layerCount" 3
           "truncated" false
           "edgesTruncated" false}
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
   "truncated" false
   "edgesTruncated" false
   "graphCid" "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq"})

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
      (is (= :verified (get-in kg [:basis :graph-cid-verification])))
      ;; Exact array order is preserved (e1, e2, ..., e14 — NOT e1, e10, ...)
      (is (= ["e1" "e2" "e3" "e4" "e5" "e6" "e7" "e8" "e9" "e10" "e11" "e12" "e13" "e14"]
             (mapv :id (:edges kg))))
      (is (= (mapv #(get % "id") (get yataverse-pr83-fixture "nodes"))
             (mapv :id (:nodes kg))))
      ;; Round-trip back to Yataverse PR #83 (HEAD ef29596b) wire format
      (let [yv (ov/->yataverse-graph kg)
            {:keys [cid bytes byte-length]} (ov/encode-ontology-graph-dag-cbor yv)]
        (is (= "yataverse.ontology.graph/v1" (:schema yv)))
        (is (= 1 (:version yv)))
        (is (= "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em" (:basisCid yv)))
        (is (= "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq" (:graphCid yv)))
        (is (= "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq" cid)
            "canonical DAG-CBOR CID of round-tripped graph must match Yataverse PR #83 byte-for-byte")
        (is (= 4588 byte-length)
            "canonical DAG-CBOR byte length must match Yataverse PR #83 encodeOntologyGraphDagCbor")
        (is (= [0xae 0x62 0x69 0x64 0x78 0x20 0x79 0x61 0x74 0x61 0x76 0x65 0x72 0x73 0x65 0x2d]
               (subvec bytes 0 16))
            "canonical DAG-CBOR header bytes must match Yataverse PR #83 exactly")
        (is (= ["e1" "e2" "e3" "e4" "e5" "e6" "e7" "e8" "e9" "e10" "e11" "e12" "e13" "e14"]
               (mapv :id (:edges yv))))
        (is (= (mapv #(get % "id") (get yataverse-pr83-fixture "nodes"))
               (mapv :id (:nodes yv))))
        (is (= 9 (:nodeCount yv)))
        (is (= false (:truncated yv)))
        (is (= false (:edgesTruncated yv)))
        (is (= {:id "yataverse-seeded-kotoba-ontology"
                :snapshotSchema "yataverse.ontology.snapshot/v1"
                :stats {"objectTypes" 2 "connectors" 3 "facts" 4 "quads" 34 "joins" 1}
                :nodeCount 9
                :edgeCount 14
                :layerCount 3
                :truncated false
                :edgesTruncated false}
               (:meta yv)))
        (is (= 9 (count (:nodes yv))))
        (is (= 14 (count (:edges yv))))
        (is (every? #(and (string? (:from %)) (string? (:to %)) (map? (:meta %))) (:edges yv)))
        (is (every? #(and (string? (:id %)) (integer? (:nodeCount %))) (:layers yv)))
        (is (= "tender_with_agency" (get-in yv [:joins 0 :name])))
        (is (= 2 (get-in yv [:joins 0 :matchedRows])))
        (is (= 1 (get-in yv [:joins 0 :coverageRatio])))
        (is (= 2 (get-in yv [:coverage "totalMatchedJoinRows"]))))

      ;; Filtered / modified graph must NEVER inherit stale graphCid; it must recompute fresh CID
      (let [filtered-kg (ov/filter-graph kg {:layers ["connector" "ontology"]})
            filtered-yv (ov/->yataverse-graph filtered-kg)
            {recomputed :cid} (ov/encode-ontology-graph-dag-cbor filtered-yv)]
        (is (not= "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq" (:graphCid filtered-yv))
            "filtered graph must not inherit the unfiltered input graphCid")
        (is (= recomputed (:graphCid filtered-yv))
            "filtered graph graphCid must match its own canonical DAG-CBOR bytes")
        ;; Re-ingesting the filtered Yataverse graph verifies its freshly computed graphCid
        (is (= 5 (count (:nodes (ov/<-yataverse-graph filtered-yv))))))))

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
          i-node (ov/invoke-yataverse yataverse-pr83-fixture "ontology.inspect" {:node-id "type:tender"})
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
      (is (= "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em"
             (get-in i-res [:result :blockCids :root])))
      (is (= "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq"
             (get-in i-res [:result :blockCids :graph])))
      (is (= "bafyreie3xwjslrn6pyi67spmdclzdqtdqq3xkpo5oz6nt7b6almfid72pq"
             (get-in i-node [:result :blockCids :graph])))
      (is (= "yataverse.ontology.operations/v1" (get-in v-res [:result :semanticSchema :schema])))
      (is (some? (get-in v-res [:result :viewModel])))
      (is (string? (get-in v-res [:result :svg])))
      (is (string? (get-in v-res [:result :html])))
      (is (= 3 (get-in s-res [:result :rowCount])))
      (is (= 9 (get-in s-res [:result :scannedRows])))
      (is (= 5 (get-in q-res [:result :rowCount])))
      (is (string? (get-in q-res [:result :algebraEdn])))
      (is (str/includes? (get-in q-res [:result :algebraEdn]) ":sparql/op"))))

  (testing "KotobaSpec v1.0: basisCid pin and visibility (allowedSources / jurisdiction) fail closed"
    (let [wrong-cid "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku"
          deny-all (ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph"
                                        {:visibility {:allowedSources []}})
          only-kkj (ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph"
                                        {:visibility {:allowedSources ["jp.kkj"]}})
          only-tokyo (ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph"
                                          {:visibility {:jurisdiction "jp-tokyo"}})
          deny-jur (ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph"
                                        {:visibility {:jurisdiction []}})
          deny-sql (ov/invoke-yataverse yataverse-pr83-fixture "ontology.query_sql"
                                        {:query "SELECT id FROM nodes"
                                         :visibility {:allowedSources []}})]
      (is (= :basis-cid-mismatch
             (refusal-reason #(ov/invoke-yataverse yataverse-pr83-fixture "ontology.graph"
                                                   {:basisCid wrong-cid}))))
      (is (= 0 (count (get-in deny-all [:result :nodes])))
          "empty allowedSources: [] must fail closed with 0 nodes")
      (is (= 0 (count (get-in deny-all [:result :edges]))))
      (is (= 0 (get-in deny-sql [:result :rowCount])))
      (is (= ["fact:tender:kkj-2026-001"]
             (mapv :id (filter #(= "fact" (:kind %)) (get-in only-kkj [:result :nodes]))))
          "allowedSources: [jp.kkj] must filter out jp.geps and jp.agencies facts")
      (is (= #{"fact:agency:ag-tokyo" "fact:tender:geps-2026-042"}
             (set (map :id (filter #(= "fact" (:kind %)) (get-in only-tokyo [:result :nodes])))))
          "jurisdiction: jp-tokyo must keep only jp-tokyo facts")
      (is (= 0 (count (filter #(= "fact" (:kind %)) (get-in deny-jur [:result :nodes]))))
          "empty jurisdiction: [] must fail closed")))

  (testing "KotobaSpec v1.0: empty standard layer (nodeCount: 0) preserved on round-trip and projection"
    (let [no-facts-body (-> yataverse-pr83-fixture
                            (dissoc "graphCid")
                            (assoc "nodes" (vec (remove #(= "fact" (get % "layer"))
                                                        (get yataverse-pr83-fixture "nodes"))))
                            (assoc "edges" (vec (take 4 (get yataverse-pr83-fixture "edges"))))
                            (assoc "nodeCount" 5)
                            (assoc-in ["meta" "nodeCount"] 5)
                            (assoc-in ["meta" "edgeCount"] 4)
                            (assoc-in ["layers" 2 "nodeCount"] 0))
          {expected-cid :cid} (ov/encode-ontology-graph-dag-cbor no-facts-body)
          no-facts-yv (assoc no-facts-body "graphCid" expected-cid)
          kg (ov/<-yataverse-graph no-facts-yv)
          rt (ov/->yataverse-graph kg)]
      (is (= ["connector" "object-type" "fact"] (mapv :id (:layers rt)))
          "standard 3 layers must not be dropped when fact nodeCount is 0")
      (is (= [3 2 0] (mapv :nodeCount (:layers rt))))
      (is (= expected-cid (:graphCid rt)))
      ;; Newly projected Kotoba graph without facts also preserves all 3 standard layers
      (let [proj-kg (ov/project-graph {:ontology {:object-types [{:id :agency :name "Agency"}]}
                                       :connectors {:connectors [{:id :jp.agencies :name "Agencies" :object-type :agency}]}})
            proj-yv (ov/->yataverse-graph proj-kg)]
        (is (= ["connector" "object-type" "fact"] (mapv :id (:layers proj-yv))))
        (is (= [1 1 0] (mapv :nodeCount (:layers proj-yv))))
        (is (= 2 (count (:nodes (ov/<-yataverse-graph proj-yv))))))))

  (testing "KotobaSpec v1.0: $awaiType decimal normalization, integer equivalence, and non-finite refusal"
    (let [float-map {"a" 0.92 "b" 0.5 "c" 0.123456 "d" 0.0001 "e" 1.0e-7}
          explicit-decimal-map {"a" {"$awaiType" "decimal" "value" "0.92"}
                                "b" {"$awaiType" "decimal" "value" "0.5"}
                                "c" {"$awaiType" "decimal" "value" "0.123456"}
                                "d" {"$awaiType" "decimal" "value" "0.0001"}
                                "e" {"$awaiType" "decimal" "value" "1e-7"}}
          {cid-f :cid bytes-f :bytes} (ov/encode-ontology-graph-dag-cbor float-map)
          {cid-e :cid bytes-e :bytes} (ov/encode-ontology-graph-dag-cbor explicit-decimal-map)
          {cid-int :cid} (ov/encode-ontology-graph-dag-cbor {"n" 1 "z" 0})
          {cid-flt-int :cid} (ov/encode-ontology-graph-dag-cbor {"n" 1.0 "z" -0.0})]
      (is (= bytes-e bytes-f)
          "non-integer floats must encode identically to Yataverse {$awaiType: decimal} maps")
      (is (= cid-e cid-f))
      (is (= cid-int cid-flt-int)
          "integer-valued floats (1.0, -0.0) must encode as CBOR integers identically to 1, 0")
      (is (= :dag-cbor-non-finite
             (refusal-reason #(ov/encode-ontology-graph-dag-cbor {"bad" ##NaN}))))
      (is (= :dag-cbor-non-finite
             (refusal-reason #(ov/encode-ontology-graph-dag-cbor {"bad" ##Inf}))))
      (is (= :dag-cbor-non-finite
             (refusal-reason #(ov/encode-ontology-graph-dag-cbor {"bad" ##-Inf})))))))

(deftest yataverse-negative-validation-test
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph {"schema" "wrong/v1" "version" 1}))))
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph {"schema" "yataverse.ontology.graph/v1" "version" 2}))))
  (is (= :invalid-cid
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "basisCid" "baaaaaaaaaaaaaaaaaaaaaaaa")))))
  (is (= :invalid-cid
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "graphCid" "baaaaaaaaaaaaaaaaaaaaaaaa")))))
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "nodeCount" 999))))
      "inconsistent top-level nodeCount must fail closed")
  (is (= :invalid-yataverse-graph
         (refusal-reason #(ov/<-yataverse-graph (assoc yataverse-pr83-fixture "nodes" [{"id" "n1" "kind" "unknown-kind"}])))))
  (testing "tampered array order with stale graphCid fails closed with exact KotobaSpec v1.0 recomputed CID"
    (let [lex-sorted-edges (vec (sort-by #(get % "id") (get yataverse-pr83-fixture "edges")))
          reordered-edges-yv (assoc yataverse-pr83-fixture "edges" lex-sorted-edges)
          reversed-nodes-yv (assoc yataverse-pr83-fixture "nodes" (vec (reverse (get yataverse-pr83-fixture "nodes"))))
          err-data (try
                     (ov/<-yataverse-graph reordered-edges-yv)
                     nil
                     (catch #?(:clj clojure.lang.ExceptionInfo :cljs :default) e
                       (ex-data e)))]
      (is (= :graph-cid-mismatch (:reason err-data))
          "lexicographically reordered edges (e1, e10, ...) with old graphCid must fail closed")
      (is (= "bafyreid2ie7idv5vljfojdocazd4a4zqixz7di2nshjvvdbkknnitrye2i" (:computed err-data))
          "recomputed CID for e1,e10,... reordered edges must match KotobaSpec v1.0 vector exactly")
      (is (= :graph-cid-mismatch
             (refusal-reason #(ov/<-yataverse-graph reversed-nodes-yv)))
          "reordered nodes with old graphCid must fail closed"))))

(deftest kotobaspec-v101-unicode-ordering-and-two-axis-verification-test
  (let [u10000 "\uD800\uDC00"  ;; U+10000: UTF-16 [0xD800 0xDC00], UTF-8 4B [F0 90 80 80]
        uE000  "\uE000"        ;; U+E000:  UTF-16 [0xE000],        UTF-8 3B [EE 80 80]
        uE000a "\uE000a"]      ;; U+E000+'a':                      UTF-8 4B [EE 80 80 61]
    (testing "KotobaSpec v1.0.1 (a) Array sort UTF-16 positive: U+10000 precedes U+E000 with deterministic bytes & CID"
      (is (neg? (compare u10000 uE000))
          "UTF-16 code-unit compare must place U+10000 (0xD800) before U+E000 (0xE000)")
      (let [kg (ov/project-graph
                {:ontology {:object-types [{:id :tender :name "Tender"}]}
                 :facts [{:id (str "tender:" uE000) :ontology/type :tender :jurisdiction uE000}
                         {:id (str "tender:" u10000) :ontology/type :tender :jurisdiction u10000}]
                 :basis {:id "unicode-order-fixture"
                         :root-cid "bafyreiguv25njqmgq3nksfula2pkkflztdcltyrc4jzo3gv4yonfnfa4em"}})
            yv (ov/->yataverse-graph kg)
            fact-ids (mapv :id (filter #(= "fact" (:layer %)) (:nodes yv)))
            {:keys [cid bytes]} (ov/encode-ontology-graph-dag-cbor yv)
            rt (ov/<-yataverse-graph yv)]
        (is (= [(str "entity:tender:" u10000) (str "entity:tender:" uE000)] fact-ids)
            "newly projected array must sort nodes by UTF-16 code-unit order (U+10000 before U+E000)")
        (is (= cid (:graphCid yv)))
        (is (= :ok (ov/validate-dag-cbor! bytes)))
        (is (= :verified (get-in rt [:basis :graph-cid-verification])))
        (is (= :syntax-only (get-in rt [:basis :basis-cid-verification])))
        (is (= :syntax-only (get-in rt [:basis :cid-verification])))

        (testing "KotobaSpec v1.0.1 (b) Array sort UTF-16 negative: [...U+E000..., ...U+10000...] + stale graphCid -> :graph-cid-mismatch"
          (let [non-facts (vec (remove #(= "fact" (:layer %)) (:nodes yv)))
                rev-facts (vec (reverse (filter #(= "fact" (:layer %)) (:nodes yv))))
                tampered (assoc yv :nodes (into non-facts rev-facts))]
            (is (= :graph-cid-mismatch
                   (refusal-reason #(ov/<-yataverse-graph tampered)))
                "reordered Unicode array [U+E000, U+10000] with stale graphCid must fail closed")))))

    (testing "KotobaSpec v1.0.1 (c) DAG-CBOR map key UTF-8 positive: U+E000 (3B) -> U+E000a (4B) -> U+10000 (4B)"
      (let [bytes (ov/encode-dag-cbor {u10000 3 uE000a 2 uE000 1})
            expected-bytes [0xa3
                            0x63 0xee 0x80 0x80 0x01
                            0x64 0xee 0x80 0x80 0x61 0x02
                            0x64 0xf0 0x90 0x80 0x80 0x03]
            decoded (ov/decode-dag-cbor bytes)]
        (is (= expected-bytes bytes)
            "canonical DAG-CBOR bytes must sort keys by UTF-8 byte length then unsigned UTF-8 byte value")
        (is (nil? (ov/validate-dag-cbor bytes)))
        (is (= [uE000 uE000a u10000] (:root-keys decoded)))
        (is (= {uE000 1 uE000a 2 u10000 3} (:value decoded)))))

    (testing "KotobaSpec v1.0.1 (d) Non-canonical UTF-16 map key order in raw CBOR bytes -> :map-keys-not-sorted"
      (let [non-canon-utf16 [0xa2 0x64 0xf0 0x90 0x80 0x80 0x01 0x63 0xee 0x80 0x80 0x02]
            non-canon-same-len [0xa2 0x64 0xf0 0x90 0x80 0x80 0x01 0x64 0xee 0x80 0x80 0x61 0x02]]
        (is (= :map-keys-not-sorted (ov/validate-dag-cbor non-canon-utf16)))
        (is (= :map-keys-not-sorted (refusal-reason #(ov/validate-dag-cbor! non-canon-utf16))))
        (is (= :map-keys-not-sorted (refusal-reason #(ov/decode-dag-cbor non-canon-utf16))))
        (is (= :map-keys-not-sorted (ov/validate-dag-cbor non-canon-same-len)))
        (is (= :map-keys-not-sorted (refusal-reason #(ov/decode-dag-cbor non-canon-same-len))))))

    (testing "KotobaSpec v1.0.1 two-axis verification separation & strict wire non-inclusion"
      (let [kg (ov/<-yataverse-graph yataverse-pr83-fixture)
            yv (ov/->yataverse-graph kg)
            svg (ov/render-svg kg)
            html (ov/render-html kg)
            st (ov/initial-screen-state kg)]
        (is (= :verified (get-in kg [:basis :graph-cid-verification]))
            "graphCid verified against canonical DAG-CBOR bytes")
        (is (= :syntax-only (get-in kg [:basis :basis-cid-verification]))
            "graphCid match MUST NOT promote snapshot basisCid to :verified")
        (is (= :syntax-only (get-in kg [:basis :cid-verification])))
        (is (= "syntax-only" (:basis/basis-cid-verification st)))
        (is (= "verified" (:basis/graph-cid-verification st)))
        (is (str/includes? svg "cid=syntax-only"))
        (is (str/includes? svg "graph-cid=verified"))
        (is (str/includes? html "basis-cid: syntax-only"))
        (is (str/includes? html "graph-cid: verified"))
        (doseq [internal-k [:cid-verification :basis-cid-verification :graph-cid-verification
                            :graphCidVerified :basisCidVerified :verificationScope
                            "cid-verification" "basis-cid-verification" "graph-cid-verification"
                            "graphCidVerified" "basisCidVerified" "verificationScope"
                            "graphVerification" "basisVerification"]]
          (is (not (contains? yv internal-k))
              (str "wire yataverse.ontology.graph/v1 must NEVER contain internal verification key " internal-k)))))))
