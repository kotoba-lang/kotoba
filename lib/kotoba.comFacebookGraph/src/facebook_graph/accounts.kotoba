(ns facebook-graph.accounts
  "Ad account discovery + capability description (read-only).

  `capabilities` is a static, honest capability map, not a live call --
  ADR-0023 requires unsupported operations to return a typed capability
  result rather than silently degrading, so callers (cloud-itonami's
  provider MCP execution envelope) can check what this adapter actually
  supports before proposing an effect."
  (:require [facebook-graph.client :as client]))

#?(:clj
(defn list-accounts
  "Ad accounts the current token can act on. GET /me/adaccounts."
  ([] (list-accounts {}))
  ([opts]
   (:data (client/call! "/me/adaccounts"
                        (assoc opts :query {:fields "account_id,name,account_status,currency,timezone_name"}))))))

#?(:clj
(defn account
  "Single ad account by id (e.g. \"act_123\"). GET /{ad-account-id}."
  ([ad-account-id] (account ad-account-id {}))
  ([ad-account-id opts]
   (client/call! (str "/" ad-account-id)
                (assoc opts :query {:fields "account_id,name,account_status,currency,timezone_name,spend_cap"})))))

(def capabilities
  "Semantic capability map for this provider, per ADR-0023's provider
  contract. `:status` is one of :implemented-unauthenticated (real request/
  response shapes wired, no production-write receipt yet),
  :production-read, :production-write. Never claim a status the adapter
  cannot currently back with a receipt."
  {:accounts.list {:status :implemented-unauthenticated}
   :capabilities.get {:status :implemented-unauthenticated}
   :campaigns.list {:status :implemented-unauthenticated}
   :campaigns.create {:status :implemented-unauthenticated :default-mode :dry-run}
   :campaigns.pause {:status :implemented-unauthenticated :default-mode :dry-run}
   :campaigns.resume {:status :implemented-unauthenticated :default-mode :dry-run}
   :budgets.update {:status :implemented-unauthenticated :default-mode :dry-run}
   :creatives.validate {:status :schema-validation-only
                        :note "Field-shape validation only -- does not call the live Marketing API creative-upload flow (image/video asset hashing is out of scope for this pass)."}
   :metrics.report {:status :implemented-unauthenticated}
   :operations.status {:status :partial
                       :note "Meta campaign/adset/ad mutations respond synchronously; there is no generic async job status endpoint for them. The one real async surface is the Insights async report-run (see facebook-graph.campaigns/insights-report-status), which this maps to. Requests for any other operation kind return a typed :unsupported result, not a fabricated status."}})

#?(:clj
(defn capabilities-get []
  {:provider "kotoba-lang/com-facebook-graph"
   :canonical-api-host "graph.facebook.com"
   :api-version client/default-api-version
   :operations capabilities}))
