(ns kotoba.eda.murakumo
  "Pure payload builder for submitting kotoba EDA runner plans to murakumo.

  This namespace does not perform network I/O. Browser/UI code, a service, or a
  murakumo host adapter can turn the returned map into HTTP/XRPC/SSE calls."
  (:require [clojure.string :as str]))

(defn ready-adapters
  [runner-plan]
  (filter #(= "ready" (or (:eda.job.adapter/status %)
                          (get % "eda.job.adapter/status")))
          (or (:eda.job/adapters runner-plan)
              (get runner-plan "eda.job/adapters"))))

(defn approval-summary
  [approvals]
  {:pdk-license (contains? approvals :pdk-license)
   :nda-export (contains? approvals :nda-export)
   :mask-budget (contains? approvals :mask-budget)
   :foundry-slot (contains? approvals :foundry-slot)
   :human-signoff (contains? approvals :human-signoff)})

(defn submit-payload
  [{:keys [runner-plan artifacts approvals project dry-run?]}]
  (let [run-id (str "eda-run-" (Math/abs (hash [runner-plan artifacts approvals project])))]
    {:eda.murakumo/schema 1
     :eda.murakumo/run-id run-id
     :eda.murakumo/kind :eda.runner/job
     :eda.murakumo/project project
     :eda.murakumo/mode (if dry-run? :dry-run :requires-approval)
     :eda.murakumo/placement {:reach [:tailnet :local-workspace]
                              :class [:mac-mini :linux-workstation :licensed-runner]
                              :requires [:cpu :workspace-fs]
                              :forbids [:public-internet-egress]}
     :eda.murakumo/policy {:network :deny-by-default
                           :filesystem :workspace-only
                           :license-check :required
                           :pdk-export :deny-by-default
                           :paid-action :approval-required
                           :human-signoff :required-for-vendor-upload
                           :approvals (approval-summary approvals)}
     :eda.murakumo/runner-plan runner-plan
     :eda.murakumo/artifacts artifacts
     :eda.murakumo/ready-adapters (mapv #(or (:eda.job.adapter/id %)
                                             (get % "eda.job.adapter/id"))
                                        (ready-adapters runner-plan))
     :eda.murakumo/events-path (str "/v1/eda/runs/" run-id "/events")}))

(defn sse-event
  [run-id event-type data]
  (str "event: " (name event-type) "\n"
       "data: " (pr-str {:run-id run-id :type event-type :data data}) "\n\n"))
