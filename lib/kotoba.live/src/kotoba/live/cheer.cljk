(ns kotoba.live.cheer
  "Cheer aggregation.

  Each viewer can emit a cheer (`:clap` / `:yell` / `:light-stick` / `:jump`).
  A cheap sliding-window aggregate collapses many incoming events into a
  per-tick loudness the show queries to drive crowd reactions and PostFX
  intensity. Pure data — the aggregate is a plain map, `evict` is a pure
  function of `now`.")

(def kinds #{:clap :yell :light-stick :jump})

(defn new-aggregate
  "A sliding-window aggregate over `window-seconds` (clamped >= 0.05)."
  [window-seconds]
  {:window (max window-seconds 0.05) :samples []})

(defn push
  "Add a cheer sample `{:at seconds :kind kind :weight w}` (`:weight` optional,
  default 1.0)."
  [agg {:keys [at kind weight] :or {weight 1.0}}]
  (update agg :samples conj {:at at :kind kind :weight weight}))

(defn evict
  "Drop samples older than `now - window`. Call once per tick."
  [agg now]
  (let [cutoff (- now (:window agg))]
    (update agg :samples (fn [ss] (vec (remove #(< (:at %) cutoff) ss))))))

(defn weight-of
  "Sum of weights for `kind` in the current window."
  [agg kind]
  (reduce + 0.0 (map :weight (filter #(= kind (:kind %)) (:samples agg)))))

(defn loudness
  "Total cheer \"loudness\" — sum of weights across all kinds. Useful as an
  FX gain."
  [agg]
  (reduce + 0.0 (map :weight (:samples agg))))

(defn cheer-count [agg] (count (:samples agg)))
(defn empty-agg? [agg] (zero? (cheer-count agg)))
