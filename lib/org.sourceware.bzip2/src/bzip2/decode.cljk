(ns bzip2.decode
  "bzip2 stream and block decoding.

   Layout, in order: the stream header `BZh<level>`; then blocks, each announced
   by a 48-bit magic and carrying its own CRC-32; then a 48-bit end-of-stream
   magic and the combined CRC. A block itself is a symbol map, 2-6 Huffman
   tables, a selector per 50 symbols, the run-length-coded move-to-front
   stream, and the BWT pointer.

   Two decoding stages sit between the Huffman symbols and the output, and both
   are part of the format rather than an optimisation: RLE2 (the RUNA/RUNB
   bijective base-2 run coding of the most-frequent MTF symbol) and RLE1 (the
   pre-transform run coding, where four equal bytes are followed by a count).

   Every rejection is an `ex-info` with a `:reason`, and nothing unimplemented
   is passed through as data."
  (:require [bzip2.bits :as bits]
            [bzip2.bwt :as bwt]
            [bzip2.crc :as crc]
            [bzip2.huffman :as huff]))

(def block-magic 0x314159265359)
(def end-magic 0x177245385090)

(def ^:private default-max-output (* 128 1024 1024))

;; ---------------------------------------------------------------------------
;; Symbol map and selectors
;; ---------------------------------------------------------------------------

(defn- read-symbol-map
  "The two-level bitmap of byte values used by this block: 16 range bits, then a
   16-bit bitmap per set range."
  [r]
  (let [ranges (bits/read-bits r 16)
        used (vec (for [i (range 16)
                        :when (pos? (bit-and ranges (bit-shift-left 1 (- 15 i))))
                        :let [bm (bits/read-bits r 16)]
                        j (range 16)
                        :when (pos? (bit-and bm (bit-shift-left 1 (- 15 j))))]
                    (+ (* 16 i) j)))]
    (when (empty? used)
      (throw (ex-info "bzip2: block uses no byte values"
                      {:reason :empty-symbol-map})))
    used))

(defn- read-selectors
  "`n-selectors` table indices, move-to-front coded, each written in unary."
  [r n-selectors n-groups]
  (let [mtf (loop [i 0 out (transient [])]
              (if (= i n-selectors)
                (persistent! out)
                (let [j (loop [j 0]
                          (if (zero? (bits/read-bit r))
                            j
                            (do (when (>= j n-groups)
                                  (throw (ex-info "bzip2: selector past the table count"
                                                  {:reason :bad-selector
                                                   :selector j :n-groups n-groups})))
                                (recur (inc j)))))]
                  (recur (inc i) (conj! out j)))))]
    ;; inverse move-to-front over the table indices
    (loop [s (seq mtf) order (vec (range n-groups)) out (transient [])]
      (if-not s
        (persistent! out)
        (let [j (first s)
              v (nth order j)]
          (recur (next s)
                 (into [v] (concat (subvec order 0 j) (subvec order (inc j))))
                 (conj! out v)))))))

;; ---------------------------------------------------------------------------
;; The MTF / RLE2 symbol stream
;; ---------------------------------------------------------------------------

(defn- decode-mtf-stream
  "Decode the entropy-coded body into the BWT string (the last column).

   Returns a vector of unsigned bytes. `used` is the block's byte alphabet in
   ascending order; MTF position 0 is the one RUNA/RUNB encode runs of."
  [r used tables selectors block-limit]
  (let [alpha (+ (count used) 2)
        eob (dec alpha)
        n-sel (count selectors)]
    (letfn [(next-sym [group-pos sel-idx]
              ;; a fresh selector every 50 symbols
              (if (zero? group-pos)
                (do (when (>= sel-idx n-sel)
                      (throw (ex-info "bzip2: ran out of selectors"
                                      {:reason :bad-selector})))
                    [(huff/read-symbol r (nth tables (nth selectors sel-idx)))
                     49 (inc sel-idx)])
                [(huff/read-symbol r (nth tables (nth selectors (dec sel-idx))))
                 (dec group-pos) sel-idx]))]
      (loop [sym nil
             group-pos 0
             sel-idx 0
             mtf (vec used)
             out (transient [])
             n 0]
        (let [[sym group-pos sel-idx]
              (if (nil? sym) (next-sym group-pos sel-idx) [sym group-pos sel-idx])]
          (cond
            (= sym eob)
            (persistent! out)

            (< sym 2)
            ;; RUNA/RUNB: a run of the byte at MTF position 0, in bijective base 2.
            ;; The run ends on the first non-run symbol, which is then carried
            ;; forward and dispatched on the next pass rather than consumed here.
            (let [b (nth mtf 0)
                  [sym' gp' si' es]
                  (loop [sym sym gp group-pos si sel-idx es -1 N 1]
                    (if (< sym 2)
                      (let [es (+ es (* (if (zero? sym) 1 2) N))
                            N (* 2 N)]
                        (when (> N 2147483648)
                          (throw (ex-info "bzip2: run length overflow"
                                          {:reason :bad-run-length})))
                        (let [[s g i] (next-sym gp si)]
                          (recur s g i es N)))
                      [sym gp si (inc es)]))
                  n' (+ n es)]
              (when (> n' block-limit)
                (throw (ex-info "bzip2: block longer than its declared level allows"
                                {:reason :block-overflow :block-size n' :limit block-limit})))
              (let [out' (loop [i 0 acc out]
                           (if (= i es) acc (recur (inc i) (conj! acc b))))]
                (recur sym' gp' si' mtf out' n')))

            (< sym eob)
            ;; an ordinary MTF index; sym 2 means position 1
            (let [idx (dec sym)
                  b (nth mtf idx)
                  n' (inc n)]
              (when (> n' block-limit)
                (throw (ex-info "bzip2: block longer than its declared level allows"
                                {:reason :block-overflow :block-size n' :limit block-limit})))
              (recur nil group-pos sel-idx
                     (into [b] (concat (subvec mtf 0 idx) (subvec mtf (inc idx))))
                     (conj! out b)
                     n'))

            :else
            (throw (ex-info "bzip2: symbol outside the alphabet"
                            {:reason :bad-symbol :symbol sym :alpha-size alpha}))))))))

;; ---------------------------------------------------------------------------
;; RLE1 — the pre-transform run coding
;; ---------------------------------------------------------------------------

(defn- rle1-decode
  "Undo the run coding applied before the BWT: four equal bytes are followed by
   a single count byte saying how many more of them there are."
  [data]
  (let [n (count data)]
    (loop [i 0 run 0 prev -1 out (transient [])]
      (if (= i n)
        (persistent! out)
        (let [b (nth data i)]
          (if (= run 4)
            ;; `b` is the extra count, not a byte of output
            (recur (inc i) 0 -1
                   (loop [k 0 out out] (if (= k b) out (recur (inc k) (conj! out prev)))))
            (recur (inc i)
                   (if (= b prev) (inc run) 1)
                   b
                   (conj! out b))))))))

;; ---------------------------------------------------------------------------
;; Blocks and streams
;; ---------------------------------------------------------------------------

(defn- decode-block
  [r level]
  (let [want-crc (bits/read-u32 r)
        randomised (bits/read-bit r)
        _ (when (pos? randomised)
            (throw (ex-info "bzip2: randomised block (deprecated in bzip2 0.9.5 and never written since)"
                            {:reason :randomised-block})))
        orig-ptr (bits/read-bits r 24)
        used (read-symbol-map r)
        alpha (+ (count used) 2)
        n-groups (bits/read-bits r 3)
        _ (when (or (< n-groups 2) (> n-groups 6))
            (throw (ex-info "bzip2: Huffman table count outside 2..6"
                            {:reason :bad-group-count :n-groups n-groups})))
        n-selectors (bits/read-bits r 15)
        _ (when (zero? n-selectors)
            (throw (ex-info "bzip2: block declares no selectors"
                            {:reason :bad-selector})))
        selectors (read-selectors r n-selectors n-groups)
        tables (mapv (fn [_] (huff/decode-table (huff/read-lengths r alpha)))
                     (range n-groups))
        last-col (decode-mtf-stream r used tables selectors (* level 100000))
        block (bwt/inverse last-col orig-ptr)
        out (rle1-decode block)
        got-crc (crc/crc32 out)]
    (when-not (= got-crc want-crc)
      (throw (ex-info "bzip2: block CRC mismatch"
                      {:reason :bad-crc :expected want-crc :actual got-crc})))
    {:bytes out :crc want-crc}))

(defn- read-header
  "Consume `BZh<level>` and return the level, or nil at a clean end of input."
  [r]
  (if (bits/exhausted? r 32)
    nil
    (let [b1 (bits/read-bits r 8)
          b2 (bits/read-bits r 8)
          b3 (bits/read-bits r 8)
          lv (bits/read-bits r 8)]
      (when-not (and (= b1 0x42) (= b2 0x5a) (= b3 0x68))
        (throw (ex-info "bzip2: not a bzip2 stream (expected the BZh signature)"
                        {:reason :not-bzip2 :signature [b1 b2 b3]})))
      (when-not (and (>= lv 0x31) (<= lv 0x39))
        (throw (ex-info "bzip2: block-size level outside 1..9"
                        {:reason :bad-level :level (- lv 0x30)})))
      (- lv 0x30))))

(defn decompress
  "Decompress a bzip2 stream (unsigned bytes) → a vector of unsigned bytes.

   Concatenated streams are supported, because `cat a.bz2 b.bz2 | bunzip2`
   works and a decoder that stops at the first end-of-stream magic silently
   truncates such a file.

   Options: `:max-output` (default 128 MiB) bounds a hostile input;
   `:verify-checksum` false skips the per-block and combined CRC checks."
  ([data] (decompress data {}))
  ([data {:keys [max-output verify-checksum]
          :or {max-output default-max-output verify-checksum true}}]
   (let [r (bits/reader data)]
     (loop [out (transient []) total 0 streams 0]
       (let [level (read-header r)]
         (if (nil? level)
           (do (when (zero? streams)
                 (throw (ex-info "bzip2: empty input" {:reason :truncated})))
               (persistent! out))
           (let [[out total]
                 (loop [combined 0 out out total total]
                   (let [magic (bits/read-u48 r)]
                     (cond
                       (= magic block-magic)
                       (let [{:keys [bytes crc]} (decode-block r level)
                             total' (+ total (count bytes))]
                         (when (> total' max-output)
                           (throw (ex-info "bzip2: output exceeds :max-output"
                                           {:reason :output-too-large
                                            :limit max-output :size total'})))
                         (recur (crc/combine combined crc)
                                (reduce conj! out bytes)
                                total'))

                       (= magic end-magic)
                       (let [want (bits/read-u32 r)]
                         (when (and verify-checksum (not= want combined))
                           (throw (ex-info "bzip2: combined stream CRC mismatch"
                                           {:reason :bad-crc :expected want :actual combined})))
                         (bits/align-to-byte! r)
                         [out total])

                       :else
                       (throw (ex-info "bzip2: block magic not recognised"
                                       {:reason :bad-block-magic :magic magic})))))]
             (recur out total (inc streams)))))))))
