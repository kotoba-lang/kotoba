(ns kotobase.engine.qualification
  "Decision gates kept separate from semantic conformance. A candidate cannot
  become a default merely because its happy-path answers are correct."
  (:require [kotobase.engine.profile :as profile]))

(def semantic-gates
  #{:add-query :retract :as-of :history :idempotent-replay
    :typed-value-roundtrip :logical-checkpoint})

(def resilience-gates
  #{:compare-and-set-head :retry-after-timeout :crash-recovery
    :checkpoint-restore :content-verification
    :bounded-root-manifest :confidential-metadata})

(def performance-evidence
  #{:point-read-p50 :point-read-p99 :range-read-p99 :commit-p99
    :write-amplification :read-amplification :object-requests
    :compaction-debt :restore-throughput})

(defn- passed? [observations gates]
  (every? true? (map observations gates)))

(defn evaluate
  "Classify one engine candidate. Performance evidence is required but this
  library deliberately does not prescribe workload-specific numeric limits."
  [{:keys [engine semantic resilience performance] :as candidate}]
  (profile/validate-profile engine)
  (let [semantic-ok? (passed? semantic semantic-gates)
        resilience-ok? (passed? resilience resilience-gates)
        performance-complete? (every? #(number? (get performance %))
                                      performance-evidence)
        status (cond
                 (not semantic-ok?) :blocked
                 (not resilience-ok?) :qualifying
                 (not performance-complete?) :qualifying
                 :else :eligible)]
    (assoc candidate
           :qualification/status status
           :qualification/missing-semantic
           (into #{} (remove #(true? (get semantic %))) semantic-gates)
           :qualification/missing-resilience
           (into #{} (remove #(true? (get resilience %))) resilience-gates)
           :qualification/missing-performance
           (into #{} (remove #(number? (get performance %))) performance-evidence))))
