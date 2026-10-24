(ns kotoba.issue.gate
  "issue -> proposal(PR) -> review -> merge -> audit, as pure state transitions
  over an `IssueStore` (see `kotoba.issue.store`).

  An issue is the inbound thing to triage. A proposal is an agent's proposed
  action against an issue -- the 'PR': it carries a `rationale` (the
  human-readable diff: what would happen) and a `risk` tier. A review records
  a verdict (:approve / :reject / :request-changes). `merge!` is the step
  where an *approved* proposal is actually realized -- 'merging the PR runs
  the action' -- via caller-supplied handlers keyed by proposal kind. Every
  transition appends an audit record.

  Generalizes cloud-itonami's `activity.cljc`/`approval.cljc` and manimani's
  decision-ledger shape into one storage-agnostic vocabulary shared by both."
  (:require [kotoba.issue.store :as store]))

(def risks #{:read-only :external-send :financial :destructive})
(def verdicts #{:approve :reject :request-changes})
(def issue-states #{:open :triaged :closed})
(def proposal-statuses #{:proposed :approved :rejected :changes-requested :merged :failed :cancelled})
(def terminal-statuses #{:merged :rejected :failed :cancelled})

(defn- now [] #?(:clj (java.util.Date.) :cljs (js/Date.)))

(defn audit
  [{:keys [id type issue proposal source-event]}]
  (cond-> {:kotoba.issue.audit/id id
           :kotoba.issue.audit/type type
           :kotoba.issue.audit/at (now)}
    issue (assoc :kotoba.issue.audit/issue issue)
    proposal (assoc :kotoba.issue.audit/proposal proposal)
    source-event (assoc :kotoba.issue.audit/source-event source-event)))

;; ---------- issue ----------

(defn issue
  [{:keys [id kind title source source-id lane created-at state actor repo]
    :or {state :open}}]
  (when-not (contains? issue-states state)
    (throw (ex-info "Unknown issue state" {:state state})))
  (cond-> {:kotoba.issue/id id
           :kotoba.issue/kind kind
           :kotoba.issue/title title
           :kotoba.issue/source source
           :kotoba.issue/source-id source-id
           :kotoba.issue/state state}
    lane (assoc :kotoba.issue/lane lane)
    created-at (assoc :kotoba.issue/created-at created-at)
    actor (assoc :kotoba.issue/actor actor)
    repo (assoc :kotoba.issue/repo repo)))

(defn open-issue!
  [s issue-map]
  (let [i (if (:kotoba.issue/id issue-map) issue-map (issue issue-map))
        id (:kotoba.issue/id i)]
    (store/put-entity! s :issue id i)
    (store/append-audit! s (audit {:id (str "issue:" id ":opened")
                                    :type :issue/opened
                                    :issue id
                                    :source-event (pr-str i)}))
    (store/get-entity s :issue id)))

(defn close-issue!
  [s issue-id]
  (store/put-entity! s :issue issue-id {:kotoba.issue/state :closed})
  (store/append-audit! s (audit {:id (str "issue:" issue-id ":closed")
                                  :type :issue/closed
                                  :issue issue-id}))
  (store/get-entity s :issue issue-id))

;; ---------- proposal (the "PR") ----------

(defn proposal
  "rationale is the human-readable 'what would happen' summary -- the PR's diff."
  [{:keys [id issue kind risk tool payload rationale]}]
  (when-not (contains? risks risk)
    (throw (ex-info "Unknown proposal risk" {:risk risk})))
  (cond-> {:kotoba.issue.proposal/id id
           :kotoba.issue.proposal/issue issue
           :kotoba.issue.proposal/kind kind
           :kotoba.issue.proposal/risk risk
           :kotoba.issue.proposal/status :proposed}
    tool (assoc :kotoba.issue.proposal/tool tool)
    payload (assoc :kotoba.issue.proposal/payload-edn (pr-str payload))
    rationale (assoc :kotoba.issue.proposal/rationale rationale)))

(defn propose!
  [s proposal-map]
  (let [p (if (:kotoba.issue.proposal/id proposal-map) proposal-map (proposal proposal-map))
        id (:kotoba.issue.proposal/id p)]
    (store/put-entity! s :proposal id p)
    (store/append-audit! s (audit {:id (str "propose:" id)
                                    :type :proposal/proposed
                                    :issue (:kotoba.issue.proposal/issue p)
                                    :proposal id
                                    :source-event (pr-str p)}))
    (store/get-entity s :proposal id)))

(defn approval-required?
  ([risk] (approval-required? {:read-only :auto} risk))
  ([autonomy risk] (not= :auto (get autonomy risk :approve))))

(defn route
  "Return :auto-mergeable or :awaiting-review for a proposal under an autonomy policy."
  ([p] (route {:read-only :auto} p))
  ([autonomy p]
   (if (approval-required? autonomy (:kotoba.issue.proposal/risk p))
     :awaiting-review
     :auto-mergeable)))

;; ---------- review ----------

(defn- guard-not-terminal! [s proposal-id]
  (when (contains? terminal-statuses (:kotoba.issue.proposal/status (store/get-entity s :proposal proposal-id)))
    (throw (ex-info "Proposal is already terminal" {:proposal-id proposal-id}))))

(def ^:private verdict->status
  {:approve :approved :reject :rejected :request-changes :changes-requested})

(defn review!
  "Record a verdict on a proposal. verdict in #{:approve :reject :request-changes}."
  [s proposal-id verdict {:keys [decider note]}]
  (when-not (contains? verdicts verdict)
    (throw (ex-info "Unknown review verdict" {:verdict verdict})))
  (guard-not-terminal! s proposal-id)
  (let [p (store/get-entity s :proposal proposal-id)
        status (verdict->status verdict)
        review-id (str "review:" proposal-id ":" (name status))]
    (store/put-entity! s :proposal proposal-id {:kotoba.issue.proposal/status status})
    (store/put-entity! s :review review-id
                        {:kotoba.issue.review/id review-id
                         :kotoba.issue.review/proposal proposal-id
                         :kotoba.issue.review/verdict verdict
                         :kotoba.issue.review/decider decider
                         :kotoba.issue.review/decided-at (now)
                         :kotoba.issue.review/note note})
    (store/append-audit! s (audit {:id review-id
                                    :type (keyword "review" (name status))
                                    :issue (:kotoba.issue.proposal/issue p)
                                    :proposal proposal-id
                                    :source-event (pr-str {:proposal-id proposal-id :verdict verdict
                                                            :decider decider :note note})}))
    (store/get-entity s :proposal proposal-id)))

(defn approve! [s proposal-id opts] (review! s proposal-id :approve opts))
(defn reject! [s proposal-id opts] (review! s proposal-id :reject opts))
(defn request-changes! [s proposal-id opts] (review! s proposal-id :request-changes opts))

(defn approved-proposals
  "Every :approved proposal, or (with :proposal-id) just the one named -- so
  a caller that just approved a single proposal can merge! exactly that one
  instead of sweeping every other proposal that happens to also be sitting
  in :approved (e.g. one still awaiting a human's own separate merge!)."
  ([s] (approved-proposals s {}))
  ([s {:keys [limit proposal-id] :or {limit 50}}]
   (->> (store/list-entities s :proposal #(= :approved (:kotoba.issue.proposal/status %)))
        (filter (if proposal-id
                  #(= proposal-id (:kotoba.issue.proposal/id %))
                  (constantly true)))
        (take limit)
        vec)))

;; ---------- merge (the "PR merge triggers the action" step) ----------

(defn merge!
  "Execute approved proposals through caller-supplied handlers keyed by
  :kotoba.issue.proposal/kind. merge! only owns the state machine + audit;
  handlers decide *how* a kind of proposal is realized. Missing handlers mark
  the proposal :failed instead of executing arbitrary work.

  Without opts, this sweeps EVERY currently :approved proposal in the store
  -- pass {:proposal-id id} to scope it to just one (the caller's own),
  which any interpreter that just approved a single proposal itself should
  always do, or it will also execute unrelated proposals that merely happen
  to be sitting in :approved (e.g. one still awaiting a separate human
  merge!)."
  ([s handlers] (merge! s handlers {}))
  ([s handlers opts]
   (mapv
    (fn [p]
      (let [proposal-id (:kotoba.issue.proposal/id p)
            kind (:kotoba.issue.proposal/kind p)
            handler (or (get handlers kind) (get handlers :default))]
        (try
          (if-not handler
            (do
              (store/put-entity! s :proposal proposal-id {:kotoba.issue.proposal/status :failed})
              (store/append-audit! s (audit {:id (str "merge:" proposal-id ":failed")
                                              :type :merge/failed
                                              :issue (:kotoba.issue.proposal/issue p)
                                              :proposal proposal-id
                                              :source-event (pr-str {:reason :missing-handler :kind kind})}))
              {:proposal-id proposal-id :status :failed :reason :missing-handler})
            (let [result (handler p)]
              (store/put-entity! s :proposal proposal-id {:kotoba.issue.proposal/status :merged})
              (store/append-audit! s (audit {:id (str "merge:" proposal-id ":merged")
                                              :type :merge/merged
                                              :issue (:kotoba.issue.proposal/issue p)
                                              :proposal proposal-id
                                              :source-event (pr-str {:kind kind :result result})}))
              {:proposal-id proposal-id :status :merged}))
          (catch #?(:clj Throwable :cljs :default) t
            (store/put-entity! s :proposal proposal-id {:kotoba.issue.proposal/status :failed})
            (store/append-audit! s (audit {:id (str "merge:" proposal-id ":failed")
                                            :type :merge/failed
                                            :issue (:kotoba.issue.proposal/issue p)
                                            :proposal proposal-id
                                            :source-event (pr-str {:reason (ex-message t) :kind kind})}))
            {:proposal-id proposal-id :status :failed :reason (ex-message t)}))))
    (approved-proposals s opts))))

(defn dry-run!
  "Auto-approve every :proposed proposal, then merge! -- for tests/CLI only,
  since it skips real review."
  ([s handlers] (dry-run! s handlers {}))
  ([s handlers {:keys [decider note] :or {decider "kotoba-issue-dry-run" note "dry run"} :as opts}]
   (let [pending (store/list-entities s :proposal #(= :proposed (:kotoba.issue.proposal/status %)))
         approved (mapv #(approve! s (:kotoba.issue.proposal/id %) {:decider decider :note note}) pending)]
     {:approved (mapv :kotoba.issue.proposal/id approved)
      :merged (merge! s handlers opts)})))
