(ns kotoba.capability.can.frame-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.can.frame :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

;; See kotoba-net-datagram's test for the full explanation: `can/frame` is
;; not yet a member of kotoba-core-contracts' closed actor:host v0 catalog,
;; so `validate-manifest` reports exactly the one expected
;; `:unknown-capability` problem and nothing else -- every other structural
;; check on this manifest passes.
(deftest manifest-is-well-formed-pending-upstream-catalog-registration
  (is (= [{:problem :unknown-capability :capability/id "can/frame"}]
         (repository/validate-manifest
          (contracts/capability-contract)
          capability/manifest))))
