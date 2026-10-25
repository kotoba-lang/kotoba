(ns btc-mining.core
  "CPU proof-of-work mining engine — education/verification scope (per the
  ADR: not sized or claimed to be ASIC-competitive; a real deployment mines
  via ASIC hashrate and uses this only for the pool/job-template side, see
  kotoba-lang/mining-pool). Block header assembly, merkle root (with
  Bitcoin's odd-leaf-duplication quirk), bits<->target conversion, and a
  CPU nonce search. Builds on btc-crypto's SHA256d.

  PORTABILITY: :clj-only (wrapped #?(:clj (do ...)) with throwing :cljs
  stubs of the same names, matching eth-crypto.core's precedent) —
  needs java.math.BigInteger, and its btc-crypto.core dep is itself
  :clj-only for the same reason."
  (:require [btc-crypto.core :as btc])
  #?(:clj (:import (java.math BigInteger))))

#?(:clj
(do

;; ─── header (de)serialization (80 bytes: version+prevhash+merkle+time+bits+nonce) ───

(defn- u32-le ^bytes [^long v]
  (byte-array [(unchecked-byte v) (unchecked-byte (bit-shift-right v 8))
               (unchecked-byte (bit-shift-right v 16)) (unchecked-byte (bit-shift-right v 24))]))

(defn- parse-u32-le ^long [^bytes b ^long off]
  (bit-or (bit-and (aget b off) 0xff)
          (bit-shift-left (bit-and (aget b (+ off 1)) 0xff) 8)
          (bit-shift-left (bit-and (aget b (+ off 2)) 0xff) 16)
          (bit-shift-left (bit-and (aget b (+ off 3)) 0xff) 24)))

(defn- concat-bytes ^bytes [arrays]
  (let [total (reduce (fn [^long n ^bytes a] (+ n (alength a))) 0 arrays)
        out (byte-array total)]
    (loop [off 0 as arrays]
      (if (seq as)
        (let [^bytes a (first as)]
          (System/arraycopy a 0 out off (alength a))
          (recur (+ off (alength a)) (rest as)))
        out))))

(defn serialize-header
  "80-byte block header from {:version :prev-hash(32B, internal order)
  :merkle-root(32B, internal order) :time :bits :nonce}."
  ^bytes [{:keys [version prev-hash merkle-root time bits nonce]}]
  (concat-bytes [(u32-le version) prev-hash merkle-root (u32-le time) (u32-le bits) (u32-le nonce)]))

(defn parse-header
  "Inverse of `serialize-header`."
  [^bytes header]
  {:version (parse-u32-le header 0)
   :prev-hash (java.util.Arrays/copyOfRange header 4 36)
   :merkle-root (java.util.Arrays/copyOfRange header 36 68)
   :time (parse-u32-le header 68)
   :bits (parse-u32-le header 72)
   :nonce (parse-u32-le header 76)})

(defn header-hash
  "SHA256d of the serialized header, in internal (as-computed) byte order."
  ^bytes [header-map] (btc/sha256d (serialize-header header-map)))

(defn display-hash
  "The conventional big-endian display form of a hash (block hash / txid),
  i.e. the byte-reversal of the internal SHA256d output."
  ^bytes [^bytes internal-hash] (byte-array (reverse (seq internal-hash))))

;; ─── merkle root ──────────────────────────────────────────────────────────

(defn merkle-root
  "Bitcoin merkle root of `leaves` (txids, internal byte order, dSHA256
  already applied). A level with an odd number of nodes duplicates the last
  one before pairing (the historical Bitcoin quirk — CVE-2012-2459)."
  ^bytes [leaves]
  (if (= 1 (count leaves))
    (first leaves)
    (let [level (vec leaves)
          level (if (odd? (count level)) (conj level (peek level)) level)
          next-level (mapv (fn [[a b]] (btc/sha256d (concat-bytes [a b]))) (partition 2 level))]
      (recur next-level))))

;; ─── bits (compact) <-> target ────────────────────────────────────────────

(defn bits->target
  "Decode Bitcoin's compact 'bits' representation to the 256-bit target
  (java.math.BigInteger). bits = exponent(1 byte, MSB) + mantissa(3 bytes)."
  ^BigInteger [^long bits]
  (let [exponent (bit-and (unsigned-bit-shift-right bits 24) 0xff)
        mantissa (bit-and bits 0x00ffffff)]
    (if (<= exponent 3)
      (BigInteger/valueOf (unsigned-bit-shift-right mantissa (* 8 (- 3 exponent))))
      (.shiftLeft (BigInteger/valueOf mantissa) (* 8 (- exponent 3))))))

(def max-target-difficulty-1
  "The difficulty-1 target (bits 0x1d00ffff) — genesis-block difficulty."
  (bits->target 0x1d00ffff))

(defn difficulty
  "Bitcoin 'difficulty' relative to the genesis (difficulty-1) target."
  [^long bits]
  (double (/ (.doubleValue ^BigInteger max-target-difficulty-1)
             (.doubleValue ^BigInteger (bits->target bits)))))

(defn meets-target?
  "True if `header-hash` (internal byte order, as from `header-hash`)
  satisfies the proof-of-work target for `bits`."
  [^bytes internal-hash ^long bits]
  (let [as-int (BigInteger. 1 (display-hash internal-hash))]
    (<= (.compareTo as-int (bits->target bits)) 0)))

;; ─── CPU nonce search ─────────────────────────────────────────────────────

(defn mine
  "Search nonces [0, max-nonce) for one where `header-hash` meets `bits`'s
  target. Returns the winning header map, or nil if the 32-bit nonce space
  (or `max-nonce` if smaller) is exhausted — caller rolls the extranonce
  (rebuild the merkle root with a new coinbase) or `:time` and retries.
  CPU-only: this is an education/verification-scope search, not sized for
  ASIC-competitive throughput (see the ADR)."
  ([header] (mine header 0x100000000))
  ([{:keys [bits] :as header} max-nonce]
   (loop [nonce 0]
     (cond
       (>= nonce max-nonce) nil
       (meets-target? (header-hash (assoc header :nonce nonce)) bits) (assoc header :nonce nonce)
       :else (recur (inc nonce))))))

;; ─── getblocktemplate-shaped input -> header ──────────────────────────────

(defn template->header
  "Build an (unsolved, :nonce 0) header map from a getblocktemplate-shaped
  input: {:version :previousblockhash(32B internal) :bits :curtime
  :transactions [{:txid(32B internal) ...} ...]} (coinbase tx is expected to
  already be `(first transactions)`, as getblocktemplate callers construct
  it after picking a coinbase payout)."
  [{:keys [version previousblockhash bits curtime transactions]}]
  {:version version
   :prev-hash previousblockhash
   :merkle-root (merkle-root (map :txid transactions))
   :time curtime
   :bits bits
   :nonce 0})

) ;; end do
:cljs
(do
  (defn serialize-header [& _] (throw (ex-info "btc-mining.core/serialize-header is :clj-only" {})))
  (defn parse-header [& _] (throw (ex-info "btc-mining.core/parse-header is :clj-only" {})))
  (defn header-hash [& _] (throw (ex-info "btc-mining.core/header-hash is :clj-only (btc-crypto.core)" {})))
  (defn display-hash [& _] (throw (ex-info "btc-mining.core/display-hash is :clj-only" {})))
  (defn merkle-root [& _] (throw (ex-info "btc-mining.core/merkle-root is :clj-only (btc-crypto.core)" {})))
  (defn bits->target [& _] (throw (ex-info "btc-mining.core/bits->target is :clj-only (java.math.BigInteger)" {})))
  (def max-target-difficulty-1 nil)
  (defn difficulty [& _] (throw (ex-info "btc-mining.core/difficulty is :clj-only (java.math.BigInteger)" {})))
  (defn meets-target? [& _] (throw (ex-info "btc-mining.core/meets-target? is :clj-only (java.math.BigInteger)" {})))
  (defn mine [& _] (throw (ex-info "btc-mining.core/mine is :clj-only" {})))
  (defn template->header [& _] (throw (ex-info "btc-mining.core/template->header is :clj-only" {})))))
