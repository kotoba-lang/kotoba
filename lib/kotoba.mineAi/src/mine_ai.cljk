(ns mine-ai
  "KAMI Mine AI — AI-side heuristics for mining operations: deterministic,
  explainable helpers for extraction risk scoring and next-period
  extraction planning. Restored from the legacy kami-engine/kami-mine-ai
  Rust crate (deleted in kotoba-lang/kami-engine PR #82 'Remove Rust
  workspace from kami-engine') as part of the clj-wgsl migration
  (ADR-2607010930, com-junkawasaki/root).

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. A
  single flat namespace (the original was one flat `lib.rs`). Depends on
  kotoba-lang/mine-pds for `mine`/`mine-status`/`extraction-record` data
  shapes (duck-typed here, not a hard code dependency — matching the
  pattern used for kotoba-lang/brep's sketch-constraint-kind vocabulary)."
  (:require [kotoba.lang.text :as str]))

(def risk-levels #{:low :medium :high})

(defn risk-assessment [score level reasons] {:score score :level level :reasons reasons})

(defn extraction-plan [target-tons current-tons remaining-tons suggested-next-period-tons actions]
  {:target-tons target-tons :current-tons current-tons :remaining-tons remaining-tons
   :suggested-next-period-tons suggested-next-period-tons :actions actions})

(defn assess-extraction-risk
  "Assess extraction risk for `mine` given its `latest` extraction
  record. `mine` is `{:status ...}`, `latest` is `{:quantity-tons ...
  :grade ...}`."
  [mine latest]
  (let [score0 30
        [score reasons]
        (cond-> [score0 []]
          (not= (:status mine) :active)
          (as-> [s r] [(+ s 25) (conj r "mine is not active")])

          (> (:quantity-tons latest) 250000.0)
          (as-> [s r] [(+ s 20) (conj r "high extraction throughput")])

          (< (:quantity-tons latest) 5000.0)
          (as-> [s r] [(+ s 10) (conj r "low throughput can indicate instability")]))
        grade (str/lower (:grade latest))
        [score reasons]
        (cond-> [score reasons]
          (str/includes? grade "low")
          (as-> [s r] [(+ s 20) (conj r "reported low ore grade")])

          (str/includes? grade "high")
          (as-> [s r] [(- s 10) (conj r "reported high ore grade")]))
        score (max 0 (min 100 score))
        level (cond (>= score 70) :high (>= score 40) :medium :else :low)]
    (risk-assessment score level reasons)))

(defn plan-next-extraction
  "Plan the next extraction period given `target-tons`, `current-tons`,
  and `risk` level. Pacing factor scales down for high risk, up for low
  risk."
  [target-tons current-tons risk]
  (let [safe-target (max target-tons 0.0)
        safe-current (max current-tons 0.0)
        remaining (max (- safe-target safe-current) 0.0)
        pacing-factor (case risk :high 0.70 :medium 0.90 :low 1.10)
        suggested-next-period-tons (Math/round (* remaining pacing-factor))
        actions (case risk
                  :high ["Increase geotechnical inspection cadence"
                         "Run short-horizon simulation before blasting"
                         "Cap extraction ramp-up per shift"]
                  :medium ["Monitor production variance weekly"
                           "Tune ore blending plan"]
                  :low ["Maintain current extraction cadence"
                        "Continue monthly QA sampling"])]
    (extraction-plan safe-target safe-current remaining (double suggested-next-period-tons) actions)))
