(ns kotoba.issue.run
  "Generic agent-run FSM: plan -> act -> observe -> {done | error |
  awaiting-approval | cancelled}.

  A pure reducer over run + event, generalized from manimani's original
  agent.cljc: `plan`/`observe`/`step`/`resume-after-review`/`cancel` never
  touch a store. Side effects stay *descriptions* (`:effects` data) for the
  host to interpret -- this is what lets GUI/TUI/CI share the same loop and
  lets a crashed run be reconstructed from its ledger.

  The FSM interlocks with `kotoba.issue.gate`: `plan` emits a
  {:effect :issue/propose ...} description; a host interpreter (see
  `interpret-propose!` below for a ready-made one) calls
  gate/propose!+gate/route[+gate/merge!] and hands the result to `observe`.
  A run reaching :awaiting-approval means its proposal is sitting at
  :awaiting-review in the gate; a run reaching :done means its proposal has
  been merge!-d."
  (:require [kotoba.issue.gate :as gate]))

(def active-phases #{:plan :act :observe})
(def terminal-phases #{:done :error :awaiting-approval :cancelled})

(defn new-run
  [{:keys [run-id issue-id ts] :as attrs}]
  (merge {:run/id run-id
          :run/issue issue-id
          :phase :plan
          :history []
          :started-at ts}
         (dissoc attrs :run-id :issue-id :ts)))

(defn done? [run] (contains? terminal-phases (:phase run)))

(defn plan
  "Resolve phase=:plan via a caller-supplied plan-fn, transition to :act.

  plan-fn : (fn [run ts]) -> {:proposal <kotoba.issue.gate proposal ctor-map>
                              :note <string?>}"
  [plan-fn run ts]
  (let [{:keys [proposal note]} (plan-fn run ts)]
    {:run (assoc run :phase :act)
     :effects [{:effect :issue/propose :run-id (:run/id run) :proposal proposal}]
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts :phase :plan :note note}]}))

(defn observe
  "Take the host's result of interpreting the :issue/propose effect and
  transition accordingly.
  result = {:proposal-id id :routing (:auto-mergeable|:awaiting-review) :merged [...]?}
         | {:error str}"
  [run {:keys [proposal-id routing merged error]} ts]
  (cond
    error
    {:run (assoc run :phase :error)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts :phase :error :error error}]}

    (or merged (= routing :auto-mergeable))
    {:run (assoc run :phase :done :proposal proposal-id)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts
               :phase :done :proposal proposal-id :result {:merged merged}}]}

    :else
    {:run (assoc run :phase :awaiting-approval :proposal proposal-id)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts
               :phase :awaiting-approval :proposal proposal-id}]}))

(defn step
  "event: {:type :advance :ts ..} | {:type :result :ts .. :result {..}}"
  [plan-fn run {:keys [type ts result]}]
  (case [type (:phase run)]
    [:advance :plan] (plan plan-fn run ts)
    [:advance :act] {:run run :effects [] :ledger []}
    [:result :act] (observe run result ts)
    [:result :plan] (observe run result ts)
    {:run run :effects [] :ledger []}))

(defn resume-after-review
  "Call once a human has reviewed the run's proposal (gate/review!).
  :approve -> :done (caller must have already merge!-d and pass :merged);
  :reject -> :error; :request-changes -> back to :plan."
  [run verdict ts {:keys [merged]}]
  (case verdict
    :approve
    {:run (assoc run :phase :done)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts
               :phase :done :proposal (:proposal run) :result {:merged merged}}]}

    :reject
    {:run (assoc run :phase :error)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts
               :phase :error :proposal (:proposal run) :error "rejected"}]}

    :request-changes
    {:run (assoc run :phase :plan)
     :effects []
     :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts
               :phase :plan :proposal (:proposal run) :note "changes requested"}]}))

(defn cancel
  [run ts reason]
  {:run (assoc run :phase :cancelled)
   :effects []
   :ledger [{:run-id (:run/id run) :issue-id (:run/issue run) :ts ts :phase :cancelled :note reason}]})

;; ---------- optional convenience: a default effect interpreter over the gate ----------

(defn interpret-propose!
  "A ready-made interpreter for the {:effect :issue/propose} effect `plan`
  emits, for hosts that don't need a custom one: proposes against `store`,
  routes it per `autonomy`, and auto-merges via `handlers` when the risk
  tier allows. Returns the result map `observe` expects. This is the one
  place in this namespace that touches a store -- everything else stays a
  pure reducer."
  [store handlers autonomy {:keys [proposal]}]
  (let [p (gate/propose! store proposal)
        proposal-id (:kotoba.issue.proposal/id p)
        routing (gate/route autonomy p)]
    (if (= :auto-mergeable routing)
      (let [_ (gate/approve! store proposal-id {:decider "kotoba.issue.run/auto"
                                                 :note "auto-merge: risk tier allows"})
            ;; Scope to just the proposal this call approved -- otherwise
            ;; merge! sweeps every :approved proposal in the store,
            ;; including unrelated ones from other runs still awaiting
            ;; their own separate human review/merge!.
            merged (gate/merge! store handlers {:proposal-id proposal-id})]
        {:proposal-id proposal-id :routing routing :merged merged})
      {:proposal-id proposal-id :routing routing})))
