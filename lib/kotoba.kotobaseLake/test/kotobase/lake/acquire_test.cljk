(ns kotobase.lake.acquire-test
  (:require [clojure.test :refer [deftest is testing]]
            [columnar.source :as csrc]
            [columnar.vector :as cvec]
            [datom.source :as source]
            [kotobase.lake.acquire :as acq]
            [kotobase.lake.catalog :as cat]
            [kotobase.lake.columnar :as lcol]
            [kotobase.lake.reader :as reader]))

(def cid "bafkreiadsbmmn4waznesyuz3bjgrj33xzqhxrk6mz3ksq7meugrachh3qe")
(def other-cid "bafkreibpugzxpp3hgcpwlzphxsozeq2fzjsi33comandtcu4wsl5zorxmu")

(def quads
  (:quads (cat/admit {:cid cid :size-bytes 99 :size 99 :tenant "acme"
                      :ingested-at "2026-08-04T09:00:00Z"
                      :declared-media-type "application/vnd.apache.parquet"})))

;; A stand-in for a format library: it hands back a column source and knows
;; nothing about tenants, catalogs or patterns.
(defn- fake-column-source [opened]
  (fn [handle]
    (swap! opened conj handle)
    (reify csrc/IColumnSource
      (-schema [_] ["price"])
      (-chunk-count [_] 1)
      (-chunk-rows [_ _] 2)
      (-chunk-stats [_ _ _] {:rows 2 :nulls 0 :min 10 :max 20})
      (-read-column [_ _ _] (cvec/column :any [10 20])))))

(defn- registry [opened]
  (reader/register-scan (reader/registry) "application/vnd.apache.parquet"
                        (lcol/scan-reader (fake-column-source opened))))

;; ── the gate ────────────────────────────────────────────────────────────────

(deftest a-tenant-without-a-holding-and-a-nonexistent-object-are-indistinguishable
  (let [opened (atom [])
        reg (registry opened)
        not-mine (acq/source-for reg quads {:cid cid :tenant "globex"})
        not-there (acq/source-for reg quads {:cid other-cid :tenant "globex"})]
    (is (= not-mine not-there)
        "not `both falsey` — EQUAL. CIDs are guessable for any content a
         caller can construct, so a difference of one :reason key turns the
         catalog into a membership oracle over every tenant's data")
    (is (false? (:ok? not-mine)))
    (is (empty? @opened)
        "and the reader was never invoked, so an unauthorized caller costs a
         catalog lookup and no transfer")))

(deftest a-holder-gets-a-scannable-source
  (let [opened (atom [])
        r (acq/source-for (registry opened) quads {:cid cid :tenant "acme"
                                                   :size-bytes 99
                                                   :read-range ::range-fn})]
    (is (:ok? r))
    (is (= "application/vnd.apache.parquet" (:via r)))
    (testing "the handle carries the capability, not the bytes"
      (is (= ::range-fn (:read-range (first @opened))))
      (is (= 99 (:size-bytes (first @opened)))))
    (testing "subjects point back at the object they came from"
      (is (= (str (cat/object-id cid) "#row") (:subject-prefix (first @opened)))))))

(deftest holds?-reads-claims-not-keys
  (is (true? (acq/holds? quads cid "acme")))
  (is (false? (acq/holds? quads cid "globex"))
      "the object key is global by CID; tenant scope lives in the claim")
  (is (false? (acq/holds? quads other-cid "acme"))))

(deftest a-materializing-type-is-not-silently-substituted
  (let [reg (reader/register (reader/registry) "application/vnd.apache.parquet"
                             (fn [_ _] [{:s "a" :p "b" :o "c"}]))
        r (acq/source-for reg quads {:cid cid :tenant "acme"})]
    (is (false? (:ok? r)))
    (is (= :no-scan-reader (:reason r))
        "a whole-object decoder cannot answer a pattern by ranges; substituting
         one turns a range read into a full download exactly when the file got
         big enough to matter")))

(deftest an-incomplete-request-is-refused-before-anything-else
  (is (= :incomplete-request (:reason (acq/source-for (registry (atom [])) quads
                                                      {:cid cid}))))
  (is (= :incomplete-request (:reason (acq/source-for (registry (atom [])) quads
                                                      {:tenant "acme"})))))

;; ── the whole chain ─────────────────────────────────────────────────────────

(deftest a-triple-pattern-reaches-the-column-source-intact
  (let [opened (atom [])
        {:keys [source]} (acq/source-for (registry opened) quads
                                         {:cid cid :tenant "acme"})
        oid (cat/object-id cid)]
    (is (= #{{:s (str oid "#row0") :p "price" :o 10}
             {:s (str oid "#row1") :p "price" :o 20}}
           (source/scan-set source [nil "price" nil])))
    (testing "a bound object filters"
      (is (= #{{:s (str oid "#row1") :p "price" :o 20}}
             (source/scan-set source [nil "price" 20]))))
    (testing "a predicate the file has no column for costs nothing"
      (is (= #{} (source/scan-set source [nil "no-such-column" nil]))))))

(deftest access-profiles-are-declared-not-inferred
  (let [reg (-> (reader/registry)
                (reader/register-scan "application/vnd.apache.parquet" identity)
                (reader/register "text/csv" (fn [_ _] [])))]
    (is (= :scan (reader/access reg "application/vnd.apache.parquet")))
    (is (= :materialize (reader/access reg "TEXT/CSV; charset=utf-8")))
    (is (nil? (reader/access reg "video/mp4")))
    (is (some? (reader/scan-reader reg "application/vnd.apache.parquet")))
    (is (nil? (reader/scan-reader reg "text/csv"))
        "asking for a scan reader must not yield a materializing one")))
