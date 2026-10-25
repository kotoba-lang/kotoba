(ns etzhayyim.ie-flow.react
  "etzhayyim.ie-flow.react — close the loop: the Google co-scientist REACTS to raise an actor's
  reward score, and packages the result as a learning signal for Maxwell. ADR-2606212200 (+ the
  co-scientist ADR-2606201200 / 2606211200, Maxwell ADR-2606061000).

  An actor's 報酬系 (etzhayyim.ie-flow.reward) gives its current reward over its bounded IE-flow.
  This namespace runs ONE co-scientist beat (generate → review → rank → evolve, the charter-clean
  catalog) over that flow, PROJECTS the winning aligned intervention forward, and reports the
  reward SCORE IMPROVEMENT (baseline → projected Δ) + the winning mechanism. That score-react is the
  reinforcement gradient; its meta-review (a Murakumo-narrated lesson, fail-open template) becomes a
  reward-weighted PREFERENCE SIGNAL fed to Maxwell's learning loop. Pure + deterministic."
  (:require [etzhayyim.ie-flow.coscientist :as cosci]
            [etzhayyim.ie-flow.reward :as reward]))

(defn project-state
  "The flow-state the actor would reach if `hyp` lands: a modest proportional net-gain lift +
  an order-index rectification lift (capped at 1.0). Deterministic — the co-scientist's expected
  Δ, applied conservatively so the projected reward is a lower-bound, not a promise."
  [state hyp]
  (let [oi (double (:order-index state 0))
        dn (double (:expected-d-net hyp 0))
        dor (double (:expected-d-order hyp 0))]
    (assoc state
           :net-gain (* (double (:net-gain state 0)) (+ 1.0 (* 0.25 dn)))
           :order-index (min 1.0 (+ oi (* 0.15 dor)))
           :parasitic? false)))

(defn react
  "Run ONE co-scientist score-react over `state`. Returns the baseline reward, the projected reward
  after the top aligned intervention, the Δ (score improvement), the winning mechanism, and the
  meta-review lesson. `opts`: :weights :catalog :descendant :wellbecoming :infer (Murakumo narrator).
  Pure (deterministic unless :infer does I/O — the narration is fail-open)."
  ([state] (react state {}))
  ([state {:keys [weights catalog descendant wellbecoming infer]
           :or {weights reward/default-weights descendant 0.3 wellbecoming 0.3}}]
   (let [ropts {:weights weights :descendant descendant :wellbecoming wellbecoming}
         hyps (cosci/generate state (cond-> {:k 6} catalog (assoc :catalog catalog)))
         survivors (cosci/surviving state hyps)
         ranked (cosci/rank survivors)
         winner (first ranked)
         evolved (cosci/evolve ranked)
         chosen (or evolved winner)
         base (reward/reward-signal state ropts)
         proj (when chosen (reward/reward-signal (project-state state chosen) ropts))
         mr (when (seq ranked) (cosci/meta-review ranked state infer))]
     {:baseline (:reward base)
      :projected (if proj (:reward proj) (:reward base))
      :delta (if proj (- (:reward proj) (:reward base)) 0.0)
      :mechanism (:mechanism chosen)
      :intervention (:intervention chosen)
      :elo (:elo winner)
      :n-survivors (count survivors)
      :lesson (:pattern mr)})))

(defn maxwell-signal
  "Package an actor's score-react as a reward-weighted PREFERENCE SIGNAL for Maxwell's learning loop
  (ADR-2606061000). NOT raw data: a {prompt-context, preferred-mechanism, reward, lesson} record the
  Maxwell trainer can fold as a charter-aligned preference (higher reward ⇒ stronger preference).
  No weights are touched here — this is the SIGNAL, the trainer is a separate G7-gated step. Pure."
  [actor state react-result]
  {:maxwell/actor actor
   :maxwell/kind :preference-signal
   :maxwell/reward (:projected react-result)
   :maxwell/delta (:delta react-result)
   :maxwell/preferred-mechanism (:mechanism react-result)
   :maxwell/lesson (:lesson react-result)
   :maxwell/context {:order-index (:order-index state) :net-gain (:net-gain state)}
   :maxwell/note "reward-weighted preference; gate-conformant (aligned mechanism only); train = G7"})
