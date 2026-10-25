(ns kotobase.storage.ipfs
  "Provider-neutral IPFS immutable-block transport.

  This adapter deliberately implements only `IBlockStore`. IPFS is useful for
  distributing immutable CID-addressed bytes, but mutable database agreement
  belongs to a ref store with an explicit consistency profile. Compose the two
  planes with `kotobase.storage.core/compose`.

  The injected client is the portability boundary. It may be backed by a
  browser implementation, an embedded node, a remote pinning service, or any
  other IPFS-compatible transport; this library imports no node daemon or RPC
  API and assumes no mutable-name implementation."
  (:require [kotobase.storage.core :as storage]))

(defrecord IPFSBlockStorage [client]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (-> (mapv
         (fn [{:keys [cid bytes]}]
           (-> ((:put-block! client) cid bytes)
               (.then
                (fn [stored-cid]
                  (when-not (= cid stored-cid)
                    (throw
                     (ex-info "IPFS transport returned a different CID"
                              {:type :kotobase.storage/cid-mismatch
                               :expected-cid cid
                               :actual-cid stored-cid})))
                  cid))))
         blocks)
        clj->js
        js/Promise.all
        (.then #(vec (array-seq %)))))
  (-get-blocks [_ cids]
    (-> (mapv
         (fn [cid]
           (-> ((:get-block client) cid)
               (.then (fn [bytes] (when bytes [cid bytes])))))
         cids)
        clj->js
        js/Promise.all
        (.then #(into {} (keep identity (array-seq %))))))

  storage/IBackendCapabilities
  (-capabilities [_]
    #{:immutable-blocks :cid-addressed-read
      :batch-get :batch-put :distributed-blocks}))

(defn open
  "Open an IPFS-compatible, block-only backend.

  `client` supplies Promise-returning `:put-block!` and `:get-block`
  functions. No daemon, HTTP RPC shape, IPNS key, or node implementation is
  selected by this library.

  The returned value is accepted by `storage/validate-block-store!`, not by
  `storage/validate-backend!`. Use `(storage/compose {:blocks value :refs
  ref-store})` when an engine also needs mutable-head publication."
  [{:keys [client]}]
  (doseq [operation [:put-block! :get-block]]
    (when-not (ifn? (get client operation))
      (throw (ex-info "IPFS block client is incomplete"
                      {:type :kotobase.storage/invalid-configuration
                       :missing operation}))))
  (->IPFSBlockStorage client))
