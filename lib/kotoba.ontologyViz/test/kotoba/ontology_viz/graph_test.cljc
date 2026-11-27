(ns kotoba.ontology-viz.graph-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]))

(defn- refusal-reason [f]
  (try
    (f)
    ::no-throw
    (catch #?(:clj clojure.lang.ExceptionInfo
              :cljs :default) e
      (:reason (ex-data e)))))

;; Real valid CIDv1 (base32lower, version=1, dag-cbor/raw/dag-pb, sha2-256 32-byte digest)
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
                    :db/doc "ISO-3166 alpha-3 country code"}
                   {:db/ident :tender/country
                    :db/valueType :db.type/ref
                    :db/cardinality :db.cardinality/one}]
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
            [:tender/t-retracted :jurisdiction/code "TEMP" 100 true]
            [:tender/t-retracted :jurisdiction/code "TEMP" 102 false]
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
            :object {:rdf/type :literal :value "Tender 001" :language "en"}
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
        nodes-by-id (into {} (map (juxt :id identity) (:nodes graph)))
        node-ids (set (keys nodes-by-id))
        edge-kinds (set (map :kind (:edges graph)))
        layer-ids (set (map :id (:layers graph)))]
    (testing "conforms to canonical ontology.graph/v1 schema envelope and honest CID verification"
      (is (= "ontology.graph/v1" (:schema/version graph)))
      (is (= "ontology.graph" (:schema/kind graph)))
      (is (= sample-root-cid (get-in graph [:basis :root-cid])))
      (is (= :syntax-only (get-in graph [:basis :cid-verification])))
      (is (= "dag-cbor" (get-in graph [:basis :codec])))
      (is (= (count (:nodes graph)) (get-in graph [:basis :node-count])))
      (is (= (count (:edges graph)) (get-in graph [:basis :edge-count])))
      (is (= (count (:joins graph)) (get-in graph [:basis :join-count]))))

    (testing "preserves declared human-readable labels even after facts/datoms reference the same type or connector"
      (is (= "Procurement Tender / Opportunity" (:label (get nodes-by-id "type:tender"))))
      (is (= "kkj.go.jp 官公需情報ポータル 検索API" (:label (get nodes-by-id "connector:jp.kkj"))))
      (is (= "Cloud Platform Tender" (:label (get nodes-by-id "entity:tender-001")))))

    (testing "projects ontology types, connectors, kotoba-schema, facts, folded datoms, RDF quads, and IPLD links"
      (is (contains? node-ids "type:tender"))
      (is (contains? node-ids "type:country"))
      (is (contains? node-ids "connector:jp.kkj"))
      (is (contains? node-ids "connector:jp.geps"))
      (is (contains? node-ids "attr:jurisdiction/code"))
      (is (contains? node-ids "attr:country/iso3"))
      (is (contains? node-ids "entity:tender-001"))
      (is (contains? node-ids "entity:tender/t-2"))
      (is (not (contains? node-ids "entity:tender/t-retracted"))
          "asserted at tx 100 then retracted at tx 102 must fold away cleanly")
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

    (testing "computes deterministic scoped external join coverage with match + exclude rules"
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
        (is (= ["XX"] (:excluded-values j)))))))

(deftest eavt-temporal-folding-multivalued-and-no-spurious-string-refs-test
  (testing "chronological folding handles retract + re-assert, multi-valued attrs, and avoids string-match ref edges"
    (let [g (ov/project-graph
             {:datoms [[:doc/a :doc/tag "v1" 10 true]
                       [:doc/a :doc/tag "v2" 11 true]
                       [:doc/a :doc/tag "v1" 20 false]
                       [:doc/a :doc/tag "v3" 30 true]
                       ;; Re-assert after retraction at higher tx
                       [:doc/a :doc/reasserted "yes" 10 true]
                       [:doc/a :doc/reasserted "yes" 20 false]
                       [:doc/a :doc/reasserted "yes" 30 true]
                       ;; Plain string value matching another entity name must NOT invent :datom-ref
                       ["US" :country/name "United States" 10 true]
                       [:doc/a :doc/note "US" 10 true]]})
          doc-node (first (filter #(= "entity:doc/a" (:id %)) (:nodes g)))]
      (is (= ["v2" "v3"] (get-in doc-node [:attributes ":doc/tag"])))
      (is (= "yes" (get-in doc-node [:attributes ":doc/reasserted"])))
      (is (= "US" (get-in doc-node [:attributes ":doc/note"])))
      (is (empty? (filter #(= :datom-ref (:kind %)) (:edges g)))
          "untyped plain string matching an entity id must not silently create a :datom-ref edge")))

  (testing "non-schema namespaced keyword matching an entity ID does NOT invent :datom-ref, while genuine declared :ref self-reference preserves a self-edge"
    (let [g (ov/project-graph
             {:kotoba-schema [{:db/ident :org/parent
                               :db/valueType :db.type/ref
                               :db/cardinality :db.cardinality/one}]
              :datoms [[:status/open :label/name "Open" 10 true]
                       ;; Non-schema keyword matching entity :status/open must stay scalar
                       [:doc/b :doc/state :status/open 10 true]
                       ;; Genuine declared ref self-reference must produce a :datom-ref self-edge
                       [:org/root :org/parent :org/root 10 true]]})
          ref-edges (filter #(= :datom-ref (:kind %)) (:edges g))
          doc-b (first (filter #(= "entity:doc/b" (:id %)) (:nodes g)))]
      (is (= ":status/open" (get-in doc-b [:attributes ":doc/state"])))
      (is (= 1 (count ref-edges)))
      (is (= "entity:org/root" (:source (first ref-edges))))
      (is (= "entity:org/root" (:target (first ref-edges))))
      (is (true? (get-in (first ref-edges) [:metadata :self-ref]))))))

(deftest rdf-quad-provenance-datatype-language-and-disambiguation-test
  (let [g (ov/project-graph
           {:quads [{:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://vocab-a.example/rel"}
                     :object {:rdf/type :iri :value "urn:ex:o1"}
                     :graph {:rdf/type :iri :value "urn:g:1"}}
                    {:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://vocab-b.example/rel"}
                     :object {:rdf/type :iri :value "urn:ex:o1"}
                     :graph {:rdf/type :iri :value "urn:g:1"}}
                    {:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://vocab-a.example/rel"}
                     :object {:rdf/type :iri :value "urn:ex:o1"}
                     :graph {:rdf/type :iri :value "urn:g:2"}}
                    {:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://www.w3.org/2000/01/rdf-schema#label"}
                     :object {:rdf/type :literal :value "Hello" :language "en"}}
                    {:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://www.w3.org/2000/01/rdf-schema#label"}
                     :object {:rdf/type :literal :value "こんにちは" :language "ja"}}
                    {:subject {:rdf/type :iri :value "urn:ex:s1"}
                     :predicate {:rdf/type :iri :value "http://schema.example/amount"}
                     :object {:rdf/type :literal :value "42"
                              :datatype {:rdf/type :iri :value "http://www.w3.org/2001/XMLSchema#integer"}}}]})
        rdf-edges (filter #(= :rdf-predicate (:kind %)) (:edges g))
        s1 (first (filter #(= "rdf:urn:ex:s1" (:id %)) (:nodes g)))]
    (is (= 3 (count rdf-edges))
        "distinct predicate IRIs with same fragment and distinct named graphs must not collide")
    (is (= #{"http://vocab-a.example/rel" "http://vocab-b.example/rel"}
           (set (map #(get-in % [:metadata :predicate-iri]) rdf-edges))))
    (is (= #{"urn:g:1" "urn:g:2"}
           (set (map #(get-in % [:metadata :graph]) rdf-edges))))
    (is (= ["urn:g:1" "urn:g:2"]
           (get-in s1 [:provenance :named-graphs]))
        "same RDF node across multiple named graphs must retain sorted union of named graphs")
    (is (= ["Hello@en" "こんにちは@ja"]
           (get-in s1 [:attributes "http://www.w3.org/2000/01/rdf-schema#label"])))
    (is (= "42^^<http://www.w3.org/2001/XMLSchema#integer>"
           (get-in s1 [:attributes "http://schema.example/amount"])))))

(deftest join-scoping-and-ambiguity-handling-test
  (testing "type-scoped join isolates values by declared :from-type and :to-type, including string-ID facts extended by datoms"
    (let [g (ov/project-graph
             {:facts [{:id "t1" :ontology/type :tender :code "JP"}
                      {:id "t-str-2" :ontology/type :tender :name "Extended via datom"}
                      {:id "x1" :ontology/type :other :code "SHOULD-NOT-LEAK"}
                      {:id "c1" :ontology/type :country :iso "JP"}
                      {:id "c2" :ontology/type :country :iso "US"}]
              :datoms [["t-str-2" :code "US" 101 true]]
              :joins [{:id "join:scoped"
                       :from-type :tender :from-attr :code
                       :to-type :country :to-attr :iso
                       :match-rule :exact}]})
          j (first (:joins g))]
      (is (= 2 (:total-source-count j)))
      (is (= 2 (:matched-count j)))
      (is (= [["JP" "JP"] ["US" "US"]] (:matched-pairs j)))
      (is (= :full (:status j)))))

  (testing "ambiguous join match fails closed by default (:on-ambiguous :error)"
    (is (= :ambiguous-join-match
           (refusal-reason
            #(ov/evaluate-join {:id "join:amb"
                                :from-attr :a :to-attr :b
                                :match-rule :prefix
                                :source-values ["JP"]
                                :target-values ["JP-13" "JP-01"]})))))

  (testing ":on-ambiguous :all returns all deterministically sorted matches independent of input order"
    (let [j1 (ov/evaluate-join {:id "join:amb"
                                :from-attr :a :to-attr :b
                                :match-rule :prefix
                                :on-ambiguous :all
                                :source-values ["JP"]
                                :target-values ["JP-13" "JP-01"]})
          j2 (ov/evaluate-join {:id "join:amb"
                                :from-attr :a :to-attr :b
                                :match-rule :prefix
                                :on-ambiguous :all
                                :source-values ["JP"]
                                :target-values ["JP-01" "JP-13"]})]
      (is (= j1 j2))
      (is (= [["JP" "JP-01"] ["JP" "JP-13"]] (:matched-pairs j1))))))

(deftest filter-and-vertical-layout-test
  (let [graph (ov/project-graph sample-input)
        only-onto (ov/filter-graph graph {:layers ["connector" "ontology"]})
        empty-layers (ov/filter-graph graph {:layers []})
        empty-kinds (ov/filter-graph graph {:kinds []})
        by-kind-str (ov/filter-graph graph {:kinds ["connector"]})
        by-kind-kw (ov/filter-graph graph {:kinds [:connector]})
        by-query (ov/filter-graph graph {:query "jp.kkj"})
        vertical (ov/layout-graph graph {:direction :vertical})]
    (is (= #{"connector" "ontology"} (set (map :layer (:nodes only-onto)))))
    (is (= 0 (count (:nodes empty-layers)))
        "explicit {:layers []} must return 0 nodes (not fall back to unfiltered)")
    (is (= 0 (count (:edges empty-layers))))
    (is (= 0 (count (:nodes empty-kinds)))
        "explicit {:kinds []} must return 0 nodes")
    (is (= by-kind-str by-kind-kw) "string and keyword kind filters must agree")
    (is (= ["connector:jp.kkj"] (mapv :id (:nodes by-query))))
    (is (= :vertical (get-in vertical [:layout :direction])))
    (is (= :invalid-kind
           (refusal-reason #(ov/filter-graph graph {:kinds ["bogus-kind"]}))))))

(deftest ipld-link-and-binary-cidv1-test
  (let [l (ov/ipld-link sample-root-cid)
        parsed (ov/parse-cidv1 sample-root-cid)]
    (is (= 1 (:version parsed)))
    (is (= :dag-cbor (:codec parsed)))
    (is (= 32 (:digest-length parsed)))
    (is (= :syntax-only (:verification parsed)))
    (is (ov/ipld-link? l))
    (is (ov/ipld-link? {"/" sample-root-cid}))
    (is (ov/ipld-link? {:ipld/link sample-root-cid}))
    (is (ov/ipld-link? {:ipld/cid sample-root-cid}))
    (is (= sample-root-cid (ov/extract-cid l)))
    (is (= sample-root-cid (ov/extract-cid {"/" sample-root-cid})))))
