(ns kotoba.capability.corpus.append-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.corpus.append :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
