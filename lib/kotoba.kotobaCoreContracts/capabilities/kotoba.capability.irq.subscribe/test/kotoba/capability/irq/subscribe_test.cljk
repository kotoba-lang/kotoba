(ns kotoba.capability.irq.subscribe-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.irq.subscribe :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
