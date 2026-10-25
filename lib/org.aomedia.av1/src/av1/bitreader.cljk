(ns av1.bitreader
  "MSB-first bit reader + the AV1 bitstream 'descriptor' primitives from
   AV1 Bitstream & Decoding Process Specification (aomediacodec.github.io/av1-spec)
   section 4 (\"Descriptors\") and section 8.1 (\"Parsing process for f(n)\").

   Every primitive here is transcribed from the spec's pseudocode, not
   reconstructed from memory of libaom/dav1d source -- see the docstring on
   each fn for the exact spec section it implements. Source snapshot used:
   https://github.com/AOMediaCodec/av1-spec (master, fetched 2026-07-12),
   files 04.conventions.md / 09.parsing.process.md.

   The reader tracks a byte-array `buf` plus a bit position `pos` (in bits,
   MSB-first per byte, matching spec 8.1: \"the first bit is given by the
   most significant bit of the first byte\"). All state is carried in a
   plain map so callers can thread it explicitly (no mutable atoms) --
   every read-fn returns `[value reader']`."
  #?(:clj (:refer-clojure)))

;; ---------------------------------------------------------------------------
;; 2^n, portably.
;;
;; `(bit-shift-left 1 n)` is not this. Every ClojureScript bitwise operator
;; coerces to int32 first, so on that runtime the expression is
;; -2147483648 at n=31 (the sign bit), 1 at n=32 (the shift count is taken
;; mod 32) and 2 at n=33. Measured 2026-08-25 under nbb. The JVM answers
;; 2147483648, 4294967296 and 8589934592.
;;
;; uvlc is where that lands in this codec: its saturating value is
;; `2^32 - 1`, which came out as **0** on ClojureScript, and its
;; `2^leading_zeros - 1` term went negative at 31 leading zeros. Neither
;; threw; both returned a number of the right type.
;; ---------------------------------------------------------------------------

(defn two-pow
  "2^n for n in 0..52, exact on both runtimes."
  [n]
  (loop [i 0 v 1] (if (>= i n) v (recur (inc i) (* v 2)))))

(defn make-reader
  "byte-array (or vector of ints 0-255) -> reader map. Optionally start at
   byte offset `start-byte` (defaults to 0)."
  ([bytes] (make-reader bytes 0))
  ([bytes start-byte]
   {:bytes bytes
    :pos (* 8 start-byte)}))

(defn bit-pos [reader] (:pos reader))
(defn byte-pos
  "Current position rounded down to bytes (only meaningful when byte-aligned)."
  [reader]
  (quot (:pos reader) 8))

(defn byte-aligned? [reader] (zero? (mod (:pos reader) 8)))

(defn- get-byte [reader idx]
  (let [b (:bytes reader)]
    #?(:clj (bit-and 0xff (nth b idx))
       :cljs (bit-and 0xff (nth b idx)))))

(defn read-bit
  "spec 8.1 read_bit(): next bit from the bitstream, MSB-first within each
   byte, advances position by 1. Returns [bit reader']."
  [reader]
  (let [pos (:pos reader)
        byte-idx (quot pos 8)
        bit-idx (mod pos 8)
        byte-val (get-byte reader byte-idx)
        shift (- 7 bit-idx)
        bit (bit-and 1 (bit-shift-right byte-val shift))]
    [bit (update reader :pos inc)]))

(defn skip-bits
  "Advance the reader by `n` bits without reading/accumulating a value.
   Equivalent to calling `f` and discarding the result, but safe for large
   `n` (thousands of bits) -- `f` builds its return value via repeated
   `2*x + bit`, so for large `n` that accumulator itself overflows a 64-bit
   long well before all the bits are consumed (Clojure's `*`/`+` are
   overflow-checked by default). Needed by av1.bool-decoder/exit-symbol,
   which must skip up to `8*sz - 15` leftover bits at the end of a tile
   (hundreds to thousands of bits for a real-sized tile) but never needs the
   skipped bits' value."
  [reader n]
  (update reader :pos + n))

(defn f
  "spec 4 descriptor f(n) / 8.1 parsing process:
   x = 0; for i in 0..n-1: x = 2*x + read_bit(). n=0 reads nothing, returns 0."
  [reader n]
  (loop [x 0, i 0, r reader]
    (if (>= i n)
      [x r]
      (let [[b r'] (read-bit r)]
        (recur (+ (* 2 x) b) (inc i) r')))))

(defn uvlc
  "spec 4.340 uvlc(): Exp-Golomb-like variable length unsigned number."
  [reader]
  (loop [leading-zeros 0, r reader]
    (let [[done r'] (f r 1)]
      (if (= done 1)
        (if (>= leading-zeros 32)
          [(dec (two-pow 32)) r']
          (let [[value r''] (f r' leading-zeros)]
            [(+ value (dec (two-pow leading-zeros))) r'']))
        (recur (inc leading-zeros) r')))))

(defn le
  "spec 4.363 le(n): unsigned little-endian n-BYTE number. Only valid when
   byte-aligned."
  [reader n]
  (loop [t 0, i 0, r reader]
    (if (>= i n)
      [t r]
      (let [[byte-val r'] (f r 8)]
        (recur (+ t (bit-shift-left byte-val (* i 8))) (inc i) r')))))

(defn leb128
  "spec 4.384 leb128(): variable-length little-endian base-128 unsigned
   integer, up to 8 bytes, MSB of each byte = continuation flag.
   Returns [value leb128-byte-count reader']."
  [reader]
  (loop [value 0, i 0, r reader]
    (if (>= i 8)
      [value i r]
      (let [[byte-val r'] (f r 8)
            value' (bit-or value (bit-shift-left (bit-and byte-val 0x7f) (* i 7)))]
        (if (zero? (bit-and byte-val 0x80))
          [value' (inc i) r']
          (recur value' (inc i) r'))))))

(defn su
  "spec 4.439 su(n): signed integer from an n-bit unsigned field (bottom n
   bits of the signed value)."
  [reader n]
  (let [[value r] (f reader n)
        sign-mask (bit-shift-left 1 (dec n))]
    [(if (pos? (bit-and value sign-mask))
       (- value (* 2 sign-mask))
       value)
     r]))

(defn floor-log2
  "spec 4: FloorLog2(x) = floor(log2(x)), x >= 1."
  [x]
  (loop [s 0, x' x]
    (if (<= x' 1) s (recur (inc s) (quot x' 2)))))

(defn ns
  "spec 4.456 ns(n): non-symmetric unsigned encoded integer in range 0..n-1."
  [reader n]
  (if (<= n 1)
    [0 reader]
    (let [w (inc (floor-log2 n))
          m (- (bit-shift-left 1 w) n)
          [v r] (f reader (dec w))]
      (if (< v m)
        [v r]
        (let [[extra-bit r'] (f r 1)]
          [(- (+ (bit-shift-left v 1) extra-bit) m) r'])))))

(defn byte-alignment
  "spec 6 byte_alignment(): consume zero_bit until byte-aligned (no bits
   consumed if already aligned)."
  [reader]
  (loop [r reader]
    (if (byte-aligned? r)
      r
      (let [[_ r'] (f r 1)] (recur r')))))
