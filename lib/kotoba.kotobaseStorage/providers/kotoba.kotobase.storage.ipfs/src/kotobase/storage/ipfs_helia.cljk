(ns kotobase.storage.ipfs-helia
  "A Kubo-independent embedded Helia client for `kotobase.storage.ipfs`.

  Helia speaks the standard libp2p + Bitswap protocols, so blocks written by
  this client can be exchanged with both Helia and Kubo peers.  The adapter is
  intentionally block-only; mutable agreement remains a separate ref plane.

  `createHelia` returns a node synchronously in Helia 7.  Starting is explicit,
  while block reads
  are async iterators, not Promises, so this namespace drains that iterator
  explicitly instead of treating it as a Promise (the cause of the earlier
  false-negative nbb probe documented by this repository)."
  (:require ["helia" :refer [createHelia]]
            ["multiformats/cid" :refer [CID]]
            ["@multiformats/multiaddr" :refer [multiaddr]]))

(defn- concat-bytes [chunks]
  (let [size (reduce + (map #(.-byteLength %) chunks))
        out (js/Uint8Array. size)]
    (loop [offset 0, remaining chunks]
      (if-let [chunk (first remaining)]
        (do (.set out chunk offset)
            (recur (+ offset (.-byteLength chunk)) (next remaining)))
        out))))

(defn- drain-block [iterator]
  (letfn [(step [chunks]
            (-> (.next iterator)
                (.then (fn [result]
                         (if (.-done result)
                           (concat-bytes chunks)
                           (step (conj chunks (.-value result))))))))]
    (step [])))

(defn- missing-block? [error]
  (contains? #{"NotFoundError" "BlockNotFoundWhileOfflineError"
               "LoadBlockFailedError"}
             (.-name error)))

(defn- connect! [node addresses]
  (-> (mapv (fn [address]
              (.dial (.-libp2p node) (multiaddr address)))
            addresses)
      clj->js
      js/Promise.all
      (.then (fn [_] node))))

(defn open!
  "Open a standard IPFS client backed by embedded Helia.

  Options:
  - `:helia` injects an existing Helia-compatible node (tests/advanced use).
  - `:helia-options` is converted to JS and passed to `createHelia`.
  - `:peers` is a collection of Kubo/Helia multiaddrs to dial before return.

  Resolves to the provider-neutral client shape plus `:connect!`, `:peer-id`,
  `:helia`, and `:close!`.  A CID is always parsed and supplied to Helia's
  blockstore, so Helia verifies content identity on network retrieval."
  [{:keys [helia helia-options peers]}]
  (let [node (or helia (createHelia (clj->js (or helia-options {}))))
        peers (vec (or peers []))]
    (-> (.start node)
        (.then (fn [_] (connect! node peers)))
        (.then
         (fn [_]
           {:helia node
            :peer-id (some-> node .-libp2p .-peerId .toString)
            :connect! (fn [addresses] (connect! node addresses))
            :close! (fn [] (.stop node))
            :put-block!
            (fn [cid bytes]
              (let [parsed (.parse CID cid)]
                (-> (.put (.-blockstore node) parsed bytes)
                    (.then (fn [stored]
                             (let [stored-cid (.toString stored)]
                               (when-not (= cid stored-cid)
                                 (throw
                                  (ex-info "Helia returned a different CID"
                                           {:type :kotobase.storage.ipfs-helia/cid-mismatch
                                            :expected-cid cid
                                            :actual-cid stored-cid})))
                               cid))))))
            :get-block
            (fn [cid]
              (let [parsed (.parse CID cid)]
                (-> (drain-block (.get (.-blockstore node) parsed))
                    (.catch (fn [error]
                              (if (missing-block? error)
                                nil
                                (throw error)))))))})))))
