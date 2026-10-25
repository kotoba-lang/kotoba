(ns kakeibo.rollup
  "Period and category rollups, and budget comparison.

  One rule governs everything here: **a category with no observed data is
  `:unobserved`, never `0`.** A spending report that renders \"no statement
  ingested yet\" identically to \"spent nothing\" is worse than no report,
  because it reads as good news. This is the same discipline
  `kotoba-lang/tamaki`'s KPI control plane applies to revenue targets and
  `kotoba-lang/macos-inventory` applies to probes.")

(defn period
  "`\"2026-07-01\"` -> `\"2026-07\"`. Monthly is the only granularity the
  statement window reliably supports."
  [iso-date]
  (when (and (string? iso-date) (>= (count iso-date) 7))
    (subs iso-date 0 7)))

(defn by-period
  "`{period {category net-minor}}` — net movement, outflow negative."
  [txs]
  (reduce (fn [acc {:tx/keys [date amount category]}]
            (let [p (period date)
                  c (or category :uncategorized)]
              (if (or (nil? p) (nil? amount))
                acc
                (update-in acc [p c] (fnil + 0) amount))))
          {}
          txs))

(defn by-category
  "`{category net-minor}` across every transaction given."
  [txs]
  (reduce (fn [acc {:tx/keys [amount category]}]
            (if (nil? amount)
              acc
              (update acc (or category :uncategorized) (fnil + 0) amount)))
          {}
          txs))

(defn totals
  "Net, outflow and inflow magnitudes for a transaction sequence."
  [txs]
  (let [amounts (keep :tx/amount txs)]
    {:rollup/net     (reduce + 0 amounts)
     :rollup/outflow (reduce + 0 (map - (filter neg? amounts)))
     :rollup/inflow  (reduce + 0 (filter pos? amounts))
     :rollup/count   (count amounts)}))

(defn observed-periods
  "Sorted periods that actually have transactions."
  [txs]
  (->> txs (keep (comp period :tx/date)) distinct sort vec))

(defn coverage
  "What the rollup is entitled to claim.

  Returns the observed periods, the accounts seen, and the count of
  transactions carrying no usable date — the last one matters because a
  dateless transaction is absent from every period total while still being
  real money."
  [txs]
  {:coverage/periods  (observed-periods txs)
   :coverage/accounts (->> txs (keep :tx/account) distinct sort vec)
   :coverage/dateless (count (remove (comp period :tx/date) txs))
   :coverage/total    (count txs)})

(defn budget-report
  "Compare one period's outflow against a budget.

  `budget` is `{category magnitude-in-minor-units}` as a positive number.
  For each budgeted category the report gives `:budget/actual` (outflow
  magnitude), `:budget/remaining`, and `:budget/status` — one of
  `:under`, `:over`, or **`:unobserved`** when that category has no
  transaction in the period at all. Categories that were spent but not
  budgeted come back under `:budget/unbudgeted` rather than being folded in
  silently."
  [budget txs period-key]
  (let [in-period (filter #(= period-key (period (:tx/date %))) txs)
        actual    (by-category in-period)
        spent     (fn [c] (when-let [v (get actual c)]
                            (if (neg? v) (- v) 0)))
        lines     (into {}
                        (map (fn [[c limit]]
                               (let [a (spent c)]
                                 [c (if (nil? a)
                                      {:budget/limit limit
                                       :budget/actual nil
                                       :budget/remaining nil
                                       :budget/status :unobserved}
                                      {:budget/limit limit
                                       :budget/actual a
                                       :budget/remaining (- limit a)
                                       :budget/status (if (> a limit) :over :under)})]))
                             budget))]
    {:budget/period period-key
     :budget/observed? (boolean (seq in-period))
     :budget/lines lines
     :budget/unbudgeted (->> (keys actual)
                             (remove #(contains? budget %))
                             sort vec)
     :budget/totals (totals in-period)}))

(defn report
  "One assembled spending report: totals, per-period, per-category, coverage."
  [txs]
  {:report/totals     (totals txs)
   :report/by-period  (by-period txs)
   :report/by-category (by-category txs)
   :report/coverage   (coverage txs)})
