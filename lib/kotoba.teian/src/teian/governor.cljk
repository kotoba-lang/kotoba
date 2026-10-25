(ns teian.governor
  "BriefingGovernor — the independent censor that earns deck-LLM the right to
  *propose* a draft. The LLM has no notion of tenant boundaries, redaction
  requirements, or the no-actuation charter, so this MUST be a separate
  system (rules over the store's ground facts) able to *reject* a proposal
  and fall back to HOLD — the teian analog of kekkai's TailnetGovernor /
  tayori's ComplianceGovernor.

  The actor is **propose → draft only**. It never delivers a briefing;
  delivery (`:deck/publish`) is ALWAYS routed to a human (the teian analog of
  robotaxi's MRC / itonami's cert hold / tayori's always-human send/publish).
  Below, HARD invariants force HOLD (a human cannot approve past a proposal
  that claims to have already published, a missing redaction on a sensitive
  cite, or a draft declared for the WRONG tenant); a clean publish still
  routes to a human (high-stakes), at every phase.

  HARD invariants:
    :deck/draft
      1. Subject exists    — the artifact (itonami activity) must already be
                             a registered ground fact (an LLM can hallucinate
                             an id; the governor never trusts confidence
                             alone for this).
      2. No-actuation      — proposal :effect must be :draft (a control-
                             plane record), never :published.
      3. Redaction         — every sensitive-category cite (:financial/
                             :legal/:personnel) must appear in :redactions.
      4. Tenant-isolation  — the proposal's declared :tenant must equal the
                             artifact's own registered :repo (no cross-
                             tenant draft).
    :deck/publish
      1. Subject exists    — the artifact must already be registered.
      2. Draft exists      — a draft must already have been committed (you
                             cannot publish what was never proposed).
      3. Redaction (recheck)      — re-runs the redaction check against the
                             CURRENTLY STORED draft (fetched fresh from the
                             store, not trusted from the incoming proposal) —
                             defense-in-depth against the draft having been
                             revised between draft-time approval and this
                             publish-time delivery.
      4. Tenant-isolation (recheck) — same recheck, for the stored draft's
                             :tenant vs. the artifact's own :repo.
    (any op) — an unrecognized :op is itself a hard violation (fail-closed:
               a not-yet-wired op must never silently pass as clean).
  SOFT:
    Confidence floor → escalate.
    `:deck/publish` is high-stakes → ALWAYS human, independent of phase."
  (:require [teian.policy :as policy]
            [teian.store :as store]))

(def confidence-floor 0.6)

;; ───────────────────────── invariant checks ─────────────────────────

(defn- missing-artifact-violations [st artifact-id]
  (when (nil? (store/artifact st artifact-id))
    [{:rule :no-artifact :detail (str "未登録artifact: " artifact-id)}]))

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
  "Censors a deck-LLM proposal for a teian op. Returns
   {:ok? :violations :confidence :hard? :escalate? :high-stakes? :checked-draft}.

   Hard violations force HOLD and cannot be overridden. Delivering a
   briefing (`:deck/publish`) is high-stakes → human sign-off even when
   clean.

   `:checked-draft` is the exact value this check validated for
   `:deck/publish` (the store's `draft-of`, fetched fresh here) -- nil for
   other ops. The caller MUST deliver this value, not `proposal`: `proposal`
   is precisely what this recheck exists to NOT trust for :deck/publish (see
   below), so building the delivered record from `proposal` instead of
   `:checked-draft` would validate one map and deliver a different one."
  [request proposal st]
  (let [op          (:op request)
        artifact-id (:artifact request)
        current-draft (when (= :deck/publish op) (store/draft-of st artifact-id))
        hard (vec (case op
                    :deck/draft
                    (concat (missing-artifact-violations st artifact-id)
                            (actuation-violations proposal :draft)
                            (redaction-violations proposal)
                            (tenant-violations st artifact-id proposal))
                    :deck/publish
                    ;; Re-fetch the draft straight from the store (ground
                    ;; truth) rather than trusting `proposal`'s forwarded
                    ;; cites/redactions/tenant — the whole point of the
                    ;; recheck is to catch drift the untrusted advisor might
                    ;; not faithfully carry forward.
                    (concat (missing-artifact-violations st artifact-id)
                            (missing-draft-violations st artifact-id)
                            (when current-draft (redaction-violations current-draft))
                            (when current-draft (tenant-violations st artifact-id current-draft)))
                    [{:rule :unrecognized-op :detail (str "未対応op: " op)}]))
        conf    (:confidence proposal 0.0)
        low?    (< conf confidence-floor)
        stakes? (= :deck/publish op)
        hard?   (boolean (seq hard))]
    {:ok?           (and (not hard?) (not low?) (not stakes?))
     :violations    hard
     :confidence    conf
     :hard?         hard?
     :escalate?     (and (not hard?) (or low? stakes?))
     :high-stakes?  stakes?
     :checked-draft current-draft}))

(defn hold-fact [request verdict]
  {:t :teian-hold :op (:op request) :subject (:artifact request)
   :disposition :hold :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict) :confidence (:confidence verdict)})
