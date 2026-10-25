(ns wallet.chain
  "Non-custodial multi-chain wallet core: one BIP-32/39/44 seed, one
  ChainDriver protocol, and a DATA registry of networks (wallet.chains —
  the CoinMarketCap-major chains, each either derivable or refused with the
  mechanism it is waiting on). Drivers are built per FAMILY:

    :evm  one driver parameterized by {:chain-id :coin-type} — every EVM
          chain (:eth :bnb :polygon :avalanche :arbitrum :optimism :base)
          shares the coin-type-60 address, differs only in the EIP-155
          chain id folded into each signature.
    :utxo one driver parameterized by btc-crypto's measured network table
          (:btc :ltc :doge, :bch receive-only).

  HD derivation is chain-agnostic secp256k1 math shared via btc-crypto.bip32
  (Ethereum and Bitcoin derive on the same curve — only address encoding and
  tx format differ, which is what a ChainDriver captures).

  Custody has two shapes:

  - `account` / `sign-tx` — legacy in-process path: callers get back
    {:private-key …} and are responsible for keystore encryption
    (wallet.keystore) if persisting it.
  - `account-with` / `sign-tx-with` — the signer seam (wallet.signer):
    results carry NO private key; signing is delegated to a Signer
    (kagi.chain-signer in production), which is the only component that
    ever touches key material."
  (:require [btc-crypto.base58 :as base58]
            [btc-crypto.bip32 :as bip32]
            [btc-crypto.core :as btc]
            [btc-crypto.tx :as btc-tx]
            [eth-crypto.core :as eth]
            [wallet.chains :as chains]
            [wallet.signer :as signer]))

(defprotocol ChainDriver
  (bip44-path [driver account change index]
    "The BIP-44 derivation path string for account/change/index on this chain.")
  (address-of [driver privkey]
    "Chain address(es) for a 32-byte private key.")
  (address-of-pub [driver pub64]
    "Chain address(es) for a 64-byte uncompressed public key (X‖Y) — the
    pubkey-only counterpart of address-of, for signer-backed accounts that
    never see a private key.")
  (sign-tx* [driver privkey tx]
    "Chain-specific signed transaction for `tx` (shape is chain-specific —
    see each driver's docstring)."))

;; ─── EVM family (BIP-44 coin type 60' for every chain — the MetaMask
;;     convention: one key, one address, many chains; the EIP-155 chain id
;;     in the signature is what keeps a tx from replaying across them) ─────

(defn- evm-address
  "EIP-55 address of a 64-byte uncompressed pubkey: last 20 bytes of
  keccak256(X‖Y). Portable: slices the hex string rather than the array."
  ^String [pub64]
  (eth/eip55-checksum (subs (eth/bytes->hex (eth/keccak256 pub64)) 24)))

(defn- ensure-chain-id
  "Inject the account's chain id into `tx` when absent; REFUSE a mismatch —
  signing a transaction for a different network than the account was asked
  for is exactly the sign-the-wrong-tx hazard, and EIP-155 exists so that a
  signature carries its network. Comparison is numeric: a non-numeric
  :chain-id is refused rather than guessed at."
  [entry tx]
  (let [want (:chain-id entry)
        have (:chain-id tx)]
    (cond
      (nil? have) (assoc tx :chain-id want)
      (not (number? have))
      (throw (ex-info "wallet.chain: tx :chain-id must be a number here (hex/bytes are ambiguous to compare against the account's chain)"
                      {:reason :wallet.chain/chain-id-not-numeric :tx-chain-id have}))
      (== (long have) (long want)) tx
      :else
      (throw (ex-info (str "wallet.chain: tx :chain-id " have " does not match the account's chain ("
                           want ") — refusing to sign a transaction for a different network")
                      {:reason :wallet.chain/chain-id-mismatch
                       :account-chain-id want :tx-chain-id have})))))

(defn- eip1559? [tx] (contains? tx :max-fee-per-gas))

(defn evm-driver
  "ChainDriver for one EVM chain registry entry ({:chain-id :coin-type})."
  [entry]
  (reify ChainDriver
    (bip44-path [_ account change index]
      (str "m/44'/" (:coin-type entry) "'/" account "'/" change "/" index))
    (address-of [_ privkey]
      {:address (eth/address-of-privkey privkey) :chain-id (:chain-id entry)})
    (address-of-pub [_ pub64]
      {:address (evm-address pub64) :chain-id (:chain-id entry)})
    (sign-tx* [_ privkey tx]
      (let [tx (ensure-chain-id entry tx)]
        (if (eip1559? tx)
          (eth/sign-tx-eip1559 tx privkey)
          (eth/sign-tx-legacy tx privkey))))))

;; ─── UTXO family (btc-crypto owns the measured network constants; the
;;     registry names which network a chain key maps to. BIP-44 coin types
;;     from SLIP-44; P2WPKH-preferring callers on :btc can still derive
;;     under \"m/84'/0'/...\" directly — address-of/sign-tx* only need the
;;     raw private key) ────────────────────────────────────────────────────

(defn utxo-driver
  "ChainDriver for one UTXO chain registry entry ({:coin-type :network
  :receive-only?})."
  [entry]
  (let [net (:network entry)]
    (reify ChainDriver
      (bip44-path [_ account change index]
        (str "m/44'/" (:coin-type entry) "'/" account "'/" change "/" index))
      (address-of [_ privkey]
        (btc/address-of-privkey privkey net))
      (address-of-pub [_ pub64]
        (let [pub33 (signer/compress pub64)
              {:keys [encoding segwit?]} (btc/network net)]
          (cond-> {}
            (= :base58 encoding)   (assoc :p2pkh (btc/p2pkh-address pub33 net))
            (= :cashaddr encoding) (assoc :cashaddr (btc/cashaddr-address pub33 net))
            segwit?                (assoc :p2wpkh (btc/p2wpkh-address pub33 net)))))
      (sign-tx* [_ privkey {:keys [script-type] :as tx}]
        (when (:receive-only? entry)
          (throw (ex-info (str "wallet.chain: " (:name entry) " is RECEIVE-ONLY here — "
                               "btc-crypto does not implement its spend digest (SIGHASH_FORKID); "
                               "refusing to emit a signature the network would reject")
                          {:reason :wallet.chain/receive-only :chain (:network entry)})))
        ;; default to the best script the network actually HAS: p2wpkh where
        ;; SegWit exists, p2pkh where it does not (Dogecoin).
        (case (or script-type (if (:segwit? (btc/network net)) :p2wpkh :p2pkh))
          :p2wpkh (btc-tx/sign-p2wpkh (:tx tx) (:input-index tx) (:amount tx) privkey)
          :p2pkh (btc-tx/sign-legacy-p2pkh (:tx tx) (:input-index tx) privkey))))))

;; ─── TRON (address = the EVM address re-wrapped: 0x41 ‖ last20(keccak256
;;     (pubkey)), base58check with Bitcoin's sha256d checksum — a composition
;;     of two mechanisms already verified in eth-crypto and btc-crypto) ─────

(defn- tron-addresses [pub64]
  #?(:clj
     (let [payload (byte-array (cons (unchecked-byte 0x41)
                                     (drop 12 (seq (eth/keccak256 pub64)))))]
       {:address (base58/encode-check payload)
        :hex-address (eth/bytes->hex payload)})
     :cljs (throw (js/Error. "wallet.chain: TRON addresses not yet implemented for cljs"))))

(defn tron-driver
  "ChainDriver for TRON. Addresses are implemented; tx signing is REFUSED
  with the missing mechanism named — TRON's raw-data protobuf assembly.
  (The signature itself, secp256k1 over sha256(raw-data), is exactly what
  the signer seam already provides once the tx bytes exist.)"
  [entry]
  (reify ChainDriver
    (bip44-path [_ account change index]
      (str "m/44'/" (:coin-type entry) "'/" account "'/" change "/" index))
    (address-of [_ privkey]
      (tron-addresses #?(:clj (eth/private->public privkey)
                         :cljs (throw (js/Error. "wallet.chain: :clj-only")))))
    (address-of-pub [_ pub64]
      (tron-addresses pub64))
    (sign-tx* [_ _ _]
      (throw (ex-info "wallet.chain: TRON tx signing needs raw-data protobuf assembly, which is not implemented — refusing rather than signing bytes this library cannot canonicalize"
                      {:reason :wallet.chain/tx-format-not-implemented
                       :chain :trx
                       :needs "TRON raw-data protobuf assembly (the secp256k1-over-sha256 signature the seam already provides)"})))))

;; ─── driver registry (built from the data table) ─────────────────────────

(defn driver-for
  "The ChainDriver for `chain`, via the wallet.chains registry — unknown,
  staged, and externally-owned chains are refused there with the reason
  pinned, never answered with nil."
  [chain]
  (let [entry (chains/entry chain)]
    (case (:family entry)
      :evm (evm-driver entry)
      :utxo (utxo-driver entry)
      :tron (tron-driver entry))))

(def eth-driver (evm-driver (get chains/chains :eth)))
(def btc-driver (utxo-driver (get chains/chains :btc)))

(def drivers
  "Every implemented chain's driver, keyed by chain. Kept as a public var for
  source compatibility; `driver-for` is the lookup that refuses properly."
  (into {} (map (fn [k] [k (driver-for k)])) (chains/implemented)))

;; ─── account derivation ──────────────────────────────────────────────────

(defn account
  "Derive account/change/index for `chain` (any implemented wallet.chains
  key) from `master` (a btc-crypto.bip32 seed->master node). Returns
  {:chain :path :private-key :address(es)}. Staged/unknown chains are
  refused with the missing mechanism named."
  ([master chain] (account master chain 0 0 0))
  ([master chain account-index] (account master chain account-index 0 0))
  ([master chain account-index change index]
   (let [driver (driver-for chain)
         path (bip44-path driver account-index change index)
         node (bip32/derive-path master path)
         privkey (:private-key node)]
     (merge {:chain chain :path path :private-key privkey}
            (address-of driver privkey)))))

(defn account-with
  "Like `account`, but derived from a wallet.signer/Signer — the result
  carries NO private key. This is the production shape: the Signer (kagi in
  production) is the only component that ever touches key material."
  ([sgnr chain] (account-with sgnr chain 0 0 0))
  ([sgnr chain account-index] (account-with sgnr chain account-index 0 0))
  ([sgnr chain account-index change index]
   (let [driver (driver-for chain)
         path (bip44-path driver account-index change index)]
     (merge {:chain chain :path path}
            (address-of-pub driver (signer/public-key64 sgnr path))))))

;; ─── transaction signing ─────────────────────────────────────────────────

(defn sign-tx
  "Sign `tx` (chain-specific shape — see each driver's `sign-tx*`) with the
  private key of a derived `account`."
  [{:keys [chain private-key]} tx]
  (sign-tx* (driver-for chain) private-key tx))

;; The raw-assembly helpers below exist because eth-crypto exposes the
;; DIGESTS (legacy-digest / eip1559-digest) and the EIP-1559 assembly
;; (eip1559-raw) for out-of-process signers, but not the legacy assembly —
;; so we RLP the legacy envelope here. The byte-for-byte parity tests
;; against eth/sign-tx-legacy are what keep this assembly honest.

#?(:clj
   (defn- num-bytes
     "Minimal big-endian bytes of a non-negative number (RLP integer form:
     zero is EMPTY, no leading 0x00). Also accepts 0x-hex strings and bytes
     as-is, mirroring eth-crypto's field flexibility."
     ^bytes [v]
     (cond
       (nil? v) (byte-array 0)
       (bytes? v) v
       (string? v) (eth/hex->bytes v)
       :else (let [^bytes b (.toByteArray (biginteger v))
                   n (alength b)]
               (cond
                 (and (= 1 n) (zero? (aget b 0))) (byte-array 0)
                 (and (> n 1) (zero? (aget b 0))) (java.util.Arrays/copyOfRange b 1 n)
                 :else b)))))

#?(:clj
   (defn- byte-str
     "Opaque byte-string field (:to / :data): 0x-hex string or bytes → bytes."
     ^bytes [v]
     (cond
       (nil? v) (byte-array 0)
       (bytes? v) v
       :else (eth/hex->bytes v))))

#?(:clj
   (defn- legacy-raw
     "Assemble the raw signed EIP-155 legacy tx from `tx` (chain-id already a
     number, per ensure-chain-id) and a signature {:r :s :recovery-id} —
     v = recovery-id + chainId*2 + 35."
     ^String [tx {:keys [r s recovery-id]}]
     (let [{:keys [nonce gas-price gas to value data chain-id]} tx
           v (+ 35 (long recovery-id) (* 2 (long chain-id)))]
       (str "0x" (eth/bytes->hex
                  (eth/rlp-encode [(num-bytes nonce) (num-bytes gas-price) (num-bytes gas)
                                   (byte-str to) (num-bytes value) (byte-str data)
                                   (num-bytes v) (num-bytes r) (num-bytes s)]))))))

#?(:clj
   (defn- der-sig-with-type
     "DER-encode {:r :s} and append the SIGHASH_ALL byte — the exact assembly
     btc-crypto.tx's own sign fns produce, so the parity tests can compare
     byte-for-byte."
     ^bytes [sig]
     (let [^bytes der (btc-tx/der-encode-sig sig)]
       (byte-array (concat (seq der) [(unchecked-byte btc-tx/sighash-all)])))))

#?(:clj
   (defn- utxo-sign-with
     "Signer-seam counterpart of utxo-driver's sign-tx*: same sighash
     (btc-crypto.tx's legacy/BIP-143 digests, verified there against the
     official BIP-143 vector), same deterministic RFC-6979 signature (the
     Signer signs the digest with the same eth-crypto primitive
     btc-crypto.tx uses), same witness/scriptSig assembly — with the private
     key never leaving the Signer."
     [sgnr entry path {:keys [script-type] :as tx}]
     (when (:receive-only? entry)
       (throw (ex-info (str "wallet.chain: " (:name entry) " is RECEIVE-ONLY here — "
                            "btc-crypto does not implement its spend digest (SIGHASH_FORKID); "
                            "refusing to emit a signature the network would reject")
                       {:reason :wallet.chain/receive-only :chain (:network entry)})))
     (let [net (:network entry)
           pubkey (signer/compress (signer/public-key64 sgnr path))
           script-code (btc-tx/p2pkh-script (btc/hash160 pubkey))]
       (case (or script-type (if (:segwit? (btc/network net)) :p2wpkh :p2pkh))
         :p2wpkh
         (let [sighash (btc-tx/bip143-sighash (:tx tx) (:input-index tx)
                                              script-code (:amount tx) btc-tx/sighash-all)]
           {:witness [(der-sig-with-type (signer/sign-digest! sgnr path sighash)) pubkey]})
         :p2pkh
         (let [sighash (btc-tx/legacy-sighash (:tx tx) (:input-index tx)
                                              script-code btc-tx/sighash-all)]
           {:der-sig-with-type (der-sig-with-type (signer/sign-digest! sgnr path sighash))
            :pubkey pubkey})))))

(defn sign-tx-with
  "Sign `tx` for a signer-backed account ({:chain :path}, from
  `account-with`) via wallet.signer — the digest goes to the Signer, the key
  never comes here.

  :evm  — EIP-1559 when :max-fee-per-gas is present, EIP-155 legacy
          otherwise; :chain-id injected from the registry when absent, a
          mismatch refused.
  :utxo — legacy P2PKH and BIP-143 P2WPKH SIGHASH_ALL, same tx shape as
          `sign-tx` (:tx :input-index :amount :script-type); BCH refused as
          receive-only.
  :tron — refused: the tx raw-data assembly is not implemented (the driver
          names what is missing)."
  [sgnr {:keys [chain path]} tx]
  #?(:clj
     (let [entry (chains/entry chain)]
       (case (:family entry)
         :evm (let [tx (ensure-chain-id entry tx)]
                (if (eip1559? tx)
                  (eth/eip1559-raw tx (signer/sign-digest! sgnr path (eth/eip1559-digest tx)))
                  (legacy-raw tx (signer/sign-digest! sgnr path (eth/legacy-digest tx)))))
         :utxo (utxo-sign-with sgnr entry path tx)
         ;; other families: the driver carries its own named refusal
         (sign-tx* (driver-for chain) nil tx)))
     :cljs (throw (js/Error. "wallet.chain/sign-tx-with: not yet implemented for cljs"))))
