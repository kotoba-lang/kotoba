(ns kotoba.kgraph-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.kgraph :as kgraph]))

(def sample
  (-> []
      (kgraph/assert-datom [1 :name "Aoi"])
      (kgraph/assert-datom [1 :age 7])
      (kgraph/assert-datom [2 :name "Ren"])))

(deftest assert-and-retract
  (is (= 3 (count sample)))
  (is (= 2 (count (kgraph/retract-datom sample [1 :age 7])))))

(deftest get-objects-by-entity
  (is (= [[1 :name "Aoi"] [1 :age 7]] (kgraph/get-objects sample 1)))
  (is (= [[2 :name "Ren"]] (kgraph/get-objects sample 2)))
  (is (= [] (kgraph/get-objects sample 999))))

(deftest datalog-query
  (testing "single-clause projection"
    (is (= [["Aoi"]]
           (kgraph/query sample '{:find [?v] :where [[1 :name ?v]]}))))
  (testing "join across two clauses sharing ?e"
    (is (= #{["Aoi" 7]}
           (set (kgraph/query sample
                              '{:find [?name ?age]
                                :where [[?e :name ?name] [?e :age ?age]]})))))
  (testing "no match -> empty"
    (is (= [] (kgraph/query sample '{:find [?v] :where [[999 :name ?v]]})))))
