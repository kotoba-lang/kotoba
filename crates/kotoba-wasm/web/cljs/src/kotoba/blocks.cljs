(ns kotoba.blocks
  "CID-verified block sync for the browser kotoba node — ClojureScript port of
   kotoba-blocks.js (ADR-2606013600 D5 / 2606022150).

   BFS the canonical Prolly tree over content-addressed blocks, pulling each
   missing block (IndexedDB cache first, else `block.get` from a holder), handing
   it to `node.ingestBlock(cid, bytes)` which **re-derives and matches the CID**
   (rejecting tampered blocks), then persisting it. Repeat until none missing,
   then `node.hydrateFromProlly(root)`.

   The byte source is untrusted because trust lives in the CID — block.get on any
   kotoba-server, gateway, or the local IndexedDB cache are interchangeable."
  (:require [kotoba.idb :as idb]))

;; ── base64 <-> bytes (block.get returns {data_b64}; block.put takes data_b64) ──

(defn b64->bytes [b64]
  (let [bin (js/atob b64)
        n   (.-length bin)
        out (js/Uint8Array. n)]
    (dotimes [i n] (aset out i (.charCodeAt bin i)))
    out))

(defn bytes->b64 [^js bytes]
  (let [n (.-length bytes)
        cs (make-array n)]
    (dotimes [i n] (aset cs i (js/String.fromCharCode (aget bytes i))))
    (js/btoa (.join cs ""))))

;; ── block.get (Public, unauthenticated) ──────────────────────────────────────

(defn block-get
  "Fetch one block by CID from `remote`'s content-addressed gateway.
   `com.etzhayyim.apps.kotoba.block.get?cid=...` → {data_b64}. Returns
   Promise<Uint8Array>. CID verification is the caller's (in-wasm) on ingest."
  ([remote cid] (block-get remote cid js/fetch))
  ([remote cid fetch-fn]
   (-> (fetch-fn (str remote
                      "/xrpc/com.etzhayyim.apps.kotoba.block.get?cid="
                      (js/encodeURIComponent cid)))
       (.then (fn [^js r]
                (if (.-ok r)
                  (.json r)
                  (throw (js/Error. (str "block.get " cid " → HTTP " (.-status r)))))))
       (.then (fn [^js j]
                (let [b64 (.-data_b64 j)]
                  (when-not b64
                    (throw (js/Error. (str "block.get " cid " → no data_b64"))))
                  (b64->bytes b64)))))))

;; ── hydrate via CID-verified block sync ──────────────────────────────────────

(defn hydrate-via-blocks
  "Hydrate `node` by syncing the Prolly tree rooted at `root` over CID-verified
   blocks (IndexedDB first, then `remote`), then traversing it locally.

   `node` exposes ingestBlock / missingBlockCids / hydrateFromProlly.
   opts: :remote (REQUIRED) :fetch-fn :max-rounds (default 64).
   Returns Promise<datom-count>."
  [^js node root {:keys [remote fetch-fn max-rounds]
                  :or   {fetch-fn js/fetch max-rounds 64}}]
  (js/Promise.
   (fn [resolve reject]
     (letfn [(pull-one [cid]
               (-> (idb/get-block cid)
                   (.then (fn [cached]
                            (if cached
                              cached
                              (-> (block-get remote cid fetch-fn)
                                  (.then (fn [bytes]
                                           ;; durable for cold start — only after fetch
                                           (-> (idb/put-block cid bytes)
                                               (.then (fn [_] bytes)))))))))
                   (.then (fn [bytes]
                            (.ingestBlock node cid bytes))))) ; throws on CID mismatch
             (round [n]
               (let [missing (vec (.missingBlockCids node root))]
                 (cond
                   (zero? (count missing)) (resolve (.hydrateFromProlly node root))
                   (> n max-rounds)        (reject (js/Error. "block sync did not converge"))
                   :else
                   (-> (js/Promise.all (clj->js (map pull-one missing)))
                       (.then (fn [_] (round (inc n))))
                       (.catch reject)))))]
       (round 0)))))

(defn hydrate-from-idb-blocks
  "Pre-seed `node` from IndexedDB ONLY (offline cold start). Returns
   Promise<datom-count | nil> — nil when the tree is not fully cached offline, so
   the caller falls back to `hydrate-via-blocks`."
  [^js node root]
  (js/Promise.
   (fn [resolve reject]
     (letfn [(round [n]
               (let [missing (vec (.missingBlockCids node root))]
                 (if (zero? (count missing))
                   (resolve (.hydrateFromProlly node root))
                   (-> (js/Promise.all
                        (clj->js (map (fn [cid]
                                        (-> (idb/get-block cid)
                                            (.then (fn [bytes]
                                                     (when bytes (.ingestBlock node cid bytes))
                                                     (boolean bytes)))))
                                      missing)))
                       (.then (fn [^js progressed]
                                (cond
                                  (not (some identity (array-seq progressed))) (resolve nil)
                                  (> n 64) (resolve nil)
                                  :else (round (inc n)))))
                       (.catch reject)))))]
       (round 0)))))
