(ns brotli.bits
  "Bit reading for brotli (RFC 7932 §1.5.1).

   One direction only, unlike zstd: bits are consumed from the least significant
   bit of each byte, bytes in order. Two conventions ride on top of that —

   - **integer values** are packed starting with their own least significant bit,
     so `read-bits` accumulates LSB-first;
   - **prefix codes** are packed starting with the *most significant* bit of the
     code, so a decoder walks bit by bit, shifting each new bit in at the bottom
     (`brotli.prefix`). Same split as DEFLATE.

   The cursor is a `volatile!` so the hot loops do not allocate."
  (:refer-clojure :exclude [bytes]))

(defn reader
  "A bit reader over `data` (anything vec-able of unsigned bytes)."
  [data]
  (let [v (vec data)]
    {:v v :len (count v) :bit (volatile! 0)}))

(defn read-bit [r]
  (let [b   @(:bit r)
        idx (quot b 8)]
    (when (>= idx (:len r))
      (throw (ex-info "brotli: ran out of input" {:reason :truncated :bit b})))
    (vreset! (:bit r) (inc b))
    (bit-and (unsigned-bit-shift-right (nth (:v r) idx) (mod b 8)) 1)))

(defn read-bits
  "`n` bits as an integer, least significant bit first."
  [r n]
  (loop [i 0 acc 0]
    (if (= i n)
      acc
      ;; Multiplication rather than a shift: n can be 24, and intermediate
      ;; values stay well inside the exact range either way, but a 1 << 31 in a
      ;; later caller would not.
      (recur (inc i) (+ acc (* (read-bit r) (bit-shift-left 1 i)))))))

(defn align!
  "Discard bits up to the next byte boundary, and report whether they were all
   zero — several places in the format require that they are."
  [r]
  (let [b @(:bit r)
        pad (mod (- 8 (mod b 8)) 8)]
    ;; Not named `zero?`: shadowing the core predicate here made the loop call a
    ;; boolean as a function on every aligned meta-block.
    (loop [i 0 all-zero? true]
      (if (= i pad)
        (do (vreset! (:bit r) (+ b pad)) all-zero?)
        (recur (inc i) (and all-zero? (zero? (read-bit r))))))))

(defn bit-pos [r] @(:bit r))
(defn byte-pos [r] (quot (+ @(:bit r) 7) 8))
(defn seek-byte! [r byte-idx] (vreset! (:bit r) (* 8 byte-idx)))
(defn exhausted? [r] (>= (quot @(:bit r) 8) (:len r)))

(defn read-bytes!
  "`n` whole bytes; the reader must be byte-aligned."
  [r n]
  (let [start (quot @(:bit r) 8)]
    (when (> (+ start n) (:len r))
      (throw (ex-info "brotli: ran out of input" {:reason :truncated})))
    (vreset! (:bit r) (* 8 (+ start n)))
    (subvec (:v r) start (+ start n))))
