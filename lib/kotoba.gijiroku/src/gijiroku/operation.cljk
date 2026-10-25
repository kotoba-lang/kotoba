(ns gijiroku.operation
  "MeetingRecordActor — one gijiroku operation = one supervised actor run, a
  langgraph-clj StateGraph. Two flows share one auditable graph:

    ingest (record-op):  intake → record → END
        meeting/status/consent/recording/transcript become durable ground
        facts. This is the observe charter; always on, never an LLM call,
        never a distribution.

    assess (assess-op):  intake → advise → govern → decide → commit|hold|approval
        the scribe-LLM (sealed) proposes minutes (summary/decisions/action-
        items/cites/redactions) for :minutes/draft; the PrivacyGovernor
        enforces consent/tenant/redaction/no-actuation invariants; the phase
        gate adds caution; `:minutes/distribute` ALWAYS routes to a human
        (interrupt-before :request-approval), whatever the phase.

  Single invariant (the gijiroku analog of robotaxi's safety contract): the
  actor never commits minutes the PrivacyGovernor would reject, and never
  distributes anything itself — it drafts a record; a human-approved
  Distributor port does the actual send."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [gijiroku.scribellm :as scribellm]
            [gijiroku.governor :as gov]
            [gijiroku.phase :as phase]
            [gijiroku.store :as store]))

(defn- request->record
  "Map an ingest request to a store ground-fact record."
  [{:keys [op meeting-id value]}]
  (case op
    :meeting/register   {:kind :meeting    :id meeting-id :value value}
    :meeting/status     {:kind :meeting    :id meeting-id :value value}
    :consent/record     {:kind :consent    :id meeting-id :value value}
    :recording/fetch    {:kind :recording  :id meeting-id :value value}
    :transcript/ingest  {:kind :transcript :id meeting-id :value value}))

(defn- minutes-record
  "The store record a clean/approved assess op commits. `:minutes/draft`
  builds it from `proposal` (the scribe-LLM's fresh output for this meeting).
  `:minutes/distribute` builds it from `verdict`'s `:checked-content` — the
  store's already-committed, already-redaction-checked minutes that
  gijiroku.governor/check validated at govern-time for THIS request — NEVER
  from `proposal`: a distribute-time proposal is re-derived from the raw
  transcript by a fresh scribe-LLM call that governor/check's redaction
  re-check deliberately distrusts (see governor.cljc), so building the
  distributed record from `proposal` instead would validate one map and
  commit/distribute a different, unvalidated one."
  [request proposal verdict by]
  (case (:op request)
    :minutes/distribute
    {:kind :minutes :id (:meeting-id request)
     :value (assoc (:checked-content verdict) :by by)}
    {:kind :minutes :id (:meeting-id request)
     :value {:summary (:summary proposal) :decisions (:decisions proposal)
             :action-items (:action-items proposal) :cites (:cites proposal)
             :redactions (:redactions proposal) :by by}}))

(defn- commit-effects!
  "Op-specific side effect on commit. Only `:minutes/distribute` actuates
  anything, and only after human approval routed it here — it calls the
  injected Distributor port (default a no-op mock) with the meeting, its
  committed minutes, and the recipient list. Drafting never actuates."
  [store distributor {:keys [op meeting-id recipients]}]
  (when (and (= :minutes/distribute op) distributor)
    (distributor (store/meeting store meeting-id) (store/minutes-of store meeting-id) recipients)))

(defn build
  "Compiles a MeetingRecordActor bound to `store` (any gijiroku.store/Store).
  opts: :advisor (default mock), :distributor (default nil — no-op),
  :checkpointer (default in-mem)."
  [store & [{:keys [advisor distributor checkpointer]
             :or   {advisor      (scribellm/mock-advisor)
                    checkpointer (cp/mem-checkpointer)}}]]
  (-> (g/state-graph
       {:channels
        {:request     {:default nil}
         :context     {:default nil}   ; :phase + (future) authn
         :proposal    {:default nil}
         :verdict     {:default nil}
         :disposition {:default nil}
         :record      {:default nil}
         :approval    {:default nil}
         :audit       {:reducer into :default []}}})

      (g/add-node :intake (fn [s] s))

      ;; ── ingest path: record a ground fact (observe), no LLM/governor ──
      (g/add-node :record
        (fn [{:keys [request]}]
          (let [rec (request->record request)
                f   {:t :recorded :op (:op request) :meeting-id (:meeting-id request)
                     :disposition :record :basis (:kind rec)}]
            (store/record-datom! store rec)
            (store/append-ledger! store f)
            {:disposition :record :audit [f]})))

      ;; ── assess path ──
      (g/add-node :advise
        (fn [{:keys [request]}]
          (let [transcript (store/transcript-of store (:meeting-id request))
                p (scribellm/-advise advisor transcript)]
            {:proposal p :audit [(scribellm/trace (:meeting-id request) p)]})))

      (g/add-node :govern
        (fn [{:keys [request proposal]}]
          {:verdict (gov/check request proposal store)}))

      (g/add-node :decide
        (fn [{:keys [request context proposal verdict]}]
          (let [base (phase/verdict->disposition verdict)
                ph   (:phase context phase/default-phase)
                {:keys [disposition reason]} (phase/gate ph request base)]
            (case disposition
              :hold
              {:disposition :hold
               :audit [(cond-> (gov/hold-fact request verdict)
                         reason (assoc :phase-reason reason :phase ph))]}
              :escalate
              {:disposition :escalate
               :audit [{:t :approval-requested :op (:op request) :meeting-id (:meeting-id request)
                        :reason (or reason (if (:high-stakes? verdict) :distribute-signoff
                                               :low-confidence))
                        :summary (:summary proposal)
                        :phase ph :confidence (:confidence verdict)}]}
              :commit
              {:disposition :commit :record (minutes-record request proposal verdict :auto)}))))

      (g/add-node :request-approval
        (fn [{:keys [request proposal approval verdict]}]
          (if (= :approved (:status approval))
            {:disposition :commit
             :record (minutes-record request proposal verdict (:by approval))
             :audit [{:t :human-signoff :op (:op request) :meeting-id (:meeting-id request)
                      :by (:by approval) :summary (:summary proposal)}]}
            {:disposition :hold
             :audit [(merge (gov/hold-fact request
                                           (assoc verdict :violations
                                                  [{:rule :approval-rejected}]))
                            {:t :signoff-rejected})]})))

      ;; commit a minutes record (draft) or actuate distribution + ledger.
      (g/add-node :commit
        (fn [{:keys [request record]}]
          (store/record-datom! store record)
          (commit-effects! store distributor request)
          (let [f {:t :committed :op (:op request) :meeting-id (:meeting-id request)
                   :disposition :commit :basis (:summary (:value record))}]
            (store/append-ledger! store f)
            {:audit [f]})))

      (g/add-node :hold
        (fn [{:keys [audit]}]
          (when-let [hf (last (filter #(#{:privacy-hold :signoff-rejected} (:t %)) audit))]
            (store/append-ledger! store (assoc hf :disposition :hold)))
          {}))

      (g/set-entry-point :intake)
      ;; intake routes ingest vs assess.
      (g/add-conditional-edges :intake
        (fn [{:keys [request]}]
          (if (phase/record-op? (:op request)) :record :advise)))
      (g/add-edge :advise :govern)
      (g/add-edge :govern :decide)
      (g/add-conditional-edges :decide
        (fn [{:keys [disposition]}]
          (case disposition :commit :commit, :escalate :request-approval, :hold)))
      (g/add-conditional-edges :request-approval
        (fn [{:keys [disposition]}] (if (= :commit disposition) :commit :hold)))

      (g/set-finish-point :record)
      (g/set-finish-point :commit)
      (g/set-finish-point :hold)

      (g/compile-graph
       {:checkpointer checkpointer :interrupt-before #{:request-approval}})))
