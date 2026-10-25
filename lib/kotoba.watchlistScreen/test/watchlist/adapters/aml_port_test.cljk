(ns watchlist.adapters.aml-port-test
  (:require [aml.model :as aml-model]
            [aml.ports :as aml-ports]
            [clojure.test :refer [deftest is]]
            [watchlist.adapters.aml-port :as aml-port]
            [watchlist.model :as model]
            [watchlist.ports :as ports]))

(def now 1700000000000)
(defn- clock [] now)

(defn- fixed-index [entities manifests]
  (reify ports/IWatchlistIndex
    (entities [_] entities)
    (manifests [_] manifests)))

(def fresh-manifest (model/list-manifest :ofac-sdn {:fetched-at (- now 86400000) :entity-count 1}))
(def stale-manifest (model/list-manifest :ofac-sdn {:fetched-at (- now (* 30 86400000)) :entity-count 1}))

(def sanctioned-entity
  (model/entity "ofac-sdn:1" :ofac-sdn
                {:type :individual :primary-name "Ahmed Hassan Al-Zomor"
                 :programs ["SDGT"]}))

(defn- request-for [subject]
  (aml-model/request "req-1" subject {:case-ref "case-1" :routes [:watchlist]}))

(deftest exact-match-denies
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [fresh-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/name "Ahmed Hassan Al-Zomor"}) :watchlist)]
    (is (= :deny (:aml/level result)))
    (is (true? (:aml/non-adjudicating result)))
    (is (= "ofac-sdn:1" (:aml/evidence-ref result)))
    (is (contains? (:aml/categories result) "SDGT"))))

(deftest fuzzy-match-challenges-or-reviews-not-clear
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [fresh-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/name "Ahmad Hasan Al Zomor"}) :watchlist)]
    (is (contains? #{:challenge :review} (:aml/level result)))))

(deftest no-match-against-fresh-current-data-clears
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [fresh-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/name "Totally Unrelated Person"}) :watchlist)]
    (is (= :clear (:aml/level result)))))

(deftest stale-index-never-clears-even-with-no-match
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [stale-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/name "Totally Unrelated Person"}) :watchlist)]
    (is (= :review (:aml/level result)) "stale data must never look like a clean clearance")))

(deftest subject-with-no-name-cannot-clear-even-with-clean-fresh-data
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [fresh-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/id "did:key:z6Mk..."}) :watchlist)]
    (is (= :review (:aml/level result)) "nothing to screen against is not the same as a clean result")))

(deftest wrong-route-throws
  (let [port (aml-port/screening-port (fixed-index [] []) clock)]
    (is (thrown? #?(:clj Exception :cljs js/Error)
                 (aml-ports/screen! port (request-for "x") :yabai)))))

(deftest result-satisfies-aml-core-validity
  (let [port (aml-port/screening-port (fixed-index [sanctioned-entity] [fresh-manifest]) clock)
        result (aml-ports/screen! port (request-for {:subject/name "Ahmed Hassan Al-Zomor"}) :watchlist)]
    (is (contains? aml-model/levels (:aml/level result)))))
