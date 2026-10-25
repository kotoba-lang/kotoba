(ns bitcoin.consensus.assumeutxo
  "Bitcoin Core v31 UTXO snapshot decoding and trust-anchor verification.

  A decoded snapshot is not considered usable until its network, base block,
  coin count, and HASH_SERIALIZED commitment all match an explicit checkpoint."
  (:require [bitcoin.consensus.codec :as codec]
            [bitcoin.consensus.utxo :as utxo])
  (:import (java.io ByteArrayInputStream InputStream)
           (java.math BigInteger)
           (java.security MessageDigest)))

(def snapshot-magic [0x75 0x74 0x78 0x6f 0xff])
(def snapshot-version 2)
(def max-money 2100000000000000)
(def max-script-size 10000)

(def network-magic
  {:mainnet [0xf9 0xbe 0xb4 0xd9]
   :testnet [0x0b 0x11 0x09 0x07]
   :testnet4 [0x1c 0x16 0x3f 0x28]
   :signet [0x0a 0x03 0xcf 0x40]
   :regtest [0xfa 0xbf 0xb5 0xda]})

(def checkpoints
  "Bitcoin Core v31.1 AssumeUTXO trust anchors. Regtest fixtures are omitted:
  their block hashes depend on Core's deterministic functional-test chain."
  {:mainnet
   {840000
    {:blockhash
     "0000000000000000000320283a032748cef8227873ff4872689bf23f1cda83a5"
     :hash-serialized
     "a2a5521b1b5ab65f67818e5e8eccabb7171a517f9e2382208f77687310768f96"
     :chain-tx-count 991032194}
    880000
    {:blockhash
     "000000000000000000010b17283c3c400507969a9c2afd1dcf2082ec5cca2880"
     :hash-serialized
     "dbd190983eaf433ef7c15f78a278ae42c00ef52e0fd2a54953782175fbadcea9"
     :chain-tx-count 1145604538}
    910000
    {:blockhash
     "0000000000000000000108970acb9522ffd516eae17acddcb1bd16469194a821"
     :hash-serialized
     "4daf8a17b4902498c5787966a2b51c613acdab5df5db73f196fa59a4da2f1568"
     :chain-tx-count 1226586151}
    935000
    {:blockhash
     "0000000000000000000147034958af1652b2b91bba607beacc5e72a56f0fb5ee"
     :hash-serialized
     "e4b90ef9eae834f56c4b64d2d50143cee10ad87994c614d7d04125e2a6025050"
     :chain-tx-count 1305397408}}
   :testnet
   {2500000
    {:blockhash
     "0000000000000093bcb68c03a9a168ae252572d348a2eaeba2cdf9231d73206f"
     :hash-serialized
     "f841584909f68e47897952345234e37fcd9128cd818f41ee6c3ca68db8071be7"
     :chain-tx-count 66484552}
    4840000
    {:blockhash
     "00000000000000f4971a7fb37fbdff89315b69a2e1920c467654a382f0d64786"
     :hash-serialized
     "ce6bb677bb2ee9789c4a1c9d73e6683c53fc20e8fdbedbdaaf468982a0c8db2a"
     :chain-tx-count 536078574}}
   :testnet4
   {90000
    {:blockhash
     "0000000002ebe8bcda020e0dd6ccfbdfac531d2f6a81457191b99fc2df2dbe3b"
     :hash-serialized
     "784fb5e98241de66fdd429f4392155c9e7db5c017148e66e8fdbc95746f8b9b5"
     :chain-tx-count 11347043}
    120000
    {:blockhash
     "000000000bd2317e51b3c5794981c35ba894ce27d3e772d5c39ecd9cbce01dc8"
     :hash-serialized
     "10b05d05ad468d0971162e1b222a4aa66caca89da2bb2a93f8f37fb29c4794b0"
     :chain-tx-count 14141057}}
   :signet
   {160000
    {:blockhash
     "0000003ca3c99aff040f2563c2ad8f8ec88bd0fd6b8f0895cfaf1ef90353a62c"
     :hash-serialized
     "fe0a44309b74d6b5883d246cb419c6221bcccf0b308c9b59b7d70783dbdf928a"
     :chain-tx-count 2289496}
    290000
    {:blockhash
     "0000000577f2741bb30cd9d39d6d71b023afbeb9764f6260786a97969d5c9ac0"
     :hash-serialized
     "97267e000b4b876800167e71b9123f1529d13b14308abec2888bbd2160d14545"
     :chain-tx-count 28547497}}})

(defn- read-byte! [^InputStream input label]
  (let [value (.read input)]
    (when (= -1 value)
      (codec/fail! :bitcoin.consensus/truncated-snapshot
                   "UTXO snapshot is truncated."
                   {:field label}))
    value))

(defn- read-bytes! [^InputStream input length label]
  (let [result (byte-array length)]
    (loop [offset 0]
      (if (= offset length)
        (mapv #(bit-and 0xff %) result)
        (let [read (.read input result offset (- length offset))]
          (when (neg? read)
            (codec/fail! :bitcoin.consensus/truncated-snapshot
                         "UTXO snapshot is truncated."
                         {:field label :expected length :actual offset}))
          (recur (+ offset read)))))))

(defn- read-uint-le! [input length label]
  (reduce (fn [result byte] (+ (* result 256) byte))
          0N (reverse (read-bytes! input length label))))

(defn- read-compact-size! [input label]
  (let [prefix (read-byte! input label)]
    (case prefix
      0xfd (let [value (read-uint-le! input 2 label)]
             (when (< value 0xfd)
               (codec/fail! :bitcoin.consensus/noncanonical-compact-size
                            "Snapshot CompactSize is non-minimal."
                            {:field label :value value}))
             value)
      0xfe (let [value (read-uint-le! input 4 label)]
             (when (<= value 0xffff)
               (codec/fail! :bitcoin.consensus/noncanonical-compact-size
                            "Snapshot CompactSize is non-minimal."
                            {:field label :value value}))
             value)
      0xff (let [value (read-uint-le! input 8 label)]
             (when (<= value 0xffffffff)
               (codec/fail! :bitcoin.consensus/noncanonical-compact-size
                            "Snapshot CompactSize is non-minimal."
                            {:field label :value value}))
             value)
      prefix)))

(defn- read-varint! [input label]
  (loop [value 0N bytes-read 0]
    (when (>= bytes-read 10)
      (codec/fail! :bitcoin.consensus/snapshot-varint-overflow
                   "Snapshot VARINT is too large."
                   {:field label}))
    (let [byte (read-byte! input label)
          next-value (+ (* value 128) (bit-and byte 0x7f))]
      (if (zero? (bit-and byte 0x80))
        next-value
        (recur (inc next-value) (inc bytes-read))))))

(defn- decompress-amount [value]
  (if (zero? value)
    0N
    (let [value (dec value)
          exponent (mod value 10)
          value (quot value 10)
          amount
          (if (< exponent 9)
            (let [digit (inc (mod value 9))]
              (+ (* (quot value 9) 10) digit))
            (inc value))]
      (* amount (reduce * 1N (repeat exponent 10))))))

(def ^BigInteger secp-p
  (BigInteger. "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F"
               16))

(defn- fixed-32 [^BigInteger value]
  (let [raw (.toByteArray value)
        raw (if (and (= 33 (alength raw)) (zero? (aget raw 0)))
              (java.util.Arrays/copyOfRange raw 1 33)
              raw)
        result (byte-array 32)]
    (when (> (alength raw) 32)
      (codec/fail! :bitcoin.consensus/invalid-compressed-pubkey
                   "Compressed public key coordinate is oversized." {}))
    (System/arraycopy raw 0 result (- 32 (alength raw)) (alength raw))
    (mapv #(bit-and 0xff %) result)))

(defn- decompress-pubkey [prefix x-bytes]
  (let [x (BigInteger. 1 (byte-array (map unchecked-byte x-bytes)))
        y2 (.mod (.add (.modPow x (BigInteger/valueOf 3) secp-p)
                       (BigInteger/valueOf 7))
                 secp-p)
        y (.modPow y2 (.shiftRight (.add secp-p BigInteger/ONE) 2) secp-p)]
    (when-not (= y2 (.mod (.multiply y y) secp-p))
      (codec/fail! :bitcoin.consensus/invalid-compressed-pubkey
                   "Snapshot contains a non-curve public key." {}))
    (let [odd? (.testBit y 0)
          expected-odd? (= prefix 0x05)
          chosen (if (= odd? expected-odd?) y (.subtract secp-p y))]
      (vec (concat [0x41 0x04] x-bytes (fixed-32 chosen) [0xac])))))

(defn- read-script! [input]
  (let [code (read-varint! input :script-code)]
    (cond
      (= code 0)
      (vec (concat [0x76 0xa9 0x14]
                   (read-bytes! input 20 :p2pkh-hash)
                   [0x88 0xac]))

      (= code 1)
      (vec (concat [0xa9 0x14]
                   (read-bytes! input 20 :p2sh-hash)
                   [0x87]))

      (<= 2 code 3)
      (vec (concat [0x21 code]
                   (read-bytes! input 32 :compressed-pubkey)
                   [0xac]))

      (<= 4 code 5)
      (decompress-pubkey code
                         (read-bytes! input 32 :compressed-pubkey))

      :else
      (let [length (- code 6)]
        (when (> length max-script-size)
          (codec/fail! :bitcoin.consensus/snapshot-script-size
                       "Snapshot script exceeds MAX_SCRIPT_SIZE."
                       {:length length :limit max-script-size}))
        (read-bytes! input length :script-pubkey)))))

(defn- read-coin! [input]
  (let [code (read-varint! input :coin-height)
        height (quot code 2)
        coinbase? (odd? code)
        amount (decompress-amount (read-varint! input :amount))
        script (read-script! input)]
    (when (> amount max-money)
      (codec/fail! :bitcoin.consensus/snapshot-money-range
                   "Snapshot coin amount is outside MoneyRange."
                   {:value amount}))
    {:value (long amount)
     :script-pubkey script
     :height (long height)
     :coinbase? coinbase?}))

(defn- hex [bytes]
  (apply str (map #(format "%02x" (bit-and 0xff %)) bytes)))

(defn- displayed-hash [natural-bytes]
  (hex (reverse natural-bytes)))

(defn- update-digest! [^MessageDigest digest bytes]
  (.update digest (byte-array (map unchecked-byte bytes))))

(defn- coin-hash-bytes [txid vout coin]
  (concat txid
          (codec/uint-le vout 4)
          (codec/uint-le (+ (* (:height coin) 2)
                            (if (:coinbase? coin) 1 0))
                         4)
          (codec/uint-le (:value coin) 8)
          (codec/compact-size (count (:script-pubkey coin)))
          (:script-pubkey coin)))

(defn hash-serialized-reduce
  "Compute HASH_SERIALIZED from an ordered, constant-memory reducer.

  `reduce-entries` receives a reducing function and initial value. Entries must
  be ordered by natural txid bytes and then vout, matching Core's cursor."
  [reduce-entries]
  (let [first-hash (MessageDigest/getInstance "SHA-256")]
    (reduce-entries
     (fn [count [[txid vout] coin]]
       (update-digest! first-hash (coin-hash-bytes txid vout coin))
       (inc count))
     0)
    (displayed-hash
     (.digest (MessageDigest/getInstance "SHA-256")
              (.digest first-hash)))))

(defn hash-serialized
  "Compute Bitcoin Core HASH_SERIALIZED (hash_serialized_3) for a UTXO map."
  [coins]
  (hash-serialized-reduce
   (fn [reduce-fn initial]
     (reduce
      reduce-fn initial
      (sort-by (fn [[[txid vout] _]] [txid vout])
               (utxo/coin-entries coins))))))

(defn validate-background-commitment
  "Promote an assumed state from independently validated disk evidence."
  [loaded actual-height actual-tip actual-hash]
  (let [{:keys [base-height base-blockhash]} (:snapshot loaded)
        expected-hash (get-in loaded [:snapshot :hash-serialized])]
    (when-not (and (= base-height actual-height)
                   (= base-blockhash actual-tip))
      (codec/fail! :bitcoin.consensus/snapshot-background-base
                   "Background validation has not reached the snapshot base."
                   {:expected-height base-height :actual-height actual-height
                    :expected-hash base-blockhash :actual-hash actual-tip}))
    (when-not (= expected-hash actual-hash)
      (codec/fail! :bitcoin.consensus/snapshot-background-mismatch
                   "Background-validated UTXO set differs from the snapshot."
                   {:expected expected-hash :actual actual-hash}))
    (assoc-in loaded [:snapshot :status] :validated)))

(defn- checkpoint-for! [network base-hash supplied]
  (let [available (or supplied (get checkpoints network))
        match (some (fn [[height checkpoint]]
                      (when (= base-hash (:blockhash checkpoint))
                        [height checkpoint]))
                    available)]
    (when-not match
      (codec/fail! :bitcoin.consensus/unknown-assumeutxo-base
                   "Snapshot base block is not an approved AssumeUTXO checkpoint."
                   {:network network :base-blockhash base-hash}))
    match))

(defn load-snapshot
  "Decode and authenticate a Core v2 snapshot from an InputStream or byte array.

  `header-at-height` must resolve the independently validated header hash at a
  checkpoint height. Tests/private networks may pass `:checkpoints`; production
  callers should use the built-in Core v31.1 anchors."
  ([source network header-at-height]
   (load-snapshot source network header-at-height {}))
  ([source network header-at-height
    {:keys [checkpoints max-coins coin-consumer materialize?]
     :or {max-coins 300000000 materialize? true}}]
   (let [^InputStream input
         (if (instance? InputStream source)
           source
           (ByteArrayInputStream. ^bytes source))
         magic (read-bytes! input 5 :snapshot-magic)
         _ (when-not (= snapshot-magic magic)
             (codec/fail! :bitcoin.consensus/snapshot-magic
                          "Invalid UTXO snapshot magic." {:actual magic}))
         version (read-uint-le! input 2 :snapshot-version)
         _ (when-not (= snapshot-version version)
             (codec/fail! :bitcoin.consensus/snapshot-version
                          "Unsupported UTXO snapshot version."
                          {:actual version :supported snapshot-version}))
         actual-network-magic (read-bytes! input 4 :network-magic)
         _ (when-not (= (get network-magic network) actual-network-magic)
             (codec/fail! :bitcoin.consensus/snapshot-network
                          "UTXO snapshot network does not match the node."
                          {:network network :actual actual-network-magic}))
         base-natural (read-bytes! input 32 :base-blockhash)
         base-hash (displayed-hash base-natural)
         coin-count (read-uint-le! input 8 :coin-count)
         [height checkpoint]
         (checkpoint-for! network base-hash checkpoints)
         _ (when-not (= base-hash (header-at-height height))
             (codec/fail! :bitcoin.consensus/snapshot-header-mismatch
                          "Snapshot base is absent from the validated header chain."
                          {:height height :expected base-hash
                           :actual (header-at-height height)}))
         _ (when (> coin-count max-coins)
             (codec/fail! :bitcoin.consensus/snapshot-coin-limit
                          "Snapshot coin count exceeds its resource limit."
                          {:count coin-count :limit max-coins}))
         digest (MessageDigest/getInstance "SHA-256")
         result
         (loop [remaining coin-count
                previous-txid nil
                coins (when materialize? (transient {}))]
           (if (zero? remaining)
             (when materialize? (persistent! coins))
             (let [txid (read-bytes! input 32 :txid)
                   _ (when (and previous-txid
                                (not (neg? (compare previous-txid txid))))
                       (codec/fail! :bitcoin.consensus/snapshot-order
                                    "Snapshot transaction IDs are not strictly ordered."
                                    {:previous previous-txid :actual txid}))
                   output-count (read-compact-size! input :outputs-per-tx)
                   _ (when (or (zero? output-count)
                               (> output-count remaining))
                       (codec/fail! :bitcoin.consensus/snapshot-coin-count
                                    "Snapshot output group has an invalid size."
                                    {:group-count output-count
                                     :remaining remaining}))
                   [next-coins _]
                   (loop [left output-count
                          previous-vout nil
                          current coins]
                     (if (zero? left)
                       [current previous-vout]
                       (let [vout (read-compact-size! input :vout)
                             _ (when (> vout 0xfffffffe)
                                 (codec/fail!
                                  :bitcoin.consensus/snapshot-vout-range
                                  "Snapshot vout is outside uint32 range."
                                  {:vout vout}))
                             _ (when (and previous-vout
                                          (not (< previous-vout vout)))
                                 (codec/fail!
                                  :bitcoin.consensus/snapshot-order
                                  "Snapshot vouts are not strictly ordered."
                                  {:previous previous-vout :actual vout}))
                             coin (read-coin! input)
                             _ (when (> (:height coin) height)
                                 (codec/fail!
                                  :bitcoin.consensus/snapshot-coin-height
                                  "Snapshot coin height exceeds its base."
                                  {:coin-height (:height coin)
                                   :base-height height}))
                             key [txid (long vout)]
                             _ (update-digest!
                                digest (coin-hash-bytes txid vout coin))
                             _ (when coin-consumer
                                 (coin-consumer key coin))]
                         (recur (dec left) vout
                                (if materialize?
                                  (assoc! current key coin)
                                  current)))))]
               (recur (- remaining output-count) txid next-coins))))
         _ (when-not (= -1 (.read input))
             (codec/fail! :bitcoin.consensus/snapshot-trailing-data
                          "Snapshot has trailing data." {}))
         commitment
         (displayed-hash
          (.digest (MessageDigest/getInstance "SHA-256")
                   (.digest digest)))]
     (when-not (= (:hash-serialized checkpoint) commitment)
       (codec/fail! :bitcoin.consensus/snapshot-commitment
                    "Snapshot UTXO commitment does not match its trust anchor."
                    {:height height
                     :expected (:hash-serialized checkpoint)
                     :actual commitment}))
     {:utxo {:height height :coins result}
      :snapshot {:status :assumed
                 :network network
                 :base-height height
                 :base-blockhash base-hash
                 :coins-count (long coin-count)
                 :hash-serialized commitment
                 :chain-tx-count (:chain-tx-count checkpoint)}})))

(defn validate-background
  "Promote an assumed snapshot only after an independently fully validated
  chainstate reaches the same base and recomputes the exact commitment."
  [loaded fully-validated]
  (validate-background-commitment
   loaded
   (get-in fully-validated [:utxo :height])
   (:active-tip fully-validated)
   (hash-serialized (get-in fully-validated [:utxo :coins]))))

(defn- ancestor-hash-at-height [state tip height]
  (loop [hash tip]
    (let [node (get-in state [:nodes hash])]
      (cond
        (nil? node) nil
        (= height (:height node)) hash
        (< (:height node) height) nil
        :else (recur (:parent node))))))

(defn activate
  "Activate an authenticated snapshot on a headers-first chainstate.

  The caller must retain the original chainstate for background validation.
  Activation is refused unless the base is on the independently selected best
  header chain and has strictly more work than the current active tip."
  ([header-state loaded] (activate header-state loaded {}))
  ([header-state loaded
    {:keys [ancestor-hash-at-height-fn ancestry-hashes-fn
            activate-nodes-fn]}]
   (let [{:keys [base-height base-blockhash]} (:snapshot loaded)
        base-node (get-in header-state [:nodes base-blockhash])
        best-hash (:best-header header-state)
        best-base
        ((or ancestor-hash-at-height-fn ancestor-hash-at-height)
         header-state best-hash base-height)
        active-node (get-in header-state
                            [:nodes (:active-tip header-state)])]
    (when-not (and base-node (= base-height (:height base-node)))
      (codec/fail! :bitcoin.consensus/snapshot-base-header
                   "Snapshot base header is not indexed at its expected height."
                   {:height base-height :hash base-blockhash}))
    (when-not (= base-blockhash best-base)
      (codec/fail! :bitcoin.consensus/snapshot-not-best-chain
                   "Snapshot base is not on the best-work header chain."
                   {:height base-height :hash base-blockhash
                    :best-header best-hash}))
    (when-not (pos? (compare (:chainwork base-node)
                             (:chainwork active-node)))
      (codec/fail! :bitcoin.consensus/snapshot-work
                   "Snapshot base does not exceed active chain work."
                   {:base base-blockhash
                    :active (:active-tip header-state)}))
    (let [active-path
          (if ancestry-hashes-fn
            (ancestry-hashes-fn header-state base-blockhash)
            (loop [hash base-blockhash result #{}]
              (if (nil? hash)
                result
                (recur (get-in header-state [:nodes hash :parent])
                       (conj result hash)))))]
      (when-not (and (set? active-path)
                     (contains? active-path base-blockhash)
                     (contains? active-path (:active-tip header-state)))
        (codec/fail! :bitcoin.consensus/snapshot-ancestry
                     "Snapshot active ancestry proof is incomplete."
                     {:base base-blockhash
                      :genesis (:active-tip header-state)}))
      (-> header-state
          (assoc :active-tip base-blockhash
                 :utxo (:utxo loaded)
                 :snapshot (:snapshot loaded))
          (update :nodes
                  (fn [nodes]
                    (if activate-nodes-fn
                      (activate-nodes-fn nodes active-path)
                      (into {}
                            (map (fn [[hash node]]
                                   [hash
                                    (assoc node :active?
                                           (contains? active-path hash))]))
                            nodes)))))))))
