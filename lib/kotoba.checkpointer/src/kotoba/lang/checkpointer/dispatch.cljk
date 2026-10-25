(ns kotoba.lang.checkpointer.dispatch
  "The op-dispatch core -- mirrors checkpointer.ts's #dispatch/#put/
  #getTuple/#list/#putWrites/#anchorPending/#anchorCommit. `handle-request`
  takes a decoded Request map (STRING keys, matching the wire shape exactly:
  v, op, cell_did, thread_id, checkpoint_ns, checkpoint_id, payload, meta)
  and an `env` map bundling injected collaborators, and returns a Response
  map (STRING keys: ok, mst_root_cid, data, error) -- callable DIRECTLY in
  tests with a fake env, no socket, no msgpack framing, no real filesystem
  required (see kotoba.lang.checkpointer.sidecar for the thin socket-loop
  wrapper around this fn, and this namespace's tests for env fakes wired to
  a `java.nio.file.Files/createTempDirectory` temp dir + an in-memory index
  atom).

  env keys:
    :index-atom          atom of {index-key -> row}  (row = index/index-key shape)
    :allowed-dids         #{cell_did ...}
    :encrypt-cells        #{cell_did ...}
    :blob-inline-threshold long
    :anchor-chain-id       long
    :spool-car!            (fn [cell-did checkpoint-id bytes])
    :spool-payload!        (fn [cell-did checkpoint-id bytes])
    :load-payload          (fn [cell-did checkpoint-id] -> bytes)
    :persist-index!        (fn [index-map])
    :get-cell-key!         (fn [cell-did] -> 32-byte key)
    :pin!                  (fn [car-bytes on-result])
    :now-ms                (fn [] -> long)  -- injected for deterministic tests

  Portability: this is the pure op-dispatch core (no direct fs/socket/vendor
  calls -- everything host-specific comes in via `env`), `.cljc` so it loads
  under ClojureScript too. `index`/`msgpack` (required below) are likewise
  portable; `crypto` is `:clj`-only-wrapped (see its namespace docstring,
  it wraps `pqh`'s JVM-only AEAD) so `put!`/`get-tuple` on an `encrypt-cells`
  cell would throw under cljs -- everything else in this namespace does not
  touch `crypto` and is fully portable."
  (:require [kotoba.lang.checkpointer.commit :as commit]
            [kotoba.lang.checkpointer.msgpack :as msgpack]
            [kotoba.lang.checkpointer.index :as index]
            [kotoba.lang.checkpointer.crypto :as crypto]))

(def protocol-version 1)

(defn ok
  ([] (ok {}))
  ([{:keys [mst-root-cid data]}]
   {"ok" true "mst_root_cid" mst-root-cid "data" data "error" nil}))

(defn err [message]
  {"ok" false "mst_root_cid" nil "data" nil "error" message})

(defn- default-now-ms []
  #?(:clj (System/currentTimeMillis)
     :cljs (.getTime (js/Date.))))

(defn- now-ms [env] ((get env :now-ms default-now-ms)))

(defn- put!
  [env req]
  (let [payload (get req "payload")
        checkpoint-id (get req "checkpoint_id")]
    (if (or (nil? payload) (nil? checkpoint-id))
      (err "put requires payload + checkpoint_id")
      (let [cell-did (get req "cell_did")
            thread-id (get req "thread_id")
            checkpoint-ns (get req "checkpoint_ns")
            encrypt? (contains? (:encrypt-cells env) cell-did)
            ;; ADR-2605181100 hard rule: encrypted-at-rest cells get their
            ;; payload sealed BEFORE MST projection, so the CID/CAR/IPFS pin
            ;; only ever address ciphertext.
            effective-payload (if encrypt?
                                 (crypto/encrypt-payload ((:get-cell-key! env) cell-did) cell-did payload)
                                 payload)
            decoded-value (msgpack/decode effective-payload)
            {:keys [root-cid car-bytes blob-count]}
            (commit/commit-mst {:cell-did cell-did
                                 :thread-id thread-id
                                 :checkpoint-ns checkpoint-ns
                                 :checkpoint-id checkpoint-id
                                 :payload decoded-value
                                 :blob-inline-threshold (:blob-inline-threshold env commit/default-blob-inline-threshold)})
            row {"cell_did" cell-did "thread_id" thread-id "checkpoint_ns" checkpoint-ns
                 "checkpoint_id" checkpoint-id "mst_root_cid" root-cid
                 "car_size_bytes" (count car-bytes) "car_blob_count" blob-count
                 "mst_projected_at" (now-ms env)
                 "ipfs_pinned_at" nil "ipfs_pin_service" nil "ipfs_pin_id" nil
                 "anchor_tx_hash" nil "anchor_block_number" nil "anchor_log_index" nil
                 "anchor_chain_id" (:anchor-chain-id env) "anchored_at" nil}
            k (index/index-key row)]
        ((:spool-car! env) cell-did checkpoint-id car-bytes)
        ((:spool-payload! env) cell-did checkpoint-id effective-payload)
        (swap! (:index-atom env) assoc k row)
        ((:persist-index! env) @(:index-atom env))
        ((:pin! env) car-bytes
         (fn [result]
           (when result
             (swap! (:index-atom env) update k
                    (fn [r] (when r (assoc r "ipfs_pinned_at" (now-ms env)
                                            "ipfs_pin_service" "local-kubo"
                                            "ipfs_pin_id" (:cid result)))))
             ((:persist-index! env) @(:index-atom env)))))
        (ok {:mst-root-cid root-cid})))))

(defn- get-tuple [env req]
  (let [cell-did (get req "cell_did") thread-id (get req "thread_id") checkpoint-ns (get req "checkpoint_ns")
        checkpoint-id (get req "checkpoint_id")
        idx @(:index-atom env)
        row (if checkpoint-id
              (get idx (index/index-key {"cell_did" cell-did "thread_id" thread-id
                                          "checkpoint_ns" checkpoint-ns "checkpoint_id" checkpoint-id}))
              (index/latest-for idx cell-did thread-id checkpoint-ns))]
    (if-not row
      (ok {:data nil})
      (let [raw ((:load-payload env) cell-did (get row "checkpoint_id"))
            payload (if (contains? (:encrypt-cells env) cell-did)
                      (crypto/decrypt-payload ((:get-cell-key! env) cell-did) raw)
                      raw)]
        (ok {:mst-root-cid (get row "mst_root_cid") :data payload})))))

(defn- list-op [env req]
  (let [idx @(:index-atom env)
        rows (index/list-rows idx (get req "cell_did") (get req "thread_id") (get req "checkpoint_ns"))]
    (ok {:data (msgpack/encode rows)})))

(defn- put-writes! [env req]
  (put! env (update req "meta" (fn [m] (assoc (or m {}) "kind" "writes")))))

(defn- anchor-pending [env req]
  (let [idx @(:index-atom env)
        cell-did (get req "cell_did")
        rows (filterv (fn [r] (and (= (get r "cell_did") cell-did)
                                   (some? (get r "ipfs_pinned_at"))
                                   (nil? (get r "anchor_tx_hash"))))
                       (vals idx))]
    (ok {:data (msgpack/encode rows)})))

(defn- anchor-commit! [env req]
  (if-not (get req "payload")
    (err "anchor_commit requires payload")
    (let [commits (msgpack/decode (get req "payload"))
          cell-did (get req "cell_did")]
      (doseq [c commits]
        (let [k (index/index-key {"cell_did" cell-did "thread_id" (get c "thread_id")
                                   "checkpoint_ns" (get c "checkpoint_ns") "checkpoint_id" (get c "checkpoint_id")})]
          (swap! (:index-atom env) update k
                 (fn [row]
                   (when row
                     (assoc row
                            "anchor_tx_hash" (get c "anchor_tx_hash")
                            "anchor_block_number" (get c "anchor_block_number")
                            "anchor_log_index" (get c "anchor_log_index")
                            "anchored_at" (now-ms env)))))))
      ((:persist-index! env) @(:index-atom env))
      (ok))))

(defn handle-request
  "req: a decoded Request map (string keys). env: injected collaborators
  (see namespace docstring). Returns a Response map (string keys)."
  [env req]
  (cond
    (not= (get req "v") protocol-version) (err (str "unsupported protocol version " (get req "v")))
    (= (get req "op") "health") (ok {:data (msgpack/encode {"status" "ok"})})
    (not (contains? (:allowed-dids env) (get req "cell_did")))
    (err (str "cell_did not provisioned: " (get req "cell_did")))
    :else
    (case (get req "op")
      "put" (put! env req)
      "get_tuple" (get-tuple env req)
      "list" (list-op env req)
      "put_writes" (put-writes! env req)
      "anchor_pending" (anchor-pending env req)
      "anchor_commit" (anchor-commit! env req)
      (err (str "unknown op: " (get req "op"))))))
