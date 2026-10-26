(ns kotoba.capability.net.transport-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.net.transport :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))

(deftest tcp-data-offset-admits-standard-option-bearing-syn-acks
  (is (= 20 (capability/tcp-header-length 0x50)))
  (is (= 32 (capability/tcp-header-length 0x80)))
  (is (nil? (capability/tcp-header-length 0x40)))
  (is (capability/syn-ack-shape? 40 20 0x12))
  (is (capability/syn-ack-shape? 52 32 0x12))
  (is (not (capability/syn-ack-shape? 52 20 0x12)))
  (is (not (capability/syn-ack-shape? 52 32 0x10))))
