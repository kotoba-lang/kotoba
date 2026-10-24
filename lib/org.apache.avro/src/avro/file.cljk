(ns avro.file
  "The Avro Object Container File: header, schema, blocks, sync markers.

      'O' 'b' 'j' 0x01
      metadata map           avro.schema (JSON), avro.codec
      16-byte sync marker
      block: count, byte-size, data, sync
      block: ...

  ## The sync marker is the integrity check, and it is checked

  Every block ends with a copy of the header's 16-byte marker. A reader that
  skips it will happily walk off the end of a truncated block and decode the
  next block's length as a record — producing values, which is the failure
  mode worth paying one comparison per block to avoid.

  ## Blocks carry their byte size, so a codec this reader refuses is skippable

  The block header is `(record-count, byte-count)`. That second number is what
  lets a file compressed with a codec we do not have still report **how many
  records it holds** — the Avro analogue of Parquet statistics being readable
  from a file whose pages are not. `records` refuses, `record-count` does not."
  (:require [avro.binary :as b]
            [avro.datum :as datum]
            [avro.schema :as schema]
            [deflate.core :as deflate]
            [json.core :as json]
            [zstd.core :as zstd]))

(def magic [0x4F 0x62 0x6A 0x01])          ; "Obj\1"
(def ^:private sync-size 16)

(def decodable-codecs
  "Codecs whose blocks this reader can undo.

  `snappy` is absent: Avro frames it with a 4-byte big-endian CRC-32C suffix
  that the Parquet reader's raw-block snappy does not carry, so wiring that
  decoder here would decode most blocks and corrupt the checksum on all of
  them. Refused by name instead."
  #{"null" "deflate" "zstandard"})

(defn- header
  "-> `{:schema .. :codec .. :sync [..] :at n}`."
  [bs]
  (when-not (= magic (vec (take 4 bs)))
    (throw (ex-info "not an Avro container file" {:type :avro/not-avro})))
  (let [[meta i] (loop [i 4 acc {}]
                   (let [[n i'] (b/long-at bs i)
                         n (long n)]
                     (if (zero? n)
                       [acc i']
                       (let [[cnt i'] (if (neg? n)
                                        (let [[_ i''] (b/long-at bs i')] [(- n) i''])
                                        [n i'])
                             [m i''] (reduce (fn [[a j] _]
                                               (let [[k j'] (b/string-at bs j)
                                                     [v j''] (b/bytes-at bs j')]
                                                 [(assoc a k v) j'']))
                                             [acc i'] (range cnt))]
                         (recur i'' m)))))
        codec (if-let [c (get meta "avro.codec")] (b/utf8 c) "null")]
    {:schema (schema/parse (b/utf8 (or (get meta "avro.schema")
                                       (throw (ex-info "file declares no avro.schema"
                                                       {:type :avro/malformed})))))
     :meta meta
     :codec codec
     :sync (vec (subvec (vec bs) i (+ i sync-size)))
     :at (+ i sync-size)}))

(defn- decompress [codec block]
  (case codec
    "null" block
    "deflate" (vec (deflate/inflate-raw block))
    "zstandard" (vec (zstd/decompress block))
    (throw (ex-info (str "avro: codec " (pr-str codec) " is not implemented"
                         " — the record count is still readable from this file")
                    {:type :avro/unsupported-codec :codec codec
                     :decodable (vec decodable-codecs)}))))

(defn blocks
  "Every block's `{:count :size :at}` — **without decompressing anything**.

  This is the cheap call: it walks header-to-header using the declared byte
  sizes, verifying each sync marker, and never looks at a record. It is what
  makes `record-count` answerable for a codec this reader cannot undo."
  [bs]
  (let [{:keys [sync at]} (header bs)
        n (count bs)]
    (loop [i at out []]
      (if (>= i n)
        out
        (let [[cnt i'] (b/long-at bs i)
              [size i''] (b/long-at bs i')
              size (long size)
              data-end (+ i'' size)
              marker (vec (subvec (vec bs) data-end (+ data-end sync-size)))]
          (when-not (= sync marker)
            (throw (ex-info "block sync marker does not match the header's"
                            {:type :avro/desynchronised :at data-end})))
          (recur (+ data-end sync-size)
                 (conj out {:count (long cnt) :size size :at i''})))))))

(defn record-count
  "Total records, from block headers alone.

  Answerable on a file whose codec this reader refuses — the same property
  Parquet statistics have, and the reason a partial reader earns its keep."
  [bs]
  (reduce + 0 (map :count (blocks bs))))

(defn file-schema [bs] (:schema (header bs)))

(defn metadata
  "The file's metadata map, values decoded as UTF-8 strings.

  `avro.schema` and `avro.codec` are in here too; `schema-json` and
  `file-schema` are the named accessors for the first because that is the one
  every reader needs. Iceberg's manifest metadata (`schema`,
  `partition-spec`, `format-version`) is reached through this."
  [bs] (into {} (map (fn [[k v]] [k (b/utf8 v)])) (:meta (header bs))))

(defn schema-json
  "The file's `avro.schema` metadata, as the JSON text it is stored as.

  `file-schema` gives the resolved shape, which is what decoding needs and
  what a caller reasons about. This gives the bytes' own words, which is what
  REWRITING needs: `(write {:schema (schema-json bs) :records (records bs)})`
  reproduces a file without this repo having to be able to render a resolved
  schema back into JSON -- a second serialiser that could disagree with the
  first."
  [bs] (b/utf8 (get (:meta (header bs)) "avro.schema")))

(defn records
  "Every record in the file, decoded.

  Throws for a codec `decodable-codecs` does not name, **after** the block
  walk has succeeded — so a caller that wanted the count already has it."
  [bs]
  (let [{:keys [schema codec sync]} (header bs)
        _ sync]
    (into []
          (mapcat (fn [{:keys [count size at]}]
                    (let [raw (subvec (vec bs) at (+ at size))
                          block (decompress codec raw)]
                      (first (reduce (fn [[acc j] _]
                                       (let [[v j'] (datum/decode schema block j)]
                                         [(conj acc v) j']))
                                     [[] 0] (range count))))))
          (blocks bs))))

;; ---------------------------------------------------------------------------
;; Writing.
;; ---------------------------------------------------------------------------

(def encodable-codecs
  "Codecs this writer can produce.

  `snappy` is absent for the same reason `decodable-codecs` omits it: Avro
  frames snappy with a trailing big-endian CRC-32C this repo does not compute,
  and emitting the frame without it would produce a file every conformant
  reader rejects.

  `zstandard` is present but does not compress -- `org-ietf-zstd` writes
  conformant frames of raw blocks and has no encoder. It is here so a caller
  who must emit that codec name can, not because it saves bytes."
  #{"null" "deflate" "zstandard"})

(defn- compress [codec block]
  (case codec
    "null" (vec block)
    "deflate" (vec (deflate/deflate-raw block))
    "zstandard" (vec (zstd/compress block))
    (throw (ex-info (str "avro: cannot write codec " (pr-str codec))
                    {:type :avro/unsupported-codec :codec codec
                     :encodable (vec encodable-codecs)}))))

(defn- random-sync []
  ;; A delimiter, not a secret: its job is to be unlikely to occur inside the
  ;; encoded data, so that a truncated block is detected rather than decoded.
  ;; `rand-int` is adequate for that and portable; callers who need a
  ;; byte-identical file pass `:sync` instead.
  (vec (repeatedly sync-size #(rand-int 256))))

(defn- metadata-block
  "map<string,bytes> in Avro's block framing: count, pairs, terminator."
  [m]
  (into (into (b/long-of (count m))
              (mapcat (fn [[k v]] (into (b/string-of k) (b/bytes-of v))))
              m)
        (b/long-of 0)))

(defn write
  "Records → the bytes of an Avro Object Container File.

      (avro.file/write {:schema {\"type\" \"record\" \"name\" \"Sale\"
                                 \"fields\" [{\"name\" \"price\" \"type\" \"long\"}]}
                        :records [{\"price\" 10}]
                        :codec \"deflate\"})

  `:schema` is JSON — either a string used verbatim, or data this encodes with
  `json.core/encode`. **The same schema is written into the file and used to
  encode the records**, which is the writing half of the property `avro.file`
  is built around: a reader takes the schema from the file, so writer and
  reader cannot be given disagreeing ones.

  `:codec` defaults to the null codec. `:records-per-block` defaults to 1000 --
  blocks exist so a reader can walk or skip without decoding, and one giant
  block gives it nothing to walk. `:sync` overrides the random marker, for a
  caller that needs the same input to produce the same bytes.

  `:meta` adds entries to the file's metadata map, which is part of the
  container format and not a comment field: Apache Iceberg keeps a manifest's
  table schema and partition spec there, and a manifest without them is not
  readable as a manifest. Values may be strings (encoded UTF-8) or byte
  sequences. `avro.schema` and `avro.codec` are derived and rejected if
  passed -- a file whose declared schema and encoding schema disagree is
  exactly what this writer is built to make impossible."
  [{:keys [schema records codec sync records-per-block meta]
    :or {codec "null" records-per-block 1000}}]
  (when-not (encodable-codecs codec)
    (throw (ex-info (str "avro: cannot write codec " (pr-str codec))
                    {:type :avro/unsupported-codec :codec codec
                     :encodable (vec encodable-codecs)})))
  (let [schema-json (if (string? schema) schema (json/encode schema))
        resolved (schema/parse schema-json)
        sync (or sync (random-sync))]
    (when-not (= sync-size (count sync))
      (throw (ex-info "avro: sync marker must be 16 bytes"
                      {:type :avro/malformed :actual (count sync)})))
    (when-let [reserved (seq (filter #{"avro.schema" "avro.codec"} (keys meta)))]
      (throw (ex-info (str "avro: " (vec reserved) " is derived, not caller-set")
                      {:type :avro/reserved-metadata :keys (vec reserved)})))
    (into (into (vec magic)
                (metadata-block (into {"avro.schema" (b/utf8-of schema-json)
                                       "avro.codec" (b/utf8-of codec)}
                                      (map (fn [[k v]]
                                             [k (if (string? v) (b/utf8-of v) (vec v))]))
                                      meta)))
          (into (vec sync)
                (mapcat (fn [chunk]
                          (let [body (compress codec
                                               (into [] (mapcat #(datum/encode resolved %)) chunk))]
                            (-> (b/long-of (count chunk))
                                (into (b/long-of (count body)))
                                (into body)
                                (into sync))))
                        (partition-all records-per-block records))))))
