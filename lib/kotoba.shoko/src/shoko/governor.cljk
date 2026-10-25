(ns shoko.governor
  "ArchiveGovernor — the independent censor that earns archive-LLM the right
  to *propose* a draft. The LLM has no notion of ACL/grant state, tenant
  boundaries, or the no-actuation charter, so this MUST be a separate system
  (rules over the store's ground facts) able to *reject* a proposal and fall
  back to HOLD — the shoko analog of kekkai's TailnetGovernor / teian's
  BriefingGovernor / koyomi's ComplianceGovernor.

  The actor is **propose → draft only**. It never grants access itself;
  granting (`:file/share`) is ALWAYS routed to a human (the shoko analog of
  koyomi's always-human `:event/share` / teian's always-human
  `:deck/publish`). Below, HARD invariants force HOLD (a human cannot
  approve past a proposal that claims to have already shared, a share to an
  unregistered principal, or a file whose tenant doesn't match the activity
  driving it); a clean share still routes to a human (high-stakes).

  HARD invariants:
    :file/draft
      1. Subject-exists  — BOTH the file and the driving activity must
                           already be registered ground facts. Independent,
                           unconditional checks — fired regardless of what
                           `content`/`tenant` say, so a hallucinated file or
                           activity id can never silently no-op its way past
                           tenant-isolation below (mirrors koyomi's
                           missing-activity-violations / teian's
                           missing-artifact-violations / kekkai's
                           key-violations `:no-node` — the confirmed-bug
                           class this governor is built to avoid from the
                           start, see docs/DESIGN.md).
      2. No-actuation    — proposal :effect must be :draft, never :share (a
                           control-plane record, never an access grant).
      3. Tenant-isolation — the file's own registered :tenant must equal the
                           tenant derived from the driving activity's :repo.
                           A pure store-vs-store check (never trusts the
                           proposal's forwarded tenant), so it is exactly as
                           strong at draft-time as at share-time re-check.
    :file/share
      1. Subject-exists  — same file/activity-exist checks as :file/draft.
      2. Draft-exists    — there must already be a committed draft for the
                           file (`store/draft-of`) — otherwise this would be
                           a phantom share of nil content that still writes
                           a false :committed ledger fact.
      3. Share-requires-acl (deny-by-default) — the target :principal must
                           already have a grant recorded in shoko's own
                           grant ledger WITHIN THE SAME TENANT as the file
                           now being shared (not necessarily this exact
                           file — a different file in the SAME tenant is
                           fine, that's legitimate onboarding — but a grant
                           in an UNRELATED tenant must never vouch for them
                           here) — kekkai.acl's deny-by-default mirrored
                           onto shoko's ACL, specific-pair-matching and all:
                           an entirely unregistered principal string, OR one
                           known only in a different tenant, is a hard
                           violation, never a soft signal. (Confirmed bug:
                           this used to check 'known ANYWHERE in the ledger'
                           with zero tenant linkage — a principal known only
                           in tenant A could be granted a tenant-B file with
                           a false zero-violations verdict.)
      4. Tenant-isolation (recheck) — same store-vs-store check, re-run
                           fresh at share-time (not trusted from draft-time
                           approval) — teian's publish-time-recheck lesson
                           applied from the start.
    (any other op) — an unrecognized :op is itself a hard violation
                     (fail-closed: a not-yet-wired op must never silently
                     pass as clean).
  SOFT:
    Confidence floor → escalate.
    `:file/share` is high-stakes → ALWAYS human, independent of phase.

  Content governance (confirmed bug this closes): none of the checks above
  ever compared `(:content proposal)` against anything — an adversarial
  advisor could propose ARBITRARY forged `:content` for `:file/share`
  (unrelated to the file that was actually drafted/vetted) and it sailed
  through with zero violations, since the checks only cover existence/ACL/
  tenant facts, never the content substance itself. `check` now returns
  `:checked-content` — the file's real, freshly-read `store/draft-of`
  `:content` — which the caller MUST deliver instead of `proposal`'s (see
  shoko.operation).

  Note on TOCTOU: this governor's checks are all fresh store reads run
  BEFORE any human-approval interrupt (govern always runs ahead of
  :request-approval in shoko.operation's StateGraph) — that is what makes
  the share-time recheck meaningful. The separate TOCTOU concern (a stored
  draft mutating WHILE a share approval sits in the interrupt) is guarded
  downstream, in shoko.operation/commit-effects!, by using the CHECKPOINTED
  `verdict` channel's `:checked-content` captured at THIS governed moment,
  never a fresh post-approval store re-read (see shoko.operation docstring)."
  (:require [shoko.store :as store]))

(def confidence-floor 0.6)

;; ───────────────────────── invariant checks ─────────────────────────

(defn- missing-file-violations [st file-id]
  (when (nil? (store/file st file-id))
    [{:rule :missing-file :detail (str "未登録file: " file-id)}]))

(defn- missing-activity-violations [st activity-id]
  (when (nil? (store/activity st activity-id))
    [{:rule :missing-activity :detail (str "未登録の活動: " activity-id)}]))

(defn- missing-draft-violations [st file-id]
  (when (nil? (store/draft-of st file-id))
    [{:rule :missing-draft :detail (str "共有対象のdraftが未作成: " file-id)}]))

(defn- actuation-violations [proposal]
  (when (not= :draft (:effect proposal))
    [{:rule :no-actuation
      :detail (str "propose→draft のみ(実共有は人間承認後のshare!のみが行う)。effect="
                   (:effect proposal))}]))

(defn- tenant-violations
  "file's own registered :tenant vs the driving activity's :repo — a pure
  store-vs-store check, independent of anything the proposal claims. Only
  fires when BOTH exist (the missing-file-/missing-activity- checks already
  cover the absent case, so this never double-punishes a hallucinated id)."
  [st file-id activity-id]
  (let [f (store/file st file-id) act (store/activity st activity-id)]
    (when (and f act (not= (:tenant f) (:repo act)))
      [{:rule :tenant-mismatch
        :detail (str "fileのtenant " (:tenant f) " は活動 " activity-id
                     " のrepo " (:repo act) " と不一致")}])))

(defn- unregistered-principal-violations
  "share-requires-acl (deny-by-default, kekkai.acl analog): the target
  principal must already have a grant recorded WITHIN THE SAME TENANT as
  the file now being shared, before a NEW share can be granted to them. An
  entirely unknown principal string, OR one known only via grant(s) in a
  DIFFERENT tenant, is a hard violation, not a soft escalate — a grant in
  tenant A must never vouch for a principal being shared a tenant-B file
  (the confirmed privilege-escalation-shaped bug this scoping closes; see
  store/principal-known?)."
  [st principal tenant]
  (when-not (store/principal-known? st principal tenant)
    [{:rule :unregistered-principal
      :detail (str "tenant " tenant " 内でgrant台帳に事前記録の無いprincipalへの新規共有: " principal)}]))

(defn check
  "Censors an archive-LLM proposal for a shoko op. Returns
   {:ok? :violations :confidence :hard? :escalate? :high-stakes?
    :checked-content}.

   Hard violations force HOLD and cannot be overridden. Granting access
   (`:file/share`) is high-stakes → human sign-off even when clean.

   `:checked-content` is the file's real content for :file/share (the
   store's `draft-of`, fetched fresh here) -- nil for other ops. The caller
   MUST deliver this value, not `proposal`'s :content: none of the checks
   above validate the proposal's content against anything, so an
   adversarial/forged `(:content proposal)` would otherwise sail through
   with zero violations (see governor.cljc's namespace docstring)."
  [request proposal st]
  (let [op         (:op request)
        file-id    (:file request)
        activity-id (:activity request)
        current (when (= :file/share op) (:content (store/draft-of st file-id)))
        hard (vec (case op
                    :file/draft
                    (concat (missing-file-violations st file-id)
                            (missing-activity-violations st activity-id)
                            (actuation-violations proposal)
                            (tenant-violations st file-id activity-id))
                    :file/share
                    (concat (missing-file-violations st file-id)
                            (missing-activity-violations st activity-id)
                            (missing-draft-violations st file-id)
                            (unregistered-principal-violations
                             st (:principal request) (:tenant (store/file st file-id)))
                            (tenant-violations st file-id activity-id))
                    [{:rule :unrecognized-op :detail (str "未対応op: " op)}]))
        conf    (:confidence proposal 0.0)
        low?    (< conf confidence-floor)
        stakes? (= :file/share op)
        hard?   (boolean (seq hard))]
    {:ok?             (and (not hard?) (not low?) (not stakes?))
     :violations      hard
     :confidence      conf
     :hard?           hard?
     :escalate?       (and (not hard?) (or low? stakes?))
     :high-stakes?    stakes?
     :checked-content current}))

(defn hold-fact [request verdict]
  {:t :shoko-hold :op (:op request) :subject (:file request)
   :disposition :hold :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict) :confidence (:confidence verdict)})
