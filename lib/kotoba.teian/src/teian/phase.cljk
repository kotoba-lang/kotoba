(ns teian.phase
  "Phase 0→3 staged rollout, gating only the ASSESS ops (`:deck/draft`
  `:deck/publish`). Recording an artifact ground fact (`:artifact/register`)
  is always on — that is teian's observe charter (durable ground facts). The
  phase only decides how much autonomy *drafting* has; delivering
  (`:deck/publish`) a briefing is never in scope for autonomy — it is a
  separate, always-human charter enforced by the governor's high-stakes
  flag, not by phase.

    0 ingest-only    — record artifacts; emit NO drafts yet (shadow briefing
                       book).
    1 assisted       — `:deck/draft` allowed, but always human even to
                       commit just the draft content.
    2 assisted-draft — a clean+confident draft may auto-commit (the 'casual
                       git commit' — it is just proposed deck/doc/sheet
                       content sitting there for review); publish stays
                       human.
    3 supervised     — same autonomy as 2; `:deck/publish` is high-stakes and
                       ALWAYS routes to a human (the 'send it' call is always
                       a human call, regardless of phase).")

(def record-ops #{:artifact/register})
(def assess-ops #{:deck/draft :deck/publish})

(def phases
  {0 {:label "ingest-only"    :assess #{}        :auto #{}}
   1 {:label "assisted"       :assess assess-ops :auto #{}}
   2 {:label "assisted-draft" :assess assess-ops :auto #{:deck/draft}}
   3 {:label "supervised"     :assess assess-ops :auto #{:deck/draft}}})

(def default-phase
  "The phase used when `context` carries no :phase at all
  (teian.operation: (:phase context phase/default-phase)), AND the
  fallback `gate` itself uses for an unrecognized phase NUMBER
  (`(get phases phase (get phases default-phase))`). This is directly
  reachable by any ordinary caller that simply omits :phase -- not just
  malformed/malicious input -- so it must be the MOST CONSERVATIVE
  phase, never the most permissive. This was 3 (supervised, where
  :deck/draft can auto-commit) until a live check confirmed a caller
  who forgets :phase silently got maximum autonomy instead of the safe
  default -- the same accidental-fail-open shape already found and
  fixed this session in the shared talent.phase template
  (gftd-talent-actor) and its siblings newscaster.phase, wami.phase,
  kyoninka.phase, sng.phase, itonami.phase, tayori.phase,
  goyoukiki.phase, denrei.phase, and shoko.phase, which all inherited
  the same bug. 1 (assisted) matches those fixes. :deck/publish remains
  unaffected either way (never in any phase's :auto set -- delivering a
  briefing always requires a human)."
  1)

(defn record-op? [op] (contains? record-ops op))

(defn gate
  "Adjust an assess op's governor disposition for the rollout phase.
  Returns {:disposition kw :reason kw|nil}. `:deck/publish` is never in
  :auto, so it always escalates; the governor's high-stakes flag already
  forces this too — phase and governor agree by construction."
  [phase {:keys [op]} disposition]
  (let [{:keys [assess auto]} (get phases phase (get phases default-phase))]
    (cond
      (= :hold disposition)        {:disposition :hold :reason nil}
      (not (contains? assess op))  {:disposition :hold :reason :phase-disabled}
      (and (= :commit disposition)
           (not (contains? auto op))) {:disposition :escalate :reason :phase-approval}
      :else                        {:disposition disposition :reason nil})))

(defn verdict->disposition [v]
  (cond (:hard? v) :hold (:escalate? v) :escalate :else :commit))
