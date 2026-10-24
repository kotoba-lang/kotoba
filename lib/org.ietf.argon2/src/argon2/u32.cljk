(ns argon2.u32
  "64-bit words as pairs of 32-bit lanes, and the flat arrays that hold them.

  This is the one file that knows which runtime it is on. Everything above it
  is a single code path.

  ## Why not the representation `org-ietf-blake2` uses

  That library makes a word a `long` on the JVM and a `BigInt` under
  ClojureScript, and says in its own docstring that hashing a large file on
  the JavaScript side would be too slow. Argon2 *is* the large file: at the
  OWASP-recommended 19 MiB it performs roughly 39,000 block compressions,
  each 8 rounds of 8 mixing steps. BigInt allocates on every operation, so
  that representation is not merely slower here — it is the difference
  between seconds and hours.

  So a word here is two ordinary integers, `hi` and `lo`, each in
  `0 .. 2^32-1`, and they live in a flat array of 32-bit lanes: word `w`
  occupies lane `2w` (low half) and lane `2w+1` (high half). Both runtimes
  have a fast array of that shape — `int-array` and `Uint32Array` — and every
  arithmetic operation below stays inside the range where a JavaScript number
  is an exact integer.

  ## The one trap this file exists to contain

  JavaScript's bitwise operators are 32-bit, and its shift COUNT is taken
  mod 32, so `x << 32` is `x << 0`. Both of those are silent. Every operation
  here is written to stay under 32 bits and never to shift by 32, and every
  result passes through `u32`. Multiplication is the exception that cannot:
  `fBlaMka` needs a full 32x32 -> 64 product, which is why `mul32` splits its
  arguments into 16-bit halves rather than reaching for a wider type that
  only one runtime has."
  (:refer-clojure :exclude [rem]))

;; ── arrays ───────────────────────────────────────────────────────────────────

(defn alloc
  "A zeroed array of `n` 32-bit lanes."
  [n]
  #?(:clj (int-array n)
     :cljs (js/Uint32Array. n)))

(defn rd
  "Lane `i` as a non-negative integer. The JVM's `int-array` is signed, so
  the mask is not decoration: without it every lane with the high bit set
  reads back negative and every comparison downstream is wrong."
  [a i]
  #?(:clj (bit-and (aget ^ints a i) 0xFFFFFFFF)
     :cljs (aget a i)))

(defn wr [a i v]
  #?(:clj (aset ^ints a (int i) (unchecked-int v))
     :cljs (aset a i v))
  nil)

;; ── 32-bit arithmetic ────────────────────────────────────────────────────────

(defn u32
  "Reduce to `0 .. 2^32-1`.

  On the JVM a mask; under ClojureScript `x >>> 0`, whose ToUint32 coercion
  takes the value mod 2^32 for anything up to 2^53. Applied after every
  operation that can leave the range, which is most of them."
  [x]
  #?(:clj (bit-and x 0xFFFFFFFF)
     :cljs (unsigned-bit-shift-right x 0)))

(defn mul32!
  "Write the full 32x32 -> 64 product of `x` and `y` into `out` as
  `[hi lo]` at lanes 0 and 1.

  Split into 16-bit halves because the product fits neither a JavaScript
  number exactly nor a 32-bit operator at all. Every intermediate stays under
  2^33, well inside the exact-integer range, and the two `bit-and`s of a
  value that may exceed 2^32 are safe: ToInt32 preserves the low 32 bits, so
  the low 16 survive the coercion. The two `quot`s are division rather than
  `>>> 16` for the opposite reason — a logical shift would truncate to 32
  bits first and discard the carry this function exists to compute.

  It writes rather than returns because the caller runs it about five million
  times per hash, and a two-element vector per call is five million objects."
  [out x y]
  (let [xl (bit-and x 0xFFFF) xh (quot x 65536)
        yl (bit-and y 0xFFFF) yh (quot y 65536)
        t0 (* xl yl)
        t1 (+ (* xh yl) (quot t0 65536))
        t2 (+ (* xl yh) (bit-and t1 0xFFFF))
        lo (+ (bit-and t0 0xFFFF) (* (bit-and t2 0xFFFF) 65536))
        hi (+ (* xh yh) (quot t1 65536) (quot t2 65536))]
    (wr out 0 (u32 hi))
    (wr out 1 (u32 lo))
    nil))

(defn mul32
  "`mul32!` as a value, for callers that are not in the inner loop. The same
  code path, so a test of this is a test of what the loop runs."
  [x y]
  (let [o (alloc 2)] (mul32! o x y) [(rd o 0) (rd o 1)]))

(defn add64!
  "Write the wrapping 64-bit sum into `out` at lanes 0 and 1.

  The carry is a comparison rather than a shift of a 33-bit intermediate,
  which no 32-bit operator could hold."
  [out ahi alo bhi blo]
  (let [lo (+ alo blo)
        carry? (>= lo 4294967296)]
    (wr out 0 (u32 (+ ahi bhi (if carry? 1 0))))
    (wr out 1 (if carry? (- lo 4294967296) lo))
    nil))

(defn add64 [ahi alo bhi blo]
  (let [o (alloc 2)] (add64! o ahi alo bhi blo) [(rd o 0) (rd o 1)]))

(defn rotr64!
  "Write `(hi,lo)` rotated right by `n`, 0 < n < 64, into `out`.

  `n = 32` is a lane swap and is written as one: expressing it as a shift
  would ask ClojureScript for `<< 32`, which it silently performs as
  `<< 0`. For every other `n` the shift amounts land in 1..31."
  [out hi lo n]
  (cond
    (= n 32) (do (wr out 0 lo) (wr out 1 hi))
    (< n 32) (do (wr out 0 (u32 (bit-or (unsigned-bit-shift-right hi n)
                                        (bit-shift-left lo (- 32 n)))))
                 (wr out 1 (u32 (bit-or (unsigned-bit-shift-right lo n)
                                        (bit-shift-left hi (- 32 n))))))
    :else (let [n (- n 32)]
            (if (zero? n)
              (do (wr out 0 lo) (wr out 1 hi))
              (do (wr out 0 (u32 (bit-or (unsigned-bit-shift-right lo n)
                                         (bit-shift-left hi (- 32 n)))))
                  (wr out 1 (u32 (bit-or (unsigned-bit-shift-right hi n)
                                         (bit-shift-left lo (- 32 n)))))))))
  nil)

(defn rotr64 [hi lo n]
  (let [o (alloc 2)] (rotr64! o hi lo n) [(rd o 0) (rd o 1)]))

;; ── little-endian bytes ──────────────────────────────────────────────────────

(defn le32
  "A non-negative integer below 2^32 as four little-endian bytes."
  [n]
  [(bit-and n 0xFF)
   (bit-and (quot n 256) 0xFF)
   (bit-and (quot n 65536) 0xFF)
   (bit-and (quot n 16777216) 0xFF)])

(defn le64
  "A non-negative integer below 2^53 as eight little-endian bytes."
  [n]
  (into (le32 (u32 n)) (le32 (quot n 4294967296))))
