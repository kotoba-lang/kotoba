(ns upf.power-state
  "UPF `add_power_state` model — a named operating state for a power domain,
  carrying per-supply-net voltage/off assignments, plus all-off-state
  detection.")

(defn add-power-state
  "Build a power state map for `domain` named `state-name`.
  `supply-assignments` maps supply-net name -> voltage (a number) or `:off`."
  [domain state-name supply-assignments]
  {:domain domain :state-name state-name :supply-assignments supply-assignments})

(defn is-off-state?
  "True when `state` has at least one supply assignment and every one of
  them is `:off` — i.e. the domain is genuinely fully powered down in this
  state, as opposed to a retention or reduced-voltage state where at least
  one supply stays live."
  [state]
  (let [assignments (vals (:supply-assignments state))]
    (boolean (and (seq assignments) (every? #(= % :off) assignments)))))
