(ns kotoba.ontology-viz.render-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]
            [kotoba.ontology-viz.graph-test :as gt]))

(deftest canonical-number-formatting-test
  (is (= "120" (ov/fmt-num 120)))
  (is (= "120" (ov/fmt-num 120.0)))
  (is (= "0" (ov/fmt-num -0.0)))
  (is (= "108.5" (ov/fmt-num 108.5000)))
  (is (= "0.6667" (ov/fmt-num (/ 2.0 3.0)))))

(deftest render-svg-standalone-and-a11y-test
  (let [graph (ov/project-graph gt/sample-input)
        svg (ov/render-svg graph {:title "Procurement Ontology"})]
    (testing "emits well-formed standalone offline SVG with nodes, edges, and honest CID status"
      (is (str/starts-with? svg "<svg xmlns=\"http://www.w3.org/2000/svg\""))
      (is (str/ends-with? svg "</svg>\n"))
      (is (str/includes? svg "<title>Procurement Ontology</title>"))
      (is (str/includes? svg "data-node-id=\"type:tender\""))
      (is (str/includes? svg "data-node-id=\"connector:jp.kkj\""))
      (is (str/includes? svg "join 67%"))
      (is (str/includes? svg "schema=ontology.graph/v1"))
      (is (str/includes? svg "cid=syntax-only"))
      (is (not (str/includes? svg "<script"))
          "standalone SVG must not contain embedded script tags")
      (is (not (str/includes? svg "role=\"button\""))
          "standalone static SVG must not place focusable role=button on non-actionable graphics")
      (is (not (str/includes? svg "tabindex=\"0\""))
          "standalone static SVG must not place tabindex=0 on non-actionable graphics")
      (is (not (re-find #"(?:href|src)\s*=\s*['\"]https?://|url\(\s*['\"]?https?://" (str/lower-case svg)))
          "standalone SVG must not fetch external URLs via href/src/url()")
      (is (every? #(str/starts-with? % "ov-")
                  (map second (re-seq #"class=\"([^\"]+)\"" svg)))
          "all SVG classes must belong exclusively to the self-contained ov-* namespace"))))

(deftest render-html-viewer-g2-a11y-and-screen-state-test
  (let [artifact (ov/build-artifact gt/sample-input {:title "Yataverse Ontology Viewer"})
        html (:html artifact)
        screen-state (:screen-state artifact)]
    (testing "emits self-contained interactive HTML5 Viewer with strict CSP and live machine-readable screen state"
      (is (str/starts-with? html "<!DOCTYPE html>"))
      (is (str/ends-with? html "</html>\n"))
      (is (str/includes? html "Content-Security-Policy"))
      (is (str/includes? html "default-src 'none'"))
      (is (str/includes? html "id=\"kotoba-ontology-screen\""))
      (is (str/includes? html "data-screen-state=\""))
      (is (str/includes? html "window.__KOTOBA_ONTOLOGY_SCREEN__"))
      (is (= "kotoba.ontology-viewer" (:screen/id screen-state)))
      (is (= "ready" (:screen/status screen-state)))
      (is (= ov/operation-names (:ops screen-state)))
      (is (= 5 (count (:opAvailability screen-state))))
      (is (every? #(true? (:enabled %)) (vals (:opAvailability screen-state))))
      (is (str/includes? html "filterGraph: filterGraphLocal"))
      (is (str/includes? html "querySql: querySqlLocal"))
      (is (str/includes? html "querySparql: querySparqlLocal"))
      (is (str/includes? html "invoke: invokeLocal"))
      (is (= (count (get-in artifact [:graph :nodes])) (count (:visibleNodeIds screen-state))))
      (is (= (count (get-in artifact [:graph :edges])) (count (:visibleEdgeIds screen-state)))))

    (testing "interactive HTML viewer attaches actionable SVG roles and WAI-ARIA tablist keyboard navigation"
      (is (str/includes? html "role=\"button\""))
      (is (str/includes? html "role=\"tablist\""))
      (is (str/includes? html "id=\"ov-tab-inspect\""))
      (is (str/includes? html "aria-controls=\"ov-panel-inspect\""))
      (is (str/includes? html "aria-labelledby=\"ov-tab-inspect\""))
      (is (str/includes? html "ArrowRight"))
      (is (str/includes? html "ArrowLeft"))
      (is (str/includes? html "'Home'"))
      (is (str/includes? html "'End'"))
      (is (not (str/includes? html "ov-dimmed"))
          "browser filter hides non-matching nodes and incident edges identically to agent filter-graph"))

    (testing "embeds graph, Semantic UI schema, join table, and uses only ov-* classes"
      (is (str/includes? html "id=\"kotoba-ontology-graph\""))
      (is (str/includes? html "id=\"kotoba-semantic-ui-schema\""))
      (is (str/includes? html "join:jurisdiction-&gt;country"))
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

    (testing "ontology.graph and ontology.view honor explicit empty {:layers []} (0 nodes / 0 edges)"
      (let [by-layer (ov/invoke graph "ontology.graph" {:layers ["ipld"]})
            by-kind (ov/invoke graph "ontology.graph" {:kinds ["connector"]})
            empty-g (ov/invoke graph "ontology.graph" {:layers []})
            empty-v (ov/invoke graph "ontology.view" {:format "svg" :layers []})]
        (is (= "ontology.graph/v1" (:schema/version by-layer)))
        (is (= #{"ipld"} (set (map :layer (:nodes by-layer)))))
        (is (= #{:connector} (set (map :kind (:nodes by-kind)))))
        (is (= 0 (count (:nodes empty-g))))
        (is (= 0 (count (:edges empty-g))))
        (is (not (str/includes? (:content empty-v) "data-node-id="))
            "ontology.view with explicit {:layers []} must render 0 nodes")))

    (testing "ontology.view renders svg and html"
      (let [v-svg (ov/invoke graph "ontology.view" {:format "svg" :title "View SVG"})
            v-html (ov/invoke graph "ontology.view" {:format "html" :title "View HTML"})]
        (is (= "svg" (:format v-svg)))
        (is (= "image/svg+xml" (:content-type v-svg)))
        (is (str/includes? (:content v-svg) "View SVG"))
        (is (= "html" (:format v-html)))
        (is (= "text/html; charset=utf-8" (:content-type v-html)))
        (is (str/includes? (:content v-html) "View HTML"))))

    (testing "ontology.query_sql executes bounded read-only SELECT (accepting :sql or :query) with scanned-rows"
      (let [res (ov/invoke graph "ontology.query_sql"
                           {:sql "SELECT id, kind FROM nodes WHERE layer = 'connector' LIMIT 10"})
            res-alias (ov/invoke graph "ontology.query_sql"
                                 {:query "SELECT id, kind FROM nodes WHERE layer = 'connector' LIMIT 10"})]
        (is (= res res-alias))
        (is (= "sql-readonly-v1" (:dialect res)))
        (is (= "nodes" (:table res)))
        (is (= ["id" "kind"] (:columns res)))
        (is (= 2 (:row-count res)))
        (is (= (count (:nodes graph)) (:scanned-rows res)))
        (is (= #{"connector:jp.geps" "connector:jp.kkj"}
               (set (map #(get % "id") (:rows res)))))))

    (testing "ontology.query_sparql executes PREFIX-expanded QNames, typed/language RDF literals, and returns algebra-edn"
      (let [sel (ov/invoke graph "ontology.query_sparql"
                           {:sparql "SELECT ?s ?cid WHERE { ?s ipld:cid ?cid } LIMIT 10"})
            ask-yes (ov/invoke graph "ontology.query_sparql"
                               {:sparql "ASK { connector:jp.kkj produces type:tender }"})
            ask-no (ov/invoke graph "ontology.query_sparql"
                              {:sparql "ASK { connector:jp.kkj produces type:nonexistent }"})
            rdf-g (ov/project-graph
                   {:quads [{:subject {:rdf/type :iri :value "urn:ex:s1"}
                             :predicate {:rdf/type :iri :value "http://vocab-a.example/rel"}
                             :object {:rdf/type :iri :value "urn:ex:o1"}}
                            {:subject {:rdf/type :iri :value "urn:ex:s1"}
                             :predicate {:rdf/type :iri :value "http://vocab-b.example/rel"}
                             :object {:rdf/type :iri :value "urn:ex:o2"}}
                            {:subject {:rdf/type :iri :value "urn:ex:s1"}
                             :predicate {:rdf/type :iri :value "http://www.w3.org/2000/01/rdf-schema#label"}
                             :object {:rdf/type :literal :value "Hello" :language "en"}}
                            {:subject {:rdf/type :iri :value "urn:ex:s1"}
                             :predicate {:rdf/type :iri :value "http://schema.example/amount"}
                             :object {:rdf/type :literal :value "42"
                                      :datatype {:rdf/type :iri :value "http://www.w3.org/2001/XMLSchema#integer"}}}]})
            pfx-a (ov/invoke rdf-g "ontology.query_sparql"
                             {:sparql "PREFIX va: <http://vocab-a.example/> SELECT ?s ?o WHERE { ?s va:rel ?o }"})
            lit-lang (ov/invoke rdf-g "ontology.query_sparql"
                                {:sparql "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?s ?l WHERE { ?s rdfs:label ?l }"})
            lit-typed (ov/invoke rdf-g "ontology.query_sparql"
                                 {:sparql "PREFIX sch: <http://schema.example/> ASK { <urn:ex:s1> sch:amount \"42\"^^xsd:integer }"})
            lit-bare (ov/invoke rdf-g "ontology.query_sparql"
                                {:sparql "PREFIX sch: <http://schema.example/> ASK { <urn:ex:s1> sch:amount \"42\" }"})]
        (is (= "sparql-readonly-v1" (:dialect sel)))
        (is (= "SELECT" (:form sel)))
        (is (string? (:algebra-edn sel)))
        (is (str/includes? (:algebra-edn sel) ":sparql/op"))
        (is (pos? (:row-count sel)))
        (is (true? (:ask ask-yes)))
        (is (false? (:ask ask-no)))
        (is (= 1 (:row-count pfx-a))
            "PREFIX va: must expand va:rel to http://vocab-a.example/rel without colliding with vocab-b")
        (is (= "urn:ex:o1" (get-in pfx-a [:bindings 0 "?o"])))
        (is (some #(= "Hello@en" (get % "?l")) (:bindings lit-lang)))
        (is (true? (:ask lit-typed)))
        (is (true? (:ask lit-bare)))))))
