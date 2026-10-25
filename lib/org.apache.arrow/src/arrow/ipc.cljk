(ns arrow.ipc
  "The Arrow IPC **file** format: magic, footer, blocks, and the encapsulated
  message envelope every batch is wrapped in.

  ## What the layout buys, and what it does not

      ARROW1\\0\\0
      <message: Schema>
      <message: RecordBatch> ... one per batch
      <Footer flatbuffer>
      <int32 footer length>
      ARROW1

  The footer at the end lists every batch as a `Block` — an offset, a metadata
  length and a body length — so a reader seeks to a batch without walking the
  ones before it, and inside a batch every buffer's offset and length are in
  the metadata, so reading one column does not touch another's bytes. Both are
  the properties that make this format worth a `:scan` reader rather than a
  materializing one.

  **What is NOT here is min/max.** Arrow records `length` per batch and
  `null_count` per field, and nothing else. That is a real difference from
  Parquet rather than an omission in this reader, and it is load-bearing for
  `arrow.source`: a chunk whose bounds are unknown must be read, so an Arrow
  source prunes strictly less than a Parquet one and says so by reporting
  statistics without `:min`/`:max`. `columnar.stats` already treats absent
  bounds as \"no claim\", so nothing in the engine changed to accommodate this.

  ## Metadata survives buffers this reader cannot decode

  Body compression (LZ4, ZSTD) is a property of the **buffers**; batch
  lengths and null counts live in the **metadata**, which is never compressed.
  So a zstd file still answers `count`, still answers `count-non-null`, and
  still prunes all-null chunks, while `-read-column` refuses it by name. That
  is the same property `org-apache-parquet` holds for statistics on encodings
  it cannot decode, and `compressed.arrow` is the fixture that keeps it
  tested."
  (:require [arrow.flatbuffers :as fb]
            [columnar.bytes :as bytes]))

(def magic
  "`ARROW1`. Opens the file (padded to 8) and closes it (unpadded)."
  [0x41 0x52 0x52 0x4F 0x57 0x31])

(def footer-suffix-bytes
  "The fixed tail: a 4-byte footer length and `ARROW1`."
  10)

;; ── the type union ──────────────────────────────────────────────────────────

(def ^:private type-ids
  "`Type` union tags, in the order the schema declares them. The numbers are
  the wire format, so they are written out rather than derived from a
  sequence — inserting a name in the wrong place would silently reinterpret
  every file."
  {1 :null 2 :int 3 :floating-point 4 :binary 5 :utf8 6 :bool 7 :decimal
   8 :date 9 :time 10 :timestamp 11 :interval 12 :list 13 :struct 14 :union
   15 :fixed-size-binary 16 :fixed-size-list 17 :map 18 :duration
   19 :large-binary 20 :large-utf8 21 :large-list 22 :run-end-encoded
   23 :binary-view 24 :utf8-view 25 :list-view 26 :large-list-view})

(defn- logical-type
  "The concrete type of a field, from the union tag and the union member.

  Returns `{:type k}` plus whatever the member adds. An unknown tag is
  returned as `{:type :unknown :tag n}` rather than thrown: a schema this
  reader does not understand must still be listable, because refusing to name
  a file's columns is a worse failure than refusing to decode one of them."
  [bs field-pos]
  (let [tag (fb/scalar fb/u8 bs field-pos 2 0)
        kind (get type-ids tag :unknown)
        member (fb/ref-at bs field-pos 3)]
    (case kind
      :int (let [w (fb/scalar fb/i32 bs member 0 32)
                 signed? (not (zero? (fb/scalar fb/u8 bs member 1 0)))]
             {:type (keyword (str (if signed? "int" "uint") w)) :bit-width w :signed? signed?})
      :floating-point (let [p (fb/scalar fb/i16 bs member 0 2)]
                        {:type (case p 0 :half-float 1 :float 2 :double :unknown)
                         :precision p})
      :unknown {:type :unknown :tag tag}
      {:type kind})))

(defn- field
  "One `Field` of a schema.

  `:dictionary?` is carried because a dictionary-encoded field's buffers hold
  indices rather than values, so the column cannot be decoded without the
  dictionary batches. It is recorded here and refused in `arrow.decode`, at
  the point where it would produce wrong values."
  [bs p]
  {:name (fb/string-field bs p 0)
   :nullable? (not (zero? (fb/scalar fb/u8 bs p 1 0)))
   :dictionary? (some? (fb/ref-at bs p 4))
   :children (count (fb/table-vector bs p 5))
   :logical (logical-type bs p)})

(defn- schema-at [bs p]
  {:endianness (fb/scalar fb/i16 bs p 0 0)
   :fields (mapv #(field bs %) (fb/table-vector bs p 1))})

;; ── blocks ──────────────────────────────────────────────────────────────────

(def ^:private block-stride
  "`struct Block { offset: long; metaDataLength: int; bodyLength: long; }`.

  24 and not 20: the trailing long forces 8-byte alignment, so the int is
  followed by four bytes of padding. Getting this wrong reads the second
  block's offset out of the first block's body length, which yields a
  plausible number and a wrong seek."
  24)

(defn- block [bs p]
  {:offset (fb/i64 bs p)
   :meta-len (fb/i32 bs (+ p 8))
   :body-len (fb/i64 bs (+ p 16))})

;; ── the footer ──────────────────────────────────────────────────────────────

(defn- check-magic! [bs]
  (when-not (= magic (vec (take 6 bs)))
    (throw (ex-info "not an Arrow IPC file (bad trailing magic)"
                    {:type :arrow/not-an-arrow-file}))))

(defn footer
  "Parse the footer of `src`, an `columnar.bytes/IByteSource`.

  Two ranges, in order, and the second depends on the first — the tail carries
  the footer's length. Every later question about batch offsets, batch row
  counts and the schema is answered out of what this returned, so opening a
  file costs the footer and nothing more however large the file is."
  [src]
  (let [size (bytes/-size src)
        tail (vec (bytes/-read-range src (- size footer-suffix-bytes) size))
        _ (check-magic! (subvec tail 4))
        flen (fb/i32 tail 0)
        start (- size footer-suffix-bytes flen)
        bs (vec (bytes/-read-range src start (+ start flen)))
        root (fb/root bs)]
    {:version (fb/scalar fb/i16 bs root 0 0)
     :schema (if-let [p (fb/ref-at bs root 1)]
               (schema-at bs p)
               (throw (ex-info "footer carries no schema"
                               {:type :arrow/malformed})))
     :dictionaries (mapv #(block bs %) (fb/struct-vector bs root 2 block-stride))
     :batches (mapv #(block bs %) (fb/struct-vector bs root 3 block-stride))}))

;; ── the encapsulated message envelope ───────────────────────────────────────

(def ^:private continuation 0xFFFFFFFF)

(defn message
  "Parse the message metadata in `bs`, a range that starts at a block's offset.

  The envelope gained a `0xFFFFFFFF` continuation word in Arrow 0.15, and
  files written before that begin with the metadata length directly. Both are
  accepted: the marker is not a version to check but a discriminator to read,
  and refusing the older spelling would reject files for their vintage rather
  than their content."
  [bs]
  (let [prefix (if (= continuation (fb/u32 bs 0)) 8 4)
        meta-size (fb/i32 bs (- prefix 4))
        flat (subvec (vec bs) prefix (+ prefix meta-size))
        root (fb/root flat)]
    {:prefix prefix
     :meta-size meta-size
     :header-type (fb/scalar fb/u8 flat root 1 0)
     :header (fb/ref-at flat root 2)
     :body-length (fb/scalar fb/i64 flat root 3 0)
     :flat flat
     :root root}))

(def ^:private buffers-per-type
  "How many buffers a flat field of each type contributes, in the order the
  record batch lists them.

  A type absent from this map is one this reader cannot locate buffers for,
  which is a different failure from one it cannot decode: an unknown buffer
  count desynchronises **every column after it**, so the refusal has to happen
  before any column is read rather than when the bad one is asked for."
  {:null 0
   :bool 2 :int8 2 :int16 2 :int32 2 :int64 2
   :uint8 2 :uint16 2 :uint32 2 :uint64 2
   :half-float 2 :float 2 :double 2
   :utf8 3 :binary 3 :large-utf8 3 :large-binary 3})

(defn buffer-counts
  "Buffers each field contributes, or a throw naming the first field whose
  layout is unknown."
  [fields]
  (mapv (fn [{:keys [name logical children]}]
          (or (when (zero? children) (get buffers-per-type (:type logical)))
              (throw (ex-info (str "arrow: field " (pr-str name) " has type "
                                   (pr-str (:type logical))
                                   " whose buffer layout is not implemented"
                                   " — batch metadata is still readable")
                              {:type :arrow/unsupported-layout
                               :column name :logical (:type logical)
                               :nested? (pos? children)}))))
        fields))

(defn record-batch
  "The `RecordBatch` header of a message: row count, per-field nodes, per-field
  buffers, and the body compression when the writer applied one."
  [{:keys [flat header]}]
  (let [bs flat
        nodes (fb/struct-vector bs header 1 16)
        bufs (fb/struct-vector bs header 2 16)
        comp (fb/ref-at bs header 3)]
    {:rows (fb/scalar fb/i64 bs header 0 0)
     :nodes (mapv (fn [p] {:length (fb/i64 bs p) :nulls (fb/i64 bs (+ p 8))}) nodes)
     :buffers (mapv (fn [p] {:offset (fb/i64 bs p) :length (fb/i64 bs (+ p 8))}) bufs)
     :compression (when comp
                    (case (fb/scalar fb/u8 bs comp 0 0)
                      0 :lz4-frame
                      1 :zstd
                      :unknown))}))

(defn batch-header
  "Read and parse one batch's metadata from `src` — the message range only, not
  the body.

  This is the cheap call the whole `:scan` profile rests on: row counts and
  null counts come from here, so an aggregate that the metadata can answer
  never reaches the body."
  [src {:keys [offset meta-len]}]
  (let [bs (vec (bytes/-read-range src offset (+ offset meta-len)))
        msg (message bs)]
    (when-not (= 3 (:header-type msg))
      (throw (ex-info (str "expected a RecordBatch message, got header type "
                           (:header-type msg))
                      {:type :arrow/malformed :header-type (:header-type msg)})))
    (assoc (record-batch msg) :body-at (+ offset meta-len))))
