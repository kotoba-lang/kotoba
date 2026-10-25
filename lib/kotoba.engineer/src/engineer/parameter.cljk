(ns engineer.parameter
  "Named numeric parameters with min/max bounds and (future) expressions.
  Restored from kami-eng-core's `parameter` module (deleted PR #82). Pure
  data — an engine is a map of name -> parameter; `set` returns a Result-like
  `[:ok engine]` / `[:error msg]` pair instead of throwing, mirroring the
  original Rust's `Result<(), String>`.")

(defn engine
  "A fresh parameter engine: no parameters defined."
  []
  {:params {}})

(defn define
  "Define a parameter `name` with initial `value`. Returns the updated engine."
  [engine name value]
  (assoc-in engine [:params name]
            {:name name :value value :expression nil :min-value nil :max-value nil}))

(defn set-bounds
  "Set `min`/`max` bounds on an existing parameter (either may be nil)."
  [engine name min max]
  (-> engine
      (assoc-in [:params name :min-value] min)
      (assoc-in [:params name :max-value] max)))

(defn set-value
  "Set `name`'s value, honoring bounds. Returns `[:ok engine]` on success or
  `[:error msg engine]` (engine unchanged) if `name` is undefined or the
  value violates a bound — mirrors the original `Result<(), String>`."
  [engine name value]
  (if-let [p (get-in engine [:params name])]
    (let [{:keys [min-value max-value]} p]
      (cond
        (and min-value (< value min-value))
        [:error (str value " below minimum " min-value) engine]

        (and max-value (> value max-value))
        [:error (str value " above maximum " max-value) engine]

        :else
        [:ok (assoc-in engine [:params name :value] value)]))
    [:error (str "parameter '" name "' not found") engine]))

(defn get-value
  "The current value of parameter `name`, or nil if undefined."
  [engine name]
  (get-in engine [:params name :value]))

(defn all
  "All parameters as a vector of maps."
  [engine]
  (vec (vals (:params engine))))
