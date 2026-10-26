(ns kotoba.capability.image.metadata-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.image.metadata :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
