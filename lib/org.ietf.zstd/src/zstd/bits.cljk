(ns zstd.bits
  "The two bit readers zstd needs, which run in opposite directions.

   - **Forward, LSB-first** (`fwd-*`): used by the FSE table descriptions in a
     block header. Bytes are consumed low bit first, little-endian across bytes.
   - **Backward, MSB-first** (`rev-*`): used by every *data* bitstream — Huffman
     streams and the interleaved sequence stream. Reading starts at the end of
     the stream and walks toward the front, and the stream's final byte carries a
     padding marker: the highest set bit marks where the real data ends, so a
     decoder that ignores it reads up to seven bits of garbage first.

   Getting the direction or the padding wrong is the most common way a zstd
   decoder produces plausible-looking output for one block and then fails."
  (:refer-clojure :exclude [bytes]))

;; ---------------------------------------------------------------------------
;; Forward, LSB-first
;; ---------------------------------------------------------------------------

(defn fwd-reader [data from]
  {:v (vec data) :bit (volatile! (* 8 from))})

(defn fwd-bits
  "Read `n` bits, least-significant first."
  [r n]
  (let [v (:v r)]
    (loop [i 0 acc 0]
      (if (= i n)
        (do (vswap! (:bit r) + n) acc)
        (let [b (+ @(:bit r) i)
              byte-idx (quot b 8)]
          (when (>= byte-idx (count v))
            (throw (ex-info "zstd: bit reader ran out of input"
                            {:reason :truncated :bit b})))
          (recur (inc i)
                 (bit-or acc (bit-shift-left (bit-and (unsigned-bit-shift-right
                                                       (nth v byte-idx) (mod b 8))
                                                      1)
                                             i))))))))

(defn fwd-bit-pos [r] @(:bit r))
(defn fwd-seek! [r bit] (vreset! (:bit r) bit))

;; ---------------------------------------------------------------------------
;; Backward, MSB-first
;; ---------------------------------------------------------------------------

(defn- highest-set-bit [b]
  (loop [i 7] (cond (neg? i) nil (pos? (bit-and b (bit-shift-left 1 i))) i :else (recur (dec i)))))

(defn rev-reader
  "A backward reader over `data[from..to)`. Position 0 is the most significant
   bit of the *last* byte; the padding bits above the final byte's highest set
   bit, and that marker bit itself, are skipped."
  [data from to]
  (let [v    (vec data)
        len  (- to from)]
    (when (zero? len)
      (throw (ex-info "zstd: empty bitstream" {:reason :bad-bitstream})))
    (let [last-byte (nth v (dec to))
          h         (highest-set-bit last-byte)]
      (when (nil? h)
        (throw (ex-info "zstd: bitstream's last byte is zero (no padding marker)"
                        {:reason :bad-bitstream})))
      {:v v :from from :to to
       :total (* 8 len)
       :pos (volatile! (- 8 h))                            ; skip padding + marker
       })))

(defn- rev-bit-at [r i]
  (let [b        (- (:total r) 1 i)                        ; bit index from the stream start
        byte-idx (+ (:from r) (quot b 8))]
    (bit-and (unsigned-bit-shift-right (nth (:v r) byte-idx) (mod b 8)) 1)))

(defn rev-bits
  "Read `n` bits; the first bit read becomes the most significant bit of the
   result. Reading past the end yields zero bits, which is what the reference
   decoder does — the last sequence legitimately runs into the padding."
  [r n]
  (loop [i 0 acc 0]
    (if (= i n)
      (do (vswap! (:pos r) + n) acc)
      (let [p (+ @(:pos r) i)]
        (recur (inc i)
               (+ (* acc 2) (if (< p (:total r)) (rev-bit-at r p) 0)))))))

(defn rev-exhausted?
  "True once every real bit has been consumed."
  [r]
  (>= @(:pos r) (:total r)))

(defn rev-peek
  "Look at the next `n` bits without consuming them — Huffman decoding needs the
   maximum code length before it knows how many bits the symbol actually used."
  [r n]
  (let [p @(:pos r)
        v (rev-bits r n)]
    (vreset! (:pos r) p)
    v))

(defn rev-skip! [r n] (vswap! (:pos r) + n))

(defn rev-pos [r] @(:pos r))

(defn rev-overflow?
  "True once *more* bits than the stream holds have been consumed — the
   reference's `BIT_DStream_overflow`.

   Consuming exactly every bit is deliberately *not* overflow: an FSE stream
   legitimately ends that way, and treating it as the end stops one symbol
   early."
  [r]
  (> @(:pos r) (:total r)))
