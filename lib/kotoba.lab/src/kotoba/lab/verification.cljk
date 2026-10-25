(ns kotoba.lab.verification)

(def contract-version "kotoba-lab-verification/v1")

(def required-environment
  {:env/schema "kotoba-lab-notebook/v1"
   :env/runtime "kotoba-wasm-safe"
   :env/runtime-version "shim-0.2.0"
   :env/llm-provider "kotoba-research-assistant"
   :env/llm-provider-version "shim-0.1.0"})

(def required-coverage
  [:notebook-ui
   :manifest-contract
   :local-execution
   :runtime-adapter
   :environment-lock
   :evidence
   :llm-workflow
   :rich-outputs
   :persistence
   :review-snapshot
   :contract-verification
   :accessibility
   :replay-ledger
   :browser-verification])

(defn environment-locked?
  [environment]
  (every?
    (fn [[k v]] (= v (get environment k)))
    required-environment))

(defn review-snapshot-ready?
  [snapshot]
  (and (= :ready (:snapshot/status snapshot))
       (string? (:snapshot/id snapshot))
       (string? (:snapshot/replay-fingerprint snapshot))
       (string? (:snapshot/environment snapshot))
       (string? (:snapshot/coverage snapshot))))

(defn maturity-ready?
  [report]
  (and (>= (:coverage report 0) 70)
       (= :m4 (:maturity report))
       (every? (:covered report #{}) required-coverage)))
