(ns parquet.write
  "Parquet files, written from `columnar.vector` columns.

  ## Why this exists when `arrow.write` already did

  Arrow IPC records no column statistics, so an object materialised as Arrow
  **cannot be pruned** — every later query over it reads every batch. Chain a
  few materialisations and the intermediates are strictly weaker than the
  Parquet they came from.

  Parquet is the format that fixes that, and it fixes it in the container
  every other tool already reads rather than in a sidecar this workspace would
  have to invent and keep from drifting. **The writer computes min/max/null
  counts as it goes** — it has the columns in hand — and writes them into the
  footer, where `parquet.source` finds them without reading a page.

  There is a test asserting exactly that: a query over a file written here
  reads one row group and skips two.

  ## What it writes

  One row group per batch, one PLAIN-encoded, uncompressed data page per
  column chunk. `int32`, `int64`, `double`, `byte_array` — **exactly the set
  `parquet.decode` can read back**, because writing what our own reader
  refuses would be a strange thing to own. Everything else is refused by name.

  ## Definition levels

  A REQUIRED column writes no levels section at all. An OPTIONAL one writes a
  4-byte little-endian length, then RLE runs of the levels, then the values
  **for the present rows only** — which is why the levels have to be written
  before the count of values is known."
  (:require [columnar.vector :as cvec]
            [parquet.thrift :as th]
            [snappy.core :as snappy]))

(def ^:private physical-id {:boolean 0 :int32 1 :int64 2 :float 4 :double 5
                            :byte-array 6})
(def ^:private repetition-id {:required 0 :optional 1 :repeated 2})
(def ^:private encoding-id {:plain 0 :rle 3})

(def codec-id
  "Parquet's CompressionCodec enum, for the codecs this writer can produce.

  The others in the enum (gzip, lzo, brotli, lz4, zstd) are absent rather than
  listed and rejected later: a name in this map is a promise that a page body
  can actually be compressed with it, and this workspace has one compressor
  for a Parquet codec. `org-ietf-zstd` writes conformant frames of RAW blocks
  and has no encoder, so declaring ZSTD here would produce files that are
  correct, larger than uncompressed, and labelled compressed."
  {:uncompressed 0 :snappy 1})

(defn- compress-body
  "-> the bytes a page carries, for `codec`."
  [codec body]
  (case codec
    :uncompressed body
    :snappy (snappy/compress body)
    (throw (ex-info (str "parquet: cannot write codec " (pr-str codec))
                    {:type :parquet/unsupported-codec :codec codec
                     :writable (vec (sort (keys codec-id)))}))))
(def ^:private converted-utf8 0)

(def writable
  "Physical types this writer emits — the set `parquet.decode` reads back."
  #{:int32 :int64 :double :byte-array})

(def ^:private logical->physical
  "How a column's declared type becomes a Parquet physical type.

  `:utf8` is Arrow's name and `:byte-array` is Parquet's, so a column read out
  of an Arrow file writes to Parquet without the caller restating its type —
  which is what makes arrow→parquet conversion a two-liner, and arrow→parquet
  is how a materialised result gains statistics."
  {:int32 :int32 :uint32 :int32 :int16 :int32 :int8 :int32
   :int64 :int64 :uint64 :int64
   :double :double :float :double
   :utf8 :byte-array :large-utf8 :byte-array :string :byte-array
   :byte-array :byte-array})

;; ── little-endian primitives ────────────────────────────────────────────────

(defn- le [v n]
  #?(:clj (mapv #(bit-and (unsigned-bit-shift-right (long v) (* 8 %)) 0xff) (range n))
     :cljs (if (<= n 4)
             (mapv #(bit-and (unsigned-bit-shift-right (bit-and v 0xffffffff) (* 8 %)) 0xff)
                   (range n))
             (let [m (js/Math.abs v)]
               (when (> m js/Number.MAX_SAFE_INTEGER)
                 (throw (ex-info "integer exceeds this runtime's exact range"
                                 {:type :parquet/precision-unavailable :approx v})))
               (let [lo0 (mod m 4294967296)
                     hi0 (js/Math.floor (/ m 4294967296))
                     [lo hi] (if (neg? v)
                               (if (zero? lo0)
                                 [0 (mod (- 4294967296 hi0) 4294967296)]
                                 [(- 4294967296 lo0) (- 4294967295 hi0)])
                               [lo0 hi0])]
                 (into (mapv #(bit-and (unsigned-bit-shift-right lo (* 8 %)) 0xff) (range 4))
                       (mapv #(bit-and (unsigned-bit-shift-right hi (* 8 %)) 0xff) (range 4))))))))

(defn- plain-value [physical v]
  (case physical
    :int32 (le v 4)
    :int64 (le v 8)
    :double (th/double-bytes v)
    :byte-array (let [bs (th/string-bytes v)] (into (le (count bs) 4) bs))))

(defn- stat-bytes
  "A statistic's wire form: the value's PLAIN encoding, minus the length
  prefix a BYTE_ARRAY carries inside a page."
  [physical v]
  (case physical
    :byte-array (th/string-bytes v)
    (plain-value physical v)))

;; ── definition levels ───────────────────────────────────────────────────────

(defn rle-levels
  "Levels as RLE runs: `varint((run << 1) | 0)` then the value in
  `ceil(width/8)` bytes.

  Run-length rather than bit-packed because the runs in a real column are long
  — a column is usually mostly present or mostly absent — and because an RLE
  run is legal for any input, where a bit-packed run must be padded to a
  multiple of 8 and then trimmed by the reader."
  [levels byte-width]
  (->> levels
       (partition-by identity)
       (mapcat (fn [run]
                 (into (th/write-varint (bit-shift-left (count run) 1))
                       (le (first run) byte-width))))
       vec))

;; ── one column chunk ────────────────────────────────────────────────────────

(defn- column-chunk
  "`{:bytes .. :stats .. :num-values .. :uncompressed ..}` for one column of
  one row group.

  `:uncompressed` is what the chunk would have occupied uncompressed, header
  included. Parquet records both totals, and a reader that trusts
  total_uncompressed_size to size a buffer gets a short one if the writer
  reports the compressed number twice."
  [{:keys [physical required?]} col codec]
  (let [n (cvec/count col)
        present (filterv #(cvec/valid-at? col %) (range n))
        values (mapv #(cvec/value-at col %) present)
        nulls (- n (count present))]
    (when (and required? (pos? nulls))
      (throw (ex-info "a REQUIRED column cannot contain nulls"
                      {:type :parquet/null-in-required :nulls nulls})))
    (let [body (if required?
                 (vec (mapcat #(plain-value physical %) values))
                 (let [lv (rle-levels (mapv #(if (cvec/valid-at? col %) 1 0) (range n)) 1)]
                   (into (into (le (count lv) 4) lv)
                         (mapcat #(plain-value physical %)) values)))
          cbody (compress-body codec body)
          header (th/encode-struct
                  [[1 :i32 0]                       ; DATA_PAGE
                   [2 :i32 (count body)]            ; uncompressed_page_size
                   [3 :i32 (count cbody)]           ; compressed_page_size
                   [5 :struct (th/encode-struct
                               [[1 :i32 n]          ; num_values INCLUDES nulls
                                [2 :i32 (encoding-id :plain)]
                                [3 :i32 (encoding-id :rle)]
                                [4 :i32 (encoding-id :rle)]])]])]
      {:bytes (into (vec header) cbody)
       :uncompressed (+ (count header) (count body))
       :num-values n
       :stats (cond-> {:nulls nulls}
                (seq values)
                (assoc :min (reduce (fn [a b] (if (neg? (compare b a)) b a)) values)
                       :max (reduce (fn [a b] (if (pos? (compare b a)) b a)) values)))})))

(defn- column-meta [{:keys [name physical]} {:keys [num-values stats uncompressed]}
                    offset size codec]
  (th/encode-struct
   [[1 :i32 (physical-id physical)]
    [2 :list (th/encode-list :i32 [(encoding-id :plain) (encoding-id :rle)])]
    [3 :list (th/encode-list :binary [(th/string-bytes name)])]
    [4 :i32 (codec-id codec)]
    [5 :i64 num-values]
    [6 :i64 uncompressed]                        ; total_uncompressed_size
    [7 :i64 size]                                ; total_compressed_size
    [9 :i64 offset]                              ; data_page_offset
    [12 :struct (th/encode-struct
                 (cond-> [[3 :i64 (:nulls stats)]]
                   (contains? stats :max)
                   (conj [5 :binary (stat-bytes physical (:max stats))])
                   (contains? stats :min)
                   (conj [6 :binary (stat-bytes physical (:min stats))])))]]))

;; ── the file ────────────────────────────────────────────────────────────────

(defn- schema-elements [fields]
  (into [(th/encode-struct [[4 :binary (th/string-bytes "schema")]
                            [5 :i32 (count fields)]])]
        (map (fn [{:keys [name physical required?]}]
               (th/encode-struct
                (cond-> [[1 :i32 (physical-id physical)]
                         [3 :i32 (repetition-id (if required? :required :optional))]
                         [4 :binary (th/string-bytes name)]]
                  ;; UTF8, so other readers report `string` rather than opaque
                  ;; binary. Ours decodes BYTE_ARRAY to a string either way.
                  (= physical :byte-array) (conj [6 :i32 converted-utf8])))))
        fields))

(defn fields-of
  "Schema fields from `named-cols` (`[[name column] ...]`).

  Columns are declared OPTIONAL: a materialised query result may have nulls in
  the next batch even when this one has none, and REQUIRED is the claim that
  cannot be walked back."
  [named-cols]
  (mapv (fn [[n c]]
          (let [t (:type c)
                physical (or (logical->physical t)
                             (throw (ex-info (str "parquet: writing " (pr-str t)
                                                  " is not implemented")
                                             {:type :parquet/unsupported-type
                                              :column n :logical t
                                              :writable writable})))]
            {:name n :physical physical :required? false}))
        named-cols))

(def ^:private magic [0x50 0x41 0x52 0x31])

(defn file
  "Parquet file bytes.

  `{:fields [{:name :physical :required?} ...] :batches [[col ...] ...]}` —
  one row group per batch, columns matching `:fields` in order."
  [{:keys [fields batches codec] :or {codec :uncompressed}}]
  (doseq [{:keys [physical name]} fields]
    (when-not (contains? writable physical)
      (throw (ex-info (str "parquet: writing " (pr-str physical) " is not implemented")
                      {:type :parquet/unsupported-type :column name
                       :logical physical :writable writable}))))
  (loop [bs batches, out (vec magic), groups [], total-rows 0]
    (if-let [cols (first bs)]
      (let [rows (if (seq cols) (cvec/count (first cols)) 0)
            ;; Pages first: a column chunk's metadata carries the offset it was
            ;; written at, so the bytes have to exist before the footer can
            ;; describe them.
            [out' metas]
            (reduce (fn [[acc ms] [f c]]
                      (let [chunk (column-chunk f c codec)
                            at (count acc)]
                        [(into acc (:bytes chunk))
                         (conj ms [(column-meta f chunk at (count (:bytes chunk)) codec) at])]))
                    [out []] (map vector fields cols))
            group (th/encode-struct
                   [[1 :list (th/encode-list
                              :struct
                              (mapv (fn [[m at]]
                                      (th/encode-struct
                                       ;; file_offset is REQUIRED by the thrift
                                       ;; IDL. Our reader never looks at it, so
                                       ;; omitting it round-trips here and is
                                       ;; rejected outright by a strict
                                       ;; deserialiser. Measured: pyarrow said
                                       ;; "Couldn't deserialize thrift".
                                       [[2 :i64 at]
                                        [3 :struct m]]))
                                    metas))]
                    [2 :i64 (- (count out') (count out))]
                    [3 :i64 rows]])]
        (recur (rest bs) out' (conj groups group) (+ total-rows rows)))
      (let [;; One ColumnOrder per leaf, each the TYPE_DEFINED_ORDER union
            ;; member (an empty struct in field 1).
            ;;
            ;; Without this, `min_value`/`max_value` are INVISIBLE to other
            ;; readers: the spec says a reader may only trust them when the
            ;; sort order is declared, so pyarrow reports statistics as None
            ;; and every pruning decision it would have made is lost. Our own
            ;; reader reads them regardless, so the file looks perfect from
            ;; inside this repo and useless from outside — which would defeat
            ;; the entire reason for writing Parquet instead of a sidecar.
            ;; Measured: statistics were None until this was added.
            column-orders (mapv (fn [_] (th/encode-struct [[1 :struct (th/encode-struct [])]]))
                                fields)
            footer (th/encode-struct
                    [[1 :i32 1]                       ; version
                     [2 :list (th/encode-list :struct (schema-elements fields))]
                     [3 :i64 total-rows]
                     [4 :list (th/encode-list :struct groups)]
                     [6 :binary (th/string-bytes "kotoba-lang/org-apache-parquet")]
                     [7 :list (th/encode-list :struct column-orders)]])]
        (vec (concat out footer (le (count footer) 4) magic))))))

(defn of-columns
  "A single-row-group file from `[[name column] ...]`.

  `codec` defaults to `:uncompressed`, which is what this writer did before it
  could do anything else. Callers writing to object storage want `:snappy`."
  ([named-cols] (of-columns named-cols :uncompressed))
  ([named-cols codec]
   (file {:fields (fields-of named-cols) :batches [(mapv second named-cols)]
          :codec codec})))

(defn columns-of-rows
  "Columns from `rows` (maps) for `named-types` (`[[name type] ...]`)."
  [named-types rows]
  (mapv (fn [[n t]] [n (cvec/column t (mapv #(get % n) rows))]) named-types))
