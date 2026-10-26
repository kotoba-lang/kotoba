(ns kotoba.capability.kami.engine-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.kami.engine :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
