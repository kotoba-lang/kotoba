(ns kotoba.capability.net.datagram-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba.capability.net.datagram :as capability]
            [kotoba.core.capability-repository :as repository]
            [kotoba.core.contracts :as contracts]))

;; kotoba-core-contracts' actor:host v0 catalog (both the legacy
;; `actor-host-capability-ids` map and the `capability_contract.edn` 201+
;; wire-id registry) is a closed, authority-owned list. `net/datagram` is a
;; NEW capability introduced by this repository and is not yet a member of
;; that upstream catalog -- registering it there is a separate change to
;; kotoba-lang/kotoba-core-contracts, out of scope here. `validate-manifest`
;; therefore reports exactly one problem, `:unknown-capability`, and nothing
;; else: every OTHER structural check this contract performs (schema,
;; authority, hash-contract-cid, definition-cid, radicle-rid format,
;; provider-status, dependencies, artifact shape) passes against the current
;; manifest. This assertion is the honest, current state -- not a claim that
;; `net/datagram` is upstream-registered.
(deftest manifest-is-well-formed-pending-upstream-catalog-registration
  (is (= [{:problem :unknown-capability :capability/id "net/datagram"}]
         (repository/validate-manifest
          (contracts/capability-contract)
          capability/manifest))))
