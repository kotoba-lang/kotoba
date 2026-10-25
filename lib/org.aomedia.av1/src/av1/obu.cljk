(ns av1.obu
  "OBU (Open Bitstream Unit) framing -- AV1 spec section 6.2 (\"General OBU
   syntax\") / 6.2.2 (\"OBU header semantics\"). Transcribed from
   06.bitstream.syntax.md #General OBU syntax / #OBU header syntax /
   #OBU extension header syntax, fetched from
   https://github.com/AOMediaCodec/av1-spec (master) 2026-07-12.

   This namespace only assumes the 'low overhead bitstream format' (spec
   5.2): obu_has_size_field == 1 for every OBU, i.e. each OBU is
   self-delimiting via a leb128 obu_size. This is what ffmpeg's `-f obu`
   muxer produces and is also the format required by the spec whenever no
   surrounding container supplies lengths."
  (:require [av1.bitreader :as br]
            [av1.bitwriter :as bw]))

(def obu-type->kw
  {0 :reserved
   1 :obu-sequence-header
   2 :obu-temporal-delimiter
   3 :obu-frame-header
   4 :obu-tile-group
   5 :obu-metadata
   6 :obu-frame
   7 :obu-redundant-frame-header
   8 :obu-tile-list
   15 :obu-padding})

(defn obu-type-kw [n]
  (get obu-type->kw n (if (<= 9 n 14) :reserved :unknown)))

(defn parse-obu-extension-header
  "spec #OBU extension header syntax: temporal_id f(3), spatial_id f(2),
   extension_header_reserved_3bits f(3)."
  [reader]
  (let [[temporal-id r1] (br/f reader 3)
        [spatial-id r2] (br/f r1 2)
        [_reserved r3] (br/f r2 3)]
    [{:temporal-id temporal-id :spatial-id spatial-id} r3]))

(defn parse-obu-header
  "spec #OBU header syntax. Returns [header reader']."
  [reader]
  (let [[forbidden-bit r1] (br/f reader 1)
        [obu-type-num r2] (br/f r1 4)
        [ext-flag r3] (br/f r2 1)
        [has-size-field r4] (br/f r3 1)
        [_reserved r5] (br/f r4 1)
        [ext r6] (if (= ext-flag 1)
                   (parse-obu-extension-header r5)
                   [{:temporal-id 0 :spatial-id 0} r5])]
    [(merge {:obu-forbidden-bit forbidden-bit
             :obu-type obu-type-num
             :obu-type-kw (obu-type-kw obu-type-num)
             :obu-extension-flag ext-flag
             :obu-has-size-field has-size-field}
            ext)
     r6]))

(defn parse-obu
  "Parse one open_bitstream_unit at the (byte-aligned) current reader
   position. Returns a map:
     {:header        <obu header map, see parse-obu-header>
      :obu-size      <int, payload byte length>
      :payload-start <bit position where the payload begins (byte-aligned)>
      :payload-end   <bit position just past the payload -- always
                      payload-start + 8*obu-size, i.e. the next OBU's start>
      :reader-at-payload <reader positioned at payload-start, for callers
                          that want to parse the payload themselves>}

   This function does NOT parse the payload -- callers dispatch on
   `(:obu-type-kw header)` and either parse the payload with a
   type-specific parser (av1.sequence-header, av1.frame-header) or skip
   straight to `:payload-end` (byte-exact skip via the leb128 obu_size,
   spec-legal because obu_size is authoritative regardless of whether the
   payload's own internal syntax was fully walked -- this is what lets
   Phase 0 stop early inside frame_header_obu without corrupting the parse
   of subsequent OBUs)."
  [reader]
  (let [[header r1] (parse-obu-header reader)]
    (if (= 1 (:obu-has-size-field header))
      (let [[obu-size _n-bytes r2] (br/leb128 r1)
            payload-start (:pos r2)]
        {:header header
         :obu-size obu-size
         :payload-start payload-start
         :payload-end (+ payload-start (* 8 obu-size))
         :reader-at-payload r2})
      (throw (ex-info "obu_has_size_field == 0 (length-delimited/Annex B format) not supported by Phase 0"
                       {:header header})))))

(defn seek
  "Return a reader positioned at bit-position `pos` (byte-exact skip to the
   next OBU boundary)."
  [reader pos]
  (assoc reader :pos pos))

;; =======================================================================
;; ENCODE side: `write-obu-header`/`write-obu` -- the encode-side inverse
;; of `parse-obu-header`/`parse-obu` above (2026-07 AV1 encode task,
;; ADR-2607122000 Migration step 9 continuation). Only the low-overhead
;; bitstream format (`obu_has_size_field == 1`, this namespace's only
;; supported format on the decode side too, see namespace docstring) with
;; no extension header (`obu_extension_flag == 0`, `temporal_id`/
;; `spatial_id` both 0) -- this repo's encode scope never needs scalable
;; OBU dropping.

(defn write-obu-header
  "spec #OBU header syntax, `obu_extension_flag=0` only (this namespace's
   encode scope)."
  [writer obu-type-num]
  (-> writer
      (bw/f 1 0)   ;; obu_forbidden_bit = 0
      (bw/f 4 obu-type-num)
      (bw/f 1 0)   ;; obu_extension_flag = 0
      (bw/f 1 1)   ;; obu_has_size_field = 1
      (bw/f 1 0))) ;; obu_reserved_1bit = 0

(defn write-obu
  "Writes one complete `open_bitstream_unit()`: header + leb128 `obu_size` +
   payload. `payload-bytes` is the ALREADY-SERIALIZED payload (a vector of
   byte values 0-255, e.g. from av1.bitwriter/to-bytes) -- this fn is
   payload-format-agnostic (obu_size is simply `(count payload-bytes)`),
   matching how `parse-obu` itself never interprets the payload, only
   frames it. `writer` must already be byte-aligned (every OBU starts
   byte-aligned, spec 5.2)."
  [writer obu-type-num payload-bytes]
  (let [w1 (write-obu-header writer obu-type-num)
        w2 (bw/leb128 w1 (count payload-bytes))]
    (reduce (fn [w byte] (bw/f w 8 byte)) w2 payload-bytes)))

(defn parse-all
  "Walk an entire OBU stream (byte-array/vector), calling
   `(payload-parser obu reader-at-payload)` for each OBU whose
   `(:obu-type-kw header)` is in `parse-types` (a set) -- the parser must
   return a map of parsed fields (merged into the obu entry under
   :parsed), or nil. All other OBU types (and any parse-types OBU where
   the parser throws) are recorded with only the header/size info and the
   payload is skipped byte-exactly via obu_size.

   Returns a vector of obu entries (without :reader-at-payload, which is
   dropped after use since readers are only valid mid-parse)."
  [bytes payload-parser parse-types]
  (loop [reader (br/make-reader bytes)
         acc []]
    (if (>= (br/byte-pos reader) (count bytes))
      acc
      (let [obu (parse-obu reader)
            type-kw (get-in obu [:header :obu-type-kw])
            parsed (when (contains? parse-types type-kw)
                     (payload-parser obu (:reader-at-payload obu)))
            entry (-> obu
                      (dissoc :reader-at-payload)
                      (cond-> parsed (assoc :parsed parsed)))]
        (recur (seek reader (:payload-end obu))
               (conj acc entry))))))
