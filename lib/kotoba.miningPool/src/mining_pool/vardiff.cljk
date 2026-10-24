(ns mining-pool.vardiff
  "Variable difficulty: adjust a miner's per-share pool target toward a
  target share-submission rate, so a slow CPU miner and a fast ASIC on the
  same pool both submit shares at a similar cadence (too-easy a target
  floods the pool with shares; too-hard and the miner rarely gets credit)."
  )

(defn adjust-difficulty
  "`current` — the miner's current difficulty. `observed-seconds-per-share`
  — the recently observed average time between their accepted shares.
  `opts` — {:target-seconds-per-share (default 4) :min-difficulty (default 1)
  :max-adjust-factor (default 4, clamps any single adjustment to at most 4x
  up or down)}."
  ([current observed-seconds-per-share] (adjust-difficulty current observed-seconds-per-share {}))
  ([current observed-seconds-per-share
    {:keys [target-seconds-per-share min-difficulty max-adjust-factor]
     :or {target-seconds-per-share 4 min-difficulty 1 max-adjust-factor 4}}]
   (let [safe-observed (max observed-seconds-per-share 0.001)
         ratio (/ (double target-seconds-per-share) safe-observed)
         clamped-ratio (max (/ 1.0 max-adjust-factor) (min max-adjust-factor ratio))]
     (max (double min-difficulty) (* current clamped-ratio)))))
