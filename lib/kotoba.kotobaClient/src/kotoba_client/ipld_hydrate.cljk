(ns kotoba-client.ipld-hydrate
  "The generic `missing-cids` implementation (see
  `kotoba-client.core/hydrate-via-blocks`): walk whatever blocks are
  already present in `store`, follow their REAL tag-42 IPLD links via
  `ipld.core/links`, and report every reachable CID not yet fetched.

  Because prolly-tree nodes, quad-store commit blocks, and commit-dag
  commits all encode their references as tag-42 links now, this one walk
  hydrates ANY of them — no per-schema walker (the old prolly-specific
  `children` walk) needed. A not-yet-present block is itself reported
  missing; its own links are undiscoverable until it is fetched, which is
  exactly why `hydrate-via-blocks` loops to convergence."
  (:require [ipld.core :as ipld]))

(defn missing-cids
  "`root-cid` : the block to resolve the graph of.
  `store`     : `{:get-fn (cid -> bytes-or-nil), ...}`.
  Returns every CID reachable from `root-cid` (following tag-42 links in
  already-present blocks) that is not yet in `store`."
  [root-cid {:keys [get-fn]}]
  (letfn [(walk [cid]
            (let [bytes (get-fn cid)]
              (if (nil? bytes)
                [cid]
                (mapcat walk (ipld/links (ipld/decode bytes))))))]
    (vec (walk root-cid))))
