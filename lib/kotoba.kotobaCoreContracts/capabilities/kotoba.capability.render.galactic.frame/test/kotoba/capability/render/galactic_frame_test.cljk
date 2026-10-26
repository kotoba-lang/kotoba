(ns kotoba.capability.render.galactic-frame-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.render.galactic-frame :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))
