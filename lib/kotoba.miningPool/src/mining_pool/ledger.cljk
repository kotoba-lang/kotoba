(ns mining-pool.ledger
  "Append-only accepted-share ledger + a pluggable payout scheme, with PPLNS
  (Pay Per Last N Shares) as the reference implementation. This is a plain
  audit log (a vector of entries), not an actor/governor checkpoint — see
  the ADR: mining-pool is a library, not an actor."
  )

(defn append
  "Append an accepted-share entry {:miner :difficulty :timestamp :block?} to
  `ledger` (a vector). Never rewrites or removes prior entries."
  [ledger entry]
  (conj ledger entry))

(defn pplns-payout
  "Pay-Per-Last-N-Shares: take the last `window-n` entries of `ledger` and
  split `total-reward` among miners in proportion to their summed
  :difficulty within that window. Returns {miner reward-share ...} (a map,
  values sum to `total-reward` modulo floating-point rounding)."
  [ledger window-n total-reward]
  (let [window (vec (take-last window-n ledger))
        total-diff (reduce + (map :difficulty window))]
    (if (zero? total-diff)
      {}
      (->> window
           (group-by :miner)
           (map (fn [[miner entries]]
                  [miner (* total-reward (/ (reduce + (map :difficulty entries)) total-diff))]))
           (into {})))))

(defn pay-per-share
  "PPS (pay-per-share): every accepted share in `ledger` (regardless of
  window) is worth `reward-per-difficulty-unit` times its :difficulty,
  independent of whether the pool has actually found a block yet (the
  operator bears variance). Provided as a second reference scheme —
  `pplns-payout` is this library's default."
  [ledger reward-per-difficulty-unit]
  (->> ledger
       (group-by :miner)
       (map (fn [[miner entries]]
              [miner (* reward-per-difficulty-unit (reduce + (map :difficulty entries)))]))
       (into {})))
