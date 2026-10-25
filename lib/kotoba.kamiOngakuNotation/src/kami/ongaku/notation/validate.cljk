(ns kami.ongaku.notation.validate
  "Cross-note structural validation: does each voice in a measure sum to
  the measure's time-signature capacity? `kami.ongaku.notation/measure`
  only checks the shape of individual notes; this ns is where the
  \"real notation software\" invariant (durations account for the whole
  measure) lives, matching MusicXML's persisted-attributes semantics
  (a measure without its own <time> inherits the last one seen)."
  (:require [kami.ongaku.notation :as notation]
            [kami.ongaku.notation.rational :as r]))

(defn- group-by-voice [notes]
  (group-by #(or (:note/voice %) 1) notes))

(defn validate-measure
  "Validate a single measure against an explicit (already-resolved) time
  signature."
  [time-sig measure]
  (let [capacity (notation/time-signature-capacity time-sig)
        totals (into {}
                     (map (fn [[voice notes]]
                            [voice (reduce r/add r/zero (map notation/duration-value notes))]))
                     (group-by-voice (:measure/notes measure)))
        bad (into {} (filter (fn [[_ total]] (not= total capacity))) totals)]
    (if (empty? bad)
      {:validate/valid? true}
      {:validate/valid? false
       :validate/error :duration-mismatch
       :validate/capacity capacity
       :validate/voice-totals totals})))

(defn validate-part
  "Validate every measure of a part, carrying forward the last-seen time
  signature across measures that don't restate one (per MusicXML
  semantics). Measures before any time signature has appeared are skipped
  (nothing to validate against)."
  [part]
  (loop [measures (:part/measures part) current-ts nil errors []]
    (if-let [m (first measures)]
      (let [ts (or (:measure/time-signature m) current-ts)
            result (when ts (validate-measure ts m))]
        (recur (rest measures)
               ts
               (if (and result (not (:validate/valid? result)))
                 (conj errors (assoc result :measure/number (:measure/number m)))
                 errors)))
      {:validate/valid? (empty? errors) :validate/errors errors})))

(defn validate-score
  [score]
  (let [results (map (fn [p] [(:part/id p) (validate-part p)]) (:score/parts score))
        bad (into {} (remove (fn [[_ r]] (:validate/valid? r))) results)]
    (if (empty? bad)
      {:validate/valid? true}
      {:validate/valid? false :validate/parts bad})))
