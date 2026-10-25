(ns denrei.operation
  "ChannelActor — one draft/post operation = one supervised actor run, a
  langgraph-clj StateGraph. Two flows share one auditable graph:

    ingest (record-op):  intake → record → END
        :space/register mechanically records a kaisha.model space (channels/
        members) as a durable ground fact. This is the observe charter;
        always on, never an LLM call, never an outbound post.

    assess (assess-op):  intake → advise → govern → decide → commit|hold|approval
        post-LLM (sealed) proposes a drafted channel message, or (for
        :message/post) a pass-through recommendation over the already-
        committed draft; MembershipGovernor enforces no-actuation /
        membership / mention-consent / tenant-isolation; the phase gate adds
        caution; posting a message ALWAYS routes to a human
        (interrupt-before :request-approval).

  Single invariant (the denrei analog of kekkai's no-data-plane-actuation /
  tayori's no-send-no-publish / koyomi's no-share):
    the actor never posts what the MembershipGovernor would reject, and
    post-LLM never actuates directly — committing a draft is data (a
    'casual commit'); only a human approval turns it into an actual post
    into the space."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [denrei.coordllm :as coordllm]
            [denrei.governor :as gov]
            [denrei.model :as model]
            [denrei.phase :as phase]
            [denrei.channelport :as channelport]
            [denrei.store :as store]))

(defn- request->record
  "Map an ingest request to a store ground-fact record."
  [{:keys [op space value]}]
  (case op
    :space/register {:kind :space :id space :value value}))

(defn- subject [{:keys [message space]}] (or message space))

(defn- pending-record
  "The store record a clean/approved assess op commits. :message/draft stores
  the proposal itself (via denrei.model/draft, the canonical draft shape);
  :message/post flips the already-stored draft's :status AND carries forward
  `verdict`'s `:checked-content` — the exact value denrei.governor/check
  validated at govern-time for THIS request (the store's `draft-of`, per
  `content-of`) — so commit-effects! can post that exact, already-
  checkpointed content instead of re-reading (and potentially re-trusting a
  since-mutated) store draft at commit time (TOCTOU fix, mirrored from
  koyomi). It must NOT carry forward `proposal`'s :content: `content-of`
  deliberately distrusts the proposal for :message/post, so using `proposal`
  here would post whatever a forged/buggy post-LLM claims instead of what
  was actually governed."
  [request proposal verdict message-id]
  (case (:op request)
    :message/draft
    {:kind :draft :id message-id
     :value (model/draft (:activity request) message-id (:content proposal)
                          {:confidence (:confidence proposal)
                           :cites      (:cites proposal)
                           :redactions (:redactions proposal)})}
    :message/post
    {:kind :draft :id message-id :value {:status :posted :content (:checked-content verdict)}}))

(defn- commit-effects!
  "Perform the op-specific EXTERNAL effect BEFORE anything is written to the
  store — if the ChannelTarget call throws (network error, deliverer
  failure, …), no store mutation and no :committed ledger fact happen, so the
  store never durably claims a post that didn't actually occur.

  Both branches read content from `record` (the commit about to be written),
  NEVER from a fresh `store/draft-of` re-read:

  `:message/draft` records its content via propose-revision! from `record` —
  the store doesn't have it yet at this point anyway.

  `:message/post` posts `record`'s `:value :content`, which pending-record
  carried forward from the governed `verdict`'s `:checked-content` — the
  exact content denrei.governor/check already vetted for THIS approval
  request back at govern-time (before :request-approval's human-in-the-loop
  interrupt), never the untrusted `proposal` channel. A fresh
  `(store/draft-of store message)` re-read here would be a TOCTOU: the
  human approved what they reviewed at govern-time, but if the stored draft
  was mutated while the approval sat in the interrupt (e.g. a legitimate
  concurrent :message/draft revision landing on the same message), a re-read
  would post whatever is CURRENTLY in the store — content that was never
  re-governed. Using the checkpointed `record` content instead means the
  post is always exactly what was approved, unaffected by any later
  mutation.

  Returns a map of extra store facts to merge in on success (the
  propose-revision! :proposal-id, so a later :message/post knows the draft
  was proposed against a real target), or nil."
  [channelport _store {:keys [op message]} record]
  (case op
    :message/draft
    (let [{:keys [proposal-id]} (channelport/propose-revision! channelport message
                                  (get-in record [:value :content]))]
      {:kind :draft :id message :value {:proposal-id proposal-id}})
    :message/post
    (do (channelport/post! channelport message (get-in record [:value :content]))
        nil)
    nil))

(defn build
  "Compiles a ChannelActor bound to `store` (any denrei.store/Store).
  opts: :advisor (default mock), :channelport (default mock), :checkpointer
  (default in-mem)."
  [store & [{:keys [advisor channelport checkpointer]
             :or   {advisor      (coordllm/mock-advisor)
                    channelport  (denrei.channelport/mock-channelport)
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
                                                  (seq (:duplicates verdict)) :duplicate-body
                                                  :else :low-confidence))
                        :recommendation (:recommendation proposal)
                        :phase ph :confidence (:confidence verdict)}]}
              :commit
              {:disposition :commit :record (pending-record request proposal verdict subj)}))))

      (g/add-node :request-approval
        (fn [{:keys [request proposal approval verdict]}]
          (let [subj (subject request)]
            (if (= :approved (:status approval))
              {:disposition :commit
               :record (update (pending-record request proposal verdict subj)
                               :value assoc :approved-by (:by approval))
               :audit [{:t :human-signoff :op (:op request) :subject subj
                        :by (:by approval) :recommendation (:recommendation proposal)}]}
              {:disposition :hold
               :audit [{:t :signoff-rejected :op (:op request) :subject subj
                        :disposition :hold :basis [:human-rejected]}]}))))

      ;; op-specific EXTERNAL effect FIRST, then the record + ledger — a
      ;; thrown effect leaves no trace of a post that never actually happened.
      (g/add-node :commit
        (fn [{:keys [request record]}]
          (let [extra (commit-effects! channelport store request record)]
            (store/record-datom! store record)
            (when extra (store/record-datom! store extra))
            (let [f {:t :committed :op (:op request) :subject (subject request)
                     :disposition :commit :basis (get-in record [:value :status] :proposed)}]
              (store/append-ledger! store f)
              {:audit [f]}))))

      (g/add-node :hold
        (fn [{:keys [audit]}]
          (when-let [hf (last (filter #(#{:denrei-hold :signoff-rejected} (:t %)) audit))]
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
