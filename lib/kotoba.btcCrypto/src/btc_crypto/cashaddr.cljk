(ns btc-crypto.cashaddr
  "CashAddr — Bitcoin Cash's address format. Needed because BCH abandoned
  Base58Check for its own encoding, so a BCH address cannot be produced by the
  Base58 or Bech32 code already in this library.

  It LOOKS like Bech32 and shares its charset, which is the trap: the checksum is
  a different code entirely — a 40-bit BCH code with its own five generator
  constants, against Bech32's 30-bit one. Reusing Bech32's polymod would produce
  strings that look exactly like valid addresses and are not.

  So the constants here are not transcribed on faith. They are validated in
  `test/btc_crypto/test_cashaddr.cljc` against a real BCH address that BOTH
  verifies under this checksum AND was accepted by a live THORChain node as a
  valid BCH destination (a node that rejects malformed addresses with \"unable to
  parse address\", making it a usable independent oracle). Decoding that address
  and re-encoding its hash reproduces it character for character; a wrong
  generator constant fails that immediately.

  :clj-only, matching the rest of this library — the 40-bit polymod needs real
  64-bit integer arithmetic, and ClojureScript's bitwise operators are 32-bit
  (the same hazard documented in eth-crypto.core, where a naive port would have
  silently computed wrong values rather than failing to compile)."
  (:require [btc-crypto.bech32 :as bech32]
            [kotoba.lang.text :as str]))

#?(:clj
(do

(def ^:private CHARSET "qpzry9x8gf2tvdw0s3jn54khce6mua7l")
(def ^:private CHARSET-IDX (into {} (map-indexed (fn [i c] [c i]) CHARSET)))

(def ^:private GEN
  "The five generator constants of CashAddr's 40-bit BCH code. NOT Bech32's."
  [0x98f2bc8e61 0x79b76d99e2 0xf33e5fb3c4 0xae2eabe2a8 0x1e4f43e470])

(def default-prefix "bitcoincash")

(defn- polymod ^long [values]
  (loop [c 1 vs (seq values)]
    (if vs
      (let [c0 (bit-shift-right c 35)
            c (bit-xor (bit-shift-left (bit-and c 0x07ffffffff) 5) (long (first vs)))
            c (loop [i 0 c c]
                (if (< i 5)
                  (recur (inc i)
                         (if (bit-test c0 i) (bit-xor c (nth GEN i)) c))
                  c))]
        (recur c (next vs)))
      (bit-xor c 1))))

(defn- expand-prefix
  "Prefix chars reduced to their low 5 bits, then a 0 separator."
  [^String prefix]
  (conj (mapv #(bit-and (int %) 0x1f) prefix) 0))

(defn- version-byte
  "CashAddr version byte: type in bits 3-7, hash-size code in bits 0-2.
  Only 160-bit hashes (code 0) are produced here — that is what a P2PKH or P2SH
  address of a compressed key is."
  ^long [type]
  (case type
    :p2pkh 0x00
    :p2sh  0x08
    (throw (ex-info "cashaddr: unsupported address type" {:type type}))))

(defn encode
  "hash160 bytes -> a CashAddr string including the `prefix:` part.
  `type` is :p2pkh (default) or :p2sh."
  (^String [hash160] (encode hash160 default-prefix :p2pkh))
  (^String [hash160 ^String prefix] (encode hash160 prefix :p2pkh))
  (^String [hash160 ^String prefix type]
   (let [bytes (map #(bit-and % 0xff) (seq hash160))]
     (when-not (= 20 (count bytes))
       (throw (ex-info "cashaddr: expected a 20-byte hash160" {:length (count bytes)})))
     (let [payload (cons (version-byte type) bytes)
           words (bech32/convert-bits payload 8 5 true)
           checksum (polymod (concat (expand-prefix prefix) words (repeat 8 0)))
           check-words (mapv (fn [i] (bit-and (bit-shift-right checksum (* 5 (- 7 i))) 0x1f))
                             (range 8))]
       (str prefix ":"
            (apply str (map #(nth CHARSET %) (concat words check-words))))))))

(defn decode
  "CashAddr string (with or without the `prefix:` part) ->
  {:prefix :type :hash160 (seq of ints)}. Throws on a bad checksum, which is the
  whole point: a mistyped address must not silently become a different one."
  ([^String address] (decode address default-prefix))
  ([^String address ^String default-pref]
   (let [[prefix body] (if (str/includes? address ":")
                         (str/split address #":" 2)
                         [default-pref address])
         body (str/lower body)
         words (mapv (fn [c]
                       (or (CHARSET-IDX c)
                           (throw (ex-info "cashaddr: character outside the charset"
                                           {:char c :address address}))))
                     body)]
     (when (< (count words) 9)
       (throw (ex-info "cashaddr: too short" {:address address})))
     (when-not (zero? (polymod (concat (expand-prefix prefix) words)))
       (throw (ex-info "cashaddr: checksum failed" {:address address :prefix prefix})))
     (let [payload (bech32/convert-bits (subvec words 0 (- (count words) 8)) 5 8 false)
           v (first payload)
           type (case (bit-and v 0x78) 0x00 :p2pkh 0x08 :p2sh :unknown)]
       {:prefix prefix
        :type type
        :version-byte v
        :hash160 (vec (rest payload))}))))

)) ;; end #?(:clj (do …))

#?(:cljs
   (do
     (defn- nope [n]
       (throw (ex-info (str "btc-crypto.cashaddr/" n " is :clj-only — the 40-bit BCH "
                            "polymod needs real 64-bit integer arithmetic, and cljs "
                            "bitwise operators are 32-bit (they would silently compute "
                            "wrong checksums rather than fail to compile)")
                       {})))
     (defn encode [& _] (nope "encode"))
     (defn decode [& _] (nope "decode"))))
