(ns kotobase.lake.catalog-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotobase.lake.catalog :as cat]
            [kotobase.lake.sniff :as sniff]))

(def base
  {:cid "bafkreiabc" :size 12 :tenant "acme" :ingested-at "2026-08-04T09:00:00Z"})

;; ── the property the whole library exists for ──────────────────────────────

(deftest accepts-anything
  (testing "no byte sequence is turned away on format grounds"
    (doseq [[label prefix]
            [["empty object"        []]
             ["one byte"            [0x00]]
             ["512 zeros"           (vec (repeat 512 0))]
             ["512 high bytes"      (vec (repeat 512 0xFF))]
             ["truncated PNG magic" [0x89 0x50]]
             ;; real UTF-8 multibyte, spelled out: ascii-bytes is ASCII only.
             ["utf-8 text"          (into (sniff/ascii-bytes "hi ") [0xE4 0xB8 0x96 0xE7 0x95 0x8C])]
             ["csv"                 (sniff/ascii-bytes "id,name\n1,alice\n")]
             ["a real PDF"          (sniff/ascii-bytes "%PDF-1.7")]
             ["encrypted noise"     (vec (repeat 200 0x5A))]]]
      (let [r (cat/admit (assoc base :prefix prefix))]
        (is (:admitted? r) (str label " must be admissible"))
        (is (seq (:quads r)) (str label " must produce catalog facts")))))
  (testing "a zero-length object is an object"
    (is (:admitted? (cat/admit (assoc base :size 0 :prefix [])))))
  (testing "nothing optional is required"
    (is (:admitted? (cat/admit base))
        "the four required fields and no format information at all")))

(deftest refuses-exactly-four-things-and-none-of-them-is-a-format
  (doseq [[field descriptor]
          [[:cid         (dissoc base :cid)]
           [:size        (dissoc base :size)]
           [:tenant      (dissoc base :tenant)]
           [:ingested-at (dissoc base :ingested-at)]]]
    (let [r (cat/admit descriptor)]
      (is (false? (:admitted? r)))
      (is (= #{field} (into #{} (map :field) (:refusals r))))))
  (testing "size must be a non-negative integer, because it comes from the bytes"
    (is (false? (:admitted? (cat/admit (assoc base :size -1)))))
    (is (false? (:admitted? (cat/admit (assoc base :size 1.5)))))
    (is (false? (:admitted? (cat/admit (assoc base :size "12"))))))
  (testing "id components must not smuggle the separator"
    (is (false? (:admitted? (cat/admit (assoc base :tenant "ac|me")))))))

;; ── the object / claim cut ─────────────────────────────────────────────────

(deftest same-bytes-are-one-object-across-tenants
  (let [a (cat/admit (assoc base :tenant "acme"  :declared-media-type "text/csv"))
        b (cat/admit (assoc base :tenant "globex" :declared-media-type "application/json"))
        object-facts (fn [r] (into #{} (filter #(= (:object-id r) (:s %))) (:quads r)))]
    (is (= (:object-id a) (:object-id b))
        "content addressing already decided this; dedup is not a feature to add")
    (is (not= (:claim-id a) (:claim-id b)))
    (is (= (object-facts a) (object-facts b))
        "object facts are functions of the bytes alone, so two observers must agree")
    (testing "contradictory declarations coexist instead of clobbering"
      (let [both (into (:quads a) (:quads b))]
        (is (= 2 (count (cat/claims both (:object-id a)))))
        (is (= 1 (count (cat/objects both))))))))

(deftest replay-is-idempotent
  (let [d (assoc base :declared-media-type "text/csv" :filename "a.csv")]
    (is (= (:quads (cat/admit d)) (:quads (cat/admit d)))
        "a retried upload must not accumulate an indistinguishable second claim")))

(deftest observations-are-recorded-against-the-observer
  (let [r (cat/admit (assoc base :prefix (sniff/ascii-bytes "%PDF-1.7")))
        e (cat/entity (:quads r) (:claim-id r))]
    (is (= "pdf" (get e "claim/observed-format")))
    (is (= sniff/sniffer-version (get e "claim/sniffer-version"))
        "a classification is a function of bytes AND classifier; the version says which one spoke")
    (is (nil? (get (cat/entity (:quads r) (:object-id r)) "claim/observed-format"))
        "nothing observer-dependent may sit on the object entity"))
  (testing "the version is recorded even when the observer said nothing"
    (let [r (cat/admit (assoc base :prefix (sniff/ascii-bytes "id,name\n")))
          e (cat/entity (:quads r) (:claim-id r))]
      (is (nil? (get e "claim/observed-format")))
      (is (= sniff/sniffer-version (get e "claim/sniffer-version"))))))

;; ── declared vs observed ───────────────────────────────────────────────────

(deftest declared-vs-observed-verdicts
  (testing "undetermined is the majority verdict in a real lake"
    (is (= :undetermined (:declared-vs-observed
                          (cat/admit (assoc base :declared-media-type "text/csv"
                                            :prefix (sniff/ascii-bytes "id,name\n"))))))
    (is (= :undetermined (:declared-vs-observed (cat/admit base)))))
  (testing "agree"
    (is (= :agree (:declared-vs-observed
                   (cat/admit (assoc base :declared-media-type "application/pdf"
                                     :prefix (sniff/ascii-bytes "%PDF-1.7")))))))
  (testing "a compression envelope is a different layer, not a disagreement"
    (is (= :enveloped (:declared-vs-observed
                       (cat/admit (assoc base :declared-media-type "text/csv"
                                         :prefix [0x1F 0x8B 0x08]))))))
  (testing "a real contradiction is recorded, not refused"
    (let [r (cat/admit (assoc base :declared-media-type "text/csv"
                              :filename "quarterly.csv"
                              :prefix (sniff/ascii-bytes "%PDF-1.7")))]
      (is (:admitted? r) "the most interesting objects must not be turned away")
      (is (= :conflict (:declared-vs-observed r)))
      (is (= #{(:claim-id r)} (cat/conflicting-claims (:quads r)))
          "and must be findable by asking"))))

;; ── reading it back ────────────────────────────────────────────────────────

(deftest catalog-is-queryable-quads
  (let [r (cat/admit (assoc base :declared-media-type "text/csv"
                            :filename "a.csv"
                            :source-uri "s3://bucket/a.csv"
                            :ingest-actor "did:key:z6Mk"))
        e (cat/entity (:quads r) (:claim-id r))]
    (is (every? #(and (contains? % :s) (contains? % :p) (contains? % :o)) (:quads r))
        "the shape datom-source scans and datalog.index indexes")
    (is (= 12 (cat/object-size (:quads r) (:object-id r))))
    (is (= "a.csv" (get e "claim/filename")))
    (is (= "s3://bucket/a.csv" (get e "claim/source-uri")))
    (is (= "did:key:z6Mk" (get e "claim/ingest-actor")))
    (is (= "acme" (get e "claim/tenant")))
    (is (= (:object-id r) (get e "claim/object")))))

(deftest absent-optional-fields-emit-no-facts
  (let [r (cat/admit base)
        e (cat/entity (:quads r) (:claim-id r))]
    (doseq [attr ["claim/filename" "claim/source-uri" "claim/ingest-actor"
                  "claim/declared-media-type" "claim/observed-format"]]
      (is (nil? (get e attr)) (str attr " must be absent, not blank")))))
