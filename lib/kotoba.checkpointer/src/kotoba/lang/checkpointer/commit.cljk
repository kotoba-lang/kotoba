(ns kotoba.lang.checkpointer.commit
  "The `#commitMst` pipeline from checkpointer.ts -- pure (no I/O): project a
  decoded checkpoint payload onto a fresh single-entry atproto-shaped MST,
  build a deterministic CAR, return the root CID + CAR bytes synchronously.

  DETERMINISM CONTRACT (verbatim from checkpointer.ts's #commitMst doc
  comment): same (cell_did, checkpoint_id, payload bytes) => same rootCid,
  bit for bit. Do NOT introduce non-deterministic sources here (no random
  IDs, no wall-clock timestamps, no map-iteration-order dependence beyond
  dagcbor's canonical sort)."
  (:require [kotoba.lang.checkpointer.mst :as mst]
            [kotoba.lang.checkpointer.blockmap :as bm]
            [kotoba.lang.checkpointer.car :as car]
            [kotoba.lang.checkpointer.dagcbor :as cbor]))

(def default-blob-inline-threshold (* 16 1024))

(defn commit-mst
  "opts: {:cell-did :thread-id :checkpoint-ns :checkpoint-id :payload
  :blob-inline-threshold}. `:payload` is the ALREADY msgpack-decoded Clojure
  value (map/vector/string/long/boolean/nil/bytes) -- this fn does zero
  msgpack work, matching checkpointer.ts's `payload = decode(req.payload)`
  happening one level up in `#put`.

  Returns {:root-cid String :car-bytes bytes :blob-count (0|1)}."
  [{:keys [cell-did thread-id checkpoint-ns checkpoint-id payload blob-inline-threshold]
    :or {blob-inline-threshold default-blob-inline-threshold}}]
  (let [[payload-cid blocks0] (bm/bm-add (bm/empty-block-map) payload)
        payload-bytes (bm/bm-get blocks0 payload-cid)
        big? (> (alength ^bytes payload-bytes) (long blob-inline-threshold))
        [record-cid blocks1 blob-count]
        (if big?
          (let [ref {"$type" "kotodama.cell.checkpoint.ref"
                     "blob" (cbor/cid-link payload-cid)
                     "checkpoint_id" checkpoint-id
                     "cell_did" cell-did
                     "thread_id" thread-id
                     "checkpoint_ns" checkpoint-ns}
                [ref-cid blocks'] (bm/bm-add blocks0 ref)]
            [ref-cid blocks' 1])
          [payload-cid blocks0 0])
        storage-cids (bm/bm-cid-set blocks1)
        key (str "kotodama.cell.checkpoint/" checkpoint-id)
        root-node (mst/mst-add (mst/mst-empty) key record-cid)
        {:keys [root blocks]} (mst/get-unstored-blocks root-node storage-cids)
        car-blocks (bm/bm-add-map blocks1 blocks)
        car-bytes (car/blocks->car-bytes root car-blocks)]
    {:root-cid root
     :car-bytes car-bytes
     :blob-count blob-count}))
