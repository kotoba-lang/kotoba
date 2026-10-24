(ns btc-crypto.tx
  "Minimal Bitcoin transaction serialization + signing: classic (pre-segwit)
  SIGHASH_ALL for P2PKH inputs, and BIP-143 SIGHASH_ALL for native P2WPKH
  inputs. Reuses eth-crypto's RFC-6979 deterministic ECDSA (`secp256k1-sign`)
  for the signature math — Bitcoin and Ethereum sign the same secp256k1
  curve with the same deterministic-nonce scheme, so the same primitive
  produces Bitcoin-consensus-valid signatures once DER-encoded.

  Scope: SIGHASH_ALL only, single scriptCode style (P2PKH / P2WPKH-in-P2PKH-
  shape scriptCode), no P2SH/P2SH-wrapped-segwit/P2TR/multisig. See the ADR's
  out-of-scope list.

  PORTABILITY: :clj-only (wrapped #?(:clj (do ...)) with throwing :cljs
  stubs of the same names, matching eth-crypto.core's precedent) — its
  btc-crypto.core dep is itself :clj-only for the same reason."
  (:require [eth-crypto.core :as eth]
            [btc-crypto.core :as btc])
  #?(:clj (:import (java.math BigInteger))))

(def sighash-all 0x01)

#?(:clj
(do

;; ─── little-endian integer + varint primitives ───────────────────────────────

(defn- u32-le ^bytes [^long v]
  (byte-array [(unchecked-byte v) (unchecked-byte (bit-shift-right v 8))
               (unchecked-byte (bit-shift-right v 16)) (unchecked-byte (bit-shift-right v 24))]))

(defn- u64-le ^bytes [^long v]
  (byte-array (map #(unchecked-byte (bit-shift-right v (* 8 %))) (range 8))))

(defn varint
  "Bitcoin CompactSize varint encoding of a non-negative integer."
  ^bytes [^long n]
  (cond
    (< n 0xfd) (byte-array [(unchecked-byte n)])
    (<= n 0xffff) (byte-array (cons (unchecked-byte 0xfd) (seq (byte-array [(unchecked-byte n) (unchecked-byte (bit-shift-right n 8))]))))
    (<= n 0xffffffff) (byte-array (cons (unchecked-byte 0xfe) (seq (u32-le n))))
    :else (byte-array (cons (unchecked-byte 0xff) (seq (u64-le n))))))

(defn- concat-bytes ^bytes [arrays]
  (let [total (reduce (fn [^long n ^bytes a] (+ n (alength a))) 0 arrays)
        out (byte-array total)]
    (loop [off 0 as arrays]
      (if (seq as)
        (let [^bytes a (first as)]
          (System/arraycopy a 0 out off (alength a))
          (recur (+ off (alength a)) (rest as)))
        out))))

(defn- reverse-bytes ^bytes [^bytes b] (byte-array (reverse (seq b))))

;; ─── scripts ──────────────────────────────────────────────────────────────

(defn p2pkh-script
  "The classic P2PKH scriptPubKey / legacy sighash scriptCode:
  OP_DUP OP_HASH160 <20-byte hash> OP_EQUALVERIFY OP_CHECKSIG."
  ^bytes [^bytes pubkey-hash160]
  (concat-bytes [(byte-array [(unchecked-byte 0x76) (unchecked-byte 0xa9) (unchecked-byte 0x14)])
                 pubkey-hash160
                 (byte-array [(unchecked-byte 0x88) (unchecked-byte 0xac)])]))

;; ─── outpoint / output serialization ─────────────────────────────────────

(defn- serialize-outpoint ^bytes [{:keys [txid vout]}]
  ;; txid as conventionally displayed is big-endian; on the wire it's reversed (LE).
  (concat-bytes [(reverse-bytes txid) (u32-le vout)]))

(defn- serialize-output ^bytes [{:keys [value script-pubkey]}]
  (concat-bytes [(u64-le value) (varint (alength ^bytes script-pubkey)) script-pubkey]))

(defn- with-length-prefix ^bytes [^bytes data]
  (concat-bytes [(varint (alength data)) data]))

;; ─── classic (non-witness) SIGHASH_ALL ───────────────────────────────────

(defn legacy-sighash
  "Classic pre-BIP143 SIGHASH_ALL preimage hash for input `input-index`:
  serialize the whole tx with that input's scriptSig replaced by
  `script-code` and every other input's scriptSig emptied, append the 4-byte
  little-endian sighash type, SHA256d. `tx` is {:version :inputs
  [{:txid :vout :sequence}] :outputs [{:value :script-pubkey}] :locktime}."
  ^bytes [{:keys [version inputs outputs locktime]} ^long input-index ^bytes script-code sighash-type]
  (let [ins (map-indexed
             (fn [i {:keys [sequence] :as in}]
               (concat-bytes [(serialize-outpoint in)
                              (with-length-prefix (if (= i input-index) script-code (byte-array 0)))
                              (u32-le sequence)]))
             inputs)
        outs (map serialize-output outputs)
        body (concat-bytes (concat [(u32-le version) (varint (count inputs))]
                                    ins
                                    [(varint (count outputs))]
                                    outs
                                    [(u32-le locktime) (u32-le sighash-type)]))]
    (btc/sha256d body)))

;; ─── BIP-143 (native P2WPKH) SIGHASH_ALL ─────────────────────────────────

(defn bip143-preimage
  "The BIP-143 sighash preimage for a P2WPKH (or P2WPKH-shaped scriptCode)
  input. `tx` as in `legacy-sighash`; `amount` is the spent output's value in
  satoshi (part of what BIP-143 commits to, unlike the legacy algorithm)."
  ^bytes [{:keys [version inputs outputs locktime]} input-index script-code amount sighash-type]
  (let [{:keys [sequence] :as this-in} (nth inputs input-index)
        hash-prevouts (btc/sha256d (concat-bytes (map serialize-outpoint inputs)))
        hash-sequence (btc/sha256d (concat-bytes (map (fn [{:keys [sequence]}] (u32-le sequence)) inputs)))
        hash-outputs (btc/sha256d (concat-bytes (map serialize-output outputs)))]
    (concat-bytes [(u32-le version)
                   hash-prevouts
                   hash-sequence
                   (serialize-outpoint this-in)
                   (with-length-prefix script-code)
                   (u64-le amount)
                   (u32-le sequence)
                   hash-outputs
                   (u32-le locktime)
                   (u32-le sighash-type)])))

(defn bip143-sighash
  ^bytes [tx input-index script-code amount sighash-type]
  (btc/sha256d (bip143-preimage tx input-index script-code amount sighash-type)))

;; ─── DER signature encoding + signing ────────────────────────────────────

(defn- der-int ^bytes [^BigInteger n]
  (let [^bytes raw (.toByteArray n)]
    (concat-bytes [(byte-array [(unchecked-byte 0x02) (unchecked-byte (alength raw))]) raw])))

(defn der-encode-sig
  "DER-encode an (r, s) ECDSA signature (as returned by eth-crypto's
  `secp256k1-sign`, which already normalizes to low-s)."
  ^bytes [{:keys [r s]}]
  (let [rb (der-int r) sb (der-int s)
        body (concat-bytes [rb sb])]
    (concat-bytes [(byte-array [(unchecked-byte 0x30) (unchecked-byte (alength body))]) body])))

(defn sign-legacy-p2pkh
  "Sign input `input-index` of `tx` spending a P2PKH output, SIGHASH_ALL.
  Returns {:der-sig-with-type bytes :pubkey compressed-pubkey-bytes}."
  [tx ^long input-index ^bytes privkey]
  (let [pubkey (btc/compressed-pubkey privkey)
        script-code (p2pkh-script (btc/hash160 pubkey))
        sighash (legacy-sighash tx input-index script-code sighash-all)
        sig (eth/secp256k1-sign privkey sighash)]
    {:der-sig-with-type (concat-bytes [(der-encode-sig sig) (byte-array [(unchecked-byte sighash-all)])])
     :pubkey pubkey}))

(defn sign-p2wpkh
  "Sign input `input-index` of `tx` spending a P2WPKH output of `amount`
  satoshi, BIP-143 SIGHASH_ALL. Returns {:witness [der-sig-with-type
  compressed-pubkey]} — the two-element witness stack for a P2WPKH input."
  [tx ^long input-index ^long amount ^bytes privkey]
  (let [pubkey (btc/compressed-pubkey privkey)
        script-code (p2pkh-script (btc/hash160 pubkey)) ; BIP-143: scriptCode for P2WPKH == P2PKH script of the same hash
        sighash (bip143-sighash tx input-index script-code amount sighash-all)
        sig (eth/secp256k1-sign privkey sighash)]
    {:witness [(concat-bytes [(der-encode-sig sig) (byte-array [(unchecked-byte sighash-all)])]) pubkey]}))

) ;; end do
:cljs
(do
  (defn varint [& _] (throw (ex-info "btc-crypto.tx/varint is :clj-only" {})))
  (defn p2pkh-script [& _] (throw (ex-info "btc-crypto.tx/p2pkh-script is :clj-only" {})))
  (defn legacy-sighash [& _] (throw (ex-info "btc-crypto.tx/legacy-sighash is :clj-only" {})))
  (defn bip143-preimage [& _] (throw (ex-info "btc-crypto.tx/bip143-preimage is :clj-only" {})))
  (defn bip143-sighash [& _] (throw (ex-info "btc-crypto.tx/bip143-sighash is :clj-only" {})))
  (defn der-encode-sig [& _] (throw (ex-info "btc-crypto.tx/der-encode-sig is :clj-only (java.math.BigInteger)" {})))
  (defn sign-legacy-p2pkh [& _] (throw (ex-info "btc-crypto.tx/sign-legacy-p2pkh is :clj-only" {})))
  (defn sign-p2wpkh [& _] (throw (ex-info "btc-crypto.tx/sign-p2wpkh is :clj-only" {})))))
