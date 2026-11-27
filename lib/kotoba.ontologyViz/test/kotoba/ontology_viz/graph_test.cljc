(ns kotoba.ontology-viz.graph-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]))

(def sample-root-cid
  "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyku")

(def sample-block-cid
  "bafkreigh2akiscaildcqabsyg3dfr6chu3fgpregiymsck7e7aqa4s52zy")

(def sample-leaf-cid
  "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi")

(def sample-input
  {:ontology {:kotoba.registry/id :kotoba/ontology
              :kotoba.registry/version 1
              :object-types
              [{:id :tender
                :name "Procurement Tender / Opportunity"
                :attributes {:status :keyword
                             :jurisdiction/code :string}
                :key [:status]
                :cid (ov/ipld-link sample-root-cid)}
               {:id :country
                :name "Country Reference"
                :attributes {:country/iso3 :string}
                :key [:country/iso3]}]}
   :connectors {:kotoba.registry/id :kotoba/ontology-connectors
                :kotoba.registry/version 1
                :connectors
                [{:id :jp.kkj
                  :name "kkj.go.jp 官公需情報ポータル 検索API"
                  :object-type :tender
                  :repo "https://github.com/kotoba-lang/goyoukiki"
                  :status :implemented}
                 {:id :jp.geps
                  :name "GEPS 落札実績オープンデータ"
                  :object-type :tender
                  :repo "https://github.com/kotoba-lang/goyoukiki"
                  :status :implemented}]}
   :kotoba-schema [{:db/ident :jurisdiction/code
                    :db/valueType :db.type/string
                    :db/cardinality :db.cardinality/one
                    :db/doc "ISO-3166 alpha-2 or regional jurisdiction code"}
                   {:db/ident :country/iso3
                    :db/valueType :db.type/string
                    :db/cardinality :db.cardinality/one
                    :db/doc "ISO-3166 alpha-3 country code"}]
   :facts [{:id "tender-001"
            :name "Cloud Platform Tender"
            :status :open
            :jurisdiction/code "JP"
            :ontology/type :tender
            :ontology/source :jp.kkj
            :ontology/fetched-at "2026-11-27"
            :ontology/confidence 0.95
            :ipld/cid (ov/ipld-link sample-block-cid)}]
   :datoms [[:tender/t-2 :jurisdiction/code "US" 101 true]
            [:tender/t-3 :jurisdiction/code "XX" 101 true]
            [:tender/t-4 :jurisdiction/code "ZZ" 101 true]
            [:tender/t-retracted :jurisdiction/code "RETRACTED" 102 false]
            [:country/jpn :country/iso3 "JPN" 101 true]
            [:country/usa :country/iso3 "USA" 101 true]
            [:tender/t-2 :tender/country :country/usa 101 true]
            [:tender/t-2 :ipld/manifest {"/" sample-leaf-cid} 101 true]]
   :quads [{:subject {:rdf/type :iri :value "urn:kotoba:tender:001"}
            :predicate {:rdf/type :iri :value "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"}
            :object {:rdf/type :iri :value "urn:kotoba:class:Tender"}
            :graph {:rdf/type :iri :value "urn:kotoba:graph:procurement"}}
           {:subject {:rdf/type :iri :value "urn:kotoba:tender:001"}
            :predicate {:rdf/type :iri :value "http://www.w3.org/2000/01/rdf-schema#label"}
            :object {:rdf/type :literal :value "Tender 001"}
            :graph {:rdf/type :iri :value "urn:kotoba:graph:procurement"}}]
   :ipld-nodes {sample-root-cid {"name" "ontology-root"
                                 "schema" (ov/ipld-link sample-block-cid)
                                 "entries" [{"/" sample-leaf-cid}]}}
   :joins [{:id "join:jurisdiction->country"
            :from-type :tender
            :from-attr :jurisdiction/code
            :to-type :country
            :to-attr :country/iso3
            :match-rule :mapping
            :mapping {"JP" "JPN" "US" "USA"}
            :exclude #{"XX"}
            :cardinality :many-to-one
            :description "Map jurisdiction code to ISO-3166 alpha-3 country code"}]
   :basis {:root-cid (ov/ipld-link sample-root-cid)
           :codec "dag-cbor"
           :hash-alg "sha2-256"
           :source "kotoba.ontology"
           :snapshot-at "2026-11-27T00:00:00Z"}})

(deftest project-graph-full-pipeline-test
  (let [graph (ov/project-graph sample-input)
        node-ids (set (map :id (:nodes graph)))
        edge-kinds (set (map :kind (:edges graph)))
        layer-ids (set (map :id (:layers graph)))]
    (testing "conforms to Yataverse ontology.graph/v1 schema envelope"
      (is (= "ontology.graph/v1" (:schema/version graph)))
      (is (= "ontology.graph" (:schema/kind graph)))
      (is (= sample-root-cid (get-in graph [:basis :root-cid])))
      (is (= "dag-cbor" (get-in graph [:basis :codec])))
      (is (= (count (:nodes graph)) (get-in graph [:basis :node-count])))
      (is (= (count (:edges graph)) (get-in graph [:basis :edge-count])))
      (is (= (count (:joins graph)) (get-in graph [:basis :join-count]))))

    (testing "projects ontology types, connectors, kotoba-schema, facts, datoms, RDF quads, and IPLD links"
      (is (contains? node-ids "type:tender"))
      (is (contains? node-ids "type:country"))
      (is (contains? node-ids "connector:jp.kkj"))
      (is (contains? node-ids "connector:jp.geps"))
      (is (contains? node-ids "attr:jurisdiction/code"))
      (is (contains? node-ids "attr:country/iso3"))
      (is (contains? node-ids "entity:tender-001"))
      (is (contains? node-ids "entity:tender/t-2"))
      (is (not (contains? node-ids "entity:tender/t-retracted"))
          "retracted datoms (added? = false) must not appear")
      (is (contains? node-ids "rdf:urn:kotoba:tender:001"))
      (is (contains? node-ids "rdf:urn:kotoba:class:Tender"))
      (is (contains? node-ids (str "ipld:" sample-root-cid)))
      (is (contains? node-ids (str "ipld:" sample-block-cid)))
      (is (contains? node-ids (str "ipld:" sample-leaf-cid))))

    (testing "populates all expected edge kinds and layers"
      (is (contains? edge-kinds :produces))
      (is (contains? edge-kinds :has-attribute))
      (is (contains? edge-kinds :instance-of))
      (is (contains? edge-kinds :datom-ref))
      (is (contains? edge-kinds :rdf-predicate))
      (is (contains? edge-kinds :join))
      (is (contains? edge-kinds :ipld-link))
      (is (= #{"connector" "ontology" "attribute" "instance" "rdf" "ipld"} layer-ids)))

    (testing "collects all referenced IPLD CIDs into basis"
      (let [cids (set (get-in graph [:basis :cids]))]
        (is (contains? cids sample-root-cid))
        (is (contains? cids sample-block-cid))
        (is (contains? cids sample-leaf-cid))))

    (testing "computes deterministic external join coverage with match + exclude rules"
      (let [j (first (:joins graph))]
        (is (= "join:jurisdiction->country" (:id j)))
        (is (= :mapping (:match-rule j)))
        (is (= 2 (:matched-count j)))
        (is (= 1 (:unmatched-count j)))
        (is (= 1 (:excluded-count j)))
        (is (= 3 (:eligible-count j)))
        (is (= 0.6667 (:coverage j)))
        (is (= :partial (:status j)))
        (is (= [["JP" "JPN"] ["US" "USA"]] (:matched-pairs j)))
        (is (= ["ZZ"] (:unmatched-values j)))
        (is (= ["XX"] (:excluded-values j)))))

    (testing "layout is deterministic and assigns positive geometry to every node"
      (let [graph2 (ov/project-graph sample-input)]
        (is (= graph graph2))
        (is (every? #(and (number? (get-in % [:layout :x]))
                          (number? (get-in % [:layout :y]))
                          (pos? (get-in % [:layout :width]))
                          (pos? (get-in % [:layout :height])))
                    (:nodes graph)))))))

(deftest filter-and-vertical-layout-test
  (let [graph (ov/project-graph sample-input)
        only-onto (ov/filter-graph graph {:layers ["connector" "ontology"]})
        by-query (ov/filter-graph graph {:query "jp.kkj"})
        vertical (ov/layout-graph graph {:direction :vertical})]
    (is (= #{"connector" "ontology"} (set (map :layer (:nodes only-onto)))))
    (is (every? #(and (contains? (set (map :id (:nodes only-onto))) (:source %))
                      (contains? (set (map :id (:nodes only-onto))) (:target %)))
                (:edges only-onto)))
    (is (= ["connector:jp.kkj"] (mapv :id (:nodes by-query))))
    (is (= :vertical (get-in vertical [:layout :direction])))))

(deftest ipld-link-interoperability-test
  (let [l (ov/ipld-link sample-root-cid)]
    (is (ov/ipld-link? l))
    (is (ov/ipld-link? {"/" sample-root-cid}))
    (is (ov/ipld-link? {:ipld/link sample-root-cid}))
    (is (ov/ipld-link? {:ipld/cid sample-root-cid}))
    (is (= sample-root-cid (ov/extract-cid l)))
    (is (= sample-root-cid (ov/extract-cid {"/" sample-root-cid})))
    (is (= sample-root-cid (ov/extract-cid sample-root-cid)))))
