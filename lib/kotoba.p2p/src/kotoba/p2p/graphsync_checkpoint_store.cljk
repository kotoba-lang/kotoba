(ns kotoba.p2p.graphsync-checkpoint-store
  "Bounded, capability-gated retention state for GraphSync checkpoints."
  (:require [ipld.core :as ipld]
            [ipld.value :as value]))

(def snapshot-version 1)

(defn- invalid! [message data]
  (throw (ex-info message (assoc data :type :graphsync/invalid-checkpoint-store))))

(defn- positive! [config key]
  (let [n (get config key)]
    (when-not (and (integer? n) (pos? n))
      (invalid! "checkpoint store requires positive limits" {:limit key :value n}))
    n))

(defn- byte-length [bytes]
  #?(:clj (if (bytes? bytes) (alength ^bytes bytes) (count bytes))
     :cljs (if (vector? bytes) (count bytes) (.-length bytes))))

(defn new-store [config]
  (doseq [key [:max-checkpoints :max-total-bytes :max-checkpoint-bytes :ttl-ms]]
    (positive! config key))
  {:config (select-keys config
                        [:max-checkpoints :max-total-bytes
                         :max-checkpoint-bytes :ttl-ms])
   :entries {}
   :total-bytes 0})

(defn- authorize! [authorize-fn action context]
  (when-not (fn? authorize-fn)
    (invalid! "checkpoint store requires authorization hook" {:action action}))
  (when-not (true? (authorize-fn (assoc context :action action)))
    (throw (ex-info "checkpoint store operation is unauthorized"
                    {:type :graphsync/unauthorized :action action
                     :principal (:principal context)}))))

(defn- now! [now-ms]
  (when-not (and (integer? now-ms) (<= 0 now-ms))
    (invalid! "checkpoint store requires non-negative now-ms" {:now-ms now-ms}))
  now-ms)

(defn put-checkpoint
  "Admit CID-verified bytes under bounded capacity and a fresh TTL lease."
  [store {:keys [cid bytes request-id principal now-ms]} authorize-fn]
  (authorize! authorize-fn :checkpoint/put
              {:cid cid :request-id request-id :principal principal})
  (when-not (= cid (ipld/cid bytes))
    (invalid! "checkpoint bytes do not match CID" {:cid cid :actual (ipld/cid bytes)}))
  (now! now-ms)
  (let [size (byte-length bytes)
        old (get-in store [:entries cid])
        next-count (+ (count (:entries store)) (if old 0 1))
        next-bytes (+ (- (:total-bytes store) (or (:size old) 0)) size)]
    (when (> size (get-in store [:config :max-checkpoint-bytes]))
      (throw (ex-info "checkpoint exceeds per-item limit"
                      {:type :graphsync/resource-limit :limit :max-checkpoint-bytes})))
    (when (> next-count (get-in store [:config :max-checkpoints]))
      (throw (ex-info "checkpoint count capacity exceeded"
                      {:type :graphsync/resource-limit :limit :max-checkpoints})))
    (when (> next-bytes (get-in store [:config :max-total-bytes]))
      (throw (ex-info "checkpoint byte capacity exceeded"
                      {:type :graphsync/resource-limit :limit :max-total-bytes})))
    (-> store
        (assoc :total-bytes next-bytes)
        (assoc-in [:entries cid]
                  {:cid cid :bytes bytes :size size :request-id (vec request-id)
                   :principal principal :created-at-ms (or (:created-at-ms old) now-ms)
                   :expires-at-ms (+ now-ms (get-in store [:config :ttl-ms]))}))))

(defn get-checkpoint
  "Return bytes only while the lease is live and the caller is authorized."
  [store cid principal now-ms authorize-fn]
  (now! now-ms)
  (let [entry (get-in store [:entries cid])]
    (when entry
      (authorize! authorize-fn :checkpoint/get
                  {:cid cid :request-id (:request-id entry) :principal principal
                   :owner (:principal entry)})
      (when (< now-ms (:expires-at-ms entry))
        (:bytes entry)))))

(defn gc-expired
  "Remove expired metadata/bytes and return explicit deletion receipts."
  [store principal now-ms authorize-fn]
  (now! now-ms)
  (authorize! authorize-fn :checkpoint/gc {:principal principal :now-ms now-ms})
  (let [expired (->> (:entries store)
                     (filter (fn [[_ entry]] (<= (:expires-at-ms entry) now-ms)))
                     (map first) vec)
        reclaimed (reduce + 0 (map #(get-in store [:entries % :size]) expired))]
    {:store (-> store
                (update :entries #(apply dissoc % expired))
                (update :total-bytes - reclaimed))
     :deleted-cids expired :reclaimed-bytes reclaimed}))

(defn snapshot [store]
  (value/encode-value {:version snapshot-version :store store}))

(defn restore [bytes]
  (let [envelope (value/decode-value bytes)]
    (when-not (and (= snapshot-version (:version envelope))
                   (map? (:store envelope)))
      (invalid! "invalid checkpoint store snapshot" {}))
    (:store envelope)))
