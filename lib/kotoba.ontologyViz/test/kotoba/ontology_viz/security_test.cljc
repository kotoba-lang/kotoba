(ns kotoba.ontology-viz.security-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [kotoba.ontology-viz :as ov]
            [kotoba.ontology-viz.graph-test :as gt]))

(defn- refusal-reason [f]
  (try
    (f)
    ::no-throw
    (catch #?(:clj clojure.lang.ExceptionInfo
              :cljs :default) e
      (:reason (ex-data e)))))

(deftest malformed-inputs-fail-closed-test
  (testing "non-map input, malformed types, connectors, datoms, quads, joins, and CIDs are refused"
    (is (= :invalid-input (refusal-reason #(ov/project-graph "not-a-map"))))
    (is (= :invalid-object-type
           (refusal-reason #(ov/project-graph {:ontology {:object-types [{:name "missing-id"}]}}))))
    (is (= :invalid-connector
           (refusal-reason #(ov/project-graph {:connectors {:connectors [{:id :jp.kkj}]}}))))
    (is (= :invalid-datom
           (refusal-reason #(ov/project-graph {:datoms [[:only-two]]}))))
    (is (= :invalid-rdf-quad
           (refusal-reason #(ov/project-graph {:quads [{:subject "s"}]}))))
    (is (= :invalid-join
           (refusal-reason #(ov/project-graph {:joins [{:from-attr :a :to-attr :b :match-rule :eval-js}]}))))
    (is (= :invalid-cid
           (refusal-reason #(ov/ipld-link "not-a-cid"))))
    (is (= :invalid-cid
           (refusal-reason #(ov/project-graph {:basis {:root-cid "http://evil.example/cid"}}))))))

(deftest remote-context-and-external-fetch-refused-test
  (testing "remote JSON-LD @context string or @import directive fails closed"
    (is (= :remote-context-forbidden
           (refusal-reason #(ov/project-graph
                             {:facts [{"@context" "https://schema.org/" :id "f1"}]}))))
    (is (= :remote-context-forbidden
           (refusal-reason #(ov/project-graph
                             {:facts [{(keyword "@context") ["https://example.org/ctx.jsonld"] :id "f1"}]}))))
    (is (= :remote-context-forbidden
           (refusal-reason #(ov/project-graph
                             {:facts [{(keyword "@context") {(keyword "@import") "https://example.org/ctx.jsonld"} :id "f1"}]})))))
  (testing "explicit remote fetch flags fail closed"
    (is (= :remote-fetch-forbidden
           (refusal-reason #(ov/project-graph {:fetch-remote? true})))))
  (testing "inline local @context map (no @import) is allowed"
    (let [g (ov/project-graph {:facts [{(keyword "@context") {:name "rdfs:label"} :id "local-1" :name "Local"}]})]
      (is (= 1 (count (:nodes g)))))))

(deftest explicit-bounds-enforced-test
  (testing "invalid or ceiling-exceeding limit overrides are rejected"
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes 0}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes -5}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes 999999}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:unknown-limit 10})))))

  (testing "max-nodes bound fails closed"
    (is (= :max-nodes-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-nodes 2}
               :ontology {:object-types [{:id :a :name "A"}
                                         {:id :b :name "B"}
                                         {:id :c :name "C"}]}})))))

  (testing "max-edges bound fails closed"
    (is (= :max-edges-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-edges 1}
               :ontology {:object-types [{:id :t :name "T" :attributes {:a :string :b :string}}]}})))))

  (testing "max-label-length bound fails closed"
    (let [too-long (apply str (repeat 40 "x"))]
      (is (= :max-label-length-exceeded
             (refusal-reason
              #(ov/project-graph
                {:limits {:max-label-length 32}
                 :ontology {:object-types [{:id :t :name too-long}]}}))))))

  (testing "max-depth bound fails closed on deeply nested IPLD/input maps"
    (let [deep (reduce (fn [acc i] {(str "k" i) acc}) "leaf" (range 12))]
      (is (= :max-depth-exceeded
             (refusal-reason
              #(ov/project-graph
                {:limits {:max-depth 5}
                 :ipld-nodes {gt/sample-root-cid deep}}))))))

  (testing "max-joins bound fails closed"
    (is (= :max-joins-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-joins 1}
               :joins [{:from-attr :a :to-attr :b}
                       {:from-attr :c :to-attr :d}]}))))))

(deftest xss-and-script-injection-escaped-test
  (let [xss-payload "</script><img src=x onerror=alert(1)><svg onload=\"alert('x')\"> & '\"test\"'"
        artifact (ov/build-artifact
                  {:ontology {:object-types
                              [{:id :xss-type
                                :name xss-payload
                                :attributes {:evil/attr :string}
                                :key [:evil/attr]}]}
                   :joins [{:from-type :xss-type
                            :from-attr :evil/attr
                            :to-type :xss-type
                            :to-attr :evil/attr
                            :source-values [xss-payload]
                            :target-values []
                            :description xss-payload}]}
                  {:title xss-payload})
        svg (:svg artifact)
        html (:html artifact)]
    (testing "SVG escapes all angle brackets and quotes from untrusted labels"
      (is (not (str/includes? svg "<img")))
      (is (not (str/includes? svg "<svg onload")))
      (is (not (str/includes? svg "</script>")))
      (is (str/includes? svg "&lt;")))
    (testing "HTML escapes untrusted labels and prevents </script> breakout in embedded JSON"
      (is (not (str/includes? html "<img src=x")))
      (is (not (str/includes? html "<svg onload")))
      ;; Exactly 3 closing </script> tags belong to the viewer itself (graph JSON, schema JSON, viewer JS)
      (is (= 3 (count (re-seq #"</script>" html)))
          "untrusted </script> payload must not create extra closing script tags")
      (is (str/includes? html "\\u003c\\/script\\u003e")
          "embedded JSON must escape </script> safely"))))

(deftest semantic-query-guards-fail-closed-test
  (let [graph (ov/project-graph gt/sample-input)]
    (testing "SQL rejects DML, DDL, comments, and stacked statements"
      (doseq [bad ["DROP TABLE nodes"
                   "DELETE FROM nodes"
                   "SELECT id FROM nodes; DROP TABLE nodes"
                   "SELECT id FROM nodes -- comment"
                   "UPDATE nodes SET label='x'"
                   "INSERT INTO nodes VALUES ('a')"]]
        (is (= :unsafe-sql
               (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql bad})))
            (str "expected :unsafe-sql for " bad))))

    (testing "SPARQL rejects SERVICE remote federation, LOAD, and UPDATE"
      (doseq [bad ["SELECT * WHERE { SERVICE <https://evil.example/sparql> { ?s ?p ?o } }"
                   "LOAD <https://evil.example/data.ttl>"
                   "DELETE WHERE { ?s ?p ?o }"
                   "INSERT DATA { <a> <b> <c> }"
                   "SELECT ?s FROM <https://evil.example/g> WHERE { ?s ?p ?o }"]]
        (is (= :remote-fetch-forbidden
               (refusal-reason #(ov/invoke graph "ontology.query_sparql" {:sparql bad})))
            (str "expected :remote-fetch-forbidden for " bad))))

    (testing "unknown Semantic UI operation or view format fails closed"
      (is (= :unknown-operation
             (refusal-reason #(ov/invoke graph "ontology.drop_all" {}))))
      (is (= :invalid-format
             (refusal-reason #(ov/invoke graph "ontology.view" {:format "exe"})))))))
