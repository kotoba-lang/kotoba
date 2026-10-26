(ns kotoba.capability.crypto.tls-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.crypto.tls :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
