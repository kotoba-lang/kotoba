(ns loop-ka.decide
  "decide — publish, hold, or discard, from the verdict plus the channel's phase.

  The loop never publishes anything itself; the publish key belongs to the
  channel's own actor. What it decides is whether to ASK the channel to publish,
  and that decision is the whole point of measuring the legs.

  Phases mirror the -ka actors' existing rollout vocabulary (dougaka-actor /
  minidrama README): 0 draft = ledger only, 1 unlisted = preview, 2 public =
  needs a standing grant or a per-episode human sign-off."
  (:require [kotoba.lang.text :as str]))

(def phases #{0 1 2})

(defn publishable-grades
  "Which verdicts may reach the public feed at a given phase.

  :degraded is absent from every phase on purpose. A flat-colour card or an
  episode with dead air is not a release, and the way it shipped for two weeks
  was precisely that nothing between 'it encoded' and 'it posted' asked."
  [phase]
  (case (long phase)
    0 #{}
    1 #{:clean :thin}
    2 #{:clean :thin}
    #{}))

(defn decide
  "-> {:action :reason :phase :grade}

  :publish  ask the channel to publish (phase and grade allow it, and the
            phase-2 grant/sign-off is present)
  :hold     produced and recorded, not published — recoverable by an operator
  :discard  nothing worth keeping (an :empty producer report)

  `:approvals` is the set of grants present for this run — `:publish` for a
  per-episode human sign-off, `:auto-publish` for the outer-loop standing grant.
  Phase 2 requires one of them; asking for a public post with neither is a
  :hold, not an error, because the artifact is fine and only the authority is
  missing."
  [{:keys [grade]} {:keys [phase approvals] :or {phase 0 approvals #{}}}]
  (let [phase (long (if (contains? phases (long phase)) phase 0))
        allowed (publishable-grades phase)
        granted? (or (contains? approvals :publish) (contains? approvals :auto-publish))]
    (cond
      (= :empty grade)
      {:action :discard :reason :producer-reported-no-shots :phase phase :grade grade}

      (not (contains? allowed grade))
      {:action :hold
       :reason (if (= :degraded grade) :degraded-never-auto-publishes :phase-does-not-publish)
       :phase phase :grade grade}

      (and (= 2 phase) (not granted?))
      {:action :hold :reason :public-phase-needs-grant :phase phase :grade grade}

      :else
      {:action :publish :reason :allowed :phase phase :grade grade})))

(defn explain [{:keys [action reason phase grade]}]
  (str (str/upper (name action))
       "  phase=" phase " grade=" (name grade) "  (" (name reason) ")"))
