(ns soukai.operation
  "MeetingActor — one draft/send/finalize operation = one supervised actor
  run, a langgraph-clj StateGraph. Two flows share one auditable graph:

    ingest (record-op):  intake → record → END
        :meeting/register / :record-date/snapshot / :agenda/register /
        :vote/record mechanically record soukai's ground facts. This is the
        observe charter; always on, never an LLM call, never an outbound
        notice.

    assess (assess-op):  intake → advise → govern → decide → commit|hold|approval
        secretary-LLM (sealed) proposes a convocation-notice draft, a
        resolution-outcome explanation (whose :outcome is ALWAYS soukai.
        tally/outcome-of's verbatim output), a minutes draft, or (for
        :convocation/send / :minutes/finalize) a pass-through recommendation
        over an already-committed draft; ResolutionGovernor enforces
        no-actuation / notice-period / electronic-provision / resolution-
        mismatch / minutes-legal-fields / tenant-isolation; the phase gate
        adds caution; sending the notice and finalizing the minutes ALWAYS
        route to a human (interrupt-before :request-approval).

  Single invariant (the soukai analog of koyomi's no-shared-consent-blocked /
  tayori's no-send-no-publish):
    the actor never sends/finalizes anything the ResolutionGovernor would
    reject, and secretary-LLM never actuates directly — committing a draft
    is data (a 'casual commit'); only a human approval turns it into an
    outbound notice send or a legally-final minutes record."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [soukai.secretaryllm :as secretaryllm]
            [soukai.governor :as gov]
            [soukai.model :as model]
            [soukai.noticeport :as noticeport]
            [soukai.phase :as phase]
            [soukai.store :as store]))

(defn- request->record
  "Map an ingest request to a store ground-fact record."
  [{:keys [op meeting agenda value]}]
  (case op
    :meeting/register     {:kind :meeting  :id meeting :value value}
    :record-date/snapshot {:kind :snapshot :id meeting :value value}
    :agenda/register      {:kind :agenda   :id agenda  :value value}
    :vote/record          {:kind :vote     :id agenda  :value value}))

(defn- subject
  "The ledger-facing subject id for a request: the meeting for every op
  except :resolution/finalize (and its ingest counterparts :agenda/register
  / :vote/record), which are about a specific agenda item."
  [{:keys [op meeting agenda]}]
  (if (contains? #{:agenda/register :vote/record :resolution/finalize} op) agenda meeting))

(defn- pending-record
  "The store record a clean/approved assess op commits. :convocation/draft,
  :resolution/finalize, and :minutes/draft store the proposal itself (via
  soukai.model/draft, the canonical draft shape). :convocation/send and
  :minutes/finalize flip the already-stored draft's :status AND carry
  forward the proposal's :content — the same content the governor already
  vetted at govern-time for THIS request — so commit-effects! can act on
  that exact, already-checkpointed content instead of re-reading (and
  potentially re-trusting a since-mutated) store draft at commit time
  (TOCTOU fix, mirrors koyomi.operation/pending-record)."
  [request proposal]
  (case (:op request)
    :convocation/draft
    (let [k (store/convocation-key (:meeting request))]
      {:kind :draft :id k
       :value (model/draft k (:content proposal)
                {:confidence (:confidence proposal) :cites (:cites proposal) :redactions (:redactions proposal)})})
    :convocation/send
    (let [k (store/convocation-key (:meeting request))]
      {:kind :draft :id k :value {:status :sent :content (:content proposal)}})
    :resolution/finalize
    (let [k (store/resolution-key (:agenda request))]
      {:kind :draft :id k
       :value (model/draft k (:content proposal)
                {:confidence (:confidence proposal) :cites (:cites proposal) :redactions (:redactions proposal)
                 :outcome (:outcome proposal)})})
    :minutes/draft
    (let [k (store/minutes-key (:meeting request))]
      {:kind :draft :id k
       :value (model/draft k (:content proposal)
                {:confidence (:confidence proposal) :cites (:cites proposal) :redactions (:redactions proposal)})})
    :minutes/finalize
    (let [k (store/minutes-key (:meeting request))]
      {:kind :draft :id k :value {:status :finalized :content (:content proposal)}})))

(defn- commit-effects!
  "Perform the op-specific EXTERNAL effect BEFORE anything is written to the
  store — if the NoticeTarget call throws (distributor failure, …), no
  store mutation and no :committed ledger fact happen, so the store never
  durably claims a send that didn't actually occur.

  Both effect-bearing branches read content from `record` (the commit about
  to be written), NEVER from a fresh `store/draft-of` re-read — the exact
  content soukai.governor/check already vetted for THIS approval request
  back at govern-time (before :request-approval's human-in-the-loop
  interrupt). A fresh store re-read here would be a TOCTOU: the human
  approved what they reviewed at govern-time, but if the stored draft was
  mutated while the approval sat in the interrupt (e.g. a legitimate
  concurrent :convocation/draft revision landing on the same meeting), a
  re-read would send whatever is CURRENTLY in the store — content that was
  never re-governed. Using the checkpointed `record` content instead means
  the send is always exactly what was approved, unaffected by any later
  mutation (mirrors koyomi.operation/commit-effects!'s TOCTOU discipline
  verbatim).

  :resolution/finalize and :minutes/draft have no external effect — a
  resolution/minutes draft is a control-plane record, not an outbound
  document.

  Returns a map of extra store facts to merge in on success, or nil."
  [noticeport _store {:keys [op meeting]} record]
  (case op
    :convocation/draft
    (let [{:keys [proposal-id]} (noticeport/propose-revision! noticeport meeting
                                  (get-in record [:value :content]))]
      {:kind :draft :id (:id record) :value {:proposal-id proposal-id}})
    :convocation/send
    (do (noticeport/send! noticeport meeting (get-in record [:value :content]))
        nil)
    nil))

(defn build
  "Compiles a MeetingActor bound to `store` (any soukai.store/Store).
  opts: :advisor (default mock), :noticeport (default mock), :checkpointer
  (default in-mem)."
  [store & [{:keys [advisor noticeport checkpointer]
             :or   {advisor      (secretaryllm/mock-advisor)
                    noticeport   (soukai.noticeport/mock-noticeport)
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
                f   {:t :recorded :op (:op request) :subject (subject request)
                     :disposition :record :basis (:kind rec)}]
            (store/record-datom! store rec)
            (store/append-ledger! store f)
            {:disposition :record :audit [f]})))

      ;; ── assess path ──
      (g/add-node :advise
        (fn [{:keys [request]}]
          (let [p (secretaryllm/-advise advisor store request)]
            {:proposal p :audit [(secretaryllm/trace request p)]})))

      (g/add-node :govern
        (fn [{:keys [request proposal]}]
          {:verdict (gov/check request proposal store)}))

      (g/add-node :decide
        (fn [{:keys [request context proposal verdict]}]
          (let [base (phase/verdict->disposition verdict)
                ph   (:phase context phase/default-phase)
                {:keys [disposition reason]} (phase/gate ph request base)
                subj (subject request)]
            (case disposition
              :hold
              {:disposition :hold
               :audit [(cond-> (gov/hold-fact request verdict)
                         reason (assoc :phase-reason reason :phase ph))]}
              :escalate
              {:disposition :escalate
               :audit [{:t :approval-requested :op (:op request) :subject subj
                        :reason (or reason (cond (:high-stakes? verdict) :human-signoff
                                                  (:close-margin? verdict) :close-margin
                                                  :else :low-confidence))
                        :recommendation (:recommendation proposal)
                        :phase ph :confidence (:confidence verdict)}]}
              :commit
              {:disposition :commit :record (pending-record request proposal)}))))

      (g/add-node :request-approval
        (fn [{:keys [request proposal approval]}]
          (let [subj (subject request)]
            (if (= :approved (:status approval))
              {:disposition :commit
               :record (update (pending-record request proposal)
                               :value assoc :approved-by (:by approval))
               :audit [{:t :human-signoff :op (:op request) :subject subj
                        :by (:by approval) :recommendation (:recommendation proposal)}]}
              {:disposition :hold
               :audit [{:t :signoff-rejected :op (:op request) :subject subj
                        :disposition :hold :basis [:human-rejected]}]}))))

      ;; op-specific EXTERNAL effect FIRST, then the record + ledger — a
      ;; thrown effect leaves no trace of a send that never actually happened.
      (g/add-node :commit
        (fn [{:keys [request record]}]
          (let [extra (commit-effects! noticeport store request record)]
            (store/record-datom! store record)
            (when extra (store/record-datom! store extra))
            (let [f {:t :committed :op (:op request) :subject (subject request)
                     :disposition :commit :basis (get-in record [:value :status] :proposed)}]
              (store/append-ledger! store f)
              {:audit [f]}))))

      (g/add-node :hold
        (fn [{:keys [audit]}]
          (when-let [hf (last (filter #(#{:soukai-hold :signoff-rejected} (:t %)) audit))]
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
