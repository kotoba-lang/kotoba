(ns moyai.ledger
  "moyai 舫い — append-only, non-monetary, non-transferable reciprocity-credit ledger.
  Clojure port of `methods/ledger.py` (ADR-2606062100), reused verbatim by the
  mishmar/mimamori social-capital bridge (ADR-2606082100 Part A).

  Charter invariants enforced HERE by construction, not by policy:

  - cash≡0 / non-monetary — no USDC/amount field exists on an entry;
    `redeemable-usd-micros` is a const-0 function (BHI firewall, N1).
  - non-transferable — the ledger exposes ONLY `mint` and `burn`. No
    transfer/gift/merge/pool var exists in this namespace (test-enforced),
    so a sybil farm cannot aggregate credit across identities.
  - conservation (sink ≤ source) — a burn can never exceed the holder's live
    (decayed) balance; no inflation, no negative balances.
  - decay (anti-hoarding) — credit halves every `half-life-epochs`: a flow,
    never a store of wealth/power. 1 SBT = 1 vote is untouched.

  The ledger is a plain vector of immutable entry maps (kotoba-Datom-isomorphic);
  balances are a fold over the log, never a mutable row. Time is integer epochs —
  deterministic, no wall clock, replays bit-identically."
  (:refer-clojure :exclude [resolve]))

(def half-life-epochs
  "Anti-hoarding half-life (reference value; Council-attested in production)."
  30)

(defn redeemable-usd-micros
  "INVARIANT: moyai credit is non-monetary. Always 0, for every entry, forever."
  [& _]
  0)

(defn grants-governance-weight?
  "INVARIANT: social capital never weighs a vote. 1 SBT = 1 vote."
  []
  false)

(defn grants-benefit-or-stage?
  "INVARIANT: social capital never gates 救済/benefit/stage (BHI floor unconditional)."
  []
  false)

(defn- entry [holder-did op units epoch ref]
  (when-not (and (integer? units) (pos? units))
    (throw (ex-info "moyai ledger: units must be a positive integer" {:units units})))
  (when-not (#{:mint :burn} op)
    (throw (ex-info (str "moyai ledger: unknown op " op " (only mint/burn exist)") {:op op})))
  {:holder-did holder-did :op op :units units :epoch epoch :ref ref})

(defn- guard-epoch [log epoch]
  (when (and (seq log) (< epoch (:epoch (peek log))))
    (throw (ex-info "moyai ledger: append-only — epoch must be monotone non-decreasing"
                    {:epoch epoch}))))

(defn- decay [amount dt-epochs half-life]
  (if (or (<= amount 0) (<= dt-epochs 0))
    (max amount 0.0)
    (* amount #?(:clj  (Math/pow 0.5 (/ (double dt-epochs) half-life))
                 :cljs (js/Math.pow 0.5 (/ dt-epochs half-life))))))

(defn balance
  "Live, decayed balance for one identity. Pure event-sourced fold over the log."
  [log holder-did now-epoch]
  (let [[bal last-epoch]
        (reduce (fn [[bal last-epoch] e]
                  (if (not= (:holder-did e) holder-did)
                    [bal last-epoch]
                    (let [bal (if last-epoch
                                (decay bal (- (:epoch e) last-epoch) half-life-epochs)
                                bal)
                          bal (if (= :mint (:op e))
                                (+ bal (:units e))
                                (- bal (:units e)))]
                      [(max bal 0.0) (:epoch e)])))
                [0.0 nil]
                log)]
    (if (and last-epoch (> now-epoch last-epoch))
      (decay bal (- now-epoch last-epoch) half-life-epochs)
      bal)))

(defn mint
  "Mint credit from VERIFIED contribution. Returns the grown log."
  [log holder-did units epoch ref]
  (guard-epoch log epoch)
  (conj log (entry holder-did :mint units epoch ref)))

(defn burn
  "Spend credit on a discretionary surplus draw. Refuses to overdraw."
  [log holder-did units epoch ref]
  (guard-epoch log epoch)
  (let [avail (balance log holder-did epoch)]
    (when (> units (+ avail 1e-9))
      (throw (ex-info (str "moyai ledger: overdraw refused — " holder-did " has " avail
                           " credit, tried to burn " units
                           ". Contribute first (情報を得るには情報を生成する).")
                      {:holder-did holder-did :available avail :units units}))))
  (conj log (entry holder-did :burn units epoch ref)))

(defn total-minted
  ([log] (total-minted log nil))
  ([log holder-did]
   (transduce (comp (filter #(= :mint (:op %)))
                    (filter #(or (nil? holder-did) (= holder-did (:holder-did %))))
                    (map :units))
              + 0 log)))

(defn total-burned
  ([log] (total-burned log nil))
  ([log holder-did]
   (transduce (comp (filter #(= :burn (:op %)))
                    (filter #(or (nil? holder-did) (= holder-did (:holder-did %))))
                    (map :units))
              + 0 log)))

(defn assert-conservation
  "sink ≤ source: you can never have spent more than was ever verifiably minted."
  [log]
  (when (> (total-burned log) (total-minted log))
    (throw (ex-info "moyai ledger: conservation violated — burned > minted" {})))
  log)
