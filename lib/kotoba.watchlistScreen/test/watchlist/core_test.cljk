(ns watchlist.core-test
  (:require [clojure.test :refer [deftest is]]
            [watchlist.core :as core]
            [watchlist.model :as model]
            [watchlist.ports :as ports]))

(def now 1700000000000)

(defn- fixed-index [entities manifests]
  (reify ports/IWatchlistIndex
    (entities [_] entities)
    (manifests [_] manifests)))

(def sample-entity
  (model/entity "ofac-sdn:1" :ofac-sdn
                {:type :individual :primary-name "Ahmed Hassan Al-Zomor"
                 :aliases ["Abbud Zumar"]}))

(def fresh-manifest
  (model/list-manifest :ofac-sdn {:fetched-at (- now (* 2 86400000)) :entity-count 1}))

(def stale-manifest
  (model/list-manifest :ofac-sdn {:fetched-at (- now (* 30 86400000)) :entity-count 1}))

(deftest screen-returns-sorted-candidates-and-fresh-status
  (let [index (fixed-index [sample-entity] [fresh-manifest])
        result (core/screen index "Ahmed Hassan Alzomor" now)]
    (is (= 1 (count (:watchlist/candidates result))))
    (is (= :fuzzy-high (:tier (first (:watchlist/candidates result)))))
    (is (false? (:watchlist/stale? result)))
    (is (< 1.9 (:watchlist/list-age-days result) 2.1))
    (is (= now (:watchlist/checked-at result)))))

(deftest screen-no-candidates-when-nothing-clears-threshold
  (let [index (fixed-index [sample-entity] [fresh-manifest])
        result (core/screen index "Totally Unrelated Name" now)]
    (is (= [] (:watchlist/candidates result)))
    (is (false? (:watchlist/stale? result)) "absence of a match is distinct from staleness")))

(deftest screen-flags-stale-when-manifest-past-threshold
  (let [index (fixed-index [sample-entity] [stale-manifest])
        result (core/screen index "anything" now)]
    (is (true? (:watchlist/stale? result)))))

(deftest screen-flags-stale-when-no-manifest-at-all-fail-closed
  (let [index (fixed-index [sample-entity] [])
        result (core/screen index "anything" now)]
    (is (true? (:watchlist/stale? result))
        "an index with entities but no manifest cannot vouch for freshness -- fail closed, not fail open")))

(deftest highest-confidence-candidate-picks-the-top-of-the-sorted-list
  (let [low (model/entity "un-consolidated:1" :un-consolidated {:type :individual :primary-name "Zzz Query Name Lowmatch"})
        high (model/entity "ofac-sdn:2" :ofac-sdn {:type :individual :primary-name "Query Name"})
        index (fixed-index [low high] [fresh-manifest])
        result (core/screen index "Query Name" now)]
    (is (= "ofac-sdn:2" (get-in (core/highest-confidence-candidate result) [:entity :entity/id])))))
