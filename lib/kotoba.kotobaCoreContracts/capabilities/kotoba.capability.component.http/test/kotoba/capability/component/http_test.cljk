(ns kotoba.capability.component.http-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.component.http :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
