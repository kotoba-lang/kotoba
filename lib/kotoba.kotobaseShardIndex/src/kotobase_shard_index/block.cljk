(ns kotobase-shard-index.block
  "The S3 shape, and the instrument that measures it.

  An object store gives you exactly two things: fetch an immutable object by
  name, and fetch a byte range of one. Both cost one round trip. Everything
  this subsystem claims about scale reduces to HOW MANY of those a query
  issues, so the store protocol and the counter that wraps it live together.

  We count GETs, not milliseconds. `kotobase-peer`'s dag-shape bench
  (ADR-2608021000) established that discipline for exactly this reason: wall
  clock on a shared workstation measures the workstation. A GET count is a
  property of the design."
  (:require [kotobase-shard-index.codec :as codec]))

(defprotocol IBlockStore
  "Read side. Both operations are one remote round trip."
  (-get [this cid]
    "The whole object as a string. nil when absent.")
  (-get-range [this cid offset length]
    "`length` bytes from `offset`. The reason a client can descend a tree
     without downloading it."))

(defprotocol IBlockSink
  "Write side. Separate protocol because the client half never has it — a
  reader that cannot write is the point, not an omission."
  (-put! [this cid payload]))

;; ── in-memory store ─────────────────────────────────────────────────
;; Stands in for the bucket in tests and benches. It is NOT a cache: the
;; measurements below count what a client would ask a real bucket for.

(defrecord ^:no-doc MemoryStore [state]
  IBlockStore
  (-get [_ cid] (get @state cid))
  (-get-range [_ cid offset length]
    (when-let [s (get @state cid)] (subs s offset (min (count s) (+ offset length)))))
  IBlockSink
  (-put! [_ cid payload] (swap! state assoc cid payload) cid))

(defn memory-store [] (->MemoryStore (atom {})))

(defn block-count [store] (count @(:state store)))

(defn total-bytes [store]
  (reduce + 0 (map codec/byte-length (vals @(:state store)))))

;; ── counting wrapper ────────────────────────────────────────────────

(defrecord ^:no-doc CountingStore [inner tally]
  IBlockStore
  (-get [_ cid]
    (let [payload (-get inner cid)]
      (swap! tally (fn [t] (-> t
                               (update :gets inc)
                               (update :bytes + (if payload (codec/byte-length payload) 0)))))
      payload))
  (-get-range [_ cid offset length]
    (let [payload (-get-range inner cid offset length)]
      (swap! tally (fn [t] (-> t
                               (update :gets inc)
                               (update :bytes + (if payload (codec/byte-length payload) 0)))))
      payload))
  IBlockSink
  (-put! [_ cid payload] (-put! inner cid payload)))

(defn counting
  "Wrap `store` so every read is tallied. Returns `[store tally-atom]`."
  [store]
  (let [tally (atom {:gets 0 :bytes 0})]
    [(->CountingStore store tally) tally]))

(defn reset-tally! [tally] (reset! tally {:gets 0 :bytes 0}))

;; ── typed helpers ───────────────────────────────────────────────────

(defn put-block!
  "Encode, address, store. Returns the cid. Idempotent by construction: the
  same value always lands on the same key, so a rebuild overwrites rather
  than duplicates."
  [sink hash-fn value]
  (let [payload (codec/encode value)
        cid (codec/cid hash-fn value)]
    (-put! sink cid payload)
    cid))

(defn get-block
  "Fetch and decode. Throws on a missing cid — a dangling reference in a
  content-addressed manifest is a corrupt index, not an empty result."
  [store cid]
  (let [payload (-get store cid)]
    (when (nil? payload)
      (throw (ex-info "block not found" {:cid cid})))
    (codec/decode payload)))

(defn verify-block
  "Re-derive the address from the bytes. The store is untrusted; this is the
  one check that makes it not need to be trusted."
  [store hash-fn cid]
  (let [payload (-get store cid)]
    (and (some? payload)
         (= cid (codec/address hash-fn payload)))))
