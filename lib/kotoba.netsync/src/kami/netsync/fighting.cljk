(ns kami.netsync.fighting
  "Deterministic 2-player combat netcode: rollback (GGPO) and delay-based.

   Local simultaneous 2P is not buildable in the guest DSL (one input stream).
   Network 2P is: each peer has its own stream and both run the same `step`.
   Missing remote input is predicted as last-seen; a correction rolls back and
   resimulates. Delay mode waits until every real input for the next tick is
   present, so both sides see the same inputs without rewind.

   Confirm is emitted only for ticks past the rollback window — a tick that
   can still be revised is not confirmed (the kotoba-rt finality rule).

   Transport is out of scope. T1 / T2 / T3 all ingest the same per-tick input.
   No clock, no sockets. `step` is `(fn [state inputs] state)` where `inputs`
   is `{player input}`.")

(def default-policy
  "Forkable. `:mode` is `:rollback` or `:delay`. `:input-delay` is unused by
   rollback (prediction covers RTT) and unused by delay as a wait-count —
   delay simply refuses to simulate a tick until every player has a real
   input for it. `:rollback-window` is how far a late input may rewrite.
   `:save-cap` bounds the save ring."
  {:mode :rollback
   :players #{:p1 :p2}
   :input-delay 0
   :rollback-window 8
   :save-cap 16
   :empty-input {:dx 0 :attack false}})

(defn- canon
  [x]
  (cond
    (map? x) (into (sorted-map) (map (fn [[k v]] [k (canon v)]) x))
    (vector? x) (mapv canon x)
    (set? x) (into (sorted-set) (map canon x))
    :else x))

(defn state-hash
  "Deterministic integer over a nested map/vector state. Used as a desync
   detector, not a reconciler — mismatch means resync from a snapshot."
  [state]
  (let [s (pr-str (canon state))]
    (reduce (fn [h i]
              (let [c #?(:clj (int (.charAt s i)) :cljs (.charCodeAt s i))]
                (mod (+ (* 31 h) c) 4294967296)))
            5381
            (range (count s)))))

(defn engine-new
  ([initial-state] (engine-new default-policy initial-state))
  ([policy initial-state]
   {:policy policy
    :tick 0
    :state initial-state
    :saves {0 initial-state}
    :inputs {}
    :simulated-inputs {}
    :last-input {}
    :confirmed-through 0
    :pending-confirms []
    :rewind-from nil
    :rollbacks 0
    :stalled? false
    :rejected []}))

(defn- players [engine]
  (get-in engine [:policy :players] #{:p1 :p2}))

(defn- empty-input [engine]
  (get-in engine [:policy :empty-input] {:dx 0 :attack false}))

(defn- rollback-window [engine]
  (get-in engine [:policy :rollback-window] 8))

(defn ingest
  "Record `input` for `player` at simulation `tick`. A late input that disagrees
   with what was actually simulated marks `:rewind-from`. Inputs at or before
   `:confirmed-through` are rejected (`:too-late`) — delay mode has no rewind
   either, so a late input after simulate is the same refuse."
  [engine player tick input]
  (cond
    (not (contains? (players engine) player))
    (update engine :rejected conj {:reason :unknown-player :player player :tick tick})

    (not (integer? tick))
    (update engine :rejected conj {:reason :bad-tick :player player :tick tick})

    (<= tick (:confirmed-through engine))
    (update engine :rejected conj {:reason :too-late :player player :tick tick
                                   :confirmed-through (:confirmed-through engine)})

    :else
    (let [simulated (get-in engine [:simulated-inputs tick player])
          dirty? (and (some? simulated)
                      (not= simulated input)
                      (<= tick (:tick engine)))
          engine (-> engine
                     (assoc-in [:inputs tick player] input)
                     (assoc-in [:last-input player] input))]
      (cond-> engine
        dirty? (update :rewind-from #(if % (min % tick) tick))))))

(defn- trim-saves [engine]
  (let [cap (get-in engine [:policy :save-cap] 16)
        saves (:saves engine)]
    (if (<= (count saves) cap)
      engine
      (let [keep (->> saves keys sort (take-last cap) set)]
        (assoc engine :saves (into {} (filter (fn [[t _]] (contains? keep t)) saves)))))))

(defn- emit-confirms [engine]
  (let [window (rollback-window engine)
        target (max (:confirmed-through engine)
                    (- (:tick engine) window))
        from (inc (:confirmed-through engine))
        new (when (and (= :rollback (get-in engine [:policy :mode] :rollback))
                       (>= target from))
              (mapv (fn [t]
                      {:confirm/tick t
                       :confirm/state-hash (state-hash (get-in engine [:saves t]))})
                    (range from (inc target))))]
    (if (seq new)
      (-> engine
          (assoc :confirmed-through target)
          (update :pending-confirms into new))
      engine)))

(defn drain-confirms
  "Take the confirms that became final since last drain. Delay mode confirms
   every simulated tick immediately (no rewrite window)."
  [engine]
  [(:pending-confirms engine) (assoc engine :pending-confirms [])])

(defn- inputs-for
  "The input map `step` will see at `tick`. Rollback fills holes with last-seen
   (or empty). Delay returns nil when any player is missing — the caller stalls."
  [engine tick]
  (let [mode (get-in engine [:policy :mode] :rollback)
        ps (players engine)]
    (if (= mode :delay)
      (let [got (into {} (keep (fn [p]
                                 (when-let [in (get-in engine [:inputs tick p])]
                                   [p in]))
                               ps))]
        (when (= (count got) (count ps)) got))
      (into {} (map (fn [p]
                      [p (or (get-in engine [:inputs tick p])
                             (get-in engine [:last-input p])
                             (empty-input engine))])
                    ps)))))

(defn- restore [engine from-tick]
  (let [state (get-in engine [:saves (dec from-tick)])]
    (if (nil? state)
      (update engine :rejected conj {:reason :no-save :tick from-tick})
      (-> engine
          (assoc :state state
                 :tick (dec from-tick)
                 :rewind-from nil)
          (update :simulated-inputs (fn [m]
                                      (into {} (filter (fn [[t _]] (< t from-tick)) m))))
          (update :saves (fn [m]
                           (into {} (filter (fn [[t _]] (< t from-tick)) m))))))))

(defn- simulate-one [engine step]
  (let [next-tick (inc (:tick engine))
        inputs (inputs-for engine next-tick)]
    (if (nil? inputs)
      (assoc engine :stalled? true)
      (let [state' (step (:state engine) inputs)]
        (-> engine
            (assoc :stalled? false
                   :tick next-tick
                   :state state')
            (assoc-in [:saves next-tick] state')
            (assoc-in [:simulated-inputs next-tick] inputs)
            trim-saves)))))

(defn- resimulate [engine step up-to]
  (loop [e engine]
    (if (>= (:tick e) up-to)
      e
      (let [e' (simulate-one e step)]
        (if (:stalled? e')
          e'
          (recur e'))))))

(defn advance
  "Simulate the next tick. `step` is pure `(fn [state inputs] state)`.

   Rollback: if a late input dirtied a past tick, restore the save before that
   tick and resimulate to the previous present, then step once more.
   Delay: if any real input is missing, return `:stalled? true` and do not
   advance. Confirms: rollback emits them only past the window; delay emits
   them for every simulated tick (no rewrite)."
  [engine step]
  (let [mode (get-in engine [:policy :mode] :rollback)
        present (:tick engine)
        engine (if (and (= mode :rollback) (:rewind-from engine))
                 (let [from (:rewind-from engine)
                       restored (restore engine from)
                       rolled (update restored :rollbacks inc)]
                   (resimulate rolled step present))
                 engine)
        engine (simulate-one engine step)]
    (if (:stalled? engine)
      engine
      (if (= mode :delay)
        (let [t (:tick engine)]
          (-> engine
              (assoc :confirmed-through t)
              (update :pending-confirms conj
                      {:confirm/tick t
                       :confirm/state-hash (state-hash (:state engine))})))
        (emit-confirms engine)))))
