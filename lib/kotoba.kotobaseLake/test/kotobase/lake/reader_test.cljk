(ns kotobase.lake.reader-test
  (:require [kotoba.lang.text :as str]
            [clojure.test :refer [deftest is testing]]
            [datom.source :as source]
            [kotobase.lake.catalog :as cat]
            [kotobase.lake.reader :as reader]))

(def base
  {:cid "bafkreiabc" :size 12 :tenant "acme" :ingested-at "2026-08-04T09:00:00Z"})

(defn- csv-decoder
  "Toy decoder: one quad per cell. Enough to prove the seam, not a CSV parser."
  [text {:keys [object-id]}]
  (let [[header & rows] (str/split-lines text)
        cols (str/split header #",")]
    (for [[i row] (map-indexed vector rows)
          [col cell] (map vector cols (str/split row #","))]
      {:s (str object-id "#row" i) :p col :o cell})))

(deftest no-reader-is-not-a-failure
  (let [r (reader/decode (reader/registry)
                         {:claim-id "c" :object-id "o" :declared-media-type "video/mp4"}
                         "…")]
    (is (false? (:decoded? r)))
    (is (= :no-reader (:reason r)))
    (is (= ["video/mp4"] (:tried r))
        "which hypotheses were considered must be visible, or 'no reader' is unactionable")))

(deftest a-throwing-decoder-does-not-fail-the-query
  (let [reg (reader/register (reader/registry) "text/csv"
                             (fn [_ _] (throw (ex-info "row 41: unterminated quote" {}))))
        r   (reader/decode reg {:claim-id "c" :object-id "o" :declared-media-type "text/csv"} "…")]
    (is (false? (:decoded? r)))
    (is (= :decoder-threw (:reason r)))
    (is (= "text/csv" (:via r)))
    (is (re-find #"row 41" (:message r))
        "malformed input is the normal state of real data; it must be reported, not swallowed")))

(deftest the-type-is-a-hypothesis-tried-in-order
  (let [reg (-> (reader/registry)
                (reader/register "text/csv" (fn [_ _] [{:s "a" :p "via" :o "declared"}]))
                (reader/register "application/pdf" (fn [_ _] [{:s "a" :p "via" :o "observed"}])))]
    (testing "declared wins when it has a decoder -- it knows what magic bytes cannot say"
      (is (= "text/csv"
             (:via (reader/decode reg {:declared-media-type "text/csv"
                                       :observed {:media-type "application/pdf" :format :pdf}}
                                  "…")))))
    (testing "observed is the fallback when the producer named a type nobody can read"
      (is (= "application/pdf"
             (:via (reader/decode reg {:declared-media-type "application/x-unknown"
                                       :observed {:media-type "application/pdf" :format :pdf}}
                                  "…")))))
    (testing "candidate order and de-duplication"
      (is (= ["text/csv"] (reader/candidate-types {:declared-media-type "TEXT/CSV"
                                                   :observed {:media-type "text/csv"}})))
      (is (= [] (reader/candidate-types {}))))))

(deftest decoded-rows-join-against-their-provenance
  (let [admitted (cat/admit (assoc base :declared-media-type "text/csv" :filename "a.csv"))
        reg      (reader/register (reader/registry) "text/csv" csv-decoder)
        decoded  (reader/decode reg (assoc admitted :declared-media-type "text/csv")
                                "id,name\n1,alice\n2,bob\n")
        src      (reader/source (:quads admitted) (:quads decoded))]
    (is (:decoded? decoded))
    (is (= 4 (count (:quads decoded))) "2 rows x 2 columns")
    (testing "rows and catalog facts are in one scannable plane"
      (is (= #{"alice" "bob"}
             (into #{} (map :o) (source/scan-set src [nil "name" nil]))))
      (is (= #{"a.csv"}
             (into #{} (map :o) (source/scan-set src [nil "claim/filename" nil]))))
      (is (= #{(:object-id admitted)}
             (into #{} (map :o) (source/scan-set src [(:claim-id admitted) "claim/object" nil])))))
    (testing "an object that did not decode still contributes its catalog facts"
      (let [undecodable (cat/admit (assoc base :cid "bafkreixyz" :tenant "globex"))
            src2 (reader/source (into (:quads admitted) (:quads undecodable)) (:quads decoded))]
        (is (= 2 (count (cat/objects (source/scan-set src2 [nil "object/cid" nil]))))
            "objects stay visible as objects rather than vanishing from the plane")))))
