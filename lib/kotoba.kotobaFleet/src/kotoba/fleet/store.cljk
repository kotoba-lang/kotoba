(ns kotoba.fleet.store
  "Append-only store contract (`:db-api`) + an in-memory MemStore.

  The fleet talks to its backend ONLY through a plain map of pure functions, so
  the same lease/governor/view logic runs on MemStore (here), a real Datomic, or
  the kotoba-db XRPC pod — whichever map is injected. The log is append-only:
  facts are added, never overwritten, so two agents writing concurrently is a
  set-union, not a destructive race.

      {:transact! (fn [datoms] …)          ; append [e a v t] datoms, return {:added n}
       :transact-with-t! (fn [build-fn] …) ; atomically assign t THEN append (build-fn t)'s datoms
       :datoms    (fn [] …)                ; the whole append-only log
       :by        (fn [a v] …)             ; datoms with attribute a and value v
       :entity    (fn [e] …)}              ; pull {:db/id e, a v, …}

  A datom is a vector [e a v t]: entity, attribute (namespaced keyword), value,
  monotonically non-decreasing tx ordinal t (append order = causal order).

  `:transact-with-t!` exists because callers that need a FRESH t to build their
  own datoms (lease/claim!, governor/submit-proposal!) used to read `next-t`
  and call `transact!` as two separate steps -- a classic TOCTOU race: two
  concurrent callers can both read the same `next-t` before either appends,
  producing two entities tagged with the identical ordinal. Since `lease/holder`
  is defined as \"the earliest active claim (smallest t) wins,\" a t collision
  breaks the whole point of this lock-server-free coordination primitive (two
  agents can each be told they hold the same exclusive lease). Verified via 50
  real concurrent threads calling governor/submit-proposal! against the old
  two-step pattern: only 23-37 distinct t values came out of 50 submissions.
  `:transact-with-t!` closes this the same way kagi.store/append-chained-ledger!
  does -- compute t and append inside ONE atomic operation.")

(defn mem-store
  "In-memory append-only MemStore implementing the `:db-api` contract. State is
  an atom holding the datom vector; every transact! only ever conj-es."
  []
  (let [log (atom [])]
    {:transact! (fn [datoms]
                  (let [ds (vec datoms)]
                    (swap! log into ds)
                    {:added (count ds)}))
     ;; swap!'s retry semantics make this atomic: build-fn always runs
     ;; against the CURRENT log length on every CAS retry, so two racing
     ;; callers can never compute the same t.
     :transact-with-t! (fn [build-fn]
                          (let [captured (volatile! nil)]
                            (swap! log (fn [cur]
                                         (let [t (count cur)
                                               ds (vec (build-fn t))]
                                           (vreset! captured {:t t :added (count ds)})
                                           (into cur ds))))
                            @captured))
     :datoms    (fn [] @log)
     :by        (fn [a v]
                  (filterv (fn [[_ da dv]] (and (= da a) (= dv v))) @log))
     :entity    (fn [e]
                  (reduce (fn [m [de a v]] (if (= de e) (assoc m a v) m))
                          {:db/id e}
                          @log))}))

(defn transact!
  "Append `datoms` (a seq of [e a v t]) to the store."
  [db datoms]
  ((:transact! db) datoms))

(defn transact-with-t!
  "Atomically assign the next tx ordinal AND append `(build-fn t)`'s datoms in
  ONE operation. Returns {:t t :added n}. Use this (not next-t followed by a
  separate transact!) whenever a caller needs a fresh t to build the very
  datoms it's about to append -- see the namespace docstring for why the
  two-step version is a TOCTOU race."
  [db build-fn]
  ((:transact-with-t! db) build-fn))

(defn datoms
  "The whole append-only log."
  [db]
  ((:datoms db)))

(defn by
  "Datoms whose attribute = `a` and value = `v`."
  [db a v]
  ((:by db) a v))

(defn entity
  "Pull the entity map for `e`."
  [db e]
  ((:entity db) e))

(defn next-t
  "Next tx ordinal = current log length. Append order is causal order, which is
  what makes the lease winner deterministic without a lock server."
  [db]
  (count (datoms db)))
