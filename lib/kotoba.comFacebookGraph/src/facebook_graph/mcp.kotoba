(ns facebook-graph.mcp
  "MCP tool exposure for this provider, per ADR-0023's provider contract
  ('Every mature provider offers equivalent semantic operations, scoped
  under its own MCP server name'). `tools` is pure data (tool-call
  transport/JSON-RPC framing is left to the orchestrator embedding this
  library, matching how cloudflare.client keeps HTTP transport injectable
  rather than owning a server loop). `call-tool` is the single dispatch
  point cloud-itonami's provider MCP execution envelope calls into.

  Every tool name is prefixed `facebook_graph.` so multiple provider MCP
  surfaces can be aggregated without name collisions (same convention as
  ai-gftd-project-exoclick's `exoclick.*` tool names)."
  (:require [facebook-graph.accounts :as accounts]
            [facebook-graph.campaigns :as campaigns]))

(def tools
  [{:name "facebook_graph.accounts.list"
    :description "List ad accounts the current token can act on."
    :inputSchema {:type "object" :properties {}}}
   {:name "facebook_graph.capabilities.get"
    :description "This provider's semantic capability map (what is implemented/unauthenticated/production-write, per operation)."
    :inputSchema {:type "object" :properties {}}}
   {:name "facebook_graph.campaigns.list"
    :description "List campaigns for an ad account."
    :inputSchema {:type "object"
                  :properties {:ad-account-id {:type "string"}}
                  :required ["ad-account-id"]}}
   {:name "facebook_graph.campaigns.create"
    :description "Create a campaign (dry-run by default -- see :dry-run? in args)."
    :inputSchema {:type "object"
                  :properties {:ad-account-id {:type "string"}
                              :name {:type "string"}
                              :objective {:type "string" :description "e.g. OUTCOME_TRAFFIC, OUTCOME_LEADS, OUTCOME_SALES, OUTCOME_ENGAGEMENT"}
                              :status {:type "string" :description "PAUSED (default) or ACTIVE"}
                              :special-ad-categories {:type "array" :items {:type "string"}}
                              :dry-run? {:type "boolean" :description "default true"}}
                  :required ["ad-account-id" "name" "objective"]}}
   {:name "facebook_graph.campaigns.pause"
    :description "Pause a campaign (dry-run by default)."
    :inputSchema {:type "object"
                  :properties {:campaign-id {:type "string"} :dry-run? {:type "boolean"}}
                  :required ["campaign-id"]}}
   {:name "facebook_graph.campaigns.resume"
    :description "Resume a campaign (dry-run by default)."
    :inputSchema {:type "object"
                  :properties {:campaign-id {:type "string"} :dry-run? {:type "boolean"}}
                  :required ["campaign-id"]}}
   {:name "facebook_graph.budgets.update"
    :description "Update a campaign's daily or lifetime budget (dry-run by default; requires an explicit ceiling)."
    :inputSchema {:type "object"
                  :properties {:campaign-id {:type "string"}
                              :budget-minor-units {:type "integer"}
                              :budget-kind {:type "string" :enum ["daily" "lifetime"]}
                              :budget-ceiling-minor-units {:type "integer"}
                              :dry-run? {:type "boolean"}}
                  :required ["campaign-id" "budget-minor-units" "budget-kind" "budget-ceiling-minor-units"]}}
   {:name "facebook_graph.creatives.validate"
    :description "Schema-only validation of a creative spec shape (does not call the live creative-upload API)."
    :inputSchema {:type "object"
                  :properties {:name {:type "string"} :object-story-spec {:type "object"}}
                  :required ["name" "object-story-spec"]}}
   {:name "facebook_graph.metrics.report"
    :description "Aggregate insights report for an ad account."
    :inputSchema {:type "object"
                  :properties {:ad-account-id {:type "string"}
                              :fields {:type "string"}
                              :date-preset {:type "string"}}
                  :required ["ad-account-id"]}}
   {:name "facebook_graph.operations.status"
    :description "Poll an async operation. Meta campaign mutations are synchronous; only insights report-runs are pollable -- other kinds return a typed :unsupported result."
    :inputSchema {:type "object"
                  :properties {:operation-kind {:type "string"} :ref-id {:type "string"}}
                  :required ["operation-kind"]}}])

#?(:clj
(defn call-tool
  "Dispatch one MCP tool call. args is a plain map (already parsed from
  JSON by the transport layer). Returns {:ok? true :result ...} or
  {:ok? false :error {...}} -- never throws for a caller-facing bad
  request; only genuine transport exceptions from the underlying client
  propagate (matching cloudflare.client's fail-closed convention)."
  [tool-name args]
  (try
    {:ok? true
     :result
     (case tool-name
       "facebook_graph.accounts.list" (accounts/list-accounts args)
       "facebook_graph.capabilities.get" (accounts/capabilities-get)
       "facebook_graph.campaigns.list" (campaigns/list-campaigns (:ad-account-id args) args)
       "facebook_graph.campaigns.create" (campaigns/create-campaign! (:ad-account-id args) args args)
       "facebook_graph.campaigns.pause" (campaigns/pause-campaign! (:campaign-id args) args)
       "facebook_graph.campaigns.resume" (campaigns/resume-campaign! (:campaign-id args) args)
       "facebook_graph.budgets.update" (campaigns/update-budget!
                                        (:campaign-id args) (:budget-minor-units args)
                                        (keyword (:budget-kind args)) args)
       "facebook_graph.creatives.validate" (campaigns/validate-creative args)
       "facebook_graph.metrics.report" (campaigns/insights-report (:ad-account-id args) args)
       "facebook_graph.operations.status" (campaigns/operation-status (update args :operation-kind keyword))
       (throw (ex-info "Unknown tool" {:tool-name tool-name})))}
    (catch #?(:clj Exception :cljs :default) e
      {:ok? false :error (merge {:message (ex-message e)} (ex-data e))}))))
