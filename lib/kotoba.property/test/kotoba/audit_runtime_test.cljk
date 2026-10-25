(ns kotoba.audit-runtime-test
  (:require [cljs.test :refer [deftest is]]
            [kotoba.property.audit-runtime :as audit]))

(deftest tracks-added-and-removed-records
  (let [entry (audit/source-audit "source" "2026-07-10T00:00:00Z" "hash"
                                  {"a" {} "b" {}}
                                  {"b" {} "c" {}})]
    (is (= 1 (:source-audit/added-count entry)))
    (is (= 1 (:source-audit/removed-count entry)))))
