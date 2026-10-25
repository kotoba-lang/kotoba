(ns engineer.drc
  "Design Rule Check / Electrical Rule Check base: a rule-violation reporter.
  Restored from kami-eng-core's `drc` module (deleted PR #82). Real rule
  checks (min-clearance, trace-width, etc.) live in domain repos (dft/spice/
  pdk/pnr/bim/rtl) and `report` violations here; this namespace only
  aggregates + counts.")

(def severities #{:error :warning :info})

(defn engine
  "A fresh rule engine: no violations reported."
  []
  {:violations []})

(defn report
  "Report a violation `{:rule-id :severity :message :entity-ids :location}`."
  [engine violation]
  (update engine :violations conj violation))

(defn clear [engine] (assoc engine :violations []))
(defn violations [engine] (:violations engine))

(defn error-count [engine]
  (count (filter #(= :error (:severity %)) (:violations engine))))

(defn warning-count [engine]
  (count (filter #(= :warning (:severity %)) (:violations engine))))

(defn has-errors? [engine] (pos? (error-count engine)))
