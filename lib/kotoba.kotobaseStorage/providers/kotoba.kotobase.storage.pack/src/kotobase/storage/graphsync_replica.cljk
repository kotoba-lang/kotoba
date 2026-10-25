(ns kotobase.storage.graphsync-replica
  "A GraphSync replication port backed by a CARv2 PackBlockStore.

  A receipt means more than a successful PUT: the block was sealed into a
  pack, entered the catalog, and was read back through the untrusted object
  plane with CID verification before the replica signed the statement."
  (:require [ipld.core :as ipld]
            [ipld.value :as value]
            [kotobase.storage.core :as storage]))

(def receipt-type "kotoba.graphsync/packed-replica.v1")

(defn- fail! [problem data]
  (throw (ex-info (name problem) (assoc data :type problem))))

(defn receipt-payload
  "The canonical, signature-covered availability statement."
  [{:keys [cid replica-id stored-at-ms pack-cid]}]
  {:receipt/type receipt-type
   :receipt/cid cid
   :receipt/replica-id replica-id
   :receipt/stored-at-ms stored-at-ms
   :receipt/pack-cid pack-cid})

(defn signing-bytes [receipt]
  (value/encode-value (receipt-payload receipt)))

(defn replicate-fn
  "Build the function expected by `graphsync-replication/execute-effects`.

  `catalog` is the same injected catalog used by PackBlockStore. `sign-fn`
  receives canonical bytes and returns a signature."
  [{:keys [store catalog replica-id sign-fn]}]
  (when-not (and (storage/packed? store) (map? catalog)
                 (fn? (:lookup catalog)) (string? replica-id) (fn? sign-fn))
    (fail! :graphsync/invalid-packed-replica {:replica-id replica-id}))
  (fn [planned-replica cid bytes now-ms]
    (when-not (= replica-id planned-replica)
      (fail! :graphsync/replica-mismatch
             {:expected replica-id :actual planned-replica}))
    (when-not (= cid (ipld/cid bytes))
      (fail! :graphsync/cid-mismatch {:expected cid :actual (ipld/cid bytes)}))
    (storage/-put-blocks! store [{:cid cid :bytes bytes}])
    (let [location (get ((:lookup catalog) [cid]) cid)
          landed (get (storage/-get-blocks store [cid]) cid)]
      (when-not (and location landed (= cid (ipld/cid landed)))
        (fail! :graphsync/physical-landing-unverified
               {:cid cid :replica-id replica-id :location location}))
      (let [receipt {:cid cid :replica-id replica-id :stored-at-ms now-ms
                     :pack-cid (:pack-cid location)}]
        (assoc receipt :signature (sign-fn (signing-bytes receipt)))))))

(defn verifier
  "Build a fail-closed receipt verifier.

  `key-fn` resolves an enrolled replica id to its public key. `verify-fn`
  receives public-key, canonical payload bytes, and signature."
  [key-fn verify-fn]
  (fn [receipt]
    (try
      (let [public-key (key-fn (:replica-id receipt))]
        (and public-key
             (= #{:cid :replica-id :stored-at-ms :pack-cid :signature}
                (set (keys receipt)))
             (true? (verify-fn public-key (signing-bytes receipt)
                               (:signature receipt)))))
      (catch Exception _ false))))
