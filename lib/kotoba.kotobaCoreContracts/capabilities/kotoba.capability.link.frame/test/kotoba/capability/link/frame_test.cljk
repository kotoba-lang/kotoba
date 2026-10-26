(ns kotoba.capability.link.frame-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.link.frame :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

;; See kotoba-net-datagram's test for the full explanation: `link/frame` is
;; not yet a member of kotoba-core-contracts' closed actor:host v0 catalog,
;; so `validate-manifest` reports exactly the one expected
;; `:unknown-capability` problem and nothing else -- every other structural
;; check on this manifest passes.
(deftest manifest-is-well-formed-pending-upstream-catalog-registration
  (is (= [{:problem :unknown-capability :capability/id "link/frame"}]
         (repository/validate-manifest
          (contracts/capability-contract)
          capability/manifest))))

(deftest ethernet-wire-length-is-pre-fcs-and-pads-runts
  (is (nil? (capability/tx-wire-length 13)))
  (is (= 60 (capability/tx-wire-length 14)))
  (is (= 60 (capability/tx-wire-length 54)))
  (is (= 62 (capability/tx-wire-length 62)))
  (is (= 1514 (capability/tx-wire-length 1514)))
  (is (nil? (capability/tx-wire-length 1515))))

(deftest ipv4-total-length-does-not-consume-ethernet-padding
  (is (capability/ipv4-datagram-fits? 60 40))
  (is (capability/ipv4-datagram-fits? 74 40))
  (is (not (capability/ipv4-datagram-fits? 53 40)))
  (is (not (capability/ipv4-datagram-fits? 60 19))))
