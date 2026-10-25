(ns kotoba.reji.core
  "The two operations a cash register actually needs around coins/notes:
   tallying a physical count into a total (till-close reconciliation), and
   working out the smallest possible set of coins/notes for a given amount
   of change. Everything is integer arithmetic in minor units — see
   `kotoba.reji.currency` for why."
  (:require [kotoba.reji.currency :as currency]))

(defn tally
  "counts: a map of {denom-value minor-unit-count} (e.g. {500 3, 100 12} for
   3x ¥500 coins and 12x ¥100 coins). Returns the per-denomination breakdown
   plus the grand total, all in minor units. Throws if a key isn't one of
   `code`'s denominations."
  [code counts]
  (let [by-value (into {} (map (juxt :reji.denom/value identity))
                        (currency/denominations code))
        lines (for [[value n] counts
                    :when (pos? n)]
                (let [d (or (get by-value value)
                            (throw (ex-info (str "not a " code " denomination: " value)
                                             {:reji/error :unknown-denomination
                                              :code code :value value})))]
                  {:reji.tally.line/value value
                   :reji.tally.line/kind (:reji.denom/kind d)
                   :reji.tally.line/label (:reji.denom/label d)
                   :reji.tally.line/count n
                   :reji.tally.line/subtotal (* value n)}))
        lines (vec (sort-by :reji.tally.line/value > lines))]
    {:reji.tally/currency code
     :reji.tally/lines lines
     :reji.tally/total (reduce + 0 (map :reji.tally.line/subtotal lines))}))

(defn till-report
  "A `tally` plus the difference against `expected-total` (e.g. the register
   tape's expected cash sales) — :balanced / :over / :short."
  [code counts expected-total]
  (let [t (tally code counts)
        diff (- (:reji.tally/total t) expected-total)]
    (assoc t
           :reji.till/expected expected-total
           :reji.till/difference diff
           :reji.till/status (cond (zero? diff) :balanced (pos? diff) :over :else :short))))

(defn- unbounded-change-dp
  "dp[x] = {:pieces n :via denom-value} for the minimal-piece way to make x
   from `values` (unlimited supply of each), for every x in 0..amount that's
   reachable; unreachable x's are absent. Standard single-pass unbounded
   coin-change DP — dp is a plain vector used as a function of index, so this
   reads dp[x - v] computed earlier in the *same* pass, which is what allows
   a denomination to be reused any number of times."
  [values amount]
  (reduce
   (fn [dp x]
     (let [best (reduce
                 (fn [best v]
                   (let [px (- x v)]
                     (if-let [from (and (>= px 0) (dp px))]
                       (let [pieces (inc (:pieces from))]
                         (if (or (nil? best) (< pieces (:pieces best)))
                           {:pieces pieces :via v}
                           best))
                       best)))
                 nil values)]
       (cond-> dp best (assoc x best))))
   (assoc (vec (repeat (inc amount) nil)) 0 {:pieces 0 :via nil})
   (range 1 (inc amount))))

(defn- largest-reachable [dp amount]
  (loop [x amount]
    (cond (zero? x) 0
          (dp x) x
          :else (recur (dec x)))))

(defn make-change
  "The fewest coins/notes that make up `amount` minor units of `code`,
   assuming an unlimited supply of every denomination (the ordinary
   \"how much change is owed\" question). When `amount` isn't exactly
   representable (e.g. 3 centavos when the smallest MXN coin is 5), returns
   the largest representable amount below it plus the leftover in
   `:reji.change/remainder` instead of throwing — a real register still has
   to hand back *something* close."
  [code amount]
  (when (neg? amount)
    (throw (ex-info "amount must be >= 0" {:reji/error :negative-amount :amount amount})))
  (let [values (mapv :reji.denom/value (currency/denominations code))
        dp (unbounded-change-dp values amount)
        given (largest-reachable dp amount)
        pieces (loop [x given acc []]
                 (if (zero? x)
                   acc
                   (let [{:keys [via]} (dp x)]
                     (recur (- x via) (conj acc via)))))
        by-value (into {} (map (juxt :reji.denom/value identity))
                        (currency/denominations code))
        breakdown (->> (frequencies pieces)
                       (map (fn [[value n]]
                              (let [d (get by-value value)]
                                {:reji.change.line/value value
                                 :reji.change.line/kind (:reji.denom/kind d)
                                 :reji.change.line/label (:reji.denom/label d)
                                 :reji.change.line/count n})))
                       (sort-by :reji.change.line/value >)
                       vec)]
    {:reji.change/currency code
     :reji.change/requested amount
     :reji.change/given given
     :reji.change/remainder (- amount given)
     :reji.change/breakdown breakdown}))
