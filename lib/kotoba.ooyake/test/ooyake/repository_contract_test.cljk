(ns ooyake.repository-contract-test
  (:require [kotoba.lang.edn :as edn]
            [clojure.test :refer [deftest is]]))

(deftest standalone-metadata-is-edn
  (doseq [path ["identity.edn" "dependencies.edn" "repository-contracts.edn"
                "migration.edn" "manifest.edn"]]
    (is (map? (edn/read-string (slurp path))) path)))

(deftest wire-boundary-is-declared
  (let [contract (edn/read-string (slurp "repository-contracts.edn"))]
    (is (= :edn (:canonical-data contract)))
    (is (= "wire" (get-in contract [:external-formats :root])))
    (is (= #{:go :tinygo} (:deprecated-languages contract)))))
