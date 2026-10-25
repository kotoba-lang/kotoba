(ns arrow.source
  "An Arrow IPC file as a `columnar/IColumnSource`.

  A record batch is the chunk. That mapping is the whole adapter, and it is
  worth stating what it cost, because this repo exists to find out: **nothing
  in `columnar` changed to accept it.**

  ## Where Arrow differs from Parquet, and why the seam did not have to bend

  `columnar.source` splits cheap metadata from expensive reads, and Arrow
  honours that split with a strictly smaller cheap side:

  | question | Parquet | Arrow IPC |
  |---|---|---|
  | rows per chunk | footer | batch metadata |
  | nulls per column chunk | footer statistics | `FieldNode.null_count` |
  | min / max per column chunk | footer statistics | **not recorded** |

  So `-chunk-stats` here returns `:rows` and `:nulls` and **no bounds**, and
  the protocol already had a meaning for that: `columnar.stats` documents
  absent min/max as \"the source is not making a claim\", and refuses to prune
  on it. The consequence is visible rather than hidden — an Arrow source
  prunes only all-null chunks, `count` and `count-non-null` still come back
  `{:from :statistics :read 0}`, and `min`/`max` fall through to a scan.

  That is the answer to the question this repo was written to ask. The seam is
  not Parquet-shaped: a format that records less plugs in by reporting less,
  not by growing a special case.

  ## What it did cost

  One thing moved. `IByteSource` lived in `parquet.bytes`, and a second format
  needing the identical protocol made it shared rather than Parquet's, so it
  is now `columnar.bytes` — beside `IColumnSource`, which is the other half of
  the same seam."
  (:require [arrow.decode :as decode]
            [arrow.ipc :as ipc]
            [columnar.bytes :as bytes]
            [columnar.source :as csrc]))

(defn- column-index [fields column]
  (or (first (keep-indexed (fn [i f] (when (= column (:name f)) i)) fields))
      (throw (ex-info "column not in this file"
                      {:type :arrow/unknown-column
                       :column column :columns (mapv :name fields)}))))

(defn- buffer-base
  "Index of the first buffer belonging to field `k`.

  Buffers are listed for every field in order, so a field's own buffers begin
  after the sum of all the ones before it. `ipc/buffer-counts` throws for a
  layout it cannot size, which is what keeps this from silently reading the
  wrong field's bytes."
  [counts k]
  (reduce + 0 (take k counts)))

(defprotocol IArrowBufferSource
  (-column-buffer-views [source chunk column]
    "Borrow one uncompressed Arrow column's physical buffers.

    The returned `columnar.bytes/IByteView` values retain host backing storage;
    they do not decode or materialise row values. Compressed buffers fail
    closed because decompression necessarily owns a new buffer and therefore
    is not this API's zero-copy path."))

(defn column-buffer-views
  "Borrow the validity/value or validity/offset/data buffers for one column.

  This is the CPU zero-copy seam and the GPU one-upload seam. It does not claim
  that network ingress or GPU device upload allocates nothing; it guarantees
  that Arrow projection adds no intermediate row/value copy."
  [source chunk column]
  (-column-buffer-views source chunk column))

(defn- buffer-roles [{:keys [type]}]
  (case type
    :null []
    (:utf8 :large-utf8 :binary :large-binary) [:validity :offsets :data]
    [:validity :values]))

(defn open
  "A `columnar/IColumnSource` over `src` — a `columnar.bytes/IByteSource`, or a
  vector for a file already in memory.

  The footer is parsed once, here, from two ranges. Batch metadata is read
  lazily and memoised: a query that prunes on nulls, or asks only for `count`,
  pays for the small message headers and never reaches a body."
  [src]
  (let [src (bytes/source src)
        {:keys [schema batches]} (ipc/footer src)
        fields (:fields schema)
        counts (ipc/buffer-counts fields)
        header (memoize (fn [i] (ipc/batch-header src (nth batches i))))]
    (reify csrc/IColumnSource
      (-schema [_] (mapv :name fields))
      (-chunk-count [_] (count batches))
      (-chunk-rows [_ chunk] (:rows (header chunk)))
      (-chunk-stats [_ chunk column]
        (let [k (column-index fields column)
              {:keys [nodes rows]} (header chunk)
              node (nth nodes k nil)]
          ;; No :min/:max, ever — Arrow does not record them. `columnar.stats`
          ;; reads their absence as "no claim" and refuses to prune, which is
          ;; the correct and strictly weaker behaviour, and the reason this
          ;; must not be padded out with invented bounds.
          (when node
            {:rows (or (:length node) rows) :nulls (:nulls node)})))
      (-read-column [_ chunk column]
        (let [k (column-index fields column)
              f (nth fields k)
              {:keys [rows buffers compression body-at]} (header chunk)]
          ;; Before any byte of the body is fetched: a refusal must not cost a
          ;; download.
          (decode/check-readable! f compression)
          (let [base (buffer-base counts k)
                mine (subvec buffers base (+ base (nth counts k)))
                fetched (mapv (fn [{:keys [offset length]}]
                                (->> (if (zero? length)
                                       []
                                       (vec (bytes/-read-range
                                             src (+ body-at offset)
                                             (+ body-at offset length))))
                                     ;; Per BUFFER, not per body -- each carries
                                     ;; its own length prefix, and a -1 means
                                     ;; this one was stored raw.
                                     (decode/decompress-buffer compression)))
                              mine)]
            (decode/column f rows fetched))))
      IArrowBufferSource
      (-column-buffer-views [_ chunk column]
        (let [k (column-index fields column)
              f (nth fields k)
              {:keys [rows buffers compression body-at]} (header chunk)]
          (decode/check-readable! f compression)
          (when compression
            (throw (ex-info "compressed Arrow buffers cannot be borrowed"
                            {:type :arrow/buffer-view-requires-decompression
                             :compression compression :column column
                             :copy-boundary :decompression})))
          (let [base (buffer-base counts k)
                mine (subvec buffers base (+ base (nth counts k)))
                roles (buffer-roles (:logical f))]
            {:field f
             :rows rows
             :copy-boundary :borrowed-source
             :buffers
             (mapv (fn [role {:keys [offset length]}]
                     (let [start (+ body-at offset)]
                       {:role role
                        :file-offset start
                        :length length
                        :view (if (zero? length)
                                (bytes/view [])
                                (bytes/read-view-range src start (+ start length)))}))
                   roles mine)}))))))

(defn metadata
  "The parsed footer, for callers that want the schema or the batch blocks
  without going through the column source."
  [src]
  (ipc/footer (bytes/source src)))
