(ns parquet.footer
  "The Parquet footer: schema, row groups, and the statistics pruning runs on.

  A Parquet file ends `… <FileMetaData> <4-byte footer length LE> PAR1`, so
  the metadata is found by reading the last 8 bytes and then seeking
  backwards. Two range reads locate everything about a file of any size —
  which is the entire reason in-place query is affordable.

  **The footer does not depend on how the pages were encoded.** Statistics
  are readable from a file compressed with a codec this repo cannot
  decompress and encoded with an encoding it cannot decode. That is not a
  curiosity: it means chunk pruning, `count`, `min` and `max` work on files
  `read-column` refuses. `parquet.source` leans on it, and there is a fixture
  written with snappy + dictionary specifically to hold that line."
  (:require [parquet.bytes :as pbytes]
            [parquet.thrift :as th]))

(def magic [0x50 0x41 0x52 0x31]) ; "PAR1"

(def physical-types
  {0 :boolean 1 :int32 2 :int64 3 :int96 4 :float 5 :double
   6 :byte-array 7 :fixed-len-byte-array})

(def repetitions {0 :required 1 :optional 2 :repeated})

(def codecs
  {0 :uncompressed 1 :snappy 2 :gzip 3 :lzo 4 :brotli 5 :lz4 6 :zstd 7 :lz4-raw})

(def encodings
  {0 :plain 2 :plain-dictionary 3 :rle 4 :bit-packed 5 :delta-binary-packed
   6 :delta-length-byte-array 7 :delta-byte-array 8 :rle-dictionary
   9 :byte-stream-split})

(def page-types {0 :data-page 1 :index-page 2 :dictionary-page 3 :data-page-v2})

(defn- le32 [bs i] (th/le-uint bs i 4))

(defn footer-span
  "`[start length]` of the FileMetaData struct, from the file's last 8 bytes.

  Reads the tail and the leading magic — 12 bytes total — rather than the
  file. Both magic markers are checked: a file whose trailing magic is right
  and whose leading magic is not has been truncated at the front or is not
  Parquet at all, and its footer would decode to plausible nonsense."
  [src]
  (let [src (pbytes/source src)
        n (-> src pbytes/-size long)]
    (when (< n 12)
      (throw (ex-info "too short to be a Parquet file" {:type :parquet/not-parquet :size n})))
    (when-not (= magic (vec (pbytes/-read-range src 0 4)))
      (throw (ex-info "missing leading PAR1" {:type :parquet/not-parquet})))
    (let [tail (vec (pbytes/-read-range src (- n 8) n))]
      (when-not (= magic (subvec tail 4 8))
        (throw (ex-info "missing trailing PAR1" {:type :parquet/not-parquet})))
      (let [len (long (le32 tail 0))
            start (- n 8 len)]
        (when (or (neg? start) (< start 4))
          (throw (ex-info "footer length points outside the file"
                          {:type :parquet/malformed :footer-length len :size n})))
        [start len]))))

(defn- statistics
  "Bounds a caller may prune with, or fewer of them.

  A bound this runtime cannot represent exactly is **dropped, not raised**.
  The two cases differ in whether a safe degradation exists: an absent bound
  means `columnar.stats` will not prune, which is slower and still correct,
  while an unrepresentable VALUE has no safe answer and `parquet.decode`
  refuses it. Raising here instead would make one oversized column render the
  whole file unopenable on ClojureScript — including for the columns that are
  perfectly fine. Measured: a single int64 past 2^53 did exactly that."
  [m physical]
  (when m
    (let [decode (fn [bv]
                   (try
                     (case physical
                       :int64 (th/le-uint bv 0 (min 8 (count bv)))
                       :int32 (th/le-uint bv 0 (min 4 (count bv)))
                       (:byte-array :fixed-len-byte-array) (th/bytes->string bv)
                       nil)
                     (catch #?(:clj Exception :cljs :default) e
                       (when-not (= :parquet/precision-unavailable (:type (ex-data e)))
                         (throw e))
                       nil)))
          ;; 5/6 are max_value/min_value; 1/2 are the deprecated max/min. Prefer
          ;; the former: the deprecated pair was written with a signed-comparison
          ;; bug for BYTE_ARRAY that the newer fields exist to escape.
          mx (some-> (or (get m 5) (get m 1)) decode)
          mn (some-> (or (get m 6) (get m 2)) decode)]
      (cond-> {:nulls (long (or (get m 3) 0))}
        (some? mn) (assoc :min mn)
        (some? mx) (assoc :max mx)))))

(defn- column-metadata [m]
  (let [physical (physical-types (get m 1))]
    {:type physical
     :encodings (mapv encodings (get m 2))
     :path (mapv th/bytes->string (get m 3))
     :codec (codecs (get m 4))
     :num-values (long (get m 5))
     :total-compressed-size (long (get m 7))
     :data-page-offset (long (get m 9))
     :dictionary-page-offset (some-> (get m 11) long)
     :statistics (statistics (get m 12) physical)}))

(defn- row-group [m]
  {:columns (mapv (fn [c] (column-metadata (get c 3))) (get m 1))
   :num-rows (long (get m 3))})

(defn- schema-element [m]
  (cond-> {:name (th/bytes->string (get m 4))}
    (get m 1) (assoc :type (physical-types (get m 1)))
    (get m 3) (assoc :repetition (repetitions (get m 3)))
    (get m 5) (assoc :num-children (long (get m 5)))))

(defn parse
  "Decode the footer of `src` (an `IByteSource`, or a whole-file vector).

  -> `{:version :num-rows :created-by :schema [..] :row-groups [..]}`.
  The first schema element is the root and carries no type; the leaf elements
  after it are the columns, in the order chunks appear.

  Two ranges are read: the 12 bytes that locate the footer, and the footer
  itself. Nothing else in the file is touched, whatever its size."
  [src]
  (let [src (pbytes/source src)
        [start len] (footer-span src)
        ;; Indexed from 0 within the fetched window. Absolute-to-relative
        ;; translation happens here and at the page read, and nowhere else --
        ;; the thrift decoder never learns that the file is bigger than what
        ;; it was handed.
        window (vec (pbytes/-read-range src start (+ start len)))
        m (th/parse-struct window 0)
        schema (mapv schema-element (get m 2))]
    {:version (some-> (get m 1) long)
     :num-rows (long (get m 3))
     :created-by (some-> (get m 6) th/bytes->string)
     :schema schema
     :columns (mapv :name (rest schema))
     :row-groups (mapv row-group (get m 4))}))

(defn page-header
  "Decode a PageHeader at `i`. -> `[header next-index]`, where next-index is
  where the page's (possibly compressed) body begins."
  [bs i]
  (let [[m i'] (th/parse-struct-with-end bs i)
        dp (get m 5)
        dict (get m 7)]
    [(cond-> {:type (page-types (get m 1))
              :uncompressed-size (long (get m 2))
              :compressed-size (long (get m 3))}
       dp (assoc :num-values (long (get dp 1))
                 :encoding (encodings (get dp 2))
                 :definition-level-encoding (encodings (get dp 3))
                 :repetition-level-encoding (encodings (get dp 4)))
       dict (assoc :num-values (long (get dict 1))
                   :encoding (encodings (get dict 2))))
     i']))
