(ns filecoin.node.block
  "A Filecoin block header: its CBOR, its CID, and the bytes a miner signs.

  A header is a **16-element definite-length CBOR array** in declaration
  order (`cbor-gen` emits `0x90`), and four of those elements are nullable:

      [miner ticket election-proof beacon-entries win-post-proof
       parents parent-weight height parent-state-root
       parent-message-receipts messages bls-aggregate timestamp
       block-sig fork-signaling parent-base-fee]

  `ticket`, `election-proof`, `bls-aggregate` and `block-sig` become CBOR
  null (`0xf6`) when absent, which is a *value in the array*, not an omitted
  field — the array is 16 long either way.

  **The signing rule here is not the one messages use.** A message signature
  covers the message's CID; a block signature covers the header's own
  serialised bytes with `BlockSig` set to null:

      func (blk *BlockHeader) SigningBytes() {
          blkcopy := *blk; blkcopy.BlockSig = nil; return blkcopy.Serialize()
      }

  So `signing-bytes` here returns CBOR, while `filecoin.message/signing-bytes`
  returns a CID. Carrying the message habit over produces a signature over
  32 bytes that nothing on the network will accept, and the failure looks like
  a bad key rather than like a wrong preimage.

  A CID inside CBOR is tag 42 over a byte string that begins with a `0x00`
  identity-multibase prefix — `d8 2a 58 27 00 01 71 a0 e4 02 …`. Dropping the
  `0x00` shortens every link by one byte and changes the header's CID, so the
  header is then addressed by a name no peer has."
  (:require [cbor.core :as cbor]
            [filecoin.address :as addr]
            [filecoin.bigint :as bigint]
            [filecoin.cid :as fcid]
            [filecoin.signature :as sig]))

(def ^:const field-count 16)

(def ^:const cid-tag
  "The IPLD link tag. Registered as `dag-cbor`'s CID tag in the CBOR tag
  registry, and the only tag that appears anywhere in Filecoin's chain data."
  42)

(def ^:const max-slice
  "cbor-gen refuses slices longer than this on both encode and decode, so a
  header claiming more parents than this is not a header a node would read."
  8192)

(defn- ->ints [data]
  (cond (nil? data) []
        (vector? data) data
        :else (mapv #(bit-and (int %) 0xff) (seq data))))

(defn- ->bytes [ints]
  #?(:clj (byte-array (map unchecked-byte ints))
     :cljs (let [out (js/Uint8Array. (count ints))]
             (dotimes [i (count ints)] (aset out i (nth ints i)))
             out)))

;; ── links ────────────────────────────────────────────────────────────────────

(defn link
  "A CID string as the tagged byte string CBOR carries."
  [cid-string]
  (cbor/tagged cid-tag (->bytes (into [0x00] (fcid/string->bytes cid-string)))))

(defn unlink
  "The inverse. Refuses anything that is not tag 42 with the identity prefix
  — a bare byte string in a link position is a different structure, and
  reading it as a CID would silently shift every following byte."
  [x]
  (when-not (and (cbor/tagged? x) (= cid-tag (cbor/tag-number x)))
    (throw (ex-info "block: expected a CID link (tag 42)"
                    {:tag (when (cbor/tagged? x) (cbor/tag-number x))})))
  (let [bs (->ints (cbor/tag-value x))]
    (when-not (= 0x00 (first bs))
      (throw (ex-info "block: CID link is missing its 0x00 multibase prefix" {})))
    (fcid/bytes->string (vec (rest bs)))))

;; ── the nested structures ────────────────────────────────────────────────────

(defn ticket
  "`{:vrf-proof [ints…]}` — a 1-element array on the wire."
  [vrf-proof]
  {:vrf-proof (->ints vrf-proof)})

(defn election-proof [win-count vrf-proof]
  {:win-count win-count :vrf-proof (->ints vrf-proof)})

(defn beacon-entry [round data]
  {:round round :data (->ints data)})

(defn post-proof
  "A `proof.PoStProof`: a registered proof type and the proof bytes."
  [proof-type proof-bytes]
  {:post-proof proof-type :proof-bytes (->ints proof-bytes)})

(defn- encode-ticket [t]
  (when t [(->bytes (:vrf-proof t))]))

(defn- encode-election-proof [e]
  (when e [(:win-count e) (->bytes (:vrf-proof e))]))

(defn- encode-beacon-entry [b]
  [(:round b) (->bytes (:data b))])

(defn- encode-post-proof [p]
  [(:post-proof p) (->bytes (:proof-bytes p))])

(defn- encode-signature [s]
  (when s (->bytes (sig/to-wire s))))

(defn- decode-signature [x]
  (when (some? x) (sig/from-wire x)))

;; ── the header ───────────────────────────────────────────────────────────────

(defn- addr-of [x]
  (cond (map? x) x
        (string? x) (addr/from-string x)
        :else (throw (ex-info "block: not an address" {:value x}))))

(def ^:private header-defaults
  {:ticket nil :election-proof nil :beacon-entries [] :win-post-proof []
   :parents [] :parent-weight "0" :height 0 :bls-aggregate nil :timestamp 0
   :block-sig nil :fork-signaling 0 :parent-base-fee "0"})

(defn block-header
  "Normalise a header map. Addresses may be strings or `filecoin.address`
  maps; `parent-weight` and `parent-base-fee` are decimal strings; the four
  CID fields are `bafy…` strings.

  Idempotent, so `encode` can call it unconditionally rather than guessing
  from the presence of a key whether a map has been through here already."
  [m]
  (let [h (merge header-defaults m)]
    (assoc h
           :miner (addr-of (:miner h))
           :beacon-entries (vec (:beacon-entries h))
           :win-post-proof (vec (:win-post-proof h))
           :parents (vec (:parents h))
           :parent-weight (str (:parent-weight h))
           :parent-base-fee (str (:parent-base-fee h)))))

(defn encode
  "The header's CBOR bytes."
  [bh]
  (let [h (block-header bh)]
    (when (> (count (:parents h)) max-slice)
      (throw (ex-info "block: too many parents" {:count (count (:parents h))})))
    (cbor/encode
     [(->bytes (->ints (addr/to-bytes (:miner h))))
      (encode-ticket (:ticket h))
      (encode-election-proof (:election-proof h))
      (mapv encode-beacon-entry (:beacon-entries h))
      (mapv encode-post-proof (:win-post-proof h))
      (mapv link (:parents h))
      (->bytes (bigint/->wire (:parent-weight h)))
      (:height h)
      (link (:parent-state-root h))
      (link (:parent-message-receipts h))
      (link (:messages h))
      (encode-signature (:bls-aggregate h))
      (:timestamp h)
      (encode-signature (:block-sig h))
      (:fork-signaling h)
      (->bytes (bigint/->wire (:parent-base-fee h)))])))

(defn decode
  "CBOR bytes → a header map. Throws unless the array is exactly 16 long."
  [bs]
  (let [v (cbor/decode bs)]
    (when-not (and (sequential? v) (= field-count (count v)))
      (throw (ex-info "block: not a 16-element array"
                      {:count (when (sequential? v) (count v))})))
    (let [[miner tkt ep beacons post parents weight height state receipts
           msgs bls-agg ts blk-sig fork base-fee] v]
      {:miner (addr/from-bytes miner)
       :ticket (when (some? tkt) (ticket (first tkt)))
       :election-proof (when (some? ep)
                         (election-proof (first ep) (second ep)))
       :beacon-entries (mapv #(beacon-entry (first %) (second %)) beacons)
       :win-post-proof (mapv #(post-proof (first %) (second %)) post)
       :parents (mapv unlink parents)
       :parent-weight (bigint/<-wire weight)
       :height height
       :parent-state-root (unlink state)
       :parent-message-receipts (unlink receipts)
       :messages (unlink msgs)
       :bls-aggregate (decode-signature bls-agg)
       :timestamp ts
       :block-sig (decode-signature blk-sig)
       :fork-signaling fork
       :parent-base-fee (bigint/<-wire base-fee)})))

(defn cid
  "The header's CID — `bafy2bzace…`, the name every peer knows the block by."
  [bh]
  (fcid/of-cbor (encode bh)))

(defn cid-bytes [bh]
  (fcid/to-bytes (encode bh)))

(defn signing-bytes
  "What a miner's `BlockSig` covers: the header serialised with `BlockSig`
  null. **CBOR, not a CID** — see this namespace's docstring."
  [bh]
  (encode (assoc (block-header bh) :block-sig nil)))

;; ── message meta ─────────────────────────────────────────────────────────────

(defn msg-meta
  "The 2-element structure a header's `messages` link points at: the root of
  the BLS message AMT and the root of the secp256k1 one. They are separate
  because BLS signatures are aggregated into `bls-aggregate` and secp256k1
  ones travel with each message."
  [bls-messages secpk-messages]
  {:bls-messages bls-messages :secpk-messages secpk-messages})

(defn encode-msg-meta [mm]
  (cbor/encode [(link (:bls-messages mm)) (link (:secpk-messages mm))]))

(defn decode-msg-meta [bs]
  (let [v (cbor/decode bs)]
    (when-not (and (sequential? v) (= 2 (count v)))
      (throw (ex-info "block: MsgMeta is a 2-element array"
                      {:count (when (sequential? v) (count v))})))
    (msg-meta (unlink (first v)) (unlink (second v)))))

(defn msg-meta-cid [mm]
  (fcid/of-cbor (encode-msg-meta mm)))
