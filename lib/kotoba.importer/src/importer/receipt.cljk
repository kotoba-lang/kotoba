(ns importer.receipt
  "What one page did, as evidence rather than as a log line.

  A log line says `synced 42`. A receipt says which cursor it started from,
  which it ended at, how many records the plan held, how many the sink
  committed, and whether the cursor moved -- which is enough for a reader to
  find the one failure this whole library exists to prevent, without trusting
  the importer's own summary of itself.")

(defn receipt
  [{:keys [cursor-in cursor-out moved? planned persisted rejected outcome
           held-reason held-detail resync-required? at blobs]}]
  (cond-> {:importer.receipt/source-id (:importer.cursor/source-id cursor-in)
           :importer.receipt/stream (:importer.cursor/stream cursor-in)
           :importer.receipt/key (:importer.cursor/key cursor-in)
           :importer.receipt/phase (:importer.cursor/phase cursor-in)
           :importer.receipt/token-in (:importer.cursor/token cursor-in)
           :importer.receipt/token-out (:importer.cursor/token cursor-out)
           :importer.receipt/moved? (boolean moved?)
           :importer.receipt/planned planned
           :importer.receipt/persisted persisted
           :importer.receipt/rejected (or rejected 0)
           :importer.receipt/outcome outcome
           :importer.receipt/at at}
    held-reason (assoc :importer.receipt/held-reason held-reason)
    held-detail (assoc :importer.receipt/held-detail held-detail)
    resync-required? (assoc :importer.receipt/resync-required? true)
    (seq blobs) (assoc :importer.receipt/blobs (vec blobs))))

(defn silent-hole?
  "The cursor moved past records the sink did not take.

  This must be false for every receipt this library ever produces --
  `importer.cursor/advance` refuses exactly this case. It is computed here
  anyway, from the receipt alone, so that a reader auditing a ledger of
  receipts can check the invariant without re-running the code that is
  supposed to hold it."
  [r]
  (and (:importer.receipt/moved? r)
       (< (:importer.receipt/persisted r 0) (:importer.receipt/planned r 0))))

(defn problems [r]
  (cond-> []
    (silent-hole? r)
    (conj {:importer/code :receipt/silent-hole
           :importer/msg (str "cursor advanced past "
                              (- (:importer.receipt/planned r 0)
                                 (:importer.receipt/persisted r 0))
                              " records the sink did not take")})

    (and (:importer.receipt/moved? r)
         (not= :synced (:importer.receipt/outcome r)))
    (conj {:importer/code :receipt/moved-without-sync
           :importer/msg "cursor moved on an outcome that was not :synced"})

    (and (not (:importer.receipt/moved? r))
         (= :synced (:importer.receipt/outcome r)))
    (conj {:importer/code :receipt/sync-without-move
           :importer/msg "reported :synced while the cursor was held"})))
