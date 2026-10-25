(ns haishin.core
  "配信 — single entry point.

  Consumers require this namespace and nothing else, the same single-entry
  discipline `kotoba-ui` uses. Requiring `haishin.target` or `haishin.constraints`
  directly is an opt-out that wants a reason, because those are where the
  platform-specific detail lives and the point of the boundary is that callers
  do not handle it.

      (require '[haishin.core :as haishin])

      (def plan
        (haishin/plan artifact [:youtube :instagram :x] {:at \"2026-08-04T09:00:00Z\"}))

      (println (haishin/summary plan))     ; what would go out, and what would not

      (haishin/execute! plan {:grant #{:youtube}
                              :senders {:youtube my-youtube-sender}})

  Planning is pure and unconditional; sending requires a grant and a sender the
  caller wrote. There is no transport and no credential handling in this library."
  (:require [haishin.adapt :as adapt]
            [haishin.artifact :as artifact]
            [haishin.constraints :as constraints]
            [haishin.execute :as execute]
            [haishin.plan :as plan]
            [haishin.receipt :as receipt]))

;; artifact
(def normalize artifact/normalize)
(def artifact-problems artifact/problems)
(def valid-artifact? artifact/valid?)

;; planning (pure)
(def plan plan/plan)
(def summary plan/summary)
(def targets-in plan/targets-in)
(def all-warnings plan/all-warnings)

;; execution (capability-gated)
(def execute! execute/execute!)
(def dry-run execute/dry-run)

;; receipts
(def ok? receipt/ok?)
(def tally receipt/tally)

;; targets
(def target-ids constraints/target-ids)
(def describe-target constraints/describe)
(def unverified-targets constraints/unverified-targets)

;; workspace adapters
(def tamaki-content->artifact adapt/tamaki-content->artifact)
(def plan->grant adapt/plan->grant)
(def grant-explanation adapt/grant-explanation)

(defn syndicate!
  "The whole path for a tamaki producer, in one call.

  Takes the two maps a `*ka` actor already has — the artifact manifest and the
  publication plan — and produces receipts. The grant is derived from the
  publication plan's `:executable?`, so an unapproved plan sends nothing and
  still records why.

  Returns {:run/receipts .. :run/tally .. :haishin/plan .. :haishin/grant-note ..}
  — the plan rides along so the caller can write the skipped targets and their
  reasons into its own ledger alongside the receipts."
  [manifest publication-plan {:keys [senders at] :as opts}]
  (let [a (adapt/tamaki-content->artifact manifest opts)
        grant (adapt/plan->grant publication-plan)
        targets (into (sorted-set) (concat grant (:haishin/also-plan opts)))
        p (plan/plan a targets (assoc opts :at at))]
    (merge (execute/execute! p {:grant grant :senders (or senders {}) :at at})
           {:haishin/plan p
            :haishin/grant-note (adapt/grant-explanation publication-plan)})))
