(ns kotoba.lang.checkpointer.blockmap
  "An insertion-order-preserving CID(string)->bytes map, mirroring
  @atproto/repo's `BlockMap` (a JS `Map` keyed by CID string) closely enough
  to reproduce byte-identical CAR file block ordering: `bm-set` on an
  EXISTING key updates the value in place without moving its position (JS
  `Map.set` semantics -- re-setting an existing key never changes iteration
  order); a NEW key is appended at the end. `bm-entries` yields [cid bytes]
  pairs in that insertion order, which is exactly the order
  `blocksToCarFile` (kotoba.lang.checkpointer.car) writes blocks in."
  (:require [kotoba.lang.checkpointer.dagcbor :as cbor]
            [multiformats.core :as mf]))

(defrecord BlockMap [order blocks])

(defn empty-block-map [] (->BlockMap [] {}))

(defn bm-set
  "Set `cid` -> `bytes`. Preserves original insertion position if `cid`
  already present (matches JS Map.set)."
  [bm cid bytes]
  (if (contains? (:blocks bm) cid)
    (update bm :blocks assoc cid bytes)
    (-> bm
        (update :order conj cid)
        (update :blocks assoc cid bytes))))

(defn bm-get [bm cid] (get (:blocks bm) cid))

(defn bm-has? [bm cid] (contains? (:blocks bm) cid))

(defn bm-add
  "dag-cbor-encode `value`, compute its CID (codec 0x71, sha2-256), bm-set
  it. Returns [cid bm']. Mirrors @atproto/repo's `BlockMap.add`."
  [bm value]
  (let [bytes (cbor/encode value)
        cid (mf/cidv1-dag-cbor bytes)]
    [cid (bm-set bm cid bytes)]))

(defn bm-add-map
  "Merge `other` into `bm`, preserving `other`'s relative insertion order for
  any keys not already in `bm` (mirrors `BlockMap.addMap`)."
  [bm other]
  (reduce (fn [acc cid] (bm-set acc cid (bm-get other cid))) bm (:order other)))

(defn bm-entries
  "Ordered seq of [cid bytes] pairs, in insertion order."
  [bm]
  (map (fn [cid] [cid (get (:blocks bm) cid)]) (:order bm)))

(defn bm-cid-set
  "The set of CID strings currently held -- used as the 'already stored'
  membership test in kotoba.lang.checkpointer.mst/get-unstored-blocks."
  [bm]
  (set (:order bm)))
