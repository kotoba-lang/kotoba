(ns bitcoin.consensus.utxo
  "Deterministic value-safe UTXO transitions. Script verification is injected
  and therefore cannot be accidentally skipped by callers."
  (:require [bitcoin.consensus.codec :as codec]
            [bitcoin.consensus.transaction :as transaction]))

(def coinbase-maturity 100)
(def initial-subsidy 5000000000)
(def halving-interval 210000)
(def max-block-sigop-cost 80000)
(def max-script-size 10000)

(defn money-range?
  "Bitcoin Core's consensus MoneyRange predicate."
  [value]
  (and (integer? value)
       (<= 0 value transaction/max-money)))

(defprotocol CoinStore
  "Persistent-map semantics required by consensus. Implementations may return
  immutable overlays backed by an on-disk ordered store."
  (-coin-get [coins key])
  (-coin-contains? [coins key])
  (-coin-assoc [coins key coin])
  (-coin-dissoc [coins key])
  (-coin-entries [coins])
  (-coin-count [coins]))

(defn coin-get [coins key]
  (if (satisfies? CoinStore coins)
    (-coin-get coins key)
    (get coins key)))

(defn coin-contains? [coins key]
  (if (satisfies? CoinStore coins)
    (-coin-contains? coins key)
    (contains? coins key)))

(defn coin-assoc [coins key coin]
  (if (satisfies? CoinStore coins)
    (-coin-assoc coins key coin)
    (assoc coins key coin)))

(defn coin-dissoc [coins key]
  (if (satisfies? CoinStore coins)
    (-coin-dissoc coins key)
    (dissoc coins key)))

(defn coin-entries [coins]
  (if (satisfies? CoinStore coins)
    (-coin-entries coins)
    (seq coins)))

(defn coin-count [coins]
  (if (satisfies? CoinStore coins)
    (-coin-count coins)
    (count coins)))

(defn block-subsidy
  ([height] (block-subsidy height halving-interval))
  ([height interval]
   (let [halvings (quot height interval)]
     (if (>= halvings 64)
       0
       (quot initial-subsidy
             (reduce * 1 (repeat halvings 2)))))))

(defn outpoint-key [txid-natural vout] [txid-natural vout])

(defn- spend-input
  [state transaction input-index input height verify-script]
  (let [key (outpoint-key (:txid-natural input) (:vout input))
        coin (coin-get (:coins state) key)]
    (when-not coin
      (codec/fail! :bitcoin.consensus/missing-input
                   "Transaction spends a missing or already-spent output."
                   {:input-index input-index :outpoint key}))
    (when (and (:coinbase? coin)
               (< (- height (:height coin)) coinbase-maturity))
      (codec/fail! :bitcoin.consensus/premature-coinbase-spend
                   "Transaction spends an immature coinbase output."
                   {:input-index input-index :coin-height (:height coin)
                    :height height}))
    (when-not (money-range? (:value coin))
      (codec/fail! :bitcoin.consensus/input-value-out-of-range
                   "Spent output value is outside MoneyRange."
                   {:input-index input-index :value (:value coin)}))
    (when-not (true? (verify-script transaction input-index coin))
      (codec/fail! :bitcoin.consensus/script-failed
                   "Input script verification failed."
                   {:input-index input-index}))
    [(update state :coins coin-dissoc key) (:value coin)]))

(defn- provably-unspendable? [output]
  (let [script-pubkey (:script-pubkey output)]
    (or (= 0x6a (first script-pubkey))
        (> (count script-pubkey) max-script-size))))

(defn- add-outputs
  [state transaction height coinbase? allow-overwrite?]
  (reduce-kv
   (fn [result index output]
     (if (provably-unspendable? output)
       result
       (let [key (outpoint-key (:txid-natural transaction) index)]
       (when (and (not allow-overwrite?)
                  (coin-contains? (:coins result) key))
         (codec/fail! :bitcoin.consensus/overwrite-unspent
                      "Transaction would overwrite an unspent output."
                      {:outpoint key}))
         (update result :coins coin-assoc key
                 (assoc output :height height :coinbase? coinbase?)))))
   state (vec (:outputs transaction))))

(defn- validate-bip30-collisions!
  [state transactions]
  (doseq [transaction transactions
          [index output] (map-indexed vector (:outputs transaction))
          :when (not (provably-unspendable? output))]
    (let [key (outpoint-key (:txid-natural transaction) index)]
      (when (coin-contains? (:coins state) key)
        (codec/fail! :bitcoin.consensus/overwrite-unspent
                     "Block would overwrite an initially unspent output."
                     {:outpoint key}))))
  state)

(defn- validate-sequence-locks!
  [state transaction height {:keys [sequence-locks? coin-mtp parent-mtp]}]
  (when sequence-locks?
    (let [prev-heights
          (mapv
           (fn [input]
             (or (:height
                  (coin-get
                   (:coins state)
                   (outpoint-key (:txid-natural input) (:vout input))))
                 (codec/fail! :bitcoin.consensus/missing-input
                              "Transaction spends a missing output."
                              {:outpoint [(:txid-natural input)
                                          (:vout input)]})))
           (:inputs transaction))
          locks (transaction/calculate-sequence-locks
                 transaction prev-heights coin-mtp)]
      (when-not (transaction/sequence-locks-satisfied?
                 locks height parent-mtp)
        (codec/fail! :bitcoin.consensus/non-final-sequence
                     "Transaction violates BIP68 relative lock-time."
                     {:height height :parent-mtp parent-mtp
                      :locks locks})))))

(defn- input-coins [state transaction]
  (mapv
   (fn [input]
     (coin-get (:coins state)
               (outpoint-key (:txid-natural input) (:vout input))))
   (:inputs transaction)))

(defn- add-sigop-cost!
  [total state transaction sigop-cost-fn]
  (let [next-total
        (+ total
           (if sigop-cost-fn
             (sigop-cost-fn transaction (input-coins state transaction))
             0))]
    (when (> next-total max-block-sigop-cost)
      (codec/fail! :bitcoin.consensus/too-many-sigops
                   "Block exceeds MAX_BLOCK_SIGOPS_COST."
                   {:cost next-total :limit max-block-sigop-cost}))
    next-total))

(defn apply-block
  "Apply a parsed block atomically. `verify-script` is mandatory and must
  return exactly true for every non-coinbase input."
  ([state block height verify-script]
   (apply-block state block height verify-script {}))
  ([state block height verify-script options]
   (when-not (ifn? verify-script)
     (codec/fail! :bitcoin.consensus/missing-script-verifier
                  "A script verifier is required." {}))
   (let [transactions (:transactions block)
        _ (when-not (:allow-bip30-overwrite? options)
            ;; ConnectBlock performs BIP30 against the unmodified parent view,
            ;; before any transaction in this block can spend a collision.
            (validate-bip30-collisions! state transactions))
        coinbase (first transactions)
        initial-sigops
        (add-sigop-cost! 0 state coinbase (:sigop-cost-fn options))
        [working fees _sigops]
        (reduce
         (fn [[working total-fees sigops] transaction]
           (validate-sequence-locks! working transaction height options)
           (let [transaction
                 (assoc transaction :prevout-coins
                        (input-coins working transaction))
                 sigops
                 (add-sigop-cost! sigops working transaction
                                  (:sigop-cost-fn options))
                 [spent input-value]
                 (reduce-kv
                  (fn [[current total] index input]
                    (let [[next-state value]
                          (spend-input current transaction index input
                                       height verify-script)
                          next-total (+ total value)]
                      (when-not (money-range? next-total)
                        (codec/fail!
                         :bitcoin.consensus/input-value-out-of-range
                         "Transaction input total exceeds MAX_MONEY."
                         {:input-index index :value next-total}))
                      [next-state next-total]))
                  [working 0] (vec (:inputs transaction)))
                 output-value (transaction/output-value transaction)]
             (when (> output-value input-value)
               (codec/fail! :bitcoin.consensus/inputs-below-outputs
                            "Transaction creates value."
                            {:inputs input-value :outputs output-value}))
             (let [next-fees (+ total-fees (- input-value output-value))]
               (when-not (money-range? next-fees)
                 (codec/fail!
                  :bitcoin.consensus/accumulated-fee-out-of-range
                  "Accumulated block fees exceed MAX_MONEY."
                  {:fees next-fees}))
               ;; Core's AddCoins permits BIP30 replacement only for a
               ;; coinbase. A non-coinbase output may never overwrite an
               ;; unspent outpoint, including inside either repeat block.
               [(add-outputs spent transaction height false false)
                next-fees
                sigops])))
         [state 0 initial-sigops] (rest transactions))
        coinbase-value (transaction/output-value coinbase)
        allowed (+ (block-subsidy
                    height (or (:halving-interval options)
                               halving-interval))
                   fees)
        _ (when (> coinbase-value allowed)
            (codec/fail! :bitcoin.consensus/bad-coinbase-amount
                         "Coinbase exceeds subsidy plus fees."
                         {:value coinbase-value :allowed allowed}))]
     (-> working
         (add-outputs coinbase height true
                      (:allow-bip30-overwrite? options))
         (assoc :height height)))))

(def empty-state {:height -1 :coins {}})

(defn apply-block-with-undo
  "Apply a block and return {:state next-state :undo reversible-delta}."
  ([state block height verify-script]
   (apply-block-with-undo state block height verify-script {}))
  ([state block height verify-script options]
   (let [next-state (apply-block state block height verify-script options)
        before (:coins state)
        after (:coins next-state)
        touched
        (into #{}
              (mapcat
               (fn [transaction]
                 (concat
                  (map (fn [input]
                         (outpoint-key (:txid-natural input) (:vout input)))
                       (:inputs transaction))
                  (keep-indexed
                   (fn [index output]
                     (when-not (provably-unspendable? output)
                       (outpoint-key (:txid-natural transaction) index)))
                   (:outputs transaction))))
               (:transactions block)))
        spent (into {}
                    (keep (fn [key]
                            (let [coin (coin-get before key)]
                              (when (and coin
                                         (not= coin (coin-get after key)))
                                [key coin]))))
                    touched)
        created (into #{}
                      (keep (fn [key]
                              (let [coin (coin-get after key)]
                                (when (and coin
                                           (not= coin (coin-get before key)))
                                  key))))
                      touched)]
     {:state next-state
      :undo {:height (:height state) :spent spent :created created}})))

(defn disconnect-block
  "Reverse exactly one apply-block-with-undo transition."
  [state {:keys [height spent created]}]
  (-> state
      (update :coins #(reduce coin-dissoc % created))
      (update :coins #(reduce-kv coin-assoc % spent))
      (assoc :height height)))
