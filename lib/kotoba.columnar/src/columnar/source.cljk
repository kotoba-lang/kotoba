(ns columnar.source
  "The seam a file format plugs into.

  The split between `-chunk-stats` and `-read-column` **is** the design.
  Planning must be possible without reading data — that is the entire
  mechanism by which an analytic engine is fast — so the protocol makes the
  cheap call and the expensive call different methods rather than one method
  with a flag. A source that computes statistics by reading the chunk is
  legal and correct and slow, and it will show up in the read counters
  instead of hiding.

  A chunk is whatever unit the format prunes at: a Parquet row group, a
  partition file, a sorted run. The engine does not care, and deliberately
  cannot express a preference."
  (:refer-clojure :exclude [count]))

(defprotocol IColumnSource
  (-schema [source]
    "Ordered column names, as strings. The allowlist a caller checks a
    query's column against before it becomes an identifier anywhere.")
  (-chunk-count [source]
    "How many prunable chunks this source has.")
  (-chunk-rows [source chunk]
    "Rows in `chunk`. Metadata: answering this must not read column data,
    because row numbering needs it for chunks that are about to be skipped.")
  (-chunk-stats [source chunk column]
    "Statistics for one column chunk, or **nil** when the source makes no
    claim. Must be cheap. nil is an ordinary answer — a writer that recorded
    no bounds, or a type with no ordering — and it forbids pruning rather
    than permitting it.")
  (-read-column [source chunk column]
    "The column chunk as a `columnar.vector` column. The expensive call, and
    the one the engine exists to avoid making."))

(defn counting
  "Wrap a source so reads are counted.

  Not a debugging aid: it is how a test proves a filter caused chunks to be
  skipped. Answers alone cannot — a source that reads everything and filters
  afterwards returns the identical rows."
  [source]
  (let [reads (atom {:chunks #{} :columns 0})]
    {:reads reads
     :source
     (reify IColumnSource
       (-schema [_] (-schema source))
       (-chunk-count [_] (-chunk-count source))
       (-chunk-rows [_ c] (-chunk-rows source c))
       (-chunk-stats [_ c col] (-chunk-stats source c col))
       (-read-column [_ c col]
         (swap! reads (fn [r] (-> r (update :chunks conj c) (update :columns inc))))
         (-read-column source c col)))}))

(defn read-counts
  "`{:chunks #{...} :columns n}` — which chunks were actually touched, and how
  many column reads it took."
  [counting-source]
  @(:reads counting-source))
