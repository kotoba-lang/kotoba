(ns soukai.phase
  "Phase 0→3 staged rollout, gating only the ASSESS ops (draft/finalize/send
  decisions). Recording ground facts (a meeting/snapshot/agenda/vote
  appearing via the record-ops below) is always on — that is soukai's
  observe charter (durable ground facts). The phase only decides how much
  autonomy *drafting and finalizing* has; SENDING the convocation notice and
  FINALIZING the minutes are never in scope for autonomy — those are
  separate, always-human charters enforced by the governor's high-stakes
  flag, not by phase (mirrors koyomi's :event/share never being in :auto at
  any phase).

    0 ingest-only    — record meeting/snapshot/agenda/vote ground facts;
                       emit NO drafts yet (shadow AGM record).
    1 assisted       — drafting/finalizing allowed, but always human even to
                       commit just the draft content.
    2 assisted-draft — a clean+confident :convocation/draft,
                       :resolution/finalize, or :minutes/draft may
                       auto-commit (it is just proposed/explanatory content
                       sitting there for review); sending the notice and
                       finalizing the minutes stay human.
    3 supervised     — same autonomy as 2; :convocation/send and
                       :minutes/finalize are high-stakes and ALWAYS route to
                       a human (regardless of phase).")

(def record-ops #{:meeting/register :record-date/snapshot :agenda/register :vote/record})
(def assess-ops #{:convocation/draft :convocation/send :resolution/finalize :minutes/draft :minutes/finalize})

;; :convocation/send and :minutes/finalize are external effects (an actual
;; notice send / a legally-final minutes record) — they are NEVER in :auto
;; at any phase, the permanent human gate this actor's charter requires.
(def ^:private drafting-ops #{:convocation/draft :resolution/finalize :minutes/draft})

(def phases
  {0 {:label "ingest-only"    :assess #{}        :auto #{}}
   1 {:label "assisted"       :assess assess-ops :auto #{}}
   2 {:label "assisted-draft" :assess assess-ops :auto drafting-ops}
   3 {:label "supervised"     :assess assess-ops :auto drafting-ops}})

(def default-phase 3)

(defn record-op? [op] (contains? record-ops op))

(defn gate
  "Adjust an assess op's governor disposition for the rollout phase.
  Returns {:disposition kw :reason kw|nil}. `:convocation/send` and
  `:minutes/finalize` are never in :auto, so they always escalate; the
  governor's high-stakes flag already forces this too — phase and governor
  agree by construction."
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
