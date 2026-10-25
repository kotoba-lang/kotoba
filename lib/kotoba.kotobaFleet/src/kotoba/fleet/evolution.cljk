(ns kotoba.fleet.evolution
  "Portable governance policy for evidence-backed self-improvement.

  This is deliberately a policy library, not an agent: agents may propose a
  candidate, but this namespace never merges code or changes a model registry.
  The caller records its result through `kotoba.fleet.governor`'s single writer."
  (:require [kotoba.lang.text :as str]))

(def required-attestations
  #{:council-charter-attestation
    :murakumo-only-inference-baseline
    :append-only-gate-baseline
    :kotoba-only-substrate-baseline})

(defn valid-evidence-cid?
  "Conservative CID check for evidence anchors accepted by the promotion gate.
  It admits CIDv1 base32 (`bafy…`) and CIDv0 base58 (`Qm…`) only; opaque labels
  and URLs are not reproducible content-addressed evidence."
  [cid]
  (boolean (and (string? cid)
                (or (re-matches #"bafy[a-z2-7]{20,}" cid)
                    (re-matches #"Qm[1-9A-HJ-NP-Za-km-z]{44}" cid)))))

(defn missing-attestations
  "Return required attestations absent from a set or a keyword→truthy map."
  [attestations]
  (let [present? (fn [k]
                   (if (map? attestations) (boolean (get attestations k))
                       (contains? (set attestations) k)))]
    (->> required-attestations (remove present?) sort vec)))

(defn evidence-verdict
  "Evaluate a candidate from measured, reproducible evidence.

  A promotion needs both the configured score gain and enough benchmark steps.
  Passing candidates still require a member CACAO signature: this function only
  grants `:human-signoff`, never autonomous promotion."
  [{:keys [baseline-score candidate-score benchmark-steps min-steps
           min-improvement-pp evidence-cid] :as candidate}]
  (let [gain (when (and (number? baseline-score) (number? candidate-score))
               (* 100.0 (- candidate-score baseline-score)))
        min-steps (or min-steps 250)
        min-gain (or min-improvement-pp 5.0)]
    (cond
      (str/blank? (str evidence-cid))
      {:status :rejected :reason :missing-evidence-cid}

      (not (valid-evidence-cid? evidence-cid))
      {:status :rejected :reason :invalid-evidence-cid}

      (not (number? gain))
      {:status :rejected :reason :missing-measurement}

      (and (< (or benchmark-steps 0) min-steps) (< gain min-gain))
      {:status :rejected :reason :insufficient-evidence
       :improvement-pp gain :benchmark-steps (or benchmark-steps 0)}

      :else
      {:status :human-signoff :reason :measured-improvement
       :improvement-pp gain :benchmark-steps benchmark-steps
       :candidate (select-keys candidate [:candidate-id :evidence-cid])})))

(defn promotion-verdict
  "Combine constitutional attestations with benchmark evidence.
  The result is a pure, append-only-friendly receipt payload."
  [{:keys [attestations] :as candidate}]
  (let [missing (missing-attestations attestations)]
    (if (seq missing)
      {:status :blocked :reason :missing-attestations :missing-attestations missing}
      (evidence-verdict candidate))))
