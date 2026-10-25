(ns ichiran.governor
  "TallyGovernor — the independent censor that earns tally-LLM the right to
  *propose* a tally workbook draft. The LLM has no notion of tenant
  boundaries, redaction requirements, or the no-actuation charter, so this
  MUST be a separate system (rules over the store's ground facts) able to
  *reject* a proposal and fall back to HOLD — the ichiran analog of teian's
  BriefingGovernor / koyomi's ComplianceGovernor / kekkai's TailnetGovernor.

  The actor is **propose → draft only**. It never publishes a tally;
  publishing (`:tally/publish`) is ALWAYS routed to a human (the ichiran
  analog of teian's always-human `:deck/publish`). Below, HARD invariants
  force HOLD (a human cannot approve past a proposal for a nonexistent
  activity, a missing redaction on a sensitive cite, or a workbook declared
  for the WRONG tenant); a clean publish still routes to a human
  (high-stakes), at every phase.

  HARD invariants:
    :tally/draft
      1. Missing-subject  — the artifact (itonami activity) must already be
                             a registered ground fact. This is an
                             INDEPENDENT, UNCONDITIONAL check — it never
                             looks at the proposal's :content/:tenant to
                             decide whether to fire (an LLM can hallucinate
                             an id; the governor never trusts confidence
                             alone for this). Modeled fresh on koyomi's fixed
                             `missing-activity-violations` (koyomi.governor):
                             that check runs unconditionally, in the SAME
                             top-level `concat` as every other hard check,
                             so a nonexistent subject can never silently
                             no-op its way past tenant-isolation/redaction
                             (the class of gap koyomi's own review closed —
                             see koyomi.governor's docstring on
                             `missing-activity-violations`).
      2. No-actuation      — proposal :effect must be :draft (a control-
                             plane record), never :published.
      3. Redaction         — every sensitive-category cite (:financial/
                             :legal/:personnel) must appear in :redactions.
      4. Tenant-isolation  — the proposal's declared :tenant must equal the
                             artifact's own registered :repo (no cross-
                             tenant tally).
    :tally/publish
      1. Missing-subject   — same unconditional check as :tally/draft (the
                             artifact must already be registered).
      2. Missing-draft     — a draft must already have been committed (you
                             cannot publish a tally that was never
                             proposed).
      3. Redaction (recheck)      — re-runs the redaction check against the
                             CURRENTLY STORED draft (fetched fresh from the
                             store, not trusted from the incoming proposal) —
                             defense-in-depth against the draft having been
                             revised between draft-time approval and this
                             publish-time delivery (ADR-2607062030 amendment:
                             the exact TOCTOU gap teian's `:deck/publish`
                             review found and fixed — ichiran implements the
                             recheck from the start).
      4. Tenant-isolation (recheck) — same recheck, for the stored draft's
                             :tenant vs. the artifact's own :repo.
    (any op) — an unrecognized :op is itself a hard violation (fail-closed:
               a not-yet-wired op must never silently pass as clean).
  SOFT:
    Confidence floor → escalate.
    `:tally/publish` is high-stakes → ALWAYS human, independent of phase."
  (:require [ichiran.policy :as policy]
            [ichiran.store :as store]))

(def confidence-floor 0.6)

;; ───────────────────────── invariant checks ─────────────────────────

(defn- missing-subject-violations
  "Unconditional hard check: the artifact-id the request claims to be about
  must actually be registered. Independent of/prior to every other check
  below — it never inspects the proposal's :content/:tenant, so a
  nonexistent artifact can never silently no-op its way past
  tenant-isolation/redaction and auto-commit a rogue-tenant tally. Modeled
  fresh on koyomi's fixed `missing-activity-violations` (see this ns's
  docstring); applies unconditionally to BOTH :tally/draft and
  :tally/publish."
  [st artifact-id]
  (when (nil? (store/artifact st artifact-id))
    [{:rule :missing-subject :detail (str "未登録artifact: " artifact-id)}]))

(defn- missing-draft-violations [st artifact-id]
  (when (nil? (store/draft-of st artifact-id))
    [{:rule :no-draft :detail (str "未commitのdraft: " artifact-id)}]))

(defn- actuation-violations [proposal expected]
  (when (not= expected (:effect proposal))
    [{:rule :no-actuation
      :detail (str "この段階のeffectは" expected "固定(propose→"
                   (name expected) "のみ)。実際=" (:effect proposal))}]))

(defn- redaction-violations [proposal]
  (let [missing (policy/missing-redactions (:cites proposal) (:redactions proposal))]
    (when (seq missing)
      [{:rule :missing-redaction :detail (str "機微引用にredaction無し: " missing)}])))

(defn- tenant-violations [st artifact-id proposal]
  (let [art (store/artifact st artifact-id)]
    (when (and art (policy/tenant-mismatch? art (:tenant proposal)))
      [{:rule :tenant-mismatch
        :detail (str "proposalのtenant " (:tenant proposal)
                     " はartifactのrepo " (:repo art) " と不一致")}])))

(defn check
  "Censors a tally-LLM proposal for an ichiran op. Returns
   {:ok? :violations :confidence :hard? :escalate? :high-stakes? :checked-draft}.

   Hard violations force HOLD and cannot be overridden. Publishing a tally
   (`:tally/publish`) is high-stakes → human sign-off even when clean.

   `:checked-draft` is the exact value this check validated for
   `:tally/publish` (the store's `draft-of`, fetched fresh here) -- nil for
   other ops. The caller MUST deliver this value, not `proposal`: `proposal`
   is precisely what this recheck exists to NOT trust for :tally/publish (see
   below), so building the delivered record from `proposal` instead of
   `:checked-draft` would validate one map and deliver a different one."
  [request proposal st]
  (let [op          (:op request)
        artifact-id (:artifact request)
        current-draft (when (= :tally/publish op) (store/draft-of st artifact-id))
        hard (vec (case op
                    :tally/draft
                    (concat (missing-subject-violations st artifact-id)
                            (actuation-violations proposal :draft)
                            (redaction-violations proposal)
                            (tenant-violations st artifact-id proposal))
                    :tally/publish
                    ;; Re-fetch the draft straight from the store (ground
                    ;; truth) rather than trusting `proposal`'s forwarded
                    ;; cites/redactions/tenant — the whole point of the
                    ;; recheck is to catch drift the untrusted advisor might
                    ;; not faithfully carry forward.
                    (concat (missing-subject-violations st artifact-id)
                            (missing-draft-violations st artifact-id)
                            (when current-draft (redaction-violations current-draft))
                            (when current-draft (tenant-violations st artifact-id current-draft)))
                    [{:rule :unrecognized-op :detail (str "未対応op: " op)}]))
        conf    (:confidence proposal 0.0)
        low?    (< conf confidence-floor)
        stakes? (= :tally/publish op)
        hard?   (boolean (seq hard))]
    {:ok?           (and (not hard?) (not low?) (not stakes?))
     :violations    hard
     :confidence    conf
     :hard?         hard?
     :escalate?     (and (not hard?) (or low? stakes?))
     :high-stakes?  stakes?
     :checked-draft current-draft}))

(defn hold-fact [request verdict]
  {:t :ichiran-hold :op (:op request) :subject (:artifact request)
   :disposition :hold :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict) :confidence (:confidence verdict)})
