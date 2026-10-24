(ns zstd.core
  "Zstandard decompression (RFC 8878) and a raw-block writer, portable `.cljc`,
   zero dependencies.

   A zstd frame is a header, a series of blocks, and an optional XXH64 checksum. A
   compressed block has two halves:

   - a **literals section**, Huffman-coded (`zstd.huff`), possibly across four
     independent bitstreams, whose Huffman table description may itself be
     FSE-coded;
   - a **sequences section**, three interleaved FSE streams (`zstd.fse`) giving
     literal length, match length and offset codes, plus extra bits.

   Executing a sequence copies literals then a match, and offsets may be *repeat*
   offsets referring to the last three used — a stateful rule whose corner case
   (literal length zero) is the classic zstd decoder bug.

   All data bitstreams are read **backwards** from the end of their section.

   Not implemented: dictionaries (`:dictionary-id` is reported and refused),
   and compression beyond raw blocks — see `compress`."
  (:require [zstd.bits :as bits]
            [zstd.fse :as fse]
            [zstd.huff :as huff]
            [zstd.xxhash :as xxhash]))

(def magic [0x28 0xb5 0x2f 0xfd])                          ; 0xFD2FB528, little-endian
(def ^:private max-block-size 131072)

(def ^:private pow2 (vec (reductions * 1 (repeat 33 2))))

(defn- u16 [v i] (+ (nth v i) (* 256 (nth v (+ i 1)))))
(defn- u24 [v i] (+ (u16 v i) (* 65536 (nth v (+ i 2)))))
(defn- u32 [v i] (+ (u24 v i) (* 16777216 (nth v (+ i 3)))))

(defn- le [v i n]
  (loop [k 0 acc 0 mult 1]
    (if (= k n) acc (recur (inc k) (+ acc (* (nth v (+ i k)) mult)) (* mult 256)))))

;; ---------------------------------------------------------------------------
;; Frame header
;; ---------------------------------------------------------------------------

(defn- read-frame-header [v pos]
  (when (> (+ pos 5) (count v))
    (throw (ex-info "zstd: shorter than a frame header" {:reason :truncated :pos pos})))
  (let [fhd            (nth v (+ pos 4))
        fcs-flag       (unsigned-bit-shift-right fhd 6)
        single?        (pos? (bit-and fhd 0x20))
        checksum?      (pos? (bit-and fhd 0x04))
        dict-flag      (bit-and fhd 0x03)
        _              (when (pos? (bit-and fhd 0x08))
                         (throw (ex-info "zstd: reserved frame header bit is set"
                                         {:reason :bad-frame-header :fhd fhd})))
        p              (+ pos 5)
        [window p]     (if single?
                         [nil p]
                         (let [b (nth v p)
                               exp (unsigned-bit-shift-right b 3)
                               man (bit-and b 7)
                               base (nth pow2 (+ 10 exp))]
                           [(+ base (* man (quot base 8))) (inc p)]))
        dict-size      (nth [0 1 2 4] dict-flag)
        dict-id        (when (pos? dict-size) (le v p dict-size))
        p              (+ p dict-size)
        fcs-size       (if (zero? fcs-flag) (if single? 1 0) (nth [0 2 4 8] fcs-flag))
        content-size   (when (pos? fcs-size)
                         (let [n (le v p fcs-size)]
                           (if (= fcs-size 2) (+ n 256) n)))
        p              (+ p fcs-size)]
    (when dict-id
      (throw (ex-info "zstd: frame requires a dictionary"
                      {:reason :dictionary-required :dictionary-id dict-id})))
    {:window (or window content-size)
     :content-size content-size
     :checksum? checksum?
     :single-segment? single?
     :data-start p}))

;; ---------------------------------------------------------------------------
;; Literals section
;; ---------------------------------------------------------------------------

(defn- read-literals
  "Decode a block's literals section. Returns
   `{:literals [...] :end offset :huffman table-or-nil}`; the table is carried
   forward because a 'treeless' block reuses the previous one."
  [v pos block-end prev-huff]
  (let [b0     (nth v pos)
        type   (bit-and b0 0x03)
        sf     (bit-and (unsigned-bit-shift-right b0 2) 0x03)]
    (case type
      ;; Raw and RLE share the size encoding.
      (0 1)
      (let [[regen hdr] (case sf
                          (0 2) [(unsigned-bit-shift-right b0 3) 1]
                          1     [(+ (unsigned-bit-shift-right b0 4)
                                    (* 16 (nth v (+ pos 1)))) 2]
                          3     [(+ (unsigned-bit-shift-right b0 4)
                                    (* 16 (nth v (+ pos 1)))
                                    (* 4096 (nth v (+ pos 2)))) 3])
            start (+ pos hdr)]
        (if (zero? type)
          {:literals (vec (subvec v start (+ start regen)))
           :end (+ start regen)
           :huffman prev-huff}
          {:literals (vec (repeat regen (nth v start)))
           :end (inc start)
           :huffman prev-huff}))

      ;; Compressed (2) and treeless (3).
      (2 3)
      (let [[bits* hdr streams] (case sf
                                  0 [10 3 1]
                                  1 [10 3 4]
                                  2 [14 4 4]
                                  3 [18 5 4])
            raw   (le v pos hdr)
            mask  (dec (nth pow2 bits*))
            regen (bit-and (quot raw 16) mask)
            comp  (bit-and (quot raw (nth pow2 (+ 4 bits*))) mask)
            start (+ pos hdr)
            sec-end (+ start comp)
            _     (when (> sec-end block-end)
                    (throw (ex-info "zstd: literals section runs past the block"
                                    {:reason :truncated})))
            [huff stream-start]
            (if (= type 3)
              (if prev-huff
                [prev-huff start]
                (throw (ex-info "zstd: treeless literals with no previous Huffman table"
                                {:reason :bad-literals})))
              (let [t (huff/read-table v start)]
                [t (:end t)]))
            literals
            (if (= streams 1)
              (let [r (bits/rev-reader v stream-start sec-end)]
                ;; Exactly `regen` symbols: the stream's own end is *not* the
                ;; stop condition. The last symbol may finish precisely on the
                ;; final bit, so stopping when the reader looks exhausted drops
                ;; literals — which then shifts every sequence after it.
                (loop [out (transient []) n 0]
                  (if (>= n regen)
                    (persistent! out)
                    (recur (conj! out (huff/decode-symbol r huff)) (inc n)))))
              ;; Four streams: a six-byte jump table, then three sized streams and
              ;; a fourth that runs to the end.
              (let [s1 (u16 v stream-start)
                    s2 (u16 v (+ stream-start 2))
                    s3 (u16 v (+ stream-start 4))
                    p0 (+ stream-start 6)
                    p1 (+ p0 s1)
                    p2 (+ p1 s2)
                    p3 (+ p2 s3)
                    per (quot (+ regen 3) 4)
                    targets [per per per (- regen (* 3 per))]
                    bounds  [[p0 p1] [p1 p2] [p2 p3] [p3 sec-end]]]
                (when (> p3 sec-end)
                  (throw (ex-info "zstd: literals jump table overruns the section"
                                  {:reason :bad-literals})))
                (vec (mapcat (fn [[from to] target]
                               (let [r (bits/rev-reader v from to)]
                                 (loop [out (transient []) n 0]
                                   (if (>= n target)
                                     (persistent! out)
                                     (recur (conj! out (huff/decode-symbol r huff)) (inc n))))))
                             bounds targets))))]
        (when (not= (count literals) regen)
          (throw (ex-info "zstd: literals section produced the wrong number of bytes"
                          {:reason :size-mismatch :expected regen :actual (count literals)})))
        {:literals literals :end sec-end :huffman huff}))))

;; ---------------------------------------------------------------------------
;; Sequences section
;; ---------------------------------------------------------------------------

(defn- read-seq-count [v pos]
  (let [b0 (nth v pos)]
    (cond
      (zero? b0) [0 (inc pos)]
      (< b0 128) [b0 (inc pos)]
      (< b0 255) [(+ (* 256 (- b0 128)) (nth v (inc pos))) (+ pos 2)]
      :else      [(+ (u16 v (inc pos)) 0x7f00) (+ pos 3)])))

(defn- read-seq-table
  "One of the three sequence tables. Mode 0 is the predefined distribution, 1 a
   single repeated symbol, 2 an FSE description, 3 'reuse the previous table'."
  [v pos mode default prev kind]
  (case mode
    0 [{:table (fse/build-table (:counts default) (:accuracy-log default))
        :accuracy-log (:accuracy-log default)}
       pos]
    1 (let [s (nth v pos)]
        [{:table [{:symbol s :nb-bits 0 :new-state 0}] :accuracy-log 0 :rle s} (inc pos)])
    2 (let [{:keys [counts accuracy-log end]} (fse/read-ncount v pos 255)]
        [{:table (fse/build-table counts accuracy-log) :accuracy-log accuracy-log} end])
    3 (if prev
        [prev pos]
        (throw (ex-info (str "zstd: " (name kind) " table set to 'repeat' with no previous table")
                        {:reason :bad-sequences :kind kind})))))

(defn- apply-offset
  "Repeat-offset bookkeeping (RFC 8878 §3.1.1.5). The literal-length-zero case
   shifts every code by one, which is the corner most decoders get wrong."
  [offset-value literal-length [r1 r2 r3]]
  (if (> offset-value 3)
    (let [o (- offset-value 3)] [o [o r1 r2]])
    (let [ov (if (zero? literal-length) (inc offset-value) offset-value)]
      (case ov
        1 [r1 [r1 r2 r3]]
        2 [r2 [r2 r1 r3]]
        3 [r3 [r3 r1 r2]]
        4 (let [o (dec r1)]
            (when (zero? o)
              (throw (ex-info "zstd: repeat offset would be zero"
                              {:reason :bad-offset})))
            [o [o r1 r2]])))))

(defn- read-sequences
  "Decode a block's sequences. Returns `{:sequences [[ll ml off] ...] :tables {...}}`."
  [v pos block-end prev-tables]
  (let [[n pos] (read-seq-count v pos)]
    (if (zero? n)
      {:sequences [] :tables prev-tables :end pos}
      (let [modes    (nth v pos)
            ll-mode  (unsigned-bit-shift-right modes 6)
            of-mode  (bit-and (unsigned-bit-shift-right modes 4) 3)
            ml-mode  (bit-and (unsigned-bit-shift-right modes 2) 3)
            _        (when (pos? (bit-and modes 3))
                       (throw (ex-info "zstd: reserved sequence mode bits are set"
                                       {:reason :bad-sequences :modes modes})))
            pos      (inc pos)
            [ll pos] (read-seq-table v pos ll-mode fse/literal-length-default
                                     (:ll prev-tables) :literal-lengths)
            [of pos] (read-seq-table v pos of-mode fse/offset-default
                                     (:of prev-tables) :offsets)
            [ml pos] (read-seq-table v pos ml-mode fse/match-length-default
                                     (:ml prev-tables) :match-lengths)
            r        (bits/rev-reader v pos block-end)
            ;; States are initialised literal-length, offset, match-length.
            ll-state (fse/init-state r (:accuracy-log ll))
            of-state (fse/init-state r (:accuracy-log of))
            ml-state (fse/init-state r (:accuracy-log ml))]
        (loop [i 0 lls ll-state ofs of-state mls ml-state out (transient [])]
          (if (= i n)
            {:sequences (persistent! out) :tables {:ll ll :of of :ml ml} :end block-end}
            (let [ll-code (fse/symbol-at (:table ll) lls)
                  ml-code (fse/symbol-at (:table ml) mls)
                  of-code (fse/symbol-at (:table of) ofs)
                  ;; Extra bits are read offset, then match length, then literals.
                  [of-base of-bits] (fse/offset-code of-code)
                  offset-value      (+ of-base (bits/rev-bits r of-bits))
                  [ml-base ml-bits] (nth fse/match-length-code ml-code)
                  match-length      (+ ml-base (bits/rev-bits r ml-bits))
                  [ll-base ll-bits] (nth fse/literal-length-code ll-code)
                  literal-length    (+ ll-base (bits/rev-bits r ll-bits))
                  out (conj! out [literal-length match-length offset-value])
                  last? (= (inc i) n)]
              (if last?
                (recur (inc i) lls ofs mls out)
                ;; …and the states update literal-length, match-length, offset.
                (let [lls (fse/next-state r (:table ll) lls)
                      mls (fse/next-state r (:table ml) mls)
                      ofs (fse/next-state r (:table of) ofs)]
                  (recur (inc i) lls ofs mls out))))))))))

;; ---------------------------------------------------------------------------
;; Block loop
;; ---------------------------------------------------------------------------

(defn- copy-match! [out offset len]
  (let [n (count @out)]
    (when (> offset n)
      (throw (ex-info "zstd: offset reaches before the start of the output"
                      {:reason :bad-offset :offset offset :available n})))
    (dotimes [_ len]
      ;; One byte at a time: a match may overlap itself (offset 1, length 100 is
      ;; a run of one byte), so the source grows as the copy proceeds.
      (vswap! out conj (nth @out (- (count @out) offset))))))

(defn- decode-block!
  "Decode one compressed block into `out`, threading the entropy tables that the
   next block may reuse and the repeat offsets that the next *sequence* may."
  [v start block-end out state]
  (let [lit      (read-literals v start block-end (:huffman state))
        seqs     (read-sequences v (:end lit) block-end (:tables state))
        literals (:literals lit)
        lit-pos
        (reduce
         (fn [lp [ll ml offset-value]]
           ;; Repeat offsets are stateful across sequences, so they live in a
           ;; volatile rather than the reduce accumulator.
           (let [[offset reps] (apply-offset offset-value ll @(:reps-v state))]
             (vreset! (:reps-v state) reps)
             (when (> (+ lp ll) (count literals))
               (throw (ex-info "zstd: sequence needs more literals than the block has"
                               {:reason :bad-sequences})))
             (dotimes [i ll] (vswap! out conj (nth literals (+ lp i))))
             (copy-match! out offset ml)
             (+ lp ll)))
         0
         (:sequences seqs))]
    (dotimes [i (- (count literals) lit-pos)]
      (vswap! out conj (nth literals (+ lit-pos i))))
    {:huffman (:huffman lit) :tables (:tables seqs)}))

(defn- read-frame [v pos opts]
  (let [h        (read-frame-header v pos)
        out      (volatile! [])
        reps-v   (volatile! [1 4 8])]
    (loop [p (:data-start h) huffman nil tables {}]
      (when (> (+ p 3) (count v))
        (throw (ex-info "zstd: block header runs past the end" {:reason :truncated :pos p})))
      (let [hdr    (u24 v p)
            last?  (pos? (bit-and hdr 1))
            type   (bit-and (unsigned-bit-shift-right hdr 1) 3)
            size   (unsigned-bit-shift-right hdr 3)
            start  (+ p 3)
            end    (+ start size)]
        (when (> end (count v))
          (throw (ex-info "zstd: block data runs past the end" {:reason :truncated :pos start})))
        (when (> size max-block-size)
          (throw (ex-info "zstd: block larger than the format allows"
                          {:reason :bad-block :size size})))
        (let [res (case type
                    0 (do (dotimes [i size] (vswap! out conj (nth v (+ start i))))
                          {:huffman huffman :tables tables})
                    1 (do (dotimes [_ size] (vswap! out conj (nth v start)))
                          {:huffman huffman :tables tables})
                    2 (decode-block! v start end out
                                     {:huffman huffman :tables tables :reps-v reps-v})
                    (throw (ex-info "zstd: reserved block type"
                                    {:reason :bad-block :type type})))]
          (when-let [limit (:max-output opts)]
            (when (> (count @out) limit)
              (throw (ex-info "zstd: output exceeds limit"
                              {:reason :output-limit :limit limit}))))
          (if last?
            (let [data @out
                  p    end
                  p    (if (:checksum? h)
                         (do (when (> (+ p 4) (count v))
                               (throw (ex-info "zstd: frame ends before its checksum"
                                               {:reason :truncated})))
                             (when (get opts :verify-checksum true)
                               (let [want (u32 v p)
                                     got  (xxhash/xxh64-low32 data)]
                                 (when-not (= want got)
                                   (throw (ex-info "zstd: content checksum mismatch"
                                                   {:reason :checksum-mismatch
                                                    :expected want :actual got})))))
                             (+ p 4))
                         p)]
              (when (and (:content-size h) (not= (:content-size h) (count data)))
                (throw (ex-info "zstd: decoded size does not match the frame header"
                                {:reason :size-mismatch
                                 :expected (:content-size h) :actual (count data)})))
              {:bytes data :end p :header h})
            (recur end (:huffman res) (:tables res))))))))

;; ---------------------------------------------------------------------------
;; Public API
;; ---------------------------------------------------------------------------

(defn- skippable? [v pos]
  (and (<= (+ pos 8) (count v))
       (= 0x184d2a5 (quot (u32 v pos) 16))))

(defn frames
  "Per-frame metadata, skipping over skippable frames."
  ([data] (frames data nil))
  ([data opts]
   (let [v (vec data)]
     (loop [pos 0 out []]
       (if (>= pos (count v))
         out
         (if (skippable? v pos)
           (recur (+ pos 8 (u32 v (+ pos 4))) out)
           (let [f (read-frame v pos opts)]
             (recur (:end f) (conj out (-> (:header f)
                                           (assoc :decoded-size (count (:bytes f)))))))))))))

(defn decompress
  "Decompress a zstd stream — every frame, concatenated — → vector of unsigned
   bytes.

   Options: `:verify-checksum` (default true), `:max-output`."
  ([data] (decompress data nil))
  ([data opts]
   (let [v (vec data)]
     (when (< (count v) 4)
       (throw (ex-info "zstd: shorter than a magic number" {:reason :truncated})))
     (loop [pos 0 out []]
       (if (>= pos (count v))
         out
         (if (skippable? v pos)
           (recur (+ pos 8 (u32 v (+ pos 4))) out)
           (do
             (when-not (= magic (vec (subvec v pos (+ pos 4))))
               (throw (ex-info "zstd: bad magic number" {:reason :not-zstd :pos pos})))
             (let [f (read-frame v pos opts)]
               (recur (:end f) (into out (:bytes f)))))))))))

;; ---------------------------------------------------------------------------
;; Writing (raw blocks)
;; ---------------------------------------------------------------------------

(defn compress
  "Write `data` as a single frame of *raw* (uncompressed) blocks.

   This is a conformant zstd frame — `zstd -d` and `zstd -t` accept it, which the
   suite asserts — but it does not compress. A naive encoder would be slower and
   larger than `org-ietf-deflate`'s gzip while introducing a whole class of
   \"only our decoder reads it\" bugs.

   ## What an encoder would actually need (measured 2026-08-30)

   This said \"a second project\" without saying what is in it, which makes it
   impossible to judge. The decode side already carries more than half:

     have   the predefined FSE distributions (RFC 8878 3.1.1.3.2.2.1) and the
            literal-length / match-length / offset code tables, in `zstd.fse`
     have   `fse/build-table`, though it builds a DECODE table — an encoder
            needs the inverse mapping, symbol to state, which is a different
            structure from the same distribution
     have   a match finder pattern to copy: `com-google-snappy` does exactly
            this job with a hash table over 4-byte sequences
     need   a REVERSE bit writer. `zstd.bits` has readers only, and the
            sequences bitstream is written backwards — this is the piece most
            likely to be silently wrong
     need   sequence-section assembly and a Compressed_Block header

   Huffman is avoidable: `Raw_Literals_Block` leaves literals uncompressed, so
   `zstd.huff` needing an encoder too is a second increment, not a prerequisite.
   That subset — raw literals plus FSE-coded sequences on the predefined tables
   — is real LZ77 compression and is the smallest thing worth building.

   Not started. `org-ietf-deflate` has a real encoder and `com-google-snappy`
   now does too, so nothing in this workspace is blocked on it; Parquet
   deliberately does not offer ZSTD as a codec for exactly this reason.

   Options: `:checksum` (default true)."
  ([data] (compress data nil))
  ([data {:keys [checksum] :or {checksum true}}]
   (let [v (vec data)
         n (count v)]
     (when (>= n 4294967296)
       (throw (ex-info "zstd: input too large for a 4-byte content size"
                       {:reason :too-large})))
     (-> (vec magic)
         ;; single segment, 4-byte content size, optional checksum
         (into [(bit-or 0x80 0x20 (if checksum 0x04 0))])
         (into [(bit-and n 0xff)
                (bit-and (unsigned-bit-shift-right n 8) 0xff)
                (bit-and (unsigned-bit-shift-right n 16) 0xff)
                (bit-and (unsigned-bit-shift-right n 24) 0xff)])
         (into (if (zero? n)
                 [1 0 0]                                    ; a single empty raw last block
                 (loop [pos 0 out []]
                   (if (>= pos n)
                     out
                     (let [size  (min max-block-size (- n pos))
                           last? (>= (+ pos size) n)
                           hdr   (+ (if last? 1 0) (* 8 size))]
                       (recur (+ pos size)
                              (-> out
                                  (into [(bit-and hdr 0xff)
                                         (bit-and (unsigned-bit-shift-right hdr 8) 0xff)
                                         (bit-and (unsigned-bit-shift-right hdr 16) 0xff)])
                                  (into (subvec v pos (+ pos size))))))))))
         (into (if checksum
                 (let [c (xxhash/xxh64-low32 v)]
                   [(bit-and c 0xff)
                    (bit-and (unsigned-bit-shift-right c 8) 0xff)
                    (bit-and (unsigned-bit-shift-right c 16) 0xff)
                    (bit-and (unsigned-bit-shift-right c 24) 0xff)])
                 []))))))
