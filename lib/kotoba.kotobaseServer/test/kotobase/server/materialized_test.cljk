(ns kotobase.server.materialized-test
  (:require #?(:clj  [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer [deftest is testing] :include-macros true])
            [kotobase.server.materialized :as materialized]))

(def rows
  [{:e "alice" :a ":name" :v_edn "\"Alice\"" :added true}
   {:e "alice" :a ":db/ident" :v_edn "\":person/alice\"" :added true}
   {:e "alice" :a ":secret" :v_edn "\"hidden\"" :added true}
   {:e "bob" :a ":name" :v "Bob" :added true}])

(def public? (constantly true))
(def hide-secret? #(not= ":secret" (:a %)))

(deftest materialized-rows-share-query-and-identity-semantics
  (let [db (materialized/rows->db rows)]
    (is (= #{{:s "alice" :p ":name" :o "Alice"}}
           (materialized/query-db db [nil ":name" "Alice"] public?)))
    (is (= #{["alice" "Alice"] ["bob" "Bob"]}
           (materialized/query-db
            db '{:find [?e ?name] :where [[?e ":name" ?name]]} public?)))
    (is (= "alice" (materialized/entid db :person/alice)))
    (is (= :person/alice (materialized/ident db "alice")))))

(deftest pull-and-entity-use-the-same-visibility-contract
  (let [db (materialized/rows->db rows)]
    (is (= {":name" #{"Alice"}}
           (materialized/pull db "alice" [":name" ":secret"] hide-secret?)))
    (is (= {":name" #{"Alice"} ":db/ident" #{":person/alice"}}
           (materialized/entity db "alice" hide-secret?)))
    (is (= [{":name" #{"Alice"}} {":name" #{"Bob"}}]
           (materialized/pull-many db ["alice" "bob"] [":name"] public?)))))

(deftest ordered-retraction-rows-are-honored
  (is (empty? (materialized/query-rows
               [{:e "e" :a ":a" :v "v" :added true}
                {:e "e" :a ":a" :v "v" :added false}]
               [nil nil nil] public?))))
