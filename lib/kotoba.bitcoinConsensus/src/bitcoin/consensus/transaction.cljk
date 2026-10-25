(ns bitcoin.consensus.transaction
  "Canonical legacy/SegWit transaction parsing and identifiers."
  (:require [bitcoin.consensus.codec :as codec]
            [sha256d.core :as sha256d]))

(def max-money 2100000000000000)
(def max-transaction-base-bytes 1000000)
;; Script execution has a 10,000-byte limit, but CheckTransaction does not:
;; an oversized output script is consensus-valid when created and simply
;; unspendable through legacy/witness-v0 execution. Decode up to the enclosing
;; stripped transaction limit and leave execution limits to the Script VM.
(def max-script-bytes max-transaction-base-bytes)
;; These maxima are derived from Core's stripped transaction size rule.
(def max-inputs 24389)
(def max-outputs 111105)
;; A SegWit block carrying an unknown-version spend also needs a minimal
;; coinbase, reserved value, and witness commitment. Those plus the block and
;; spending-transaction fields consume 1,007 weight units; every empty witness
;; item costs one more. A round 100,000 cap was therefore not consensus-safe.
(def max-witness-items 3998993)
(def max-witness-item-bytes 4000000)
(def locktime-threshold 500000000)
(def final-sequence 0xffffffff)
(def sequence-locktime-disable-flag 0x80000000)
(def sequence-locktime-type-flag 0x00400000)
(def sequence-locktime-mask 0x0000ffff)
(def sequence-locktime-granularity 9)

(defn- read-input [bytes offset]
  (let [[txid offset] (codec/read-bytes bytes offset 32)
        [vout offset] (codec/read-uint-le bytes offset 4)
        [script-sig offset]
        (codec/read-var-bytes bytes offset max-script-bytes "scriptSig")
        [sequence offset] (codec/read-uint-le bytes offset 4)]
    [{:txid-natural txid :vout (long vout) :script-sig script-sig
      :sequence (long sequence)}
     offset]))

(defn- read-output [bytes offset]
  (let [[value offset] (codec/read-uint-le bytes offset 8)
        _ (when (> value max-money)
            (codec/fail! :bitcoin.consensus/amount-out-of-range
                         "Transaction output exceeds MAX_MONEY."
                         {:value value}))
        [script-pubkey offset]
        (codec/read-var-bytes bytes offset max-script-bytes "scriptPubKey")]
    [{:value value :script-pubkey script-pubkey} offset]))

(defn- read-many [reader bytes offset count-value limit label]
  (when (> count-value limit)
    (codec/fail! :bitcoin.consensus/resource-limit
                 (str label " count exceeds its resource limit.")
                 {:count count-value :limit limit}))
  (loop [index 0 offset offset result []]
    (if (= index count-value)
      [result offset]
      (let [[value next-offset] (reader bytes offset)]
        (recur (inc index) next-offset (conj result value))))))

(defn- read-witness [bytes offset]
  (let [[item-count offset] (codec/read-compact-size bytes offset)]
    (when (> item-count max-witness-items)
      (codec/fail! :bitcoin.consensus/resource-limit
                   "Witness item count exceeds its resource limit."
                   {:count item-count :limit max-witness-items}))
    (loop [index 0 offset offset items []]
      (if (= index item-count)
        [items offset]
        (let [[item next-offset]
              (codec/read-var-bytes bytes offset max-witness-item-bytes
                                    "witness item")]
          (recur (inc index) next-offset (conj items item)))))))

(defn serialize-input [{:keys [txid-natural vout script-sig sequence]}]
  (vec (concat txid-natural
               (codec/uint-le vout 4)
               (codec/compact-size (count script-sig)) script-sig
               (codec/uint-le sequence 4))))

(defn serialize-output [{:keys [value script-pubkey]}]
  (vec (concat (codec/uint-le value 8)
               (codec/compact-size (count script-pubkey)) script-pubkey)))

(defn serialize
  ([transaction] (serialize transaction true))
  ([{:keys [version inputs outputs witnesses locktime segwit?]} witness?]
   (let [include-witness? (and witness? segwit?)
         witness-values (or witnesses (repeat (count inputs) []))]
     (vec
      (concat
       (codec/uint-le version 4)
       (when include-witness? [0 1])
       (codec/compact-size (count inputs))
       (mapcat serialize-input inputs)
       (codec/compact-size (count outputs))
       (mapcat serialize-output outputs)
       (when include-witness?
         (mapcat
          (fn [items]
            (concat (codec/compact-size (count items))
                    (mapcat #(concat (codec/compact-size (count %)) %) items)))
          witness-values))
       (codec/uint-le locktime 4))))))

(defn parse-at [bytes start]
  (let [[version offset] (codec/read-uint-le bytes start 4)
        version (long version)
        [first-count after-first] (codec/read-compact-size bytes offset)
        segwit? (and (zero? first-count)
                     (< after-first (count bytes))
                     (not (zero? (nth bytes after-first))))
        [input-count offset]
        (if segwit?
          (let [[flag next-offset] (codec/read-uint-le bytes after-first 1)]
            (when-not (= flag 1)
              (codec/fail! :bitcoin.consensus/unknown-witness-flag
                           "Unknown transaction witness flag."
                           {:flag flag}))
            (codec/read-compact-size bytes next-offset))
          [first-count after-first])
        _ (when (zero? input-count)
            (codec/fail! :bitcoin.consensus/empty-inputs
                         "Transaction must contain an input." {}))
        [inputs offset]
        (read-many read-input bytes offset input-count max-inputs "input")
        [output-count offset] (codec/read-compact-size bytes offset)
        _ (when (zero? output-count)
            (codec/fail! :bitcoin.consensus/empty-outputs
                         "Transaction must contain an output." {}))
        [outputs offset]
        (read-many read-output bytes offset output-count max-outputs "output")
        [witnesses offset]
        (if segwit?
          (read-many (fn [data position] (read-witness data position))
                     bytes offset input-count max-inputs "witness")
          [nil offset])
        _ (when (and segwit? (every? empty? witnesses))
            (codec/fail! :bitcoin.consensus/superfluous-witness
                         "SegWit marker/flag has no witness data." {}))
        [locktime end] (codec/read-uint-le bytes offset 4)
        locktime (long locktime)
        transaction {:version version :inputs inputs :outputs outputs
                     :witnesses witnesses :locktime locktime :segwit? segwit?}
        stripped (serialize transaction false)
        _ (when (> (count stripped) max-transaction-base-bytes)
            (codec/fail! :bitcoin.consensus/oversized-transaction
                         "Stripped transaction exceeds the consensus limit."
                         {:size (count stripped)
                          :limit max-transaction-base-bytes}))
        full (subvec bytes start end)]
    [(assoc transaction
            :raw full :stripped stripped
            :txid-natural (vec (sha256d/sha256d-bytes stripped))
            :wtxid-natural (vec (sha256d/sha256d-bytes full))
            :base-size (count stripped) :total-size (count full)
            :weight (+ (* 3 (count stripped)) (count full)))
     end]))

(defn parse [bytes]
  (let [[transaction offset] (parse-at (vec bytes) 0)]
    (when-not (= offset (count bytes))
      (codec/fail! :bitcoin.consensus/trailing-data
                   "Transaction has trailing data."
                   {:offset offset :length (count bytes)}))
    transaction))

(defn coinbase? [{:keys [inputs]}]
  (and (= 1 (count inputs))
       (every? zero? (:txid-natural (first inputs)))
       (= 0xffffffff (:vout (first inputs)))))

(defn output-value [transaction]
  (reduce + 0 (map :value (:outputs transaction))))

(defn- null-outpoint? [{:keys [txid-natural vout]}]
  (and (every? zero? txid-natural) (= 0xffffffff vout)))

(defn validate-context-free!
  "Apply Bitcoin Core's transaction checks that do not need a UTXO view."
  [transaction]
  (let [inputs (:inputs transaction)
        base-size (:base-size transaction)
        total-output (output-value transaction)
        outpoints (mapv (juxt :txid-natural :vout) inputs)]
    (when (and base-size (> base-size max-transaction-base-bytes))
      (codec/fail! :bitcoin.consensus/oversized-transaction
                   "Stripped transaction exceeds the consensus limit."
                   {:size base-size :limit max-transaction-base-bytes}))
    (when (> total-output max-money)
      (codec/fail! :bitcoin.consensus/amount-out-of-range
                   "Transaction output total exceeds MAX_MONEY."
                   {:value total-output}))
    (if (coinbase? transaction)
      (let [script-size (count (:script-sig (first inputs)))]
        (when-not (<= 2 script-size 100)
          (codec/fail! :bitcoin.consensus/bad-coinbase-script-size
                       "Coinbase scriptSig must contain 2 through 100 bytes."
                       {:size script-size})))
      (when (some null-outpoint? inputs)
        (codec/fail! :bitcoin.consensus/null-prevout
                     "A non-coinbase transaction has a null prevout." {})))
    (when-not (= (count outpoints) (count (set outpoints)))
      (codec/fail! :bitcoin.consensus/duplicate-input
                   "Transaction contains duplicate inputs." {}))
    transaction))

(defn final?
  "Whether a transaction is final for a candidate block height/time."
  [transaction block-height block-time]
  (let [locktime (:locktime transaction)
        comparison (if (< locktime locktime-threshold)
                     block-height block-time)]
    (or (zero? locktime)
        (< locktime comparison)
        (every? #(= final-sequence (:sequence %))
                (:inputs transaction)))))

(defn calculate-sequence-locks
  "Return BIP68's last-invalid {:height :time} pair.

  `prev-heights` and `coin-mtp` are supplied by the UTXO/chain view. coin-mtp
  receives max(coin-height - 1, 0), matching Bitcoin Core."
  [transaction prev-heights coin-mtp]
  (if (< (:version transaction) 2)
    {:height -1 :time -1}
    (reduce
     (fn [{:keys [height time] :as result} [input coin-height]]
       (let [sequence (:sequence input)]
         (if (not (zero? (bit-and sequence
                                  sequence-locktime-disable-flag)))
           result
           (let [relative (bit-and sequence sequence-locktime-mask)]
             (if (not (zero? (bit-and sequence
                                      sequence-locktime-type-flag)))
               (assoc result :time
                      (max time
                           (dec (+ (coin-mtp (max (dec coin-height) 0))
                                   (bit-shift-left
                                    relative sequence-locktime-granularity)))))
               (assoc result :height
                      (max height (dec (+ coin-height relative)))))))))
     {:height -1 :time -1}
     (map vector (:inputs transaction) prev-heights))))

(defn sequence-locks-satisfied?
  "Evaluate BIP68 locks for a candidate block height and its parent MTP."
  [{:keys [height time]} block-height parent-mtp]
  (and (< height block-height)
       (< time parent-mtp)))
