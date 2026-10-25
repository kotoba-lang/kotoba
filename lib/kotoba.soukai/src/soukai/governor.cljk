(ns soukai.governor
  "ResolutionGovernor — the independent censor that earns secretary-LLM the
  right to *propose* a draft. The LLM has no notion of the notice-period
  minimums, the electronic-provision requirement, the record-date-scoped
  tenant boundary, or the no-actuation charter, so this MUST be a separate
  system (rules over the store's ground facts + soukai.tally's deterministic
  math) able to *reject* a proposal and fall back to HOLD — the soukai
  analog of koyomi's ComplianceGovernor / kekkai's TailnetGovernor / tayori's
  ComplianceGovernor.

  The actor is **propose → draft only**. It never sends the convocation
  notice or finalizes the minutes itself; both ALWAYS route to a human (the
  soukai analog of koyomi's always-human `:event/share`). Below, HARD
  invariants force HOLD (a human cannot approve past a proposal for a
  nonexistent meeting/agenda, a claimed-already-actuated proposal, a notice
  sent short of the statutory minimum, a missing electronic-provision URL, a
  resolution outcome that doesn't match the deterministic tally, incomplete
  legal minutes, or a tenant mismatch); a clean send/finalize still routes
  to a human (high-stakes, unconditionally).

  HARD invariants (ADR-2607121700 §4):
    1. subject-exists       — the meeting (or, for :resolution/finalize, the
                              agenda's meeting) the request concerns must
                              actually be registered. Unconditional —
                              independent of/prior to every other check, so
                              a nonexistent meeting/agenda can never
                              silently no-op its way past tenant-isolation
                              (mirrors koyomi's missing-activity-violations).
    2. no-actuation         — proposal :effect must be :draft, ALWAYS, for
                              EVERY assess op (not just the drafting ones —
                              soukai diverges from koyomi here: a
                              :convocation/send or :minutes/finalize
                              proposal that claims :effect other than
                              :draft is itself a hard violation, since
                              actually sending/finalizing is soukai.
                              operation's commit-time effect, never
                              something the advisor may claim to have
                              already done).
    3. notice-period-gate   — :convocation/send ONLY. The committed
                              convocation draft's :notice-date must be at
                              least the meeting's :notice-scenario's
                              required lead time (soukai.facts/notice-
                              period-catalog, 会社法第299条1項) before its
                              :meeting-date.
    4. electronic-provision-gate — :convocation/send ONLY. If the meeting's
                              :electronic-provision? is true, the committed
                              convocation draft's content must carry a
                              non-blank :electronic-provision-url (会社法
                              第325条の3).
    5. resolution-mismatch  — :resolution/finalize ONLY. The proposal's
                              :outcome is recomputed INDEPENDENTLY here via
                              soukai.tally/outcome-of (never trusting the
                              proposal's own :content :tally-summary) — a
                              mismatch is hard and un-overridable. This is
                              the single load-bearing invariant of the whole
                              actor: secretary-LLM never rewrites the tally.
    6. minutes-legal-fields-gate — :minutes/finalize ONLY. Every key in
                              soukai.facts/minutes-required-fields's
                              :fields set must be present and non-blank in
                              the committed minutes draft's content
                              (会社法施行規則第72条).
    7. tenant-isolation     — every assess op. The relevant content's
                              :tenant must equal the meeting's registered
                              :tenant.
    (any other op) — an unrecognized :op is itself a hard violation
                     (fail-closed: a not-yet-wired op must never silently
                     pass as clean).
  SOFT:
    Confidence floor → escalate.
    Close-margin heuristic (:resolution/finalize, :ordinary-resolution /
      :special-resolution only) — if the deterministic for/(for+against)
      ratio is within `margin-band` of the exact approval threshold,
      escalate even though the tally is mathematically unambiguous. This is
      a PRUDENCE heuristic (mirrors koyomi's double-booking soft-escalate
      framing: 'a human should still take a look'), never a hard violation
      — the math is never in question, only whether a human should
      double-check a close real-world call before it's recorded as final.
    AOI-clamped heuristic (`aoi-clamped?`, :convocation/send /
      :resolution/finalize only) — if the meeting's/agenda's registered
      定款 override was outside soukai.facts's legal bounds and got
      silently clamped back to the statutory figure at read-time, escalate
      so a human learns their registered AOI override didn't take effect
      — never a hard violation (the ingest-time registration already
      happened and can't be un-recorded; the CLAMPED, statutory figure is
      still what the HARD gates enforce either way, see
      notice-period-gate/resolution-mismatch above).
    `:convocation/send` and `:minutes/finalize` are ALWAYS high-stakes →
      human, at every phase (koyomi's `:event/share` charter, applied to
      both of soukai's two actuation ops)."
  (:require [kotoba.lang.text :as str]
            [soukai.facts :as facts]
            [soukai.store :as store]
            [soukai.tally :as tally]))

(def confidence-floor 0.6)
(def margin-band 0.05)

;; ───────────────────────── subject / meeting resolution ─────────────────────────

(defn- subject-of [{:keys [op meeting agenda]}]
  (if (= op :resolution/finalize) agenda meeting))

(defn- meeting-id-of [st {:keys [op meeting agenda]}]
  (if (= op :resolution/finalize)
    (:meeting-id (store/agenda st agenda))
    meeting))

;; ───────────────────────── invariant checks ─────────────────────────

(defn- missing-meeting-violations
  "Unconditional hard check: the meeting the request concerns must actually
  be registered. For :resolution/finalize this means the agenda ITSELF
  must exist first (otherwise there is no meeting to resolve to at all).
  Independent of/prior to every other check below — a nonexistent
  meeting/agenda must never silently no-op its way past tenant-isolation,
  the same gap koyomi's missing-activity-violations closes for :event/*."
  [st op meeting-id agenda-id]
  (if (= op :resolution/finalize)
    (let [ag (store/agenda st agenda-id)]
      (cond
        (nil? ag) [{:rule :missing-meeting :detail (str "未登録の議案: " agenda-id)}]
        (nil? (store/meeting st (:meeting-id ag)))
        [{:rule :missing-meeting :detail (str "議案 " agenda-id " の対象総会が未登録: " (:meeting-id ag))}]
        :else nil))
    (when (nil? (store/meeting st meeting-id))
      [{:rule :missing-meeting :detail (str "未登録の総会: " meeting-id)}])))

(defn- actuation-violations
  "Applies to EVERY assess op (soukai diverges from koyomi's :event/share
  exemption here — see namespace docstring #2)."
  [proposal]
  (when (not= :draft (:effect proposal))
    [{:rule :no-actuation
      :detail (str "propose→draft のみ(実際の発送/確定は人間承認後の commit のみが行う)。effect="
                   (:effect proposal))}]))

(defn- tenant-violations [st meeting-id content]
  (when content
    (let [expected (:tenant (store/meeting st meeting-id))
          actual   (:tenant content)]
      (when (and expected (not= expected actual))
        [{:rule :tenant-mismatch
          :detail (str "content tenant " actual " は総会 " meeting-id " の tenant " expected " と不一致")}]))))

(defn- notice-period-violations
  "会社法第299条1項: the committed convocation draft's :notice-date must be
  at least the meeting's :notice-scenario's required lead time before
  :meeting-date — that lead time is `soukai.facts/effective-notice-
  period-days`'s :days (the meeting's statutory default, LENGTHENED or
  legally-SHORTENED by its own :aoi/notice-period-days if present, or the
  statutory default un-clamped-back if the meeting's shortening attempt
  was illegal — never the meeting's raw AOI figure taken at face value)."
  [st meeting-id content]
  (when-let [m (store/meeting st meeting-id)]
    (let [required    (:days (facts/effective-notice-period-days m))
          notice-date (:notice-date content)]
      (cond
        (nil? required)
        [{:rule :notice-period-gate :detail (str "未知の notice-scenario: " (:notice-scenario m))}]
        (str/blank? (str notice-date))
        [{:rule :notice-period-gate :detail "招集通知の発送日(:notice-date)が未提案"}]
        :else
        (let [gap (facts/days-between notice-date (:meeting-date m))]
          (when (< gap required)
            [{:rule :notice-period-gate
              :detail (str "招集通知は総会日の" required "日前までに必要(会社法第299条第1項) — 実際は"
                          gap "日前")}]))))))

(defn- electronic-provision-violations
  "会社法第325条の3: if the meeting requires electronic provision, the
  committed convocation draft must carry a non-blank access URL."
  [st meeting-id content]
  (when-let [m (store/meeting st meeting-id)]
    (when (:electronic-provision? m)
      (when (str/blank? (str (:electronic-provision-url content)))
        [{:rule :electronic-provision-gate
          :detail "電子提供措置のURL/アクセス情報が招集通知に欠落(会社法第325条の3)"}]))))

(defn- resolution-mismatch-violations
  "The single load-bearing invariant: recompute soukai.tally/outcome-of
  INDEPENDENTLY here (never trust the proposal's own :content
  :tally-summary) and hard-violate if the proposal's claimed :outcome
  disagrees."
  [st agenda-id proposal]
  (when-let [ag (store/agenda st agenda-id)]
    (let [snapshot (store/snapshot-of st (:meeting-id ag))
          votes    (store/votes-of st agenda-id)
          computed (tally/outcome-of ag snapshot votes)]
      (when (not= (:outcome computed) (:outcome proposal))
        [{:rule :resolution-mismatch
          :detail (str "proposal :outcome=" (:outcome proposal)
                      " は決定論的計算=" (:outcome computed) " と不一致")}]))))

(defn- minutes-legal-fields-violations
  "会社法施行規則第72条: every required field must be present and non-blank
  in the committed minutes draft's content."
  [content]
  (vec (keep (fn [k]
               (let [v (get content k)]
                 (when (or (nil? v)
                           (and (string? v) (str/blank? v))
                           (and (coll? v) (empty? v)))
                   {:rule :minutes-legal-fields-gate
                    :detail (str "議事録の必須記載事項が欠落: " (name k))})))
             (:fields facts/minutes-required-fields))))

;; ───────────────────────── SOFT: close-margin prudence heuristic ─────────────────────────

(defn- close-margin?
  "Only meaningful for :ordinary-resolution/:special-resolution's simple
  for/(for+against) ratio against a single threshold fraction —
  :special-resolution-2's headcount+rights math (soukai.tally docstring #3)
  isn't a single ratio-vs-threshold shape this heuristic covers, so it is
  deliberately out of scope for this SOFT check in R0."
  [st agenda-id]
  (when-let [ag (store/agenda st agenda-id)]
    (when (#{:ordinary-resolution :special-resolution} (:resolution-type ag))
      (let [snapshot (store/snapshot-of st (:meeting-id ag))
            votes    (store/votes-of st agenda-id)
            {:keys [outcome for against]} (tally/outcome-of ag snapshot votes)]
        (when (and (not= :no-quorum outcome) (pos? (+ for against)))
          (let [{:keys [threshold-num threshold-den]} (get facts/resolution-requirements (:resolution-type ag))
                ratio     (/ (double for) (+ for against))
                threshold (/ (double threshold-num) threshold-den)
                d         (- ratio threshold)]
            (<= (if (neg? d) (- d) d) margin-band)))))))

(defn- aoi-clamped?
  "SOFT escalate signal (never HARD — read namespace docstring's SOFT
  section): the meeting's (:convocation/send) or agenda's
  (:resolution/finalize) registered 定款 override was outside the legal
  bounds `soukai.facts/effective-notice-period-days` /
  `effective-resolution-requirements` enforces, and was silently
  corrected back to the statutory figure. The ingest-time registration of
  that meeting/agenda already happened and can't be un-recorded, so this
  can only surface the mismatch for human review here — 'your registered
  AOI override was illegal and got silently corrected to the statutory
  figure' — it never blocks the op the way a HARD violation would."
  [st op meeting-id agenda-id]
  (boolean
   (case op
     :convocation/send
     (when-let [m (store/meeting st meeting-id)]
       (:clamped? (facts/effective-notice-period-days m)))
     :resolution/finalize
     (when-let [ag (store/agenda st agenda-id)]
       (:clamped? (facts/effective-resolution-requirements ag)))
     nil)))

;; ───────────────────────── content resolution per op ─────────────────────────

(defn- content-of [request proposal st meeting-id]
  (case (:op request)
    (:convocation/draft :resolution/finalize :minutes/draft) (:content proposal)
    :convocation/send (:content (store/draft-of st (store/convocation-key meeting-id)))
    :minutes/finalize (:content (store/draft-of st (store/minutes-key meeting-id)))
    ;; an unrecognized op has no defined content shape at all — fail-closed
    ;; below via the :unrecognized-op hard violation, which never inspects
    ;; `content`, so nil is a safe, unused placeholder here.
    nil))

;; ───────────────────────── check dispatch ─────────────────────────

(defn check
  "Censors a secretary-LLM proposal for a soukai op. Returns
   {:ok? :violations :confidence :hard? :escalate? :high-stakes?
    :close-margin? :aoi-clamped?}.

   Hard violations force HOLD and cannot be overridden. Sending the
   convocation notice / finalizing the minutes is high-stakes → human
   sign-off even when clean; so is a close-margin resolution outcome; so
   is a :convocation/send or :resolution/finalize whose meeting/agenda
   carries an AOI (定款) override that got legally clamped back to the
   statutory figure (`aoi-clamped?` above) — never a hard violation (the
   ingest-time registration already happened and can't be un-recorded),
   but a human should know their registered override didn't take effect."
  [request proposal st]
  (let [op         (:op request)
        meeting-id (meeting-id-of st request)
        content    (content-of request proposal st meeting-id)
        hard (vec
              (case op
                :convocation/draft
                (concat (missing-meeting-violations st op meeting-id nil)
                        (actuation-violations proposal)
                        (tenant-violations st meeting-id content))
                :convocation/send
                (concat (missing-meeting-violations st op meeting-id nil)
                        (actuation-violations proposal)
                        (tenant-violations st meeting-id content)
                        (notice-period-violations st meeting-id content)
                        (electronic-provision-violations st meeting-id content))
                :resolution/finalize
                (concat (missing-meeting-violations st op nil (:agenda request))
                        (actuation-violations proposal)
                        (tenant-violations st meeting-id content)
                        (resolution-mismatch-violations st (:agenda request) proposal))
                :minutes/draft
                (concat (missing-meeting-violations st op meeting-id nil)
                        (actuation-violations proposal)
                        (tenant-violations st meeting-id content))
                :minutes/finalize
                (concat (missing-meeting-violations st op meeting-id nil)
                        (actuation-violations proposal)
                        (tenant-violations st meeting-id content)
                        (minutes-legal-fields-violations content))
                [{:rule :unrecognized-op :detail (str "未対応 op: " op)}]))
        conf    (:confidence proposal 0.0)
        low?    (< conf confidence-floor)
        margin? (boolean (and (= :resolution/finalize op) (close-margin? st (:agenda request))))
        aoi-clamp? (aoi-clamped? st op meeting-id (:agenda request))
        stakes? (or (contains? #{:convocation/send :minutes/finalize} op) margin? aoi-clamp?)
        hard?   (boolean (seq hard))]
    {:ok?           (and (not hard?) (not low?) (not stakes?))
     :violations    hard
     :confidence    conf
     :hard?         hard?
     :escalate?     (and (not hard?) (or low? stakes?))
     :high-stakes?  stakes?
     :close-margin? margin?
     :aoi-clamped?  aoi-clamp?}))

(defn hold-fact [request verdict]
  {:t :soukai-hold :op (:op request) :subject (subject-of request)
   :disposition :hold :basis (mapv :rule (:violations verdict))
   :violations (:violations verdict) :confidence (:confidence verdict)})
