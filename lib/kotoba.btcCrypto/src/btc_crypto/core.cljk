(ns btc-crypto.core
  "Bitcoin address/key encoding: SHA256d, HASH160, WIF, and P2PKH/P2WPKH
  address derivation. Reuses eth-crypto's secp256k1 point arithmetic
  (`private->public` — same curve as Ethereum) for the public-key math, and
  kotoba.lang.crypto for SHA-256.

  PORTABILITY: :clj-only (wrapped #?(:clj (do ...)) with throwing :cljs
  stubs of the same names, matching eth-crypto.core's precedent) — its
  ripemd160/base58 deps are themselves :clj-only for the same reason."
  (:require [eth-crypto.core :as eth]
            [btc-crypto.ripemd160 :as ripemd]
            [btc-crypto.base58 :as base58]
            [btc-crypto.bech32 :as bech32]
            [btc-crypto.cashaddr :as cashaddr]
            [kotoba.lang.crypto :as kc])
  #?(:clj (:import (java.util Arrays))))

#?(:clj
(do

(defn sha256d
  "Double SHA-256 (Bitcoin's block-hash / txid / checksum digest)."
  ^bytes [^bytes data] (kc/hash :sha256 (kc/hash :sha256 data)))

(defn hash160
  "RIPEMD160(SHA256(data)) — Bitcoin's \"HASH160\", used for P2PKH/P2WPKH
  pubkey hashes."
  ^bytes [^bytes data] (ripemd/ripemd160 (kc/hash :sha256 data)))

(defn compressed-pubkey
  "Compressed (33-byte, 0x02/0x03-prefixed) secp256k1 public key for a
  32-byte private key."
  ^bytes [^bytes privkey]
  (let [uncompressed (eth/private->public privkey) ; 64 bytes X(32)||Y(32)
        y-last (aget uncompressed 63)
        prefix (unchecked-byte (if (even? (bit-and (long y-last) 1)) 0x02 0x03))
        out (byte-array 33)]
    (aset-byte out 0 prefix)
    (System/arraycopy uncompressed 0 out 1 32)
    out))

;; ─── WIF (Wallet Import Format) ──────────────────────────────────────────────

(def networks
  "Per-network constants. Bitcoin-fork chains differ ONLY in these values plus the
  address encoding — the secp256k1 math, HASH160, Base58Check and Bech32 code above
  is shared unchanged, which is why adding a chain here is cheap.

  Every constant below was MEASURED, not transcribed from memory:

  - `:p2pkh-version` was read out of a real address of that chain by
    Base58Check-decoding it and taking the leading byte (Bitcoin's 0x00 served as
    the control, and came out right).
  - each address format was then validated by a live THORChain node ACCEPTING a
    derived address as a destination for that chain. The node rejects a malformed
    one (`unable to parse address`), and it discriminates: a Dogecoin-versioned
    address offered as a Litecoin destination was refused, and an early Litecoin
    attempt that reused Bitcoin's bech32 checksum with the `ltc` HRP was caught the
    same way.

  `:wif-version` is deliberately ABSENT for the forks. WIF is a key-export format,
  no oracle validates it, and the conventional `P2PKH version + 0x80` relationship
  is not something to assert unmeasured — `wif-encode` therefore refuses those
  networks rather than emitting a plausible-looking string.

  SIGNING, and where it stops: Litecoin and Dogecoin use Bitcoin's transaction
  format and sighash unchanged, so `btc-crypto.tx` works for them as-is (the
  network only affects addresses). **Bitcoin Cash does not** — it requires
  SIGHASH_FORKID with a BCH-specific digest, which this library does not implement.
  BCH here is RECEIVE-ONLY: you can derive an address to be paid at, and must not
  assume you can spend from it."
  {:mainnet      {:coin :bitcoin       :p2pkh-version 0x00 :wif-version 0x80
                  :bech32-hrp "bc" :segwit? true  :encoding :base58}
   :testnet      {:coin :bitcoin       :p2pkh-version 0x6f :wif-version 0xef
                  :bech32-hrp "tb" :segwit? true  :encoding :base58}
   :litecoin     {:coin :litecoin      :p2pkh-version 0x30
                  :bech32-hrp "ltc" :segwit? true  :encoding :base58}
   :dogecoin     {:coin :dogecoin      :p2pkh-version 0x1e
                  :segwit? false :encoding :base58}
   :bitcoin-cash {:coin :bitcoin-cash  :p2pkh-version 0x00
                  :cashaddr-prefix "bitcoincash" :segwit? false :encoding :cashaddr
                  :spendable? false}})

(defn network
  "Look up a network's constants, refusing an unknown one rather than returning nil
  and deriving an address on a silently-missing version byte."
  [net]
  (or (get networks net)
      (throw (ex-info (str "btc-crypto: unknown network " (pr-str net))
                      {:known (sort (keys networks))}))))

(def ^:private WIF-VERSION {:mainnet 0x80 :testnet 0xef})

(defn wif-encode
  "WIF-encode a 32-byte private key. `compressed?` (default true) marks that
  the corresponding public key should be used in compressed form."
  (^String [privkey] (wif-encode privkey :mainnet true))
  (^String [privkey network] (wif-encode privkey network true))
  (^String [^bytes privkey network compressed?]
   (let [version (or (get WIF-VERSION network)
                     (throw (ex-info
                             (str "btc-crypto: no measured WIF version byte for " network
                                  " — WIF is a key-export format with no oracle to validate"
                                  " it against, and the conventional relationship to the"
                                  " P2PKH version is not asserted here. Only :mainnet and"
                                  " :testnet (Bitcoin) have one.")
                             {:network network :known (sort (keys WIF-VERSION))})))
         suffix (if compressed? [(byte 0x01)] [])
         payload (byte-array (concat [(unchecked-byte version)] (seq privkey) suffix))]
     (base58/encode-check payload))))

(defn wif-decode
  "Decode a WIF string. Returns {:private-key bytes32 :network :mainnet|:testnet
  :compressed? bool}."
  [^String s]
  (let [payload (base58/decode-check s)
        n (alength payload)]
    ;; Length must be validated BEFORE any `aget` on payload -- a
    ;; Base58Check-valid string can still decode to a too-short (even
    ;; zero-length) payload, and `aget` on an empty array throws a raw
    ;; ArrayIndexOutOfBoundsException instead of this fn's own intended
    ;; ex-info.
    (when-not (contains? #{33 34} n) (throw (ex-info "wif: bad payload length" {:len n})))
    (let [version (bit-and (long (aget payload 0)) 0xff)
          network (some (fn [[k v]] (when (= v version) k)) WIF-VERSION)
          compressed? (and (= n 34) (= 1 (bit-and (long (aget payload 33)) 0xff)))]
      (when (nil? network) (throw (ex-info "wif: unknown version byte" {:version version})))
      {:private-key (Arrays/copyOfRange payload 1 33) :network network :compressed? compressed?})))

;; ─── addresses ────────────────────────────────────────────────────────────

(defn p2pkh-address
  "Legacy Base58Check P2PKH address for a compressed public key."
  (^String [pubkey] (p2pkh-address pubkey :mainnet))
  (^String [^bytes pubkey net]
   (base58/encode-check
    (byte-array (cons (unchecked-byte (:p2pkh-version (network net)))
                      (seq (hash160 pubkey)))))))

(defn p2wpkh-address
  "Native SegWit v0 (bech32) P2WPKH address for a compressed public key. Refuses a
  network without SegWit (Dogecoin, Bitcoin Cash) instead of inventing an HRP."
  (^String [pubkey] (p2wpkh-address pubkey :mainnet))
  (^String [^bytes pubkey net]
   (let [{:keys [bech32-hrp segwit?]} (network net)]
     (when-not (and segwit? bech32-hrp)
       (throw (ex-info (str "btc-crypto: " net " has no SegWit / bech32 address form")
                       {:network net})))
     (bech32/encode-segwit-address bech32-hrp 0 (seq (hash160 pubkey))))))

(defn cashaddr-address
  "CashAddr (Bitcoin Cash) address for a compressed public key."
  (^String [pubkey] (cashaddr-address pubkey :bitcoin-cash))
  (^String [^bytes pubkey net]
   (let [{:keys [cashaddr-prefix]} (network net)]
     (when-not cashaddr-prefix
       (throw (ex-info (str "btc-crypto: " net " does not use CashAddr") {:network net})))
     (cashaddr/encode (hash160 pubkey) cashaddr-prefix :p2pkh))))

(defn address-of-privkey
  "Addresses for a 32-byte private key on `net`, as a map of the forms that network
  actually HAS — `:p2wpkh` is absent for Dogecoin (no SegWit) and `:cashaddr`
  appears only for Bitcoin Cash. Returning a map of only-real forms is deliberate:
  a nil or fabricated address for a form the chain does not support is how funds
  get sent somewhere unspendable."
  ([privkey] (address-of-privkey privkey :mainnet))
  ([privkey net]
   (let [{:keys [encoding segwit?]} (network net)
         pubkey (compressed-pubkey privkey)]
     (cond-> {}
       (= :base58 encoding)   (assoc :p2pkh (p2pkh-address pubkey net))
       (= :cashaddr encoding) (assoc :cashaddr (cashaddr-address pubkey net))
       segwit?                (assoc :p2wpkh (p2wpkh-address pubkey net))))))

) ;; end do
:cljs
(do
  (defn sha256d [& _] (throw (ex-info "btc-crypto.core/sha256d is :clj-only" {})))
  (defn hash160 [& _] (throw (ex-info "btc-crypto.core/hash160 is :clj-only (btc-crypto.ripemd160)" {})))
  (defn compressed-pubkey [& _] (throw (ex-info "btc-crypto.core/compressed-pubkey is :clj-only" {})))
  (defn wif-encode [& _] (throw (ex-info "btc-crypto.core/wif-encode is :clj-only (btc-crypto.base58)" {})))
  (defn wif-decode [& _] (throw (ex-info "btc-crypto.core/wif-decode is :clj-only (btc-crypto.base58)" {})))
  (defn p2pkh-address [& _] (throw (ex-info "btc-crypto.core/p2pkh-address is :clj-only (btc-crypto.base58)" {})))
  (defn p2wpkh-address [& _] (throw (ex-info "btc-crypto.core/p2wpkh-address is :clj-only" {})))
  (defn address-of-privkey [& _] (throw (ex-info "btc-crypto.core/address-of-privkey is :clj-only" {})))))
