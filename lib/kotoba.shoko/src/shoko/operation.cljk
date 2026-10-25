(ns shoko.operation
  "ArchiveActor — one draft/share operation = one supervised actor run, a
  langgraph-clj StateGraph. Two flows share one auditable graph:

    ingest (record-op):  intake → record → END
        `:file/register` records a `drive.model` file/folder EDN item as a
        durable ground fact. Always on, never an LLM call, never a grant.

    assess (assess-op):  intake → advise → govern → decide → commit|hold|approval
        archive-LLM (sealed) proposes a `:file/draft` (drive.model EDN
        content + confidence + cites + redactions), or (for `:file/share`) a
        pass-through recommendation over the already-committed draft, naming
        a `:principal`; ArchiveGovernor enforces no-actuation / subject-
        exists / share-requires-acl / tenant-isolation; the phase gate adds
        caution; granting access (`:file/share`) ALWAYS routes to a human
        (interrupt-before :request-approval), at every phase.

  Single invariant (the shoko analog of kekkai's no-data-plane-actuation /
  teian's no-actuation / koyomi's no-send):
    the actor never grants access the ArchiveGovernor would reject, and
    archive-LLM never actuates directly — committing a draft is data (a
    'casual commit'); only a human approval turns it into an access grant.

  TOCTOU note (koyomi confirmed-bug-#1 lesson, applied from the start):
  `commit-effects!`'s `:file/share` branch shares `verdict`'s
  `:checked-content` — the EXACT content ArchiveGovernor/check already
  vetted for THIS request back at govern-time, before :request-approval's
  human-in-the-loop interrupt. `verdict` is a langgraph checkpointed state
  channel, so it survives the interrupt unchanged; it is NEVER re-read fresh
  from `store/draft-of` at commit time. A fresh re-read here would be a
  TOCTOU: if the stored draft were mutated while the approval sat in the
  interrupt (e.g. a legitimate concurrent `:file/draft` revision landing on
  the same file), a re-read would share whatever is CURRENTLY in the store —
  content that was never re-governed for this approval. See
  governor_contract_test's share-time TOCTOU test.

  This branch must NOT use `proposal`'s :content: governor/check never
  validates the proposal's content against anything (see governor.cljc),
  so an adversarial/forged proposal's content must never reach
  archiveport/share! — only the governed `:checked-content` may (confirmed
  bug this closes)."
  (:require [langgraph.graph :as g]
            [langgraph.checkpoint :as cp]
            [shoko.archiveport :as archiveport]
            [shoko.coordllm :as coordllm]
            [shoko.governor :as gov]
            [shoko.model :as model]
            [shoko.phase :as phase]
            [shoko.store :as store]))

(defn- request->record
  "Map an ingest request to a store ground-fact record."
  [{:keys [op file value]}]
  (case op
    :file/register {:kind :file :id file :value value}))

(defn- subject [{:keys [file]}] file)

(defn- pending-record
  "The store record a clean/approved assess op commits. `:file/draft` stores
  the proposal itself (via shoko.model/draft, the canonical draft shape);
  `:file/share` stores a NEW shoko.model/grant for (:principal request,
  file-id) — a separate ledger entity from the draft (many principals can
  be granted access to the same archived file over time). Neither branch
  ever re-reads the store — both derive entirely from `proposal`/`request`,
  the checkpointed channels carried through any human-approval interrupt."
  [request proposal file-id]
  (case (:op request)
    :file/draft
    {:kind :draft :id file-id
     :value (model/draft (:activity request) file-id (:content proposal)
                         {:confidence (:confidence proposal)
                          :cites (:cites proposal)
                          :redactions (:redactions proposal)
                          :status :proposed})}
    :file/share
    {:kind :grant :id (model/grant-id (:principal request) file-id)
     :value (model/grant (:principal request) file-id)}))

(defn- commit-effects!
  "Perform the op-specific EXTERNAL effect BEFORE anything is written to the
  store — if the ArchiveTarget call throws (network error, distributor
  failure, …), no store mutation and no :committed ledger fact happen, so
  the store never durably claims a share that didn't actually occur.

  `:file/draft` reads its content from `record` (the commit about to be
  written) — the store doesn't have it yet at this point anyway.

  `:file/share` reads content from `verdict`'s `:checked-content`, NEVER
  from `proposal` and NEVER from a fresh `store/draft-of` re-read — see the
  TOCTOU note in this namespace's docstring. `record`'s :value for
  :file/share is a shoko.model/grant (no :content field — grants stay a
  clean ACL shape), so the content to actually deliver comes from the
  checkpointed `verdict` channel instead.

  Returns a map of extra store facts to merge in on success (currently just
  `:file/draft`'s returned :branch), or nil."
  [archiveport store {:keys [op file principal]} record verdict]
  (case op
    :file/draft
    (let [f (store/file store file)
          {:keys [branch]} (archiveport/propose-revision! archiveport f (get-in record [:value :content]))]
      (when branch {:kind :draft :id file :value {:branch branch}}))
    :file/share
    (do (archiveport/share! archiveport file principal (:checked-content verdict))
        nil)
    nil))

(defn build
  "Compiles an ArchiveActor bound to `store` (any shoko.store/Store).
  opts: :advisor (default mock), :archiveport (default mock), :checkpointer
  (default in-mem)."
  [store & [{:keys [advisor archiveport checkpointer]
             :or   {advisor      (coordllm/mock-advisor)
                    archiveport  (shoko.archiveport/mock-archiveport)
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
                        :reason (or reason (if (:high-stakes? verdict) :human-signoff
                                               :low-confidence))
                        :recommendation (:recommendation proposal)
                        :phase ph :confidence (:confidence verdict)}]}
              :commit
              {:disposition :commit :record (pending-record request proposal subj)}))))

      (g/add-node :request-approval
        (fn [{:keys [request proposal approval]}]
          (let [subj (subject request)
                base (pending-record request proposal subj)]
            (if (= :approved (:status approval))
              {:disposition :commit
               ;; :now is an OPTIONAL request field for deterministic demo/test
               ;; seeding only (pass an explicit epoch-seconds value to pin
               ;; :granted-at); a real request normally omits it, so the
               ;; fallback below must be the actual current time
               ;; (store/real-now), never the fixed store/demo-now constant —
               ;; the audit ledger's "when" must be real for a real commit.
               :record (case (:op request)
                         :file/share (update base :value assoc
                                             :granted-by (:by approval)
                                             :granted-at (:now request (store/real-now)))
                         (update base :value assoc :approved-by (:by approval)))
               :audit [{:t :human-signoff :op (:op request) :subject subj
                        :by (:by approval) :recommendation (:recommendation proposal)}]}
              {:disposition :hold
               :audit [{:t :signoff-rejected :op (:op request) :subject subj
                        :disposition :hold :basis [:human-rejected]}]}))))

      ;; op-specific EXTERNAL effect FIRST, then the record + ledger — a
      ;; thrown effect leaves no trace of a share that never actually happened.
      (g/add-node :commit
        (fn [{:keys [request record verdict]}]
          (let [extra (commit-effects! archiveport store request record verdict)]
            (store/record-datom! store record)
            (when extra (store/record-datom! store extra))
            (let [f {:t :committed :op (:op request) :subject (subject request)
                     :disposition :commit :basis (get-in record [:value :status] :granted)}]
              (store/append-ledger! store f)
              {:audit [f]}))))

      (g/add-node :hold
        (fn [{:keys [audit]}]
          (when-let [hf (last (filter #(#{:shoko-hold :signoff-rejected} (:t %)) audit))]
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
