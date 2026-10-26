(ns kotoba.capability.secret.use-scram-sha256-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.secret.use-scram-sha256 :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
