(ns iceberg.rest-test
  "The protocol, checked as data. No socket, which is the point: the shape of
  a compare-and-set is what has to be right, and a test that needed a live
  catalog to see it would run rarely and prove less."
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [iceberg.rest :as rest]))

(def ^:private uri (rest/base-url "acct" "bkt"))
(def ^:private common {:uri uri :prefix "pfx" :namespace "ns" :table "t" :token "tok"})

(deftest config-carries-the-warehouse-and-nothing-else-needs-a-prefix
  (testing "measured: without ?warehouse the catalog answers 400"
    (let [r (rest/config {:uri uri :token "tok" :warehouse (rest/warehouse-name "acct" "bkt")})]
      (is (str/ends-with? (:url r) "/v1/config?warehouse=acct_bkt"))
      (is (not (str/includes? (:url r) "pfx"))))))

(deftest every-other-path-carries-the-prefix
  (testing "measured: without it the catalog answers 404 with an empty body"
    (is (= (str uri "/v1/pfx/namespaces/ns/tables/t")
           (:url (rest/load-table common))))
    (is (= (str uri "/v1/pfx/namespaces/ns/tables/t")
           (:url (rest/commit (assoc common :requirements [] :updates [])))))
    (is (= (str uri "/v1/pfx/namespaces/ns/tables")
           (:url (rest/create-table (assoc common :schema {})))))))

(deftest the-token-never-reaches-the-url
  (doseq [r [(rest/load-table common)
             (rest/config {:uri uri :token "tok" :warehouse "w"})
             (rest/commit (assoc common :requirements [] :updates []))]]
    (is (not (str/includes? (:url r) "tok")) (:url r))
    (is (= "Bearer tok" (get (:headers r) "Authorization")))))

;; ---------------------------------------------------------------------------
;; The 64-bit problem.
;; ---------------------------------------------------------------------------

(def ^:private real-id "7788483499493485286")

(deftest a-snapshot-id-is-read-from-the-text-not-the-parsed-object
  (testing "JSON.parse rounds it, measured against the live catalog"
    (let [body (str "{\"metadata\":{\"current-snapshot-id\":" real-id ",\"x\":1}}")]
      (is (= real-id (rest/current-snapshot-id-of body)))
      #?(:cljs
         (is (not= real-id
                   (str (aget (aget (js/JSON.parse body) "metadata") "current-snapshot-id")))
             "the whole reason this function takes text")))))

(deftest a-table-with-no-snapshot-reads-as-nil-not-as-an-error
  (is (nil? (rest/current-snapshot-id-of "{\"metadata\":{\"snapshots\":[]}}"))))

(deftest exact-digits-reach-the-body-as-a-json-number
  (let [body (:body (rest/commit (assoc common
                                        :requirements (rest/append-requirements real-id)
                                        :updates [])))]
    (is (str/includes? body (str "\"snapshot-id\":" real-id))
        "unquoted, or it is not a number to the catalog")
    (is (not (str/includes? body (str "\"" real-id "\""))) "and never quoted")
    (is (not (str/includes? body "iceberg-int")) "the marker must not leak")))

(deftest an-id-this-runtime-would-round-is-refused
  (testing "asserting a rounded id names a snapshot that never existed"
    #?(:cljs (is (thrown? js/Error (rest/append-requirements 7788483499493486000)))
       :clj (is true "a JVM long holds it exactly; nothing to refuse"))))

(deftest an-id-that-fits-is-passed-through
  (is (= 1234 (get-in (rest/append-requirements 1234) [0 "snapshot-id"]))))

(deftest nil-asserts-creation-rather-than-asserting-nothing
  (is (= [{"type" "assert-create"}] (rest/append-requirements nil))))

;; ---------------------------------------------------------------------------
;; Refusals and shape.
;; ---------------------------------------------------------------------------

(deftest a-commit-without-requirements-is-refused
  (testing "it would be a blind overwrite of whatever another writer just did"
    (is (thrown? #?(:clj Exception :cljs js/Error)
                 (rest/commit (assoc common :updates []))))))

(deftest an-append-moves-the-ref-as-well-as-adding-the-snapshot
  (let [snap {"snapshot-id" 99 "manifest-list" "s3://x"}
        [add set-ref] (rest/append-updates snap)]
    (is (= "add-snapshot" (get add "action")))
    (is (= snap (get add "snapshot")))
    (testing "without this second action the commit succeeds and changes nothing visible"
      (is (= "set-snapshot-ref" (get set-ref "action")))
      (is (= "main" (get set-ref "ref-name")))
      (is (= 99 (get set-ref "snapshot-id"))))))

(deftest the-prefix-comes-out-of-the-config-response
  (is (= "abc" (rest/prefix-of {"overrides" {"prefix" "abc"}})))
  (is (nil? (rest/prefix-of {"overrides" {}}))))
