(ns ichiran.operation
  "TallyActor — one tally-workbook draft-or-publish operation = one
  supervised actor run, a langgraph-clj StateGraph. Two flows share one
  auditable graph:

    ingest (record-op):  intake → record → END
        `:artifact/register` becomes a durable ground fact (the itonami
        activity this tally is for). Always on, never an LLM call, never
        a delivery.

    assess (assess-op):  intake → advise → govern → decide → commit|hold|approval
        tally-LLM (sealed) proposes a `:tally/draft` (sheets.model workbook
        EDN content + confidence + cites + redactions + declared tenant), or
        (for `:tally/publish`) a pass-through recommendation over the
        already-committed draft; TallyGovernor enforces missing-subject /
        no-actuation / redaction / tenant-isolation; the phase gate adds
        caution; publishing (`:tally/publish`) a tally ALWAYS routes to a
        human (interrupt-before :request-approval), at every phase.

  Single invariant (the ichiran analog of teian's actor-never-delivers-what-
  the-governor-would-reject / koyomi's no-actuation):
    the actor never publishes a tally workbook the TallyGovernor would
    reject, and tally-LLM never actuates directly — committing a draft is
    data (a 'casual commit'); only a human approval turns it into an
    outbound publish (the 'send it' call)."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [ichiran.model :as model]
            [ichiran.coordllm :as coordllm]
            [ichiran.governor :as gov]
            [ichiran.phase :as phase]
            [ichiran.tallyport :as tallyport]
            [ichiran.store :as store]))

(defn- request->record
  "Map an ingest request to a store ground-fact record."
  [{:keys [op artifact value]}]
  (case op
    :artifact/register {:kind :artifact :id artifact :value value}))

(defn- subject [{:keys [artifact]}] artifact)

(defn- pending-record
  "The store record a clean/approved assess op commits.

  :tally/draft stores the proposal itself (verbatim sheets EDN content) --
  proposal IS what governor/check validated for this op, so it's safe to
  carry forward directly.

  :tally/publish flips the STORE'S OWN draft (`verdict`'s :checked-draft --
  the exact value governor/check re-fetched from the store and validated at
  govern-time for THIS request) to :published. It deliberately does NOT use
  `proposal`: for :tally/publish, governor/check's whole point is to
  distrust proposal's forwarded :cites/:redactions/:tenant/:content and
  recheck the store's ground truth instead (see governor.cljc) — delivering
  from `proposal` here would commit content the redaction/tenant-isolation
  recheck never actually validated. Using :checked-draft still avoids the
  TOCTOU a fresh re-read at commit-time would introduce: it's the SAME store
  snapshot governor/check already vetted at govern-time, carried forward
  through the checkpointed `verdict` channel across the human-approval
  interrupt, not read again later (mirroring koyomi's :event/share /
  shoko's :file/share)."
  [op proposal subj verdict]
  (case op
    :tally/draft
    {:kind :draft :id subj
     :value (model/draft subj (:workbook-id proposal) (:content proposal)
                         {:confidence (:confidence proposal)
                          :cites (:cites proposal)
                          :redactions (:redactions proposal)
                          :tenant (:tenant proposal)
                          :status :proposed})}
    :tally/publish
    {:kind :draft :id subj
     :value {:status :published :content (:content (:checked-draft verdict))}}))

(defn- commit-effects!
  "Perform the op-specific EXTERNAL effect BEFORE anything is written to the
  store — if the TallyTarget call throws (network error, export failure, …),
  no store mutation and no :committed ledger fact happen, so the store never
  durably claims a publish that didn't actually occur.

  Both branches read content from `record` (the commit about to be written),
  NEVER from a fresh `store/draft-of` re-read:

  `:tally/draft` reads its content from `record` because the store doesn't
  have it yet at this point anyway.

  `:tally/publish` delivers `record`'s `:value :content`, which
  `pending-record` built from `verdict`'s `:checked-draft` — the exact store
  draft `ichiran.governor/check` already fetched AND vetted for THIS
  approval request back at govern-time (before `:request-approval`'s
  human-in-the-loop interrupt), not `proposal` (which the recheck exists
  specifically to NOT trust) and not a fresh `(store/draft-of store
  artifact)` re-read here (which would be a TOCTOU: the human approved what
  the governor checked at govern-time, but if the stored draft was mutated
  while the approval sat in the interrupt, a re-read would deliver whatever
  is CURRENTLY in the store, never re-governed). Using the checkpointed
  `:checked-draft` content instead means the delivery is always exactly what
  was vetted, unaffected by any later mutation.

  Returns a map of extra store facts to merge in on success (currently just
  `:tally/draft`'s returned :branch), or nil."
  [tallyport store {:keys [op artifact target]} record]
  (case op
    :tally/draft
    (let [art (store/artifact store artifact)
          {:keys [branch]} (tallyport/propose-revision! tallyport art (get-in record [:value :content]))]
      (when branch {:kind :draft :id artifact :value {:branch branch}}))
    :tally/publish
    (let [art (store/artifact store artifact)]
      (tallyport/publish! tallyport art target {:content (get-in record [:value :content])})
      nil)
    nil))

(defn build
  "Compiles a TallyActor bound to `store` (any ichiran.store/Store).
  opts: :advisor (default mock), :tallyport (default mock), :checkpointer
  (default in-mem)."
  [store & [{:keys [advisor tallyport checkpointer]
             :or   {advisor      (coordllm/mock-advisor)
                    tallyport    (ichiran.tallyport/mock-tallyport)
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
          (let [p (coordllm/-advise advisor store request)]
            {:proposal p :audit [(coordllm/trace request p)]})))

      (g/add-node :govern
        (fn [{:keys [request proposal]}]
          {:verdict (gov/check request proposal store)}))

      (g/add-node :decide
        (fn [{:keys [request context proposal verdict]}]
          (let [base (phase/verdict->disposition verdict)
                ;; A missing :phase in context must fail closed to the MOST
                ;; conservative phase (0, ingest-only), not the MOST
                ;; permissive `phase/default-phase` (3) — see
                ;; ichiran.phase/conservative-phase.
                ph   (:phase context phase/conservative-phase)
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
                        :reason (or reason (if (:high-stakes? verdict) :human-signoff
                                               :low-confidence))
                        :recommendation (:recommendation proposal)
                        :phase ph :confidence (:confidence verdict)}]}
              :commit
              {:disposition :commit :record (pending-record (:op request) proposal subj verdict)}))))

      (g/add-node :request-approval
        (fn [{:keys [request proposal approval verdict]}]
          (let [subj (subject request)]
            (if (= :approved (:status approval))
              {:disposition :commit
               :record (update (pending-record (:op request) proposal subj verdict)
                               :value assoc :approved-by (:by approval))
               :audit [{:t :human-signoff :op (:op request) :subject subj
                        :by (:by approval) :recommendation (:recommendation proposal)}]}
              {:disposition :hold
               :audit [{:t :signoff-rejected :op (:op request) :subject subj
                        :disposition :hold :basis [:human-rejected]}]}))))

      ;; op-specific EXTERNAL effect FIRST, then the record + ledger — a
      ;; thrown effect leaves no trace of a delivery that never happened.
      (g/add-node :commit
        (fn [{:keys [request record]}]
          (let [extra (commit-effects! tallyport store request record)]
            (store/record-datom! store record)
            (when extra (store/record-datom! store extra))
            (let [f {:t :committed :op (:op request) :subject (subject request)
                     :disposition :commit :basis (get-in record [:value :status] :proposed)}]
              (store/append-ledger! store f)
              {:audit [f]}))))

      (g/add-node :hold
        (fn [{:keys [audit]}]
          (when-let [hf (last (filter #(#{:ichiran-hold :signoff-rejected} (:t %)) audit))]
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
