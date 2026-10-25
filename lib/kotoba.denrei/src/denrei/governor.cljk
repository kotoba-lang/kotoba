(ns denrei.governor
  "MembershipGovernor — the independent censor that earns post-LLM the right
  to *propose* a draft. The LLM has no notion of channel membership, mention
  consent state, tenant boundaries, or the no-actuation charter, so this MUST
  be a separate system (rules over the store's ground facts) able to *reject*
  a proposal and fall back to HOLD — the denrei analog of koyomi's/tayori's
  ComplianceGovernor.

  The actor is **propose → draft only**. It never posts into the space
  itself; posting is ALWAYS routed to a human (the denrei analog of tayori's
  always-human `:reply/send` / koyomi's always-human `:event/share`). Below,
  HARD invariants force HOLD (a human cannot approve past a proposal that
  claims to have already posted, a post into a channel the actor's member
  identity doesn't belong to, a mention of a consent-blocked member, or a
  message whose tenant doesn't match the activity driving it); a clean post
  still routes to a human (high-stakes).

  HARD invariants:
    :message/draft
      1. Subject-exists   — the driving activity (:activity on the request)
                            must actually be registered (mirrors koyomi's
                            missing-activity, tayori's missing-thread).
      2. No-actuation     — proposal :effect must be :draft, never :post (a
                            control-plane record, never an outbound message).
      3. Target-integrity — the content's :space/:channel must equal the
                            request's (a same-tenant channel switch by the
                            LLM is a hijack of the human's review context).
      4. Channel-exists   — the target space AND channel must be registered
                            ground facts (never draft into a phantom channel).
      5. Membership       — the message's :kaisha/author (the actor's own
                            member identity) must be a member of the target
                            channel. Posting into #ops without membership is
                            structurally impossible, not merely reviewed.
      6. Model-validity   — `kaisha.validate/message-problems` over the
                            registered space: unknown author, missing
                            timestamp, orphan reply, nested thread. The
                            surface model's own invariants are the governor's
                            floor, not a separate convention.
      7. Tenant-isolation — the proposed content's :tenant must equal the
                            tenant derived from the driving activity's :repo.
    :message/post
      1. Subject-exists   — same activity-exists check as :message/draft.
      2. Draft-exists     — there must already be a committed draft for the
                            message (`store/draft-of`) — otherwise this would
                            be a phantom post of nil content that still
                            writes a false :posted/:committed ledger fact.
      3. Consent-required — EVERY @mention in the draft body (via
                            `kaisha.model/mentions`, the SAME parser the
                            ChannelTarget uses at delivery time) must not be
                            :consent :blocked. A :first-contact? mention is
                            NOT a hard violation (mirrors tayori's contact
                            model exactly) but IS high-stakes below.
      4. Channel-exists / Membership / Tenant-isolation — same checks, over
         the already-committed draft's content (defense-in-depth: the same
         sanity checks apply at both the draft and the post gate).
    (any other op) — an unrecognized :op is itself a hard violation
                     (fail-closed: a not-yet-wired op must never silently
                     pass as clean).
  SOFT:
    Confidence floor → escalate.
    Duplicate-body — an existing message in the target channel with an
      identical body → escalate, never hard (a legitimate re-announcement is
      possible; a human should still take a look before the space gets
      repetitive-bot noise).
    `:message/post` is ALWAYS high-stakes → human, at every phase. Any
      :first-contact? mention also forces high-stakes (even at
      :message/draft) — mirrors tayori's contact model, applied to mentioned
      members instead of message recipients."
  (:require [kaisha.model :as k]
            [kaisha.validate :as kv]
            [denrei.store :as store]))

(def confidence-floor 0.6)

;; ───────────────────────── invariant checks ─────────────────────────

(defn- missing-activity-violations [st activity-id]
  (when (nil? (store/activity st activity-id))
    [{:rule :missing-activity :detail (str "未登録の活動: " activity-id)}]))

(defn- missing-draft-violations
  "Unconditional hard check for :message/post: a draft must already exist for
  the message. Without this, :message/post on a never-drafted message
  proceeds with nil content all the way to commit-effects!, producing a
  phantom empty post handed to the deliverer and a false :posted/:committed
  ledger fact for a post that never meaningfully happened."
  [st message-id]
  (when (nil? (store/draft-of st message-id))
    [{:rule :missing-draft :detail (str "投稿対象のドラフトが未作成: " message-id)}]))

(defn- actuation-violations [proposal]
  (when (not= :draft (:effect proposal))
    [{:rule :no-actuation
      :detail (str "propose→draft のみ(実投稿は人間承認後の post! のみが行う)。effect="
                   (:effect proposal))}]))

(defn- target-violations
  "The content must target exactly the space/channel the request named — a
  silent channel switch by the LLM would make the human approve one thing
  while the commit posts another."
  [request content]
  (when content
    (concat
     (when (not= (:space request) (:space content))
       [{:rule :target-mismatch
         :detail (str "content space " (:space content) " ≠ request space " (:space request))}])
     (when (not= (:channel request) (:channel content))
       [{:rule :target-mismatch
         :detail (str "content channel " (:channel content) " ≠ request channel " (:channel request))}]))))

(defn- channel-violations
  "The target space and channel must be registered ground facts."
  [st content]
  (when content
    (let [sp (store/space st (:space content))
          ch (when sp (k/channel-by-id sp (:channel content)))]
      (cond
        (nil? sp) [{:rule :missing-channel :detail (str "未登録の space: " (:space content))}]
        (nil? ch) [{:rule :missing-channel :detail (str "未登録の channel: " (:channel content))}]))))

(defn- membership-violations
  "The message's author (the actor's own member identity) must belong to the
  target channel — the structural guarantee that denrei can never post into
  a private channel it wasn't invited to."
  [st content]
  (when content
    (let [sp     (store/space st (:space content))
          ch     (when sp (k/channel-by-id sp (:channel content)))
          author (get-in content [:message :kaisha/author])]
      (when (and ch (not (contains? (:kaisha/members ch) author)))
        [{:rule :not-a-member
          :detail (str author " は channel " (:channel content) " の member ではない")}]))))

(defn- model-violations
  "kaisha.validate over the registered space — the surface model's own
  structural invariants (unknown author, missing :kaisha/at, orphan reply,
  nested thread) are hard for the governor too."
  [st content]
  (when content
    (let [sp  (store/space st (:space content))
          ch  (when sp (k/channel-by-id sp (:channel content)))
          msg (:message content)]
      (when (and sp ch msg)
        (mapv (fn [p] {:rule :model-invalid :detail (str (:kaisha/code p) ": " (:kaisha/msg p))})
              (kv/message-problems sp ch msg))))))

(defn- tenant-of-activity [st activity-id] (:repo (store/activity st activity-id)))

(defn- tenant-violations [st activity-id content]
  (when content
    (let [expected (tenant-of-activity st activity-id)
          actual   (:tenant content)]
      (when (and expected (not= expected actual))
        [{:rule :tenant-mismatch
          :detail (str "message tenant " actual " は活動 " activity-id " の repo " expected " と不一致")}]))))

(defn- mention-contacts
  "Contacts for every @mention in the body — parsed with the SAME
  `kaisha.model/mentions` the ChannelTarget uses at delivery time, so what
  the governor censors is exactly what would go out."
  [st content]
  (->> (k/mentions (get-in content [:message :kaisha/body]))
       (map #(store/contact st %))
       (remove nil?)))

(defn- consent-violations [st content]
  (->> (mention-contacts st content)
       (filter #(= :blocked (:consent %)))
       (mapv (fn [c] {:rule :consent-blocked :detail (str "@" (:handle c) " は言及ブロック対象")}))))

(defn- high-stakes-mentions [st content]
  (filter :first-contact? (mention-contacts st content)))

(defn- duplicate-body-conflicts
  "Existing messages in the target channel (excluding message-id itself) with
  an identical body — a SOFT escalate signal, never hard."
  [st message-id content]
  (let [sp   (store/space st (:space content))
        ch   (when sp (k/channel-by-id sp (:channel content)))
        body (get-in content [:message :kaisha/body])]
    (->> (vals (:kaisha/messages ch))
         (remove #(= message-id (:kaisha/id %)))
         (filter #(= body (:kaisha/body %)))
         vec)))

(defn- content-of [request proposal st]
  (case (:op request)
    :message/draft (:content proposal)
    :message/post  (:content (store/draft-of st (:message request)))
    nil))

(defn check
  "Censors a post-LLM proposal for a denrei op. Returns
   {:ok? :violations :confidence :hard? :escalate? :high-stakes? :duplicates
    :checked-content}.

   Hard violations force HOLD and cannot be overridden. Posting a message is
   high-stakes → human sign-off even when clean; so is any draft mentioning a
   first-contact? member.

   `:checked-content` is the exact value this check validated (`content-of`
   above) -- for `:message/post` that's the store's `draft-of`, fetched fresh
   here, NOT `proposal`. The caller MUST deliver this value, not `proposal`:
   `content-of` deliberately distrusts the proposal for `:message/post` (see
   above), so building the delivered record from `proposal` instead of
   `:checked-content` would validate one map and deliver a different one."
  [request proposal st]
  (let [op      (:op request)
        content (content-of request proposal st)
        hard    (vec (case op
                       :message/draft
                       (concat (missing-activity-violations st (:activity request))
                               (actuation-violations proposal)
                               (target-violations request content)
                               (channel-violations st content)
                               (membership-violations st content)
                               (model-violations st content)
                               (tenant-violations st (:activity request) content))
                       :message/post
                       (concat (missing-activity-violations st (:activity request))
                               (missing-draft-violations st (:message request))
                               (channel-violations st content)
                               (membership-violations st content)
                               (consent-violations st content)
                               (tenant-violations st (:activity request) content))
                       [{:rule :unrecognized-op :detail (str "未対応 op: " op)}]))
        conf    (:confidence proposal 0.0)
        low?    (< conf confidence-floor)
        dups    (when content (duplicate-body-conflicts st (:message request) content))
        stakes? (or (= :message/post op) (boolean (seq (high-stakes-mentions st content))))
        hard?   (boolean (seq hard))]
    {:ok?             (and (not hard?) (not low?) (not stakes?) (empty? dups))
     :violations      hard
     :confidence      conf
     :hard?           hard?
     :escalate?       (and (not hard?) (or low? stakes? (seq dups)))
     :high-stakes?    stakes?
     :duplicates      dups
     :checked-content content}))

(defn hold-fact [request verdict]
  {:t :denrei-hold :op (:op request) :subject (:message request)
   :disposition :hold :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict) :confidence (:confidence verdict)})
