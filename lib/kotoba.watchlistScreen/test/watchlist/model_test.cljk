(ns watchlist.model-test
  (:require [clojure.test :refer [deftest is]]
            [watchlist.model :as model]))

(deftest entity-and-valid-entity?
  (let [e (model/entity "ofac-sdn:1" :ofac-sdn
                         {:type :individual :primary-name "Jane Doe"
                          :aliases ["J Doe"] :dob "1980" :nationality ["US"]
                          :programs ["SDGT"] :source-updated-at 0})]
    (is (model/valid-entity? e))
    (is (not (model/valid-entity? (assoc e :entity/primary-name ""))))
    (is (not (model/valid-entity? (assoc e :entity/source :not-a-real-source))))))

(deftest stale?-and-list-age-days
  (let [now 1000000000
        fresh (model/list-manifest :ofac-sdn {:fetched-at (- now (* 1 86400000))})
        old (model/list-manifest :ofac-sdn {:fetched-at (- now (* 30 86400000))})
        never (model/list-manifest :ofac-sdn {})]
    (is (not (model/stale? fresh now)))
    (is (model/stale? old now))
    (is (model/stale? never now) "no fetched-at at all is treated as stale, not fresh")
    (is (< 0.9 (model/list-age-days fresh now) 1.1))
    (is (nil? (model/list-age-days never now)))))
