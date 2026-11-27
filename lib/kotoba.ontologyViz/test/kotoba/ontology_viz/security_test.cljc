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

(deftest malformed-inputs-and-strict-cidv1-fail-closed-test
  (testing "non-map input, malformed types, connectors, datoms, quads, joins are refused"
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
           (refusal-reason #(ov/project-graph {:joins [{:from-attr :a :to-attr :b :match-rule :eval-js}]})))))

  (testing "strict binary CIDv1 parsing rejects fake base32 strings, wrong lengths, and bad padding"
    (is (false? (ov/valid-cid? "not-a-cid")))
    (is (false? (ov/valid-cid? "http://evil.example/cid")))
    (is (false? (ov/valid-cid? "baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))
        "version byte 0x00 is not CIDv1")
    (is (false? (ov/valid-cid? "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvyk"))
        "truncated digest must be rejected")
    ;; Flip last base32 char to introduce non-zero residual padding bits
    (is (false? (ov/valid-cid? "bafyreihdwdcefgh4dqkjv67uzcmw7ojee6xedzdetojuzjevtenxquvykv"))
        "non-canonical base32 padding bits must be rejected")
    (is (= :invalid-cid (refusal-reason #(ov/ipld-link "baaaaaaaaaaaaaaaaaaaaaaaaaaaa"))))
    (is (= :invalid-cid (refusal-reason #(ov/project-graph {:basis {:root-cid "baaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}))))))

(deftest g3-caller-supplied-normalized-graph-cannot-bypass-validation-test
  (let [valid-graph (ov/project-graph gt/sample-input)]
    (testing "unknown schema version or kind is rejected at render/dispatch boundaries"
      (let [bad-ver (assoc valid-graph :schema/version "ontology.graph/v99")]
        (is (= :invalid-graph-schema (refusal-reason #(ov/render-svg bad-ver))))
        (is (= :invalid-graph-schema (refusal-reason #(ov/render-html bad-ver))))
        (is (= :invalid-graph-schema (refusal-reason #(ov/invoke bad-ver "ontology.view" {:format "svg"}))))
        (is (= :invalid-graph-schema (refusal-reason #(ov/->yataverse-graph bad-ver))))))

    (testing "CSS/SVG paint injection in caller-supplied layer :color/:bg fails closed"
      (let [bad-color (assoc-in valid-graph [:layers 0 :color] "red; background:url(https://evil.example)")]
        (is (= :invalid-color (refusal-reason #(ov/render-svg bad-color))))
        (is (= :invalid-color (refusal-reason #(ov/render-html bad-color))))
        (is (= :invalid-color (refusal-reason #(ov/invoke bad-color "ontology.view" {:format "html"}))))))

    (testing "malicious or non-finite layout dimensions in caller-supplied graph fail closed"
      (let [bad-width (assoc-in valid-graph [:nodes 0 :layout :width] -50)
            bad-str (assoc-in valid-graph [:nodes 0 :layout :x] "0\" onload=\"alert(1)")]
        (is (= :invalid-layout (refusal-reason #(ov/render-svg bad-width))))
        (is (= :invalid-layout (refusal-reason #(ov/render-svg bad-str))))
        (is (= :invalid-layout (refusal-reason #(ov/render-html bad-str))))))

    (testing "invalid join counts in caller-supplied graph fail closed"
      (let [bad-join (assoc-in valid-graph [:joins 0 :matched-count] "<script>alert(1)</script>")]
        (is (= :invalid-join (refusal-reason #(ov/render-html bad-join))))))))

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

(deftest explicit-bounds-and-precount-enforced-test
  (testing "invalid or ceiling-exceeding limit overrides are rejected"
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes 0}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes -5}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:max-nodes 999999}))))
    (is (= :invalid-limit (refusal-reason #(ov/resolve-limits {:unknown-limit 10})))))

  (testing "pre-count bound stops infinite lazy sequences without hanging"
    (let [infinite-datoms (map (fn [i] [:e :a i]) (range))]
      (is (= :max-input-items-exceeded
             (refusal-reason #(ov/project-graph {:limits {:max-input-items 5}
                                                 :datoms infinite-datoms}))))))

  (testing "collection width and scalar value length bounds fail closed"
    (is (= :max-collection-width-exceeded
           (refusal-reason
            #(ov/project-graph {:limits {:max-collection-width 3}
                                :joins [{:from-attr :a :to-attr :b
                                         :source-values ["1" "2" "3" "4"]}]}))))
    (is (= :max-value-length-exceeded
           (refusal-reason
            #(ov/project-graph {:limits {:max-value-length 16}
                                :facts [{:id "f1" :note (apply str (repeat 20 "a"))}]})))))

  (testing "max-nodes, max-edges, max-label-length, max-depth, and max-joins fail closed"
    (is (= :max-nodes-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-nodes 2}
               :ontology {:object-types [{:id :a :name "A"}
                                         {:id :b :name "B"}
                                         {:id :c :name "C"}]}}))))
    (is (= :max-edges-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-edges 1}
               :ontology {:object-types [{:id :t :name "T" :attributes {:a :string :b :string}}]}}))))
    (is (= :max-label-length-exceeded
           (refusal-reason
            #(ov/project-graph
              {:limits {:max-label-length 32}
               :ontology {:object-types [{:id :t :name (apply str (repeat 40 "x"))}]}}))))
    (let [deep (reduce (fn [acc i] {(str "k" i) acc}) "leaf" (range 12))]
      (is (= :max-depth-exceeded
             (refusal-reason
              #(ov/project-graph
                {:limits {:max-depth 5}
                 :ipld-nodes {gt/sample-root-cid deep}})))))
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
      (is (= 3 (count (re-seq #"</script>" html)))
          "untrusted </script> payload must not create extra closing script tags")
      (is (str/includes? html "\\u003c\\/script\\u003e")
          "embedded JSON must escape </script> safely"))))

(deftest semantic-query-guards-and-no-silent-misanswers-test
  (let [graph (ov/project-graph gt/sample-input)]
    (testing "SQL rejects DML, DDL, comments, stacked statements, unknown columns, aliases, and bad LIMITs"
      (doseq [bad ["DROP TABLE nodes"
                   "DELETE FROM nodes"
                   "SELECT id FROM nodes; DROP TABLE nodes"
                   "SELECT id FROM nodes -- comment"
                   "UPDATE nodes SET label='x'"
                   "INSERT INTO nodes VALUES ('a')"]]
        (is (= :unsafe-sql
               (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql bad})))
            (str "expected :unsafe-sql for " bad)))
      (is (= :unknown-sql-column
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT nonexistent FROM nodes"}))))
      (is (= :unknown-sql-column
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT id FROM nodes WHERE ghost = 'x'"}))))
      (is (= :unsupported-sql-shape
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT id AS node_id FROM nodes"}))))
      (is (= :unsupported-sql-shape
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT COUNT(*) FROM nodes"}))))
      (is (= :invalid-sql
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT id FROM nodes LIMIT 0"}))))
      (is (= :invalid-sql
             (refusal-reason #(ov/invoke graph "ontology.query_sql" {:sql "SELECT id FROM nodes LIMIT 999999999999"})))))

    (testing "SPARQL rejects SERVICE, LOAD, UPDATE, trailing modifiers, and unsupported clauses (no silent drop)"
      (doseq [bad ["SELECT * WHERE { SERVICE <https://evil.example/sparql> { ?s ?p ?o } }"
                   "LOAD <https://evil.example/data.ttl>"
                   "DELETE WHERE { ?s ?p ?o }"
                   "INSERT DATA { <a> <b> <c> }"
                   "SELECT ?s FROM <https://evil.example/g> WHERE { ?s ?p ?o }"]]
        (is (= :remote-fetch-forbidden
               (refusal-reason #(ov/invoke graph "ontology.query_sparql" {:sparql bad})))
            (str "expected :remote-fetch-forbidden for " bad)))
      (doseq [unsupported ["SELECT ?s ?o WHERE { ?s rdf:type ?o } ORDER BY ?s"
                           "SELECT ?s ?o WHERE { ?s rdf:type ?o } OFFSET 5"
                           "SELECT ?s ?o WHERE { ?s rdf:type ?o . OPTIONAL { ?s ipld:cid ?c } }"
                           "SELECT ?s ?o WHERE { ?s rdf:type ?o . FILTER (?o = \"connector\") }"
                           "ASK { ?s rdf:type ?o } LIMIT 1"]]
        (is (contains? #{:unsupported-sparql-clause :unsafe-sparql}
                       (refusal-reason #(ov/invoke graph "ontology.query_sparql" {:sparql unsupported})))
            (str "expected refusal for unsupported SPARQL " unsupported)))
      (is (= :unsafe-sparql
             (refusal-reason #(ov/invoke graph "ontology.query_sparql"
                                         {:sparql "SELECT ?s ?o WHERE { ?s rdf:type ?o } TRAILING GARBAGE"})))))

    (testing "SPARQL does not prematurely truncate intermediate BGP bindings before subsequent patterns"
      (let [big-input {:ontology {:object-types
                                  (vec (for [i (range 60)]
                                         {:id (keyword (str "t" i))
                                          :name (str "Type " i)}))}}
            big-graph (ov/project-graph big-input)
            ;; Even with :limit 1, matching the last node (t59) on the 2nd pattern must succeed!
            ask-last (ov/invoke big-graph "ontology.query_sparql"
                                {:sparql "ASK { ?s rdf:type object-type . ?s rdfs:label \"Type 59\" }"
                                 :limit 1})
            sel-last (ov/invoke big-graph "ontology.query_sparql"
                                {:sparql "SELECT ?s WHERE { ?s rdf:type object-type . ?s rdfs:label \"Type 59\" } LIMIT 1"})]
        (is (true? (:ask ask-last)))
        (is (= 1 (:row-count sel-last)))
        (is (= "type:t59" (get-in sel-last [:bindings 0 "?s"])))))

    (testing "unknown Semantic UI operation or view format fails closed"
      (is (= :unknown-operation
             (refusal-reason #(ov/invoke graph "ontology.drop_all" {}))))
      (is (= :invalid-format
             (refusal-reason #(ov/invoke graph "ontology.view" {:format "exe"})))))))
