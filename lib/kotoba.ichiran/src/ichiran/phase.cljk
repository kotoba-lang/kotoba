(ns ichiran.phase
  "Phase 0→3 staged rollout, gating only the ASSESS ops (`:tally/draft`
  `:tally/publish`). Recording an artifact ground fact (`:artifact/register`)
  is always on — that is ichiran's observe charter (durable ground facts).
  The phase only decides how much autonomy *drafting* has; publishing
  (`:tally/publish`) a tally is never in scope for autonomy — it is a
  separate, always-human charter enforced by the governor's high-stakes
  flag, not by phase.

    0 ingest-only    — record artifacts; emit NO drafts yet (shadow tally
                       book).
    1 assisted       — `:tally/draft` allowed, but always human even to
                       commit just the draft content.
    2 assisted-draft — a clean+confident draft may auto-commit (the 'casual
                       git commit' — it is just proposed workbook content
                       sitting there for review); publish stays human.
    3 supervised     — same autonomy as 2; `:tally/publish` is high-stakes and
                       ALWAYS routes to a human (the 'send it' call is always
                       a human call, regardless of phase).")

(def record-ops #{:artifact/register})
(def assess-ops #{:tally/draft :tally/publish})

(def phases
  {0 {:label "ingest-only"    :assess #{}        :auto #{}}
   1 {:label "assisted"       :assess assess-ops :auto #{}}
   2 {:label "assisted-draft" :assess assess-ops :auto #{:tally/draft}}
   3 {:label "supervised"     :assess assess-ops :auto #{:tally/draft}}})

(def default-phase 3)

(def conservative-phase
  "Fail-closed floor for a missing/unrecognized :phase. `default-phase` (3)
  is the MOST permissive ruleset (auto-commits :tally/draft); a phase value
  that is absent from `context` or not a key of `phases` (garbled config, a
  forgotten context, a not-yet-wired value like 99, …) must never silently
  fall back to that most-permissive ruleset — it must fail closed to the
  LEAST permissive one instead, phase 0 (ingest-only: :assess is empty, so
  every assess op holds with :phase-disabled). See `gate` below and
  ichiran.operation's `ph` binding, both of which use this, never
  `default-phase`, as their fallback."
  0)

(defn record-op? [op] (contains? record-ops op))

(defn gate
  "Adjust an assess op's governor disposition for the rollout phase.
  Returns {:disposition kw :reason kw|nil}. `:tally/publish` is never in
  :auto, so it always escalates; the governor's high-stakes flag already
  forces this too — phase and governor agree by construction. A `phase` not
  present in `phases` (unrecognized/garbled) falls back to
  `conservative-phase`'s ruleset, NOT `default-phase`'s — fail closed, not
  open."
  [phase {:keys [op]} disposition]
  (let [{:keys [assess auto]} (get phases phase (get phases conservative-phase))]
    (cond
      (= :hold disposition)        {:disposition :hold :reason nil}
      (not (contains? assess op))  {:disposition :hold :reason :phase-disabled}
      (and (= :commit disposition)
           (not (contains? auto op))) {:disposition :escalate :reason :phase-approval}
      :else                        {:disposition disposition :reason nil})))

(defn verdict->disposition [v]
  (cond (:hard? v) :hold (:escalate? v) :escalate :else :commit))
