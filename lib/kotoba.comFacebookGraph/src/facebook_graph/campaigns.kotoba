(ns facebook-graph.campaigns
  "Campaign read/mutation surface for the Meta Marketing API.

  Every mutation defaults to dry-run (ADR-0023: 'dry-run default' is one of
  the things an LLM proposal cannot bypass). A dry-run call never touches
  the network -- it returns a typed preview of the request that WOULD be
  sent, so a caller can inspect it before opting in to a live call via
  `:dry-run? false`. Budget-changing mutations additionally require an
  explicit `:budget-ceiling-minor-units` in opts and fail closed without
  one -- ad account currencies differ, so this adapter does not guess a
  default ceiling the way a single-currency deployment might."
  (:require [facebook-graph.client :as client]))

#?(:clj
(defn list-campaigns
  "GET /{ad-account-id}/campaigns."
  ([ad-account-id] (list-campaigns ad-account-id {}))
  ([ad-account-id opts]
   (:data (client/call! (str "/" ad-account-id "/campaigns")
                        (assoc opts :query {:fields "id,name,status,objective,daily_budget,lifetime_budget,special_ad_categories"}))))))

#?(:clj
(defn- dry-run-receipt [op request]
  {:ok? true
   :mode :dry-run
   :op op
   :would-send request
   :note "No network call was made. Pass :dry-run? false (and a valid access token) to execute for real."}))

#?(:clj
(defn create-campaign!
  "POST /{ad-account-id}/campaigns. Required fields per the current Marketing
  API: :name, :objective (one of the OUTCOME_* values), :status
  (\"PAUSED\"/\"ACTIVE\"), :special-ad-categories (a vector, [] if none of
  HOUSING/EMPLOYMENT/CREDIT/SOCIAL_ISSUES_ELECTIONS_POLITICS apply --
  required on every campaign regardless, not optional).

  Defaults to :status \"PAUSED\" and dry-run so an accidental live call
  never starts delivery."
  ([ad-account-id campaign-spec] (create-campaign! ad-account-id campaign-spec {}))
  ([ad-account-id {:keys [name objective status special-ad-categories daily-budget-minor-units]
                    :or {status "PAUSED" special-ad-categories []}
                    :as campaign-spec}
    {:keys [dry-run?] :or {dry-run? true} :as opts}]
   (when-not (and name objective)
     (throw (ex-info "campaigns.create requires :name and :objective" {:campaign-spec campaign-spec})))
   (let [body (cond-> {:name name
                       :objective objective
                       :status status
                       :special_ad_categories special-ad-categories}
                daily-budget-minor-units (assoc :daily_budget daily-budget-minor-units))
         request {:method :post :path (str "/" ad-account-id "/campaigns") :body body}]
     (if dry-run?
       (dry-run-receipt :campaigns.create request)
       (client/call! (:path request) (assoc opts :method :post :body body)))))))

#?(:clj
(defn- set-status!
  [campaign-id status {:keys [dry-run?] :or {dry-run? true} :as opts}]
  (let [body {:status status}
        request {:method :post :path (str "/" campaign-id) :body body}]
    (if dry-run?
      (dry-run-receipt (if (= status "PAUSED") :campaigns.pause :campaigns.resume) request)
      (client/call! (:path request) (assoc opts :method :post :body body))))))

#?(:clj (defn pause-campaign! ([campaign-id] (pause-campaign! campaign-id {})) ([campaign-id opts] (set-status! campaign-id "PAUSED" opts))))
#?(:clj (defn resume-campaign! ([campaign-id] (resume-campaign! campaign-id {})) ([campaign-id opts] (set-status! campaign-id "ACTIVE" opts))))

#?(:clj
(defn update-budget!
  "POST /{campaign-id} with :daily_budget or :lifetime_budget (minor
  currency units, e.g. USD cents -- Meta's API convention, not this
  adapter's). Fails closed (throws, does not fall back to unlimited)
  without an explicit :budget-ceiling-minor-units in opts, and again if the
  requested budget exceeds it -- a second validation layer independent of
  whatever ceiling cloud-itonami's Campaign Governor already enforced,
  per ADR-0023's 'provider adapter's second validation'."
  ([campaign-id budget-minor-units budget-kind] (update-budget! campaign-id budget-minor-units budget-kind {}))
  ([campaign-id budget-minor-units budget-kind
    {:keys [dry-run? budget-ceiling-minor-units] :or {dry-run? true} :as opts}]
   (when-not (#{:daily :lifetime} budget-kind)
     (throw (ex-info "budget-kind must be :daily or :lifetime" {:budget-kind budget-kind})))
   (when-not budget-ceiling-minor-units
     (throw (ex-info "budgets.update requires an explicit :budget-ceiling-minor-units (no implicit default -- ad account currencies differ)" {})))
   (when (> budget-minor-units budget-ceiling-minor-units)
     (throw (ex-info "Requested budget exceeds :budget-ceiling-minor-units"
                     {:requested budget-minor-units :ceiling budget-ceiling-minor-units})))
   (let [field (if (= budget-kind :daily) :daily_budget :lifetime_budget)
         body {field budget-minor-units}
         request {:method :post :path (str "/" campaign-id) :body body}]
     (if dry-run?
       (dry-run-receipt :budgets.update request)
       (client/call! (:path request) (assoc opts :method :post :body body)))))))

#?(:clj
(defn validate-creative
  "Schema-only validation of a creative spec shape (name + object_story_spec
  presence) -- see facebook-graph.accounts/capabilities for why this does
  not call the live creative-upload API."
  [{:keys [name object-story-spec] :as creative-spec}]
  (if (and name object-story-spec)
    {:ok? true :mode :schema-validation-only :creative-spec creative-spec}
    {:ok? false :mode :schema-validation-only :error "creatives.validate requires :name and :object-story-spec" :creative-spec creative-spec})))

#?(:clj
(defn insights-report
  "GET /{ad-account-id}/insights -- synchronous aggregate report."
  ([ad-account-id] (insights-report ad-account-id {}))
  ([ad-account-id {:keys [fields date-preset] :or {fields "impressions,clicks,spend,ctr" date-preset "last_7d"} :as opts}]
   (:data (client/call! (str "/" ad-account-id "/insights")
                        (assoc opts :query {:fields fields :date_preset date-preset}))))))

#?(:clj
(defn insights-report-status
  "GET /{report-run-id} -- the one genuine async operation this provider
  exposes (see facebook-graph.accounts/capabilities :operations.status
  note). Meta's async Insights flow returns a report-run id from a POST to
  /insights with `?async=true` (not implemented here, synchronous
  insights-report above covers the common case); this polls that id."
  ([report-run-id] (insights-report-status report-run-id {}))
  ([report-run-id opts]
   (client/call! (str "/" report-run-id) (assoc opts :query {:fields "async_status,async_percent_completion"})))))

#?(:clj
(defn operation-status
  "Typed capability result for the generic ADR-0023 `operations.status`
  contract op. Meta campaign/adset/ad mutations are synchronous (the create/
  pause/resume/budget calls above already return the terminal result), so
  there is nothing to poll for those -- returning a fabricated 'pending'
  status would be feature fiction. Insights report-runs are the one real
  async surface; route those to insights-report-status instead."
  [{:keys [operation-kind ref-id] :as opts}]
  (if (= operation-kind :insights-report)
    (insights-report-status ref-id (dissoc opts :operation-kind :ref-id))
    {:ok? false
     :status :unsupported
     :note "Meta campaign/adset/ad mutations are synchronous and have no operation to poll. Pass {:operation-kind :insights-report :ref-id <report-run-id>} for the one real async surface."})))
