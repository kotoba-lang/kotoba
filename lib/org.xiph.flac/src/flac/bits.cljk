(ns flac.bits
  "MSB-first bit reading for FLAC, plus the two variable-length encodings the
   format uses.

   FLAC packs everything most-significant-bit first — the same order as bzip2 and
   the opposite of DEFLATE's data elements. Values wider than 24 bits are
   accumulated by multiplication rather than shifting, because a 32-bit shift is
   signed on ClojureScript.

   The cursor is a `volatile!` pair rather than a threaded value, which keeps the
   residual loops allocation-free; a reader is therefore not a value and must not
   be shared across streams."
  (:refer-clojure :exclude [bytes]))

(defn pow2
  "2^n as an **exact integer** on both runtimes.

   `Math/pow` returns a double on the JVM, and a double where an integer is
   expected fails loudly there (`Argument must be an integer: 246.0`) while
   passing silently under ClojureScript, where every number is a double anyway.
   Every power of two in this decoder goes through here."
  [n]
  (loop [i 0 acc 1] (if (= i n) acc (recur (inc i) (* 2 acc)))))

(defn floor-div
  "`(floor (/ x d))` for integers, correct for negative `x`.

   `quot` truncates toward zero, which is not what an arithmetic shift does, and
   `Math/floor` returns a double. LPC prediction depends on this being a floor."
  [x d]
  (quot (- x (mod x d)) d))

(defn reader
  "A bit reader over `data`, optionally starting at byte `offset`."
  ([data] (reader data 0))
  ([data offset]
   (let [v (vec data)]
     {:data v :len (count v) :pos (volatile! (* 8 offset))})))

(defn bit-pos [r] @(:pos r))
(defn byte-aligned? [r] (zero? (rem @(:pos r) 8)))

(defn align!
  "Skip to the next byte boundary."
  [r]
  (let [p @(:pos r) rem' (rem p 8)]
    (when (pos? rem') (vreset! (:pos r) (+ p (- 8 rem'))))))

(defn read-bit [r]
  (let [p @(:pos r)]
    (when (>= p (* 8 (:len r)))
      (throw (ex-info "flac: unexpected end of input"
                      {:reason :truncated :bit-pos p})))
    (vreset! (:pos r) (inc p))
    (bit-and (unsigned-bit-shift-right (nth (:data r) (quot p 8)) (- 7 (rem p 8))) 1)))

(defn read-bits
  "Read `n` bits as an unsigned integer, MSB-first. `n` may exceed 32."
  [r n]
  (loop [i 0 acc 0]
    (if (= i n) acc (recur (inc i) (+ (* 2 acc) (read-bit r))))))

(defn read-signed
  "Read `n` bits as a two's-complement signed integer."
  [r n]
  (if (zero? n)
    0
    (let [x (read-bits r n)
          half (pow2 (dec n))]
      (if (>= x half) (- x (* 2 half)) x))))

(defn read-unary
  "Count 0 bits up to and including the terminating 1 — the quotient half of a
   Rice code."
  [r]
  (loop [n 0]
    (if (zero? (read-bit r))
      (do (when (> n 1000000)
            (throw (ex-info "flac: unary run is implausibly long"
                            {:reason :bad-residual :count n})))
          (recur (inc n)))
      n)))

(defn read-utf8-number
  "FLAC's UTF-8-*like* coding of a frame or sample number.

   It is the original UTF-8 scheme extended to 36 bits — 7 bytes, well past the 4
   that Unicode allows — so a decoder written against modern UTF-8 rejects a
   perfectly legal FLAC frame at 2^31 samples. Values are read as exact integers,
   not shifted."
  [r]
  (let [b0 (read-bits r 8)]
    (cond
      (< b0 0x80) b0
      (< b0 0xc0) (throw (ex-info "flac: continuation byte where a frame number starts"
                                  {:reason :bad-frame-header :byte b0}))
      :else
      (let [n-extra (loop [mask 0x20 n 1]
                      (if (or (> n 6) (zero? (bit-and b0 mask)))
                        n
                        (recur (quot mask 2) (inc n))))
            first-bits (- 6 n-extra)
            _ (when (> n-extra 6)
                (throw (ex-info "flac: frame number longer than seven bytes"
                                {:reason :bad-frame-header})))]
        (loop [i 0 acc (mod b0 (pow2 (inc first-bits)))]
          (if (= i n-extra)
            acc
            (let [b (read-bits r 8)]
              (when-not (= 0x80 (bit-and b 0xc0))
                (throw (ex-info "flac: bad continuation byte in a frame number"
                                {:reason :bad-frame-header :byte b})))
              (recur (inc i) (+ (* 64 acc) (mod b 64))))))))))
