(ns bzip2.bits
  "Bit-level I/O for bzip2.

   **bzip2 packs every field most-significant-bit first** — the opposite of
   DEFLATE, where data elements are LSB-first and only Huffman codes are
   MSB-first. There is exactly one bit order here, and mixing it up with
   DEFLATE's is the fastest way to produce a stream only this decoder can read.

   Fields wider than 24 bits (the 48-bit block magics, the 32-bit CRCs) are
   read and written in halves and recombined by multiplication, never by
   shifting: a 32-bit shift is signed on ClojureScript and a 48-bit one does
   not exist there at all.

   The cursor is held in `volatile!` cells rather than threaded as a value,
   which keeps the hot loops allocation-free on both runtimes. Neither a reader
   nor a writer is a value — do not share one across logical streams."
  (:refer-clojure :exclude [flush]))

;; ---------------------------------------------------------------------------
;; Reader
;; ---------------------------------------------------------------------------

(defn reader
  "A bit reader over `data` (anything `vec`-able of unsigned bytes)."
  [data]
  (let [v (vec data)]
    {:data v :len (count v) :pos (volatile! 0)}))

(defn bit-pos [r] @(:pos r))

(defn exhausted?
  "True when fewer than `n` bits remain."
  [r n]
  (> (+ @(:pos r) n) (* 8 (:len r))))

(defn read-bit
  "Next bit, MSB-first within each byte."
  [r]
  (let [p @(:pos r)]
    (when (>= p (* 8 (:len r)))
      (throw (ex-info "bzip2: unexpected end of input"
                      {:reason :truncated :bit-pos p})))
    (let [b (nth (:data r) (quot p 8))
          s (- 7 (rem p 8))]
      (vreset! (:pos r) (inc p))
      (bit-and (unsigned-bit-shift-right b s) 1))))

(defn read-bits
  "Read `n` bits (n <= 24) as an integer, MSB-first."
  [r n]
  (loop [i 0 acc 0]
    (if (= i n)
      acc
      (recur (inc i) (+ (* 2 acc) (read-bit r))))))

(defn read-u32
  "Read a 32-bit big-endian field as an unsigned integer."
  [r]
  (+ (* 65536 (read-bits r 16)) (read-bits r 16)))

(defn read-u48
  "Read a 48-bit big-endian field (the block and end-of-stream magics) as an
   exact integer — 2^48 is well inside the 2^53 exact range on both runtimes."
  [r]
  (+ (* 16777216 (read-bits r 24)) (read-bits r 24)))

(defn align-to-byte!
  "Discard bits up to the next byte boundary."
  [r]
  (let [p @(:pos r)
        r' (rem p 8)]
    (when (pos? r')
      (vreset! (:pos r) (+ p (- 8 r'))))))

;; ---------------------------------------------------------------------------
;; Writer
;; ---------------------------------------------------------------------------

(defn writer
  "A bit writer accumulating unsigned bytes."
  []
  {:out (volatile! (transient [])) :cur (volatile! 0) :n (volatile! 0)})

(defn write-bit!
  [w bit]
  (let [n (inc @(:n w))
        c (+ (* 2 @(:cur w)) (if (zero? bit) 0 1))]
    (if (= n 8)
      (do (vswap! (:out w) conj! c)
          (vreset! (:cur w) 0)
          (vreset! (:n w) 0))
      (do (vreset! (:cur w) c)
          (vreset! (:n w) n))))
  w)

(defn write-bits!
  "Write the low `n` bits of `value` (n <= 24), MSB-first."
  [w n value]
  (loop [i (dec n)]
    (when (>= i 0)
      (write-bit! w (bit-and (unsigned-bit-shift-right value i) 1))
      (recur (dec i))))
  w)

(defn write-u32!
  "Write a 32-bit big-endian field, in halves — a 32-bit shift is signed on
   ClojureScript."
  [w value]
  (write-bits! w 16 (quot value 65536))
  (write-bits! w 16 (rem value 65536)))

(defn write-u48!
  "Write a 48-bit big-endian field (a block or end-of-stream magic)."
  [w value]
  (write-bits! w 24 (quot value 16777216))
  (write-bits! w 24 (rem value 16777216)))

(defn finish!
  "Pad the final partial byte with zero bits and return the bytes."
  [w]
  (let [n @(:n w)]
    (when (pos? n)
      (dotimes [_ (- 8 n)] (write-bit! w 0)))
    (persistent! @(:out w))))
