(ns kotoba.gleif-runtime-test
  (:require [cljs.test :refer [deftest is]]
            [kotoba.property.gleif-runtime :as gleif]))

(deftest normalizes-direct-parent-relationship
  (let [record (gleif/normalize-relation
                "2026-07-10T00:00:00.000Z"
                {:id "child|direct-parent"
                 :attributes {:relationship {:startNode {:id "CHILD"}
                                             :endNode {:id "PARENT"}
                                             :type "IS_DIRECTLY_CONSOLIDATED_BY"
                                             :status "ACTIVE"}}})]
    (is (= "CHILD" (:corporate-relation/child-lei record)))
    (is (= :is-directly-consolidated-by (:corporate-relation/type record)))))
