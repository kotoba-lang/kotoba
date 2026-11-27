(ns kotoba.ontology-viz.render-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]
            [kotoba.ontology-viz.graph-test :as gt]))

(deftest render-svg-standalone-test
  (let [graph (ov/project-graph gt/sample-input)
        svg (ov/render-svg graph {:title "Procurement Ontology"})]
    (testing "emits well-formed standalone offline SVG with nodes, edges, and basis"
      (is (str/starts-with? svg "<svg xmlns=\"http://www.w3.org/2000/svg\""))
      (is (str/ends-with? svg "</svg>"))
      (is (str/includes? svg "<title>Procurement Ontology</title>"))
      (is (str/includes? svg "data-node-id=\"type:tender\""))
      (is (str/includes? svg "data-node-id=\"connector:jp.kkj\""))
      (is (str/includes? svg "join 67%"))
      (is (str/includes? svg "schema=ontology.graph/v1"))
      (is (not (str/includes? svg "<script"))
          "standalone SVG must not contain embedded script tags")
      (is (not (re-find #"https?://(?!www\.w3\.org/2000/svg)" (str/lower-case svg)))
          "standalone SVG must not reference external URLs")
      (is (every? #(str/starts-with? % "ov-")
                  (map second (re-seq #"class=\"([^\"]+)\"" svg)))
          "all SVG classes must belong exclusively to the self-contained ov-* namespace"))))

(deftest render-html-viewer-test
  (let [artifact (ov/build-artifact gt/sample-input {:title "Yataverse Ontology Viewer"})
        html (:html artifact)]
    (testing "emits self-contained interactive HTML5 Viewer with strict CSP"
      (is (str/starts-with? html "<!DOCTYPE html>"))
      (is (str/includes? html "Content-Security-Policy"))
      (is (str/includes? html "default-src 'none'"))
      (is (str/includes? html "id=\"kotoba-ontology-graph\""))
      (is (str/includes? html "id=\"kotoba-semantic-ui-schema\""))
      (is (str/includes? html "ov-layer-checkbox"))
      (is (str/includes? html "ov-inspector-body"))
      (is (str/includes? html "join:jurisdiction-&gt;country"))
      (is (str/includes? html ":jurisdiction/code"))
      (is (str/includes? html ":country/iso3"))
      (doseq [op ov/operation-names]
        (is (str/includes? html op) (str "HTML viewer must declare Semantic UI op " op)))
      (is (every? #(every? (fn [c] (str/starts-with? c "ov-")) (str/split % #"\s+"))
                  (map second (re-seq #"class=\"([^\"]+)\"" html)))
          "all HTML viewer classes must belong exclusively to the self-contained ov-* namespace")
      (is (not (re-find #"<(link|script|img)\b[^>]+(href|src)\s*=\s*['\"]https?://" (str/lower-case html)))
          "HTML viewer must make zero external network requests"))))

(deftest semantic-ui-schema-and-operations-test
  (let [graph (ov/project-graph gt/sample-input)
        schema ov/semantic-schema]
    (testing "machine-readable Semantic UI schema declares all 5 noun.verb operations"
      (is (= "kotoba.semantic-ui/v1" (:schema/version schema)))
      (is (true? (:read-only schema)))
      (is (false? (:remote-fetch schema)))
      (is (= ["ontology.inspect"
              "ontology.graph"
              "ontology.view"
              "ontology.query_sql"
              "ontology.query_sparql"]
             (mapv :name (:operations schema)))))

    (testing "ontology.inspect resolves by node-id and by IPLD CID"
      (let [by-id (ov/invoke graph "ontology.inspect" {:node-id "type:tender"})
            by-cid (ov/invoke graph "ontology.inspect" {:cid gt/sample-root-cid})
            missing (ov/invoke graph "ontology.inspect" {:node-id "type:does-not-exist"})]
        (is (true? (:found by-id)))
        (is (= "type:tender" (get-in by-id [:node :id])))
        (is (pos? (count (:incoming by-id))))
        (is (pos? (count (:outgoing by-id))))
        (is (= 1 (count (:joins by-id))))
        (is (true? (:found by-cid)))
        (is (false? (:found missing)))))

    (testing "ontology.graph filters by layer"
      (let [res (ov/invoke graph "ontology.graph" {:layers ["ipld"]})]
        (is (= "ontology.graph/v1" (:schema/version res)))
        (is (= #{"ipld"} (set (map :layer (:nodes res)))))))

    (testing "ontology.view renders svg and html"
      (let [v-svg (ov/invoke graph "ontology.view" {:format "svg" :title "View SVG"})
            v-html (ov/invoke graph "ontology.view" {:format "html" :title "View HTML"})]
        (is (= "svg" (:format v-svg)))
        (is (= "image/svg+xml" (:content-type v-svg)))
        (is (str/includes? (:content v-svg) "View SVG"))
        (is (= "html" (:format v-html)))
        (is (= "text/html; charset=utf-8" (:content-type v-html)))
        (is (str/includes? (:content v-html) "View HTML"))))

    (testing "ontology.query_sql executes bounded read-only SELECT"
      (let [res (ov/invoke graph "ontology.query_sql"
                           {:sql "SELECT id, kind FROM nodes WHERE layer = 'connector' LIMIT 10"})]
        (is (= "sql-readonly-v1" (:dialect res)))
        (is (= "nodes" (:table res)))
        (is (= ["id" "kind"] (:columns res)))
        (is (= 2 (:row-count res)))
        (is (= #{"connector:jp.geps" "connector:jp.kkj"}
               (set (map #(get % "id") (:rows res)))))))

    (testing "ontology.query_sparql executes bounded read-only SELECT and ASK"
      (let [sel (ov/invoke graph "ontology.query_sparql"
                           {:sparql "SELECT ?s ?cid WHERE { ?s ipld:cid ?cid }"})
            ask-yes (ov/invoke graph "ontology.query_sparql"
                               {:sparql "ASK { connector:jp.kkj produces type:tender }"})
            ask-no (ov/invoke graph "ontology.query_sparql"
                              {:sparql "ASK { connector:jp.kkj produces type:nonexistent }"})]
        (is (= "sparql-readonly-v1" (:dialect sel)))
        (is (= "SELECT" (:form sel)))
        (is (pos? (:row-count sel)))
        (is (true? (:ask ask-yes)))
        (is (false? (:ask ask-no)))))))
