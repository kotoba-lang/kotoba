(ns kakeibo.dedup
  "Transaction identity and de-duplication across overlapping statement windows.

  This is the problem an aggregator actually has to solve. Statements are
  fetched by date window, windows overlap (you re-fetch the last 90 days every
  week), and the same purchase therefore arrives many times. Summing what you
  fetched overstates spending; keying on the payee understates it, because two
  identical coffees on the same day are two transactions.

  The rule here:

  - A transaction's **key** is its institution reference when the statement
    provides one (authoritative), else the tuple
    `account | date | amount | normalized description`.
  - Within one batch, transactions sharing a key are numbered by
    **occurrence** (0, 1, 2 …) in statement order.
  - Merging batches keeps, per key, the **highest occurrence count any single
    batch reported** — not the sum. Two overlapping windows that each saw two
    identical coffees yield two, and a window that genuinely saw three yields
    three.

  Identity is a readable tuple string, not a hash. A hash would need a hash
  function this library has no reason to own, and would make a mis-keyed
  transaction impossible to diagnose by reading it."
  (:require [kotoba.lang.text :as str]))

(defn content-key
  "Deterministic key for a transaction.

  Prefers the institution's own reference: banks that emit one guarantee it is
  unique per transaction, which is strictly better than any tuple we can
  reconstruct."
  [{:tx/keys [account date amount normalized description ref]}]
  (if (and (some? ref) (not (str/blank? (str ref))))
    (str "ref|" account "|" ref)
    (str "row|" account "|" date "|" amount "|"
         (or normalized description ""))))

(defn assign-ids
  "Attach `:tx/key`, `:tx/occurrence` and `:tx/id` to each transaction.

  Occurrence is assigned in the order given, so a stable statement export
  yields stable ids and re-ingesting the same file is a no-op."
  [txs]
  (first
   (reduce (fn [[acc counts] tx]
             (let [k (content-key tx)
                   n (get counts k 0)]
               [(conj acc (assoc tx :tx/key k
                                 :tx/occurrence n
                                 :tx/id (str k "#" n)))
                (assoc counts k (inc n))]))
           [[] {}]
           txs)))

(defn- sort-key [tx]
  [(str (:tx/date tx)) (str (:tx/key tx)) (:tx/occurrence tx)])

(defn merge-batches
  "Merge statement batches into one de-duplicated transaction set.

  `batches` is a sequence of transaction sequences, oldest ingest first;
  already-ledgered transactions are simply the first batch. Each batch is
  id-assigned independently, then per key the batch reporting the most
  occurrences wins (earliest batch breaks a tie).

  Returns `{:kakeibo/txs [...] :kakeibo/incoming n :kakeibo/suppressed n
  :kakeibo/keys n}`. `:kakeibo/suppressed` is the count of duplicate rows
  that did not survive — reported rather than silently discarded, so an
  overlap that is quietly eating real transactions is visible."
  [batches]
  (let [indexed   (map-indexed (fn [i txs] [i (assign-ids txs)]) batches)
        incoming  (reduce + 0 (map (comp count second) indexed))
        ;; key -> {:count n :batch i :txs [...]}, keeping the richest batch.
        best      (reduce
                   (fn [acc [batch-index txs]]
                     (reduce
                      (fn [acc [k group]]
                        (let [n (count group)
                              cur (get acc k)]
                          (if (or (nil? cur) (> n (:count cur)))
                            (assoc acc k {:count n :batch batch-index :txs (vec group)})
                            acc)))
                      acc
                      (group-by :tx/key txs)))
                   {}
                   indexed)
        kept      (->> (vals best) (mapcat :txs) (sort-by sort-key) vec)]
    {:kakeibo/txs        kept
     :kakeibo/incoming   incoming
     :kakeibo/suppressed (- incoming (count kept))
     :kakeibo/keys       (count best)}))

(defn new-since
  "Transactions in `merged` whose id is absent from `known`.

  Lets an ingest tick report what it actually added rather than re-posting the
  whole history every run."
  [known merged]
  (let [seen (into #{} (map :tx/id) known)]
    (vec (remove #(contains? seen (:tx/id %)) merged))))
