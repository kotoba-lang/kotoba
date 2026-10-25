(ns parquet.decode
  "Page decoding: definition levels, then PLAIN values.

  The supported subset is **declared, and everything outside it throws with
  the name of what it met**. A decoder that guesses at an encoding it does
  not know produces plausible numbers, and plausible numbers from a file
  nobody can re-check is the worst failure available to this library — worse
  than not reading the file, because it is silent.

  Supported: `UNCOMPRESSED`, `SNAPPY`, `GZIP` and `ZSTD` codecs; `PLAIN`,
  `PLAIN_DICTIONARY` and `RLE_DICTIONARY` encodings; `DATA_PAGE` (v1); flat
  schemas; `REQUIRED` and `OPTIONAL` columns. Not supported, by name: brotli /
  lz4 / lzo, delta encodings, byte-stream-split, v2 data pages, and repeated
  (nested) columns."
  (:require [deflate.core :as deflate]
            [parquet.snappy :as snappy]
            [parquet.thrift :as th]
            [zstd.core :as zstd]))

(defn decompress
  "A page body, whatever codec it arrived in.

  `:uncompressed` returns the slice untouched rather than copying it through
  a no-op codec path, because the common case should not pay for the general
  one."
  [codec bs start end uncompressed-size]
  (case codec
    :uncompressed (subvec (vec bs) start end)
    :snappy (snappy/decompress bs start end uncompressed-size)
    ;; `org-ietf-deflate` rather than a second inflate here: Huffman + LZ77 by
    ;; hand in portable .cljc, verifying CRC-32 and ISIZE. java.util.zip and
    ;; Node's zlib would each work on exactly one of the runtimes this reader
    ;; has to keep running on.
    :gzip (let [out (deflate/gunzip (subvec (vec bs) start end))]
            (when (and uncompressed-size (not= (long uncompressed-size) (count out)))
              (throw (ex-info "gzip output is not the length the page header declared"
                              {:type :parquet/codec-length-mismatch
                               :header uncompressed-size :actual (count out)})))
            (vec out))
    ;; `org-ietf-zstd` for the same reason as deflate above. The declared
    ;; uncompressed size is checked rather than trusted: zstd frames carry
    ;; their own content size and checksum, so a mismatch means the page
    ;; header and the frame disagree about the same bytes, and a decoder that
    ;; picked one silently would hand the caller a short column.
    :zstd (let [out (zstd/decompress (subvec (vec bs) start end))]
            (when (and uncompressed-size (not= (long uncompressed-size) (count out)))
              (throw (ex-info "zstd output is not the length the page header declared"
                              {:type :parquet/codec-length-mismatch
                               :header uncompressed-size :actual (count out)})))
            (vec out))
    (throw (ex-info (str "parquet: unsupported codec " (pr-str codec)
                         " — statistics are still readable from this file")
                    {:type :parquet/unsupported :codec codec
                     :supported [:uncompressed :snappy :gzip]}))))

(def ^:private le th/le-uint)

(defn- as-signed-64 [v]
  (let [v (long v)] v))

(defn bit-width
  "Bits needed to hold `max-level`. 0 when the column is REQUIRED, in which
  case the levels section is absent entirely rather than present and empty."
  [max-level]
  (loop [w 0 n max-level] (if (zero? n) w (recur (inc w) (bit-shift-right n 1)))))

(defn rle-hybrid
  "The RLE / bit-packing hybrid Parquet uses for levels and dictionary indices.

  -> a vector of at least `n` values (a bit-packed run always carries a
  multiple of 8, so the tail is trimmed by the caller)."
  [bs i end width n]
  (if (zero? width)
    (vec (repeat n 0))
    (let [byte-width (quot (+ width 7) 8)]
      (loop [i i acc []]
        (if (or (>= (count acc) n) (>= i end))
          acc
          (let [[header i'] (th/read-varint bs i)
                header (long header)]
            (if (zero? (bit-and header 1))
              ;; RLE run: `count` repeats of one value
              (let [run (bit-shift-right header 1)
                    v (long (le bs i' byte-width))]
                (recur (+ i' byte-width) (into acc (repeat run v))))
              ;; bit-packed run: groups of 8 values, LSB-first within a byte
              (let [groups (bit-shift-right header 1)
                    total (* groups 8)
                    nbytes (quot (* total width) 8)
                    vals (loop [k 0 out []]
                           (if (= k total)
                             out
                             (let [bit (* k width)
                                   v (loop [b 0 v 0]
                                       (if (= b width)
                                         v
                                         (let [pos (+ bit b)
                                               byte (nth bs (+ i' (quot pos 8)))
                                               on (bit-and (bit-shift-right byte (mod pos 8)) 1)]
                                           (recur (inc b) (bit-or v (bit-shift-left on b))))))]
                               (recur (inc k) (conj out v)))))]
                (recur (+ i' nbytes) (into acc vals))))))))))

(defn plain-values
  "Decode `n` PLAIN-encoded values of `physical` starting at `i`."
  [bs i n physical]
  (loop [k 0 i i acc []]
    (if (= k n)
      acc
      (case physical
        :int64 (recur (inc k) (+ i 8) (conj acc (as-signed-64 (le bs i 8))))
        :int32 (recur (inc k) (+ i 4) (conj acc (long (le bs i 4))))
        :double (let [[v i'] (th/read-double bs i)] (recur (inc k) i' (conj acc v)))
        :byte-array (let [len (long (le bs i 4))
                          start (+ i 4)]
                      (recur (inc k) (+ start len)
                             (conj acc (th/bytes->string (subvec (vec bs) start (+ start len))))))
        (throw (ex-info (str "PLAIN decoding of " (name physical) " is not implemented")
                        {:type :parquet/unsupported-type :physical physical}))))))

(defn- refuse! [what value extra]
  (throw (ex-info (str "parquet: unsupported " what " " (pr-str value)
                       " — statistics are still readable from this file")
                  (merge {:type :parquet/unsupported what value} extra))))

(def dictionary-encodings
  "Both spellings. `PLAIN_DICTIONARY` is the v1 name and `RLE_DICTIONARY` the
  v2 one; the data pages are identical, so refusing one and accepting the
  other would reject files for the writer's vintage rather than their
  contents."
  #{:plain-dictionary :rle-dictionary})

(defn dictionary-page
  "PLAIN-decode a dictionary page body into the vector data pages index into."
  [bs start {:keys [num-values encoding]} physical]
  (when-not (or (= :plain encoding) (dictionary-encodings encoding))
    (refuse! :dictionary-encoding encoding {:supported [:plain]}))
  (plain-values bs start num-values physical))

(defn- values-section
  "Values for the present rows, from a page's value section.

  PLAIN writes them out; a dictionary page writes indices — one leading byte
  of bit width, then the RLE/bit-packing hybrid running to the end of the
  page. There is no length prefix on the indices, which is why `end` has to
  be threaded here rather than inferred."
  [bs start end n physical encoding dictionary]
  (cond
    (= :plain encoding) (plain-values bs start n physical)

    (dictionary-encodings encoding)
    (do
      (when-not dictionary
        (refuse! :encoding encoding
                 {:reason :no-dictionary-page
                  :detail "a dictionary-encoded page without a dictionary is
                           not decodable; indices would be read as values"}))
      (let [width (nth bs start)]
        (mapv (fn [ix]
                (when-not (< -1 ix (count dictionary))
                  (throw (ex-info "dictionary index out of range"
                                  {:type :parquet/malformed :index ix
                                   :size (count dictionary)})))
                (nth dictionary ix))
              (take n (rle-hybrid bs (inc start) end width n)))))

    :else (refuse! :encoding encoding {:supported [:plain :rle-dictionary]})))

(defn data-page
  "Decode one v1 DATA_PAGE into `{:values [..] :valid [..]}`.

  `max-def-level` is 1 for an OPTIONAL flat column and 0 for a REQUIRED one.
  A value is present exactly when its definition level equals the maximum;
  values are written only for the present rows, which is why the levels have
  to be decoded first even to know how many to read."
  [bs body-start {:keys [num-values encoding definition-level-encoding]}
   physical max-def-level dictionary]
  (let [end (count bs)]
    (if (zero? max-def-level)
      {:values (values-section bs body-start end num-values physical encoding dictionary)
       :valid (vec (repeat num-values true))}
      (do
        (when-not (contains? #{:rle :bit-packed} definition-level-encoding)
          (refuse! :definition-level-encoding definition-level-encoding {}))
        (let [;; v1 pages prefix the levels section with its byte length as a
              ;; 4-byte LE int, which is what makes the values' start findable
              ;; without decoding the levels first.
              len (long (le bs body-start 4))
              levels-start (+ body-start 4)
              levels (take num-values
                           (rle-hybrid bs levels-start (+ levels-start len)
                                       (bit-width max-def-level) num-values))
              valid (mapv #(= % max-def-level) levels)
              present (count (filter true? valid))
              vs (values-section bs (+ levels-start len) end present physical
                                 encoding dictionary)]
          {:values (loop [i 0 vs vs out []]
                     (if (= i (count valid))
                       out
                       (if (nth valid i)
                         (recur (inc i) (rest vs) (conj out (first vs)))
                         (recur (inc i) vs (conj out nil)))))
           :valid valid})))))

(def supported-codecs #{:uncompressed :snappy :gzip :zstd})
(def supported-encodings
  (into #{:plain :rle :bit-packed} dictionary-encodings))

(defn check-readable!
  "Throw unless this column chunk is inside the supported subset.

  Called before any byte of the chunk is fetched, so a refusal costs one
  metadata lookup rather than a download."
  [{:keys [codec encodings path]}]
  (when-not (supported-codecs codec)
    (refuse! :codec codec {:column path :supported (vec supported-codecs)}))
  (when-let [bad (seq (remove supported-encodings encodings))]
    (refuse! :encoding (vec bad) {:column path :supported (vec supported-encodings)}))
  true)
