(ns kotobase.storage.pack-catalog-async
  "The datom catalog over Promise-returning ports.

  `kotobase.storage.pack-catalog/datom-catalog` calls `q` and uses the answer.
  On a Worker the answer is a Promise, so that catalog cannot run on the
  platform the pack plane was built for — the same split, and the same
  reason, as `pack` and `pack-async`. The vocabulary, the quads and the
  queries are `pack-catalog`, shared: two catalogs with two schemas would be
  two schemas.

  `pack-async` already awaits both ports (`seal-pack!` awaits `record!` and
  `record-pack!`; `-get-blocks` awaits `lookup`), so nothing on the store
  side changes to accept this.

  ## What packing does and does not remove

  Worth stating next to the code rather than in a commit message, because
  the round-trip number this plane is measured by does not count what
  happens here. Packing removes round trips on the OBJECT plane: forty
  blocks that used to be forty GETs become one ranged GET. It removes none
  on the datom plane. A hydrate loop calls `-get-blocks` with one CID at a
  time — that is the shape it is stuck in — so those forty reads still issue
  forty `locate-query` calls, and if the datom store is remote they are
  forty round trips to it.

  That is not a defect of packing and it is not hidden: `pack-async/stats`
  reports object requests, which is what it says it reports. But a
  deployment that put its catalog behind the same latency as its blocks
  would move the cost rather than remove it, and would be able to show a
  `{:requests 1}` while doing so. The catalog belongs somewhere cheap to
  ask."
  (:require [kotobase.storage.pack-catalog :as cat]))

(defn- promised [x] (js/Promise.resolve x))

(defn- locate-one [q cid]
  (-> (promised (q cat/locate-query [cid]))
      (.then (fn [rows] (cat/locate-row->entry cid (first rows))))))

(defn datom-catalog
  "The catalog of `pack-catalog/datom-catalog`, over Promise-returning
  `transact!` and `q`. Returns `{:lookup :record! :record-pack!}` whose
  functions resolve rather than return.

  The per-CID `locate-query` is deliberate and unchanged — see its docstring
  — and the queries for one `lookup` call are issued CONCURRENTLY. That is
  safe in a way the store's own fetches are not: `pack-async` fetches runs
  sequentially because a later run may hit a window an earlier one filled,
  and because the count is the measurement. Here the caller already holds
  every CID it is asking about, so there is nothing to learn from going in
  order and no counter to disturb. This is not the cons chain; the cons
  chain is upstream, one `-get-blocks` call per link, and it is exactly why
  concurrency inside one call buys so little."
  [{:keys [transact! q]}]
  {:lookup
   (fn [cids]
     (let [cids (vec cids)]
       (-> (js/Promise.all (clj->js (mapv #(locate-one q %) cids)))
           (.then (fn [entries]
                    ;; A CID with no location is ABSENT from the result, not
                    ;; present with a nil value: `pack-async` reads
                    ;; `(vals located)` and would otherwise plan a run for a
                    ;; frame that has no offset.
                    (into {} (keep (fn [e] (when e [(:cid e) e])))
                          (array-seq entries)))))))
   :record! (fn [entries] (promised (transact! (cat/entries->quads entries))))
   :record-pack! (fn [pack] (promised (transact! (cat/pack->quads pack))))})
