(ns kotoba.net.libp2p.bitswap
  "The Bitswap wire message (`/ipfs/bitswap/1.2.0`, and its 1.1.0/1.0.0
  ancestors), as a protobuf schema over `protobuf.wire` — no block-transfer
  logic here, only what is legal to put on the wire and how to read what came
  back.

  Field numbers are go-bitswap's `message.proto`
  (github.com/ipfs/boxo/bitswap/message/pb/message.proto), which is the
  ancestor every implementation (go-bitswap, js-libp2p bitswap, Kubo) compiles
  against. Getting one wrong does not fail loudly — `protobuf.wire` skips
  fields it does not recognise — so a mis-numbered schema would silently
  produce an empty wantlist or a block with no data rather than an error.

  ## `block` is a CID, `prefix` is not one

  `Wantlist.Entry.block` (despite the name) carries the **full CID bytes** of
  the wanted block — the same bytes `multiformats.core/cid->bytes` returns.
  `Block.prefix`, on a *response*, is the CID's version+codec+multihash-code+
  multihash-length varints WITHOUT the multihash digest — a peer sending us a
  block tells us how to re-wrap the digest we compute ourselves, and does not
  resend a multihash we can recompute from `data`. This module does not
  reconstruct a response CID from `prefix`; a caller matches a `Block` back to
  the entry it answers, and must itself verify `data` hashes to the multihash
  it asked for (see `matches-multihash?`) — `prefix` on the wire is unauthenticated,
  exactly like everything in `kotoba.net.libp2p.identify`'s claims.

  ## want-have vs want-block

  `wantType` lets a requester ask *do you have it* (cheap, no payload) rather
  than *send it* — a session with many peers wants-have broadly and wants-block
  from whichever answered HAVE first, so it does not pull the same block twice
  over two connections. This module only ever builds want-block requests: a
  session-level HAVE/broadcast strategy is out of scope here, same as
  `kotoba.net.bitswap` (which owns want/have SET bookkeeping, not the wire)."
  (:require [protobuf.wire :as pb]))

(def protocol-1-2-0 "/ipfs/bitswap/1.2.0")
(def protocol-1-1-0 "/ipfs/bitswap/1.1.0")
(def protocol-1-0-0 "/ipfs/bitswap/1.0.0")

;; A dialer proposes these in order, most-preferred first — falling back to an
;; older protocol id is not a downgrade of *this* schema, since 1.0.0-1.2.0
;; share the same message shape; it only affects `Message.blocks` (1.0.0,
;; sha256 of `data` had a well known bug in a few early implementations we
;; do not attempt to interoperate with) vs `Message.payload` (1.1.0+, this
;; module always writes and reads `:payload`, never `:blocks`).
(def protocols [protocol-1-2-0 protocol-1-1-0])

(def want-type {:block 0 :have 1})
(def want-type->kw (into {} (map (fn [[k v]] [v k])) want-type))

(def block-presence-type {:have 0 :dont-have 1})
(def block-presence-type->kw (into {} (map (fn [[k v]] [v k])) block-presence-type))

(def entry-schema
  {1 {:name :block :type :bytes}          ; the wanted CID, full bytes
   2 {:name :priority :type :int32}
   3 {:name :cancel :type :bool}
   4 {:name :want-type :type :enum}
   5 {:name :send-dont-have :type :bool}})

(def wantlist-schema
  {1 {:name :entries :type :message :schema entry-schema :repeated true}
   2 {:name :full :type :bool}})

(def block-schema
  {1 {:name :prefix :type :bytes}
   2 {:name :data :type :bytes}})

(def block-presence-schema
  {1 {:name :cid :type :bytes}
   2 {:name :type :type :enum}})

(def schema
  {1 {:name :wantlist :type :message :schema wantlist-schema}
   2 {:name :blocks :type :bytes :repeated true}          ; bitswap 1.0.0, unused by this module
   3 {:name :payload :type :message :schema block-schema :repeated true}
   4 {:name :block-presences :type :message :schema block-presence-schema :repeated true}
   5 {:name :pending-bytes :type :int32}})

;; ── constructing requests ────────────────────────────────────────────────

(defn want-entry
  "One wantlist entry. `cid-bytes` is the full CID (`multiformats.core/cid->bytes`),
  not a multihash — DHT `GET_PROVIDERS` and Bitswap disagree about this, and
  using the DHT's multihash here produces an entry that never matches anything
  a Kubo peer has."
  [cid-bytes & {:keys [priority want-kind send-dont-have? cancel?]
                :or {priority 1 want-kind :block send-dont-have? true cancel? false}}]
  {:block (vec cid-bytes)
   :priority priority
   :cancel cancel?
   :want-type (get want-type want-kind)
   :send-dont-have send-dont-have?})

(defn want-block-message
  "A Message requesting `cid-bytes` as a full block, with DONT_HAVE allowed so
  a peer that lacks it answers rather than us timing out against it. `full` is
  false: this is a diff against an empty wantlist the peer has never seen, not
  a full replacement of one we have built up over a session."
  [cid-bytes]
  {:wantlist {:entries [(want-entry cid-bytes)] :full false}})

(defn cancel-message
  "Tell the peer to forget the entry — sent once we have the block (or gave up),
  so it stops holding wantlist state for us. Optional but polite; a peer that
  never hears CANCEL keeps every entry until the connection dies."
  [cid-bytes]
  {:wantlist {:entries [(want-entry cid-bytes :cancel? true)] :full false}})

(defn encode [m] (pb/encode schema m))
(defn decode [bs] (pb/decode schema bs))

;; ── reading responses ────────────────────────────────────────────────────

(defn payload-blocks
  "The `Block`s a response carried, as `{:prefix :data}` — empty rather than nil."
  [msg]
  (vec (:payload msg)))

(defn block-presences
  "The `BlockPresence`s a response carried, decoded to `{:cid :type}` with
  `:type` as `:have`/`:dont-have` rather than the wire integer."
  [msg]
  (mapv (fn [bp] (update bp :type block-presence-type->kw)) (:block-presences msg)))

(defn dont-have?
  "Did the peer explicitly say it lacks `cid-bytes`? Distinct from *no answer
  at all* (a peer that ignores an entry it does not recognise) and from *no
  block yet* (still fetching, if it runs its own DHT-backed strategy — which
  Bitswap itself never does; a Bitswap peer only ever serves blocks it already
  holds)."
  [msg cid-bytes]
  (boolean (some #(and (= :dont-have (:type %)) (= (vec cid-bytes) (vec (:cid %))))
                 (block-presences msg))))

(defn find-block
  "The payload Block whose data hashes to `cid-bytes`'s multihash, or nil.

  Matching by content hash rather than by `Block.prefix` is deliberate:
  `prefix` is an unverified claim exactly like every other field a peer sends,
  and a peer answering a want for CID A with data for CID B would pass a
  prefix-only check. `multihash-of-fn` is injected (`multiformats.core/multihash-sha256`
  composed with `multiformats.core/cid->multihash`, or an equivalent) so this
  namespace stays free of a hash dependency, the same reason `kad.key/dht-key`
  takes `sha256-fn`."
  [msg cid-multihash multihash-of-fn]
  (some (fn [{:keys [data] :as block}]
          (when (= (vec cid-multihash) (vec (multihash-of-fn data)))
            block))
        (payload-blocks msg)))
