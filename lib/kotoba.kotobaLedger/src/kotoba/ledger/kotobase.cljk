(ns kotoba.ledger.kotobase
  "The 'kotoba git' backend: append ledger events as datoms via a
  caller-supplied transact! function, instead of requiring a concrete
  kotobase-clj dependency here (this library stays zero-dep; real
  deployments like cloud-itonami already have their own kotobase client --
  see `cloud_itonami.kotoba.cljc`/`net_kotobase.clj` -- and just pass its
  transact! in). Events become content-addressed, CID-pinned commits in
  kotobase rather than JSONL lines on local disk."
  )

(defn append!
  "tx-fn: (fn [tx-data]) -> whatever the caller's transact! returns. Wraps
  `event` (a plain map from kotoba.ledger.core) as one tx-data entry tagged
  :kotoba.ledger/event."
  [tx-fn event]
  (tx-fn [(assoc event :kotoba.ledger/event true)]))

(defn append-many!
  [tx-fn events]
  (tx-fn (mapv #(assoc % :kotoba.ledger/event true) events)))
