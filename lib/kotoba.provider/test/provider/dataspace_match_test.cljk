(ns provider.dataspace-match-test
  (:require [clojure.test :refer [deftest is]]
            [provider.dataspace-match :as match]))

(deftest temperature-tuple-binds-and-wildcards
  (is (= {'?t 21}
         (match/match '[:temperature :room/a ?t]
                      [:temperature :room/a 21])))
  (is (= {'?t 21}
         (match/match [:temperature :room/a '?t]
                      [:temperature :room/a 21])))
  (is (= {}
         (match/match [:temperature :room/a '_]
                      [:temperature :room/a 21])))
  (is (= {}
         (match/match [:temperature :_ 21]
                      [:temperature :room/a 21])))
  (is (nil? (match/match '[:temperature :room/a ?t]
                         [:humidity :room/a 21]))))

(deftest keyword-binding-and-map-extra-keys
  (is (= {'?t 21}
         (match/match {:pred :temperature :celsius :?t}
                      {:pred :temperature :celsius 21 :extra :ok})))
  (is (nil? (match/match {:pred :temperature :celsius :?t}
                         {:pred :humidity :celsius 21}))))

(deftest repeated-bindings-unify
  (is (= {'?x :room/a}
         (match/match '[:same ?x ?x] [:same :room/a :room/a])))
  (is (nil? (match/match '[:same ?x ?x] [:same :room/a :room/b]))))

(deftest copied-assertion-is-inert-data
  (let [assertion [:temperature :room/a 21]
        copied (vec assertion)]
    (is (= assertion copied))
    (is (nil? (:cap/kind copied)))
    (is (= {'?t 21} (match/match '[:temperature :room/a ?t] copied)))))
