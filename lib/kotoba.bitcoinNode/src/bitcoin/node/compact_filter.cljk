(ns bitcoin.node.compact-filter
  "Bitcoin Core-compatible BIP157/158 basic compact block filters.

  Hashes and headers are represented in Bitcoin's natural byte order. Display
  hex therefore reverses these 32-byte values."
  (:require [bitcoin.consensus.codec :as codec]
            [sha256d.core :as sha256d])
  (:import [java.io ByteArrayOutputStream]
           [java.lang Long]))

(def basic-p 19)
(def basic-m 784931)
(def max-filter-elements 4000000)
(def ^:private uint64-modulus 18446744073709551616N)

(defn- fail! [type message data]
  (throw (ex-info message (assoc data :type type))))

(defn- add64 [left right]
  (unchecked-add (long left) (long right)))

(defn- sip-round [[v0 v1 v2 v3]]
  (let [v0 (add64 v0 v1)
        v1 (Long/rotateLeft v1 13)
        v1 (bit-xor v1 v0)
        v0 (Long/rotateLeft v0 32)
        v2 (add64 v2 v3)
        v3 (Long/rotateLeft v3 16)
        v3 (bit-xor v3 v2)
        v0 (add64 v0 v3)
        v3 (Long/rotateLeft v3 21)
        v3 (bit-xor v3 v0)
        v2 (add64 v2 v1)
        v1 (Long/rotateLeft v1 17)
        v1 (bit-xor v1 v2)
        v2 (Long/rotateLeft v2 32)]
    [v0 v1 v2 v3]))

(defn- sip-rounds [state count-value]
  (nth (iterate sip-round state) count-value))

(defn- little-endian-long [bytes offset length]
  (reduce
   (fn [result index]
     (bit-or result
             (bit-shift-left
              (long (nth bytes (+ offset index)))
              (* 8 index))))
   0
   (range length)))

(defn siphash-24
  "Return SipHash-2-4's signed 64-bit representation for `bytes`."
  [k0 k1 bytes]
  (let [bytes (vec bytes)
        length (count bytes)
        initial [(bit-xor 0x736f6d6570736575 (long k0))
                 (bit-xor 0x646f72616e646f6d (long k1))
                 (bit-xor 0x6c7967656e657261 (long k0))
                 (bit-xor 0x7465646279746573 (long k1))]
        full-length (- length (mod length 8))
        after-blocks
        (loop [offset 0 state initial]
          (if (= offset full-length)
            state
            (let [word (little-endian-long bytes offset 8)
                  [v0 v1 v2 v3] state
                  mixed (sip-rounds [v0 v1 v2 (bit-xor v3 word)] 2)
                  [v0 v1 v2 v3] mixed]
              (recur (+ offset 8)
                     [(bit-xor v0 word) v1 v2 v3]))))
        tail (bit-or
              (bit-shift-left (long (bit-and length 0xff)) 56)
              (little-endian-long bytes full-length (- length full-length)))
        [v0 v1 v2 v3] after-blocks
        compressed (sip-rounds [v0 v1 v2 (bit-xor v3 tail)] 2)
        [v0 v1 v2 v3] compressed
        finalized (sip-rounds [(bit-xor v0 tail) v1 (bit-xor v2 0xff) v3] 4)]
    (reduce bit-xor finalized)))

(defn- unsigned-long [value]
  (if (neg? value)
    (+ uint64-modulus (bigint value))
    (bigint value)))

(defn- hash-to-range [k0 k1 range-size element]
  (if (zero? range-size)
    0N
    (quot (* (unsigned-long (siphash-24 k0 k1 element))
             (bigint range-size))
          uint64-modulus)))

(defn- key-pair [block-hash]
  (when-not (= 32 (count block-hash))
    (fail! :bitcoin.node/compact-filter-block-hash
           "A compact filter requires a 32-byte block hash."
           {:length (count block-hash)}))
  [(little-endian-long block-hash 0 8)
   (little-endian-long block-hash 8 8)])

(defn- bit-writer []
  {:output (ByteArrayOutputStream.)
   :state (long-array 2)})

(defn- write-bit! [{:keys [^ByteArrayOutputStream output state]} bit]
  (let [used (aget ^longs state 1)
        current (aget ^longs state 0)
        current (if (zero? bit)
                  current
                  (bit-or current (bit-shift-left 1 (- 7 used))))
        used (inc used)]
    (if (= 8 used)
      (do
        (.write output (int current))
        (aset-long ^longs state 0 0)
        (aset-long ^longs state 1 0))
      (do
        (aset-long ^longs state 0 current)
        (aset-long ^longs state 1 used)))))

(defn- finish-bits! [{:keys [^ByteArrayOutputStream output state]}]
  (when (pos? (aget ^longs state 1))
    (.write output (int (aget ^longs state 0))))
  (mapv #(bit-and 0xff %) (.toByteArray output)))

(defn- encode-deltas [values]
  (let [writer (bit-writer)]
    (loop [remaining values previous 0N]
      (if-let [value (first remaining)]
        (let [delta (- value previous)
              quotient (quot delta (bit-shift-left 1 basic-p))
              remainder (long (mod delta (bit-shift-left 1 basic-p)))]
          (dotimes [_ (long quotient)]
            (write-bit! writer 1))
          (write-bit! writer 0)
          (doseq [position (range (dec basic-p) -1 -1)]
            (write-bit! writer
                        (if (bit-test remainder position) 1 0)))
          (recur (next remaining) value))
        (finish-bits! writer)))))

(defn encode
  "Encode a deduplicated GCS element collection using BIP158 basic parameters."
  [block-hash elements]
  (let [elements (set (map vec elements))
        count-value (count elements)]
    (when (> count-value max-filter-elements)
      (fail! :bitcoin.node/compact-filter-resource-limit
             "Compact filter element count exceeds the block-derived limit."
             {:count count-value :limit max-filter-elements}))
    (let [[k0 k1] (key-pair block-hash)
          range-size (*' count-value basic-m)
          values (sort (map #(hash-to-range k0 k1 range-size %) elements))]
      (into (codec/compact-size count-value)
            (encode-deltas values)))))

(defn basic-elements
  "Return Core's deduplicated basic-filter elements for a parsed block.

  `prev-output-scripts` must contain the spent output scripts for every
  non-coinbase input in block order. Empty scripts are omitted. Created
  OP_RETURN and empty outputs are omitted."
  [parsed-block prev-output-scripts]
  (set
   (concat
    (for [transaction (:transactions parsed-block)
          output (:outputs transaction)
          :let [script (:script-pubkey output)]
          :when (and (seq script) (not= 0x6a (first script)))]
      (vec script))
    (for [script prev-output-scripts :when (seq script)]
      (vec script)))))

(defn build-basic
  "Build the encoded BIP158 basic filter for `parsed-block`."
  [parsed-block prev-output-scripts]
  (encode (get-in parsed-block [:header :hash])
          (basic-elements parsed-block prev-output-scripts)))

(defn- read-bit!
  [bytes start state]
  (let [byte-offset (aget ^longs state 0)
        bit-offset (aget ^longs state 1)
        absolute (+ start byte-offset)]
    (when (>= absolute (count bytes))
      (fail! :bitcoin.node/truncated-compact-filter
             "Compact filter bitstream is truncated."
             {:offset absolute :length (count bytes)}))
    (let [bit (if (bit-test (nth bytes absolute) (- 7 bit-offset)) 1 0)
          next-bit (inc bit-offset)]
      (if (= 8 next-bit)
        (do (aset-long ^longs state 0 (inc byte-offset))
            (aset-long ^longs state 1 0))
        (aset-long ^longs state 1 next-bit))
      bit)))

(defn- consumed-byte-count [state]
  (+ (aget ^longs state 0)
     (if (pos? (aget ^longs state 1)) 1 0)))

(defn decode-values
  "Strictly decode an encoded basic filter and return its sorted mapped values.

  Noncanonical CompactSize, truncation, count overflow, value overflow, and
  excess whole bytes fail closed. As in Core, unused bits in the final byte
  are padding."
  [encoded]
  (let [encoded (vec encoded)
        [count-value start] (codec/read-compact-size encoded 0)]
    (when (> count-value max-filter-elements)
      (fail! :bitcoin.node/compact-filter-resource-limit
             "Compact filter element count exceeds the block-derived limit."
             {:count count-value :limit max-filter-elements}))
    (let [state (long-array 2)
          range-size (*' count-value basic-m)
          values
          (loop [index 0 previous 0N result (transient [])]
            (if (= index count-value)
              (persistent! result)
              (let [quotient
                    (loop [value 0N]
                      (if (zero? (read-bit! encoded start state))
                        value
                        (recur (inc value))))
                    remainder
                    (loop [position 0 value 0N]
                      (if (= position basic-p)
                        value
                        (recur (inc position)
                               (+ (* value 2)
                                  (read-bit! encoded start state)))))
                    value (+ previous
                             (* quotient (bit-shift-left 1 basic-p))
                             remainder)]
                (when (or (< value previous)
                          (and (pos? count-value) (>= value range-size)))
                  (fail! :bitcoin.node/invalid-compact-filter
                         "Compact filter value exceeds its mapped range."
                         {:index index :value value :range range-size}))
                (recur (inc index) value (conj! result value)))))]
      (when-not (= (count encoded) (+ start (consumed-byte-count state)))
        (fail! :bitcoin.node/compact-filter-trailing-data
               "Compact filter contains excess encoded bytes."
               {:consumed (+ start (consumed-byte-count state))
                :length (count encoded)}))
      {:count (long count-value) :range range-size :values values})))

(defn match-any?
  "Return true when an encoded basic filter may contain any query element."
  [block-hash encoded elements]
  (let [{:keys [count range values]} (decode-values encoded)]
    (if (or (zero? count) (empty? elements))
      false
      (let [[k0 k1] (key-pair block-hash)
            queries (set (map #(hash-to-range k0 k1 range (vec %)) elements))]
        (boolean (some queries values))))))

(defn match?
  "Return true when an encoded basic filter may contain `element`."
  [block-hash encoded element]
  (match-any? block-hash encoded [element]))

(defn filter-hash
  "Return the double-SHA256 of an encoded filter in natural byte order."
  [encoded]
  (vec (sha256d/sha256d-bytes (vec encoded))))

(defn filter-header
  "Compute a BIP157 filter header from an encoded filter and previous header.

  `previous-header` and the return value use natural byte order."
  [encoded previous-header]
  (when-not (= 32 (count previous-header))
    (fail! :bitcoin.node/compact-filter-header
           "The previous compact filter header must contain 32 bytes."
           {:length (count previous-header)}))
  (vec
   (sha256d/sha256d-bytes
    (into (filter-hash encoded) previous-header))))

(defn next-header-from-hash
  "Compute the next BIP157 filter header from a natural-order filter hash."
  [filter-hash-value previous-header]
  (when-not (and (= 32 (count filter-hash-value))
                 (= 32 (count previous-header)))
    (fail! :bitcoin.node/compact-filter-header
           "Compact filter hashes and previous headers must contain 32 bytes."
           {:filter-hash-length (count filter-hash-value)
            :previous-header-length (count previous-header)}))
  (vec
   (sha256d/sha256d-bytes
    (into (vec filter-hash-value) previous-header))))
