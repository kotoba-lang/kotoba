(ns kotoba.lab.verification-check
  (:require [kotoba.lab.verification :as verification]))

(def required-environment-keys
  [:env/schema
   :env/runtime
   :env/runtime-version
   :env/llm-provider
   :env/llm-provider-version])

(def required-predicates
  ['verification/environment-locked?
   'verification/review-snapshot-ready?
   'verification/maturity-ready?])

(def required-contract-coverage
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

(defn contract-checks
  []
  {:check/environment-keys required-environment-keys
   :check/predicates required-predicates
   :check/coverage required-contract-coverage})
