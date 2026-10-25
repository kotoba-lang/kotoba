(ns kotobase.lake.rdf-test
  (:require [clojure.test :refer [deftest is testing]]
            [datom.source :as source]
            [kotobase.lake.reader :as reader]
            [kotobase.lake.rdf :as rdf]
            [nquads.core]))

(def ^:private oid "obj:bafkA")
(defn- decode [doc] (rdf/statements->quads oid (nquads.core/parse doc)))

(deftest a-triple-is-already-a-lake-row
  ;; The reason this reader is the cheapest in the system: no column model, no
  ;; schema inference, no type unification. Subject-predicate-object IS
  ;; {:s :p :o}.
  (is (= [{:s "urn:ex:alice" :p "urn:ex:name" :o "Alice"}]
         (decode "<urn:ex:alice> <urn:ex:name> \"Alice\" ."))))

(deftest an-iri-object-keeps-its-iri
  (is (= [{:s "urn:ex:a" :p "urn:ex:knows" :o "urn:ex:b"}]
         (decode "<urn:ex:a> <urn:ex:knows> <urn:ex:b> ."))))

(deftest typed-literals-become-values-the-plane-compares
  (is (= [{:s "urn:ex:a" :p "urn:ex:age" :o 42}]
         (decode (str "<urn:ex:a> <urn:ex:age> "
                      "\"42\"^^<http://www.w3.org/2001/XMLSchema#integer> ."))))
  (is (= [{:s "urn:ex:a" :p "urn:ex:ok" :o true}]
         (decode (str "<urn:ex:a> <urn:ex:ok> "
                      "\"true\"^^<http://www.w3.org/2001/XMLSchema#boolean> ."))))
  (testing "an ill-typed literal keeps its lexical form rather than throwing --
            RDF permits it and a document is not corrupt for containing one"
    (is (= [{:s "urn:ex:a" :p "urn:ex:age" :o "abc"}]
           (decode (str "<urn:ex:a> <urn:ex:age> "
                        "\"abc\"^^<http://www.w3.org/2001/XMLSchema#integer> .")))))
  (testing "xsd:double is deliberately NOT coerced: a column mixing longs and
            doubles compares in ways a caller does not expect, and
            columnar.stats orders with compare"
    (is (= [{:s "urn:ex:a" :p "urn:ex:v" :o "1.5"}]
           (decode (str "<urn:ex:a> <urn:ex:v> "
                        "\"1.5\"^^<http://www.w3.org/2001/XMLSchema#double> ."))))))

;; ── the three places RDF and the datom plane do not line up ────────────────

(deftest a-blank-node-is-scoped-to-the-object-it-came-from
  ;; `_:b0` in one file and `_:b0` in another are DIFFERENT nodes. Verbatim
  ;; labels merge unrelated nodes into something that still answers queries,
  ;; which is the worst kind of wrong.
  (is (= [{:s "obj:bafkA#_:b0" :p "urn:ex:name" :o "Anon"}]
         (decode "_:b0 <urn:ex:name> \"Anon\" .")))
  (testing "and two objects with the same label do not collide"
    (let [a (rdf/statements->quads "obj:A" (nquads.core/parse "_:b0 <urn:ex:p> \"x\" ."))
          b (rdf/statements->quads "obj:B" (nquads.core/parse "_:b0 <urn:ex:p> \"x\" ."))]
      (is (not= (:s (first a)) (:s (first b))))))
  (testing "a blank node in object position is scoped too"
    (is (= "obj:bafkA#_:b1"
           (:o (first (decode "<urn:ex:a> <urn:ex:p> _:b1 .")))))))

(deftest a-named-graph-is-refused-rather-than-dropped
  ;; datom.source scans [s p o] and a lake row is a TRIPLE. Dropping the graph
  ;; would merge statements RDF holds apart: <a> <b> <c> in G1 and in G2 are
  ;; different statements.
  (let [e (try (decode "<urn:ex:a> <urn:ex:b> <urn:ex:c> <urn:ex:g> .") nil
               (catch #?(:clj Exception :cljs :default) e (ex-data e)))]
    (is (= :kotobase.lake/named-graph-unrepresentable (:type e)))
    (is (= "urn:ex:g" (:graph e))
        "the refusal names the graph, so a caller knows what could not be kept")))

(deftest an-iri-and-a-string-literal-collapse-together
  ;; Documented, not fixed. Wrapping objects in a term record would stop them
  ;; joining against every other value in the plane, which is the whole point
  ;; of materialising into it.
  (is (= (:o (first (decode "<urn:ex:a> <urn:ex:p> <urn:x> .")))
         (:o (first (decode "<urn:ex:a> <urn:ex:p> \"urn:x\" .")))))
  (testing "a caller needing the distinction should not flatten RDF into the
            datom plane; this test exists so the limit is not rediscovered"
    (is (= "urn:x" (:o (first (decode "<urn:ex:a> <urn:ex:p> <urn:x> .")))))))

;; ── through the registry ────────────────────────────────────────────────────

(deftest the-decoder-registers-and-decodes-a-document
  (let [reg (reduce #(reader/register %1 %2 (rdf/decoder)) (reader/registry)
                    rdf/media-types)
        doc (str "<urn:ex:alice> <urn:ex:name> \"Alice\" .\n"
                 "# a comment, skipped\n"
                 "\n"
                 "<urn:ex:alice> <urn:ex:knows> <urn:ex:bob> .\n")
        {:keys [decoded? quads via]}
        (reader/decode reg {:claim-id "c1" :object-id oid
                            :declared-media-type "application/n-triples"}
                       doc)]
    (is decoded?)
    (is (= "application/n-triples" via))
    (is (= [{:s "urn:ex:alice" :p "urn:ex:name" :o "Alice"}
            {:s "urn:ex:alice" :p "urn:ex:knows" :o "urn:ex:bob"}]
           quads)))
  (testing "application/n-quads registers too -- a producer of the triples
            subset commonly declares it, and refusing on the NAME rather than
            on a graph being present would reject documents this handles"
    (let [reg (reduce #(reader/register %1 %2 (rdf/decoder)) (reader/registry)
                      rdf/media-types)]
      (is (:decoded? (reader/decode reg {:claim-id "c" :object-id oid
                                         :declared-media-type "application/n-quads"}
                                    "<urn:ex:a> <urn:ex:b> \"c\" ."))))))

(deftest a-malformed-document-does-not-fail-the-query
  ;; reader/decode catches: malformed input is the normal state of real data,
  ;; and one bad object must not take down a scan over the others.
  (let [reg (reader/register (reader/registry) "application/n-triples" (rdf/decoder))
        r (reader/decode reg {:claim-id "c" :object-id oid
                              :declared-media-type "application/n-triples"}
                         "this is not n-triples")]
    (is (false? (:decoded? r)))
    (is (= :decoder-threw (:reason r)))))

(deftest decoded-rows-are-scannable-beside-the-catalog
  (let [quads (decode (str "<urn:ex:alice> <urn:ex:name> \"Alice\" .\n"
                           "<urn:ex:bob> <urn:ex:name> \"Bob\" .\n"))]
    (is (= #{{:s "urn:ex:alice" :p "urn:ex:name" :o "Alice"}}
           (source/scan-set (source/of-quads quads) [nil nil "Alice"])))))
