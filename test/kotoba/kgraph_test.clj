(ns kotoba.kgraph-test
  (:require [clojure.test :refer [deftest is testing]]
            [kotoba.kgraph :as kgraph]
            [datom.core :as dc]))

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

;; ── canonical datom model (datom-clj) — ADR-2607032500 ───────────────────────
(deftest assert-entity-uses-canonical-datom-model
  (testing "assert-entity datafies via datom.core/eavt (:/id → e, rest → [e a v])"
    (is (= [["alice" :ns/a "v1"] ["alice" :ns/b "v2"]]
           (kgraph/assert-entity [] {:db/id "alice" :ns/a "v1" :ns/b "v2"}))))
  (testing "assert-entity ≡ datom.core/eavt appended (the ONE shared model)"
    (let [ent {:db/id "bob" :name "Bob" :role "admin"}]
      (is (= (vec (dc/eavt ent)) (kgraph/assert-entity [] ent)))))
  (testing "assert-entities flattens a datom log and query joins over it"
    (let [ds (kgraph/assert-entities []
                                     [{:db/id "alice" :role "admin" :name "Alice"}
                                      {:db/id "carol" :role "admin" :name "Carol"}])]
      (is (= #{["Alice"] ["Carol"]}
             (set (kgraph/query ds '{:find [?n] :where [[?e :role "admin"] [?e :name ?n]]})))))))
