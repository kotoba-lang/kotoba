(ns woff.woff2
  "WOFF 2.0 decoding (W3C WOFF2 Recommendation) — the container, the table
   directory, and the reverse transforms.

   Where WOFF 1.0 zlib-compresses each table independently, WOFF2 concatenates
   every table into a *single* brotli stream and pre-processes three of them:

   - `glyf`/`loca` are split into seven parallel substreams and must be rebuilt
     glyph by glyph (`woff.glyf`);
   - `hmtx` may drop its left-side-bearing arrays entirely, to be recovered from
     the glyph bounding boxes;
   - everything else passes through untouched.

   Reconstruction then has to *rebuild* the sfnt: table records sorted by tag,
   data 4-byte aligned, every `checkSum` recomputed, and `head`'s
   `checkSumAdjustment` recomputed over the finished font — the spec requires all
   of it, because the transforms change the bytes the checksums cover.

   Compression is `org-ietf-brotli`; this repo does not write WOFF2."
  (:require [brotli.core :as brotli]
            [opentype.core :as opentype]
            [woff.glyf :as glyf]
            [woff.woff2-data :as data]))

(def signature
  "'wOF2' — the WOFF2 magic number."
  [0x77 0x4f 0x46 0x32])

(defn- u8 [v i] (nth v i))
(defn- u16 [v i] (+ (* 256 (nth v i)) (nth v (inc i))))
(defn- u32 [v i] (+ (* 16777216 (nth v i)) (* 65536 (nth v (+ i 1)))
                    (* 256 (nth v (+ i 2))) (nth v (+ i 3))))
(defn- i16 [v i] (let [x (u16 v i)] (if (>= x 32768) (- x 65536) x)))

(defn- ->u32-bytes [n]
  [(bit-and (unsigned-bit-shift-right n 24) 0xff)
   (bit-and (unsigned-bit-shift-right n 16) 0xff)
   (bit-and (unsigned-bit-shift-right n 8) 0xff)
   (bit-and n 0xff)])

(defn- ->u16-bytes [n]
  [(bit-and (unsigned-bit-shift-right n 8) 0xff) (bit-and n 0xff)])

(defn- tag->bytes [tag] (mapv #(#?(:clj int :cljs .charCodeAt) % #?@(:clj [] :cljs [0])) (seq tag)))

;; ---------------------------------------------------------------------------
;; Variable-length integers (§3.1)
;; ---------------------------------------------------------------------------

(defn read-uint-base128
  "§3.1 UIntBase128 → `[value pos']`. Leading zeros, over-long sequences and
   values past 2^32-1 are rejected, as the spec requires."
  [v pos]
  (loop [i 0 p pos acc 0]
    (when (>= i 5)
      (throw (ex-info "woff2: UIntBase128 longer than five bytes"
                      {:reason :bad-uint-base128 :pos pos})))
    (let [b (u8 v p)]
      (when (and (zero? i) (= b 0x80))
        (throw (ex-info "woff2: UIntBase128 has a leading zero"
                        {:reason :bad-uint-base128 :pos pos})))
      (when (>= acc 33554432)                               ; would overflow 2^32 on shift
        (throw (ex-info "woff2: UIntBase128 exceeds 2^32-1"
                        {:reason :bad-uint-base128 :pos pos})))
      (let [acc (+ (* acc 128) (bit-and b 0x7f))]
        (if (zero? (bit-and b 0x80))
          [acc (inc p)]
          (recur (inc i) (inc p) acc))))))

;; ---------------------------------------------------------------------------
;; Header and directory (§4)
;; ---------------------------------------------------------------------------

(defn header
  "The WOFF2 header fields."
  [data]
  (let [v (vec data)]
    (when (< (count v) 48)
      (throw (ex-info "woff2: shorter than a WOFF2 header" {:reason :truncated})))
    (when-not (= signature (vec (subvec v 0 4)))
      (throw (ex-info "woff2: bad signature" {:reason :not-woff2})))
    {:flavor              (u32 v 4)
     :length              (u32 v 8)
     :num-tables          (u16 v 12)
     :reserved            (u16 v 14)
     :total-sfnt-size     (u32 v 16)
     :total-compressed-size (u32 v 20)
     :major-version       (u16 v 24)
     :minor-version       (u16 v 26)
     :meta-offset         (u32 v 28)
     :meta-length         (u32 v 32)
     :meta-orig-length    (u32 v 36)
     :priv-offset         (u32 v 40)
     :priv-length         (u32 v 44)}))

(defn tables
  "The table directory: `[{:tag :transform-version :orig-length :transform-length
   :transformed?} ...]` in file order, plus `:directory-end`."
  [data]
  (let [v (vec data)
        h (header v)]
    (when-not (zero? (:reserved h))
      (throw (ex-info "woff2: reserved header field is not zero"
                      {:reason :bad-header})))
    (loop [i 0 pos 48 out []]
      (if (= i (:num-tables h))
        {:entries out :directory-end pos}
        (let [flags (u8 v pos)
              idx   (bit-and flags 0x3f)
              tv    (bit-and (unsigned-bit-shift-right flags 6) 0x03)
              [tag pos] (if (= idx 63)
                          [(apply str (map char (subvec v (inc pos) (+ pos 5)))) (+ pos 5)]
                          [(nth data/known-tags idx) (inc pos)])
              [orig pos] (read-uint-base128 v pos)
              ;; §4.1: transform version 3 is the null transform for glyf/loca,
              ;; version 0 for everything else. A transformLength is present if
              ;; and only if a non-null transform was applied.
              transformed? (if (contains? #{"glyf" "loca"} tag)
                             (not= tv 3)
                             (case tag
                               "hmtx" (not= tv 0)
                               (not= tv 0)))
              [tlen pos] (if transformed? (read-uint-base128 v pos) [nil pos])]
          (when (and (not (contains? #{"glyf" "loca" "hmtx"} tag)) (not= tv 0))
            (throw (ex-info (str "woff2: unknown transform version for " tag)
                            {:reason :unsupported-transform :tag tag :version tv})))
          (recur (inc i) pos
                 (conj out {:tag tag :transform-version tv
                            :orig-length orig :transform-length tlen
                            :transformed? transformed?})))))))

;; ---------------------------------------------------------------------------
;; hmtx transform (§5.4)
;; ---------------------------------------------------------------------------

(defn- reconstruct-hmtx
  "Rebuild `hmtx` from the transformed form, taking the missing left side
   bearings from the glyph bounding boxes."
  [tv num-h-metrics num-glyphs x-mins]
  (let [v     (vec tv)
        flags (u8 v 0)]
    (when (pos? (bit-and flags 0xfc))
      (throw (ex-info "woff2: reserved hmtx transform flags are set"
                      {:reason :bad-hmtx-transform :flags flags})))
    (when (zero? (bit-and flags 0x03))
      (throw (ex-info "woff2: hmtx transform claims to omit nothing"
                      {:reason :bad-hmtx-transform :flags flags})))
    (let [lsb-omitted?  (pos? (bit-and flags 0x01))
          side-omitted? (pos? (bit-and flags 0x02))
          adv-start     1
          lsb-start     (+ adv-start (* 2 num-h-metrics))
          side-start    (+ lsb-start (if lsb-omitted? 0 (* 2 num-h-metrics)))]
      (vec (concat
            (mapcat (fn [i]
                      (concat (->u16-bytes (u16 v (+ adv-start (* 2 i))))
                              (->u16-bytes (bit-and (if lsb-omitted?
                                                      (nth x-mins i)
                                                      (i16 v (+ lsb-start (* 2 i))))
                                                    0xffff))))
                    (range num-h-metrics))
            (mapcat (fn [i]
                      (->u16-bytes (bit-and (if side-omitted?
                                              (nth x-mins i)
                                              (i16 v (+ side-start
                                                        (* 2 (- i num-h-metrics)))))
                                            0xffff)))
                    (range num-h-metrics num-glyphs)))))))

;; ---------------------------------------------------------------------------
;; sfnt assembly (§4.4 / §6)
;; ---------------------------------------------------------------------------

(defn- checksum
  "An sfnt checksum: the sum of the table's big-endian 32-bit words, with the
   table treated as zero-padded to a multiple of four."
  [bytes]
  (let [v (vec bytes)
        n (count v)]
    (loop [i 0 sum 0]
      (if (>= i n)
        (mod sum 4294967296)
        (let [b (fn [k] (if (< (+ i k) n) (nth v (+ i k)) 0))]
          (recur (+ i 4)
                 (mod (+ sum (* 16777216 (b 0)) (* 65536 (b 1)) (* 256 (b 2)) (b 3))
                      4294967296)))))))

(defn- log2-floor [n] (loop [i 0 x n] (if (< x 2) i (recur (inc i) (quot x 2)))))

(defn- assemble-sfnt
  "Build the sfnt: header, table records sorted by tag, then the table data in
   directory order, each 4-byte aligned."
  [flavor named-tables]
  (let [n            (count named-tables)
        entry-sel    (log2-floor n)
        search-range (* 16 (bit-shift-left 1 entry-sel))
        header       (vec (concat (->u32-bytes flavor)
                                 (->u16-bytes n)
                                 (->u16-bytes search-range)
                                 (->u16-bytes entry-sel)
                                 (->u16-bytes (- (* 16 n) search-range))))
        data-start   (+ (count header) (* 16 n))
        ;; Data in directory order, records sorted by tag — what the reference
        ;; decoder produces, and what makes a byte comparison against it possible.
        placed       (:tables
                      (reduce (fn [{:keys [offset tables]} {:keys [tag bytes]}]
                                (let [len (count bytes)
                                      pad (mod (- 4 (mod len 4)) 4)]
                                  {:offset (+ offset len pad)
                                   :tables (conj tables {:tag tag :bytes bytes
                                                         :offset offset :length len
                                                         :pad pad})}))
                              {:offset data-start :tables []}
                              named-tables))
        records      (vec (mapcat (fn [{:keys [tag bytes offset length]}]
                                   (concat (tag->bytes tag)
                                           (->u32-bytes (checksum bytes))
                                           (->u32-bytes offset)
                                           (->u32-bytes length)))
                                 (sort-by :tag placed)))
        body         (vec (mapcat (fn [{:keys [bytes pad]}] (concat bytes (repeat pad 0)))
                                  placed))
        font         (vec (concat header records body))
        ;; §6: the whole-font checksum has to be recomputed because the transforms
        ;; changed the bytes underneath it.
        head-entry   (first (filter #(= "head" (:tag %)) placed))]
    (if-not head-entry
      font
      (let [adj-at (+ (:offset head-entry) 8)
            zeroed (reduce (fn [f k] (assoc f (+ adj-at k) 0)) font (range 4))
            adj    (mod (- 2981146554 (checksum zeroed)) 4294967296)]  ; 0xB1B0AFBA
        (reduce (fn [f [k b]] (assoc f (+ adj-at k) b))
                zeroed
                (map-indexed vector (->u32-bytes adj)))))))

;; ---------------------------------------------------------------------------
;; Public API
;; ---------------------------------------------------------------------------

(defn ->sfnt
  "WOFF2 bytes → a reconstructed sfnt (TTF/OTF) byte vector.

   Options: `:max-output` (passed to the brotli decoder as a bomb ceiling)."
  ([data] (->sfnt data nil))
  ([data opts]
   (let [v (vec data)
         h (header v)
         {:keys [entries directory-end]} (tables v)]
     (when (= 0x74746366 (:flavor h))
       (throw (ex-info "woff2: font collections (ttcf) are not supported"
                       {:reason :font-collection})))
     (let [comp-start (+ directory-end 0)
           comp-end   (+ comp-start (:total-compressed-size h))]
       (when (> comp-end (count v))
         (throw (ex-info "woff2: compressed block runs past the end of the file"
                         {:reason :truncated})))
       (let [font-data (brotli/decompress (subvec v comp-start comp-end)
                                          (select-keys opts [:max-output]))
             expected  (reduce + (map (fn [{:keys [transformed? orig-length transform-length]}]
                                        (if transformed? transform-length orig-length))
                                      entries))]
         (when-not (= expected (count font-data))
           (throw (ex-info "woff2: decompressed size does not match the table directory"
                           {:reason :size-mismatch :declared expected :actual (count font-data)})))
         ;; Slice the decompressed block into the raw (possibly transformed) tables.
         (let [raw (:tables
                    (reduce (fn [{:keys [pos tables]} {:keys [tag transformed? orig-length
                                                              transform-length] :as e}]
                              (let [len (if transformed? transform-length orig-length)]
                                {:pos (+ pos len)
                                 :tables (conj tables (assoc e :tag tag
                                                             :bytes (subvec (vec font-data)
                                                                            pos (+ pos len))))}))
                            {:pos 0 :tables []}
                            entries))
               by-tag (into {} (map (juxt :tag identity) raw))
               ;; glyf/loca first: hmtx may need the glyph bounding boxes.
               glyf-e (get by-tag "glyf")
               rebuilt (when (and glyf-e (:transformed? glyf-e))
                         (glyf/reconstruct (:bytes glyf-e)))
               num-glyphs (if rebuilt
                            (:num-glyphs rebuilt)
                            (when-let [maxp (get by-tag "maxp")]
                              (u16 (:bytes maxp) 4)))
               num-h-metrics (when-let [hhea (get by-tag "hhea")]
                               (u16 (:bytes hhea) 34))
               resolved
               (mapv (fn [{:keys [tag transformed? bytes] :as e}]
                       (cond
                         (and (= tag "glyf") transformed?) {:tag tag :bytes (:glyf rebuilt)}
                         (and (= tag "loca") transformed?)
                         (do (when-not (zero? (:transform-length e))
                               (throw (ex-info "woff2: transformed loca must have zero transformLength"
                                               {:reason :bad-loca-transform})))
                             {:tag tag :bytes (:loca rebuilt)})
                         (and (= tag "hmtx") transformed?)
                         {:tag tag
                          :bytes (reconstruct-hmtx bytes num-h-metrics num-glyphs
                                                   (:x-mins rebuilt))}
                         :else {:tag tag :bytes bytes}))
                     raw)]
           (when (and glyf-e (:transformed? glyf-e) (nil? (get by-tag "loca")))
             (throw (ex-info "woff2: transformed glyf without a loca table"
                             {:reason :bad-glyf-transform})))
           (assemble-sfnt (:flavor h) resolved)))))))

(defn parse
  "Reconstruct the sfnt and hand it to `opentype.core/parse`, tagged `:woff2`."
  ([data] (parse data nil))
  ([data opts]
   (assoc (opentype/parse (->sfnt data opts)) :woff2 true)))
