(ns kotobase.lake.docs-test
  "The catalog encoding, both directions, in one test file for the same
  reason both directions live in one namespace: a writer and a reader that
  disagreed would produce `:no-such-object` for an object that is right
  there, which is indistinguishable from the answer the authorization gate
  gives a caller who may not have it."
  (:require [clojure.test :refer [deftest is testing]]
            [kotobase.lake.acquire :as acquire]
            [kotobase.lake.catalog :as catalog]
            [kotobase.lake.docs :as docs]))

(def ^:private cid "bafkreiadsbmmn4waznesyuz3bjgrj33xzqhxrk6mz3ksq7meugrachh3qe")

(defn- admission []
  (catalog/admit {:cid cid :size 2427 :tenant "did:key:zAcme"
                  :ingested-at "2026-08-04T09:00:00Z"
                  :filename "sales.parquet"
                  :declared-media-type "application/vnd.apache.parquet"}))

(defn- admitted [] (:quads (admission)))

(deftest quads-survive-the-document-round-trip
  (let [quads (admitted)]
    (testing "every quad comes back, and nothing extra appears"
      (is (= quads (docs/docs->quads (docs/quads->docs quads)))))
    (testing "one document per subject, keyed by the subject"
      (let [d (docs/quads->docs quads)]
        (is (contains? d (catalog/object-id cid)))
        (is (= 1 (count (filter #(re-find #"^claim:" %) (keys d)))))))))

(deftest from-state-reads-the-collection-the-deployment-names
  (let [quads (admitted)
        state {:docs {"lake-catalog" (docs/quads->docs quads)}}]
    (is (= quads (docs/from-state state)))
    (is (= quads (docs/from-state state "lake-catalog")))
    (testing "a collection this graph does not have is empty, not an error"
      (is (= #{} (docs/from-state state "somewhere-else")))
      (is (= #{} (docs/from-state {:docs {}}))))))

(deftest keyword-attributes-decode-to-the-strings-the-gate-compares-against
  ;; A document authored in EDN naturally grows keyword keys. `acquire/holds?`
  ;; compares `(get entity "claim/tenant")` against a string literal, so a
  ;; keyword that stayed a keyword would make a real claim invisible — and
  ;; invisible here means refused, which is the failure that looks like
  ;; correct behaviour.
  (let [d {"claim:acme|x|t" {:claim/object "obj:x"
                             :claim/tenant "acme"}}]
    (is (= #{{:s "claim:acme|x|t" :p "claim/object" :o "obj:x"}
             {:s "claim:acme|x|t" :p "claim/tenant" :o "acme"}}
           (docs/docs->quads d)))))

(deftest object-size-comes-from-the-catalog
  (let [quads (admitted)]
    (is (= 2427 (docs/object-size quads cid)))
    (is (nil? (docs/object-size quads "bafkreisomethingelse")))))

(deftest a-non-map-document-is-skipped-rather-than-fatal
  ;; The collection is a tenant's own; something else may be in it.
  (let [d {"obj:x" {"object/cid" "x" "object/size" 1}
           "junk" "not a map"}]
    (is (= #{{:s "obj:x" :p "object/cid" :o "x"}
             {:s "obj:x" :p "object/size" :o 1}}
           (docs/docs->quads d)))))

(deftest what-an-ingest-writes-is-what-the-gate-opens-on
  ;; The property the whole namespace exists for, asserted end to end rather
  ;; than as a round trip: documents produced from an admission, stored under
  ;; a collection and hydrated back, satisfy `acquire/holds?` for the tenant
  ;; that ingested and refuse everyone else. A round trip alone would still
  ;; pass if both directions agreed on an encoding the gate cannot read.
  (let [state {:docs {docs/default-collection (docs/admitted->docs (admission))}}
        quads (docs/from-state state)]
    (is (true? (acquire/holds? quads cid "did:key:zAcme")))
    (is (false? (acquire/holds? quads cid "did:key:zSomeoneElse")))
    (is (false? (acquire/holds? quads "bafkreisomethingelse" "did:key:zAcme")))))

(deftest a-refused-admission-produces-no-documents
  ;; `admit` refuses a descriptor whose record would be meaningless. Encoding
  ;; the refusal map's absent `:quads` would store an empty catalog entry, and
  ;; the ingest would report success for an object the reader then reports as
  ;; `:no-such-object`.
  (let [refused (catalog/admit {:cid cid :size 2427 :ingested-at "2026-08-04T09:00:00Z"})]
    (is (false? (:admitted? refused)))
    (is (nil? (docs/admitted->docs refused)))
    (is (= (docs/quads->docs (admitted)) (docs/admitted->docs (admission))))))
