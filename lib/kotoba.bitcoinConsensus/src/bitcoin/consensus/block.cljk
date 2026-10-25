(ns bitcoin.consensus.block
  "Raw block parsing and context-free full-block checks."
  (:require [bitcoin.consensus.codec :as codec]
            [bitcoin.consensus.transaction :as transaction]
            [kotobase.bitcoin.protocol :as header]
            [sha256d.core :as sha256d]))

(def max-block-weight 4000000)
(def max-block-bytes 4000000)
(def max-transactions 1000000)
(def witness-commitment-prefix [0x6a 0x24 0xaa 0x21 0xa9 0xed])

(defn merkle-root
  "Return {:root natural-order-hash :mutated? bool}. The mutation flag follows
  Bitcoin Core: equal siblings that were not introduced by odd-leaf padding
  make the tree ambiguous and invalidate the block."
  [hashes]
  (when (empty? hashes)
    (codec/fail! :bitcoin.consensus/empty-merkle-tree
                 "A block requires at least one transaction." {}))
  (loop [level (vec hashes) mutated? false]
    (if (= 1 (count level))
      {:root (first level) :mutated? mutated?}
      (let [real-pairs (partition 2 2 nil level)
            mutation-now?
            (some (fn [[left right]] (and right (= left right))) real-pairs)
            padded (if (odd? (count level)) (conj level (peek level)) level)
            next-level
            (mapv (fn [[left right]]
                    (vec (sha256d/sha256d-bytes
                          (vec (concat left right)))))
                  (partition 2 padded))]
        (recur next-level (or mutated? (boolean mutation-now?)))))))

(defn witness-merkle-root [transactions]
  (:root
   (merkle-root
    (into [(vec (repeat 32 0))]
          (map :wtxid-natural (rest transactions))))))

(defn- commitment-output [coinbase]
  (last
   (keep-indexed
    (fn [index {:keys [script-pubkey]}]
      (when (and (<= 38 (count script-pubkey))
                 (= witness-commitment-prefix (subvec script-pubkey 0 6)))
        {:index index :commitment (subvec script-pubkey 6 38)}))
    (:outputs coinbase))))

(defn validate-witness-commitment!
  "Enforce BIP141's witness Merkle commitment whenever witness serialization
  is present. The highest matching coinbase output index is authoritative."
  [transactions]
  (let [coinbase (first transactions)
        commitment (commitment-output coinbase)
        witness-present? (some :segwit? transactions)]
    (when (and witness-present? (nil? commitment))
      (codec/fail! :bitcoin.consensus/missing-witness-commitment
                   "A block carrying witness data lacks a commitment." {}))
    (when commitment
      (let [stack (get-in coinbase [:witnesses 0])
            reserved (first stack)]
        (when-not (and (= 1 (count stack)) (= 32 (count reserved)))
          (codec/fail! :bitcoin.consensus/bad-witness-reserved-value
                       "Coinbase witness reserved value must be one 32-byte item."
                       {}))
        (let [expected
              (vec
               (sha256d/sha256d-bytes
                (vec (concat (witness-merkle-root transactions) reserved))))]
          (when-not (= expected (:commitment commitment))
            (codec/fail! :bitcoin.consensus/bad-witness-commitment
                         "Witness commitment does not match the witness tree."
                         {:output-index (:index commitment)})))))
    commitment))

(defn validate-witness-malleation!
  "Apply Core's activation-aware witness malleation rule.

  Before SegWit activation, no transaction may carry witness serialization,
  even when the coinbase contains a syntactically valid commitment. After
  activation, the BIP141 commitment rules apply."
  [transactions expect-witness-commitment?]
  (if expect-witness-commitment?
    (validate-witness-commitment! transactions)
    (do
      (when (some :segwit? transactions)
        (codec/fail! :bitcoin.consensus/unexpected-witness
                     "Witness data is forbidden before SegWit activation."
                     {}))
      nil)))

(defn serialize
  "Serialize a parsed block without trusting cached size or weight fields."
  [{:keys [header transactions]}]
  (vec
   (concat (header/encode-block-header header)
           (codec/compact-size (count transactions))
           (mapcat (fn [value]
                     (or (:raw value) (transaction/serialize value)))
                   transactions))))

(defn parse [bytes]
  (let [bytes (vec bytes)
        _ (when (> (count bytes) max-block-bytes)
            (codec/fail! :bitcoin.consensus/block-too-large
                         "Serialized block exceeds the resource limit."
                         {:size (count bytes)}))
        [header-bytes offset] (codec/read-bytes bytes 0 80)
        decoded-header (header/decode-block-header header-bytes)
        [transaction-count offset] (codec/read-compact-size bytes offset)
        _ (when (or (zero? transaction-count)
                    (> transaction-count max-transactions))
            (codec/fail! :bitcoin.consensus/invalid-transaction-count
                         "Block transaction count is invalid."
                         {:count transaction-count}))
        [transactions offset]
        (loop [index 0 offset offset result []]
          (if (= index transaction-count)
            [result offset]
            (let [[value next-offset] (transaction/parse-at bytes offset)]
              (recur (inc index) next-offset (conj result value)))))
        _ (when-not (= offset (count bytes))
            (codec/fail! :bitcoin.consensus/trailing-data
                         "Block has trailing data."
                         {:offset offset :length (count bytes)}))
        prefix-size (+ 80 (count (codec/compact-size transaction-count)))
        base-size (+ prefix-size
                     (reduce + 0 (map :base-size transactions)))
        total-size (+ prefix-size
                      (reduce + 0 (map :total-size transactions)))
        weight (+ (* 3 base-size) total-size)
        txids (mapv :txid-natural transactions)
        merkle (merkle-root txids)
        _ (when (:mutated? merkle)
            (codec/fail! :bitcoin.consensus/mutated-merkle-tree
                         "Block has an ambiguous Merkle tree." {}))
        _ (when-not (= (:root merkle) (:merkle-root decoded-header))
            (codec/fail! :bitcoin.consensus/bad-merkle-root
                         "Block header Merkle root does not match transactions."
                         {}))
        _ (doseq [transaction transactions]
            (transaction/validate-context-free! transaction))
        _ (when (> weight max-block-weight)
            (codec/fail! :bitcoin.consensus/block-weight
                         "Block exceeds MAX_BLOCK_WEIGHT."
                         {:weight weight}))
        _ (when-not (transaction/coinbase? (first transactions))
            (codec/fail! :bitcoin.consensus/missing-coinbase
                         "First transaction is not coinbase." {}))
        _ (when (some transaction/coinbase? (rest transactions))
            (codec/fail! :bitcoin.consensus/multiple-coinbase
                         "Block contains more than one coinbase." {}))
        _ (when-not (= (count txids) (count (set txids)))
            (codec/fail! :bitcoin.consensus/duplicate-transaction
                         "Block contains duplicate transaction IDs." {}))]
    {:header decoded-header
     :transactions transactions
     :transaction-count transaction-count
     :size (count bytes)
     :weight weight
     :merkle-root (:root merkle)}))
