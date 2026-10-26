(ns kotoba.capability.dma.map-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.dma.map :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

(deftest manifest-conforms
  (is (= [] (repository/validate-manifest
             (contracts/capability-contract)
             capability/manifest))))

(deftest rtl-style-descriptor-commands-have-one-shared-shape
  (is (= 0xf000003c (capability/tx-command 60)))
  (is (= 0xc0000800 (capability/rx-command 2048)))
  (is (capability/device-owned? (capability/tx-command 60)))
  (is (not (capability/device-owned? 60))))

(deftest ownership-is-published-only-after-payload-and-address
  (is (= [:write-extension :write-address :release-fence :set-owner
          :release-fence :doorbell]
         capability/tx-publication-order))
  (is (= [:write-extension :write-address :release-fence :set-owner
          :release-fence]
         capability/rx-publication-order)))
