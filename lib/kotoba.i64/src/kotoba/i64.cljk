(ns kotoba.i64
  "Signed 64-bit integer semantics that do not change with the host.

  Every consumer of this workspace's compiler stack needs the same three
  things -- the range boundaries, two's-complement wraparound, and predicates
  that actually recognise a 64-bit value -- and until now each reached for the
  host to get them. Measured 2026-08-20 across amu / kotoba-kir /
  kotoba-native / kotoba-wasm: 79 references to `Long/MIN_VALUE` or
  `Long/MAX_VALUE` and 187 to `js/BigInt`, in four repositories, for one
  semantics. That is the shape of a missing library rather than a style
  preference.

  **The representation differs by host and that is deliberate.** On the JVM a
  value is a primitive `long`; on ClojureScript it is a JS `bigint`. Neither
  is wrapped in a record, because the compiler's hot paths are arithmetic and
  a box per operation would be paid on every one. What this namespace
  guarantees is that the OPERATIONS agree: the same inputs produce the same
  value, and `->string` produces the same text.

  **`clojure.core`'s own predicates are not safe on the cljs side.** Confirmed
  live: `(zero? (js/BigInt 0))` returns false, and `bit-shift-right` throws
  'Cannot mix BigInt and other types'. Use the versions here on any value that
  came from here. This is the single most important reason the namespace
  exists rather than being a pair of constants.

  Promoted from `kotoba.kir.cljs-i64`, which had the cljs half of this and no
  JVM half, so nothing outside kotoba-kir could use it."
  (:refer-clojure :exclude [zero? neg? pos? bit-not bit-and bit-or bit-xor]))

;; ---------------------------------------------------------------------------
;; Range

(def min-i64
  "-2^63. The value `Long/MIN_VALUE` names on the JVM."
  #?(:clj Long/MIN_VALUE :cljs (js/BigInt "-9223372036854775808")))

(def max-i64
  "2^63 - 1."
  #?(:clj Long/MAX_VALUE :cljs (js/BigInt "9223372036854775807")))

(def zero #?(:clj 0 :cljs (js/BigInt 0)))
(def one  #?(:clj 1 :cljs (js/BigInt 1)))

;; ---------------------------------------------------------------------------
;; Recognition and coercion

(defn i64?
  "True when X is this host's 64-bit representation.

  On cljs this checks for `bigint` specifically: a plain cljs number is an
  IEEE-754 double and loses precision silently above 2^53, so accepting one
  here would let a lossy value travel as though it were exact."
  [x]
  #?(:clj (instance? Long x)
     :cljs (boolean (and (some? x)
                         (try (= (.-constructor x) js/BigInt)
                              (catch :default _ false))))))

(defn ->i64
  "Coerce an integer literal to this host's 64-bit representation.

  Idempotent, so a value that already came from here passes through
  untouched. Every other function in this namespace assumes its inputs went
  through this once."
  [x]
  (if (i64? x) x #?(:clj (long x) :cljs (js/BigInt x))))

(defn in-range?
  "Whether X sits inside [min-i64, max-i64] without wrapping."
  [x]
  (let [v (->i64 x)] (and (<= min-i64 v) (<= v max-i64))))

;; ---------------------------------------------------------------------------
;; Predicates
;;
;; These exist because clojure.core's do not work on cljs bigint. See the ns
;; docstring -- `(clojure.core/zero? (js/BigInt 0))` is false, which is a
;; wrong answer rather than an error, so it cannot be left to the caller.

(defn zero? [x] (= (->i64 x) zero))
(defn neg?  [x] (< (->i64 x) zero))
(defn pos?  [x] (> (->i64 x) zero))

;; ---------------------------------------------------------------------------
;; Wraparound

(defn wrap
  "Two's-complement wraparound into the signed 64-bit range.

  The JVM gets this for free from `long` overflow; cljs `bigint` is unbounded
  and needs `BigInt.asIntN` to be told where to stop. Both are 'modulo 2^64'
  by construction, which is what the compiler's own execute semantics
  specify."
  [x]
  #?(:clj (long x)
     :cljs (js/BigInt.asIntN 64 (->i64 x))))

;; ---------------------------------------------------------------------------
;; Arithmetic -- wrapping, never throwing on overflow

(defn add [x y]
  #?(:clj (unchecked-add (long x) (long y))
     :cljs (wrap (+ (->i64 x) (->i64 y)))))

(defn sub [x y]
  #?(:clj (unchecked-subtract (long x) (long y))
     :cljs (wrap (- (->i64 x) (->i64 y)))))

(defn mul [x y]
  #?(:clj (unchecked-multiply (long x) (long y))
     :cljs (wrap (* (->i64 x) (->i64 y)))))

(defn negate [x]
  #?(:clj (unchecked-negate (long x))
     :cljs (wrap (- (->i64 x)))))

;; ---------------------------------------------------------------------------
;; Bitwise

(defn bit-not [x]
  #?(:clj (clojure.core/bit-not (long x))
     :cljs (wrap (clojure.core/bit-xor (->i64 x) (js/BigInt -1)))))

(defn bit-and [x y]
  #?(:clj (clojure.core/bit-and (long x) (long y))
     :cljs (wrap (clojure.core/bit-and (->i64 x) (->i64 y)))))

(defn bit-or [x y]
  #?(:clj (clojure.core/bit-or (long x) (long y))
     :cljs (wrap (clojure.core/bit-or (->i64 x) (->i64 y)))))

(defn bit-xor [x y]
  #?(:clj (clojure.core/bit-xor (long x) (long y))
     :cljs (wrap (clojure.core/bit-xor (->i64 x) (->i64 y)))))

;; ---------------------------------------------------------------------------
;; Shifts
;;
;; The shift count is a plain small non-negative number on both hosts, never
;; an i64 -- it is a count, not a value. Out-of-range counts are refused
;; rather than masked: the JVM masks a shift count modulo 64 silently, so
;; `(shl x 64)` would be a no-op there and something else on cljs, and a
;; disagreement that returns a plausible number is the worst kind.

(defn- checked-shift [n]
  (when-not (and (integer? n) (<= 0 n) (< n 64))
    (throw (ex-info "i64 shift count out of range" {:shift n :range [0 63]})))
  n)

(defn shl [x n]
  (let [s (checked-shift n)]
    #?(:clj (bit-shift-left (long x) s)
       ;; 2^s is exact as a double for every s in [0,63] (a power of two), so
       ;; the BigInt conversion below is exact.
       :cljs (wrap (* (->i64 x) (js/BigInt (js/Math.pow 2 s)))))))

(defn ashr
  "Arithmetic (sign-preserving) right shift.

  cljs has no bigint `>>`: `bit-shift-right` throws on bigint input and JS
  leaves `>>>` undefined for bigint entirely. So this is floor division by
  2^s. JS `/` on bigint truncates toward zero, which equals arithmetic shift
  only for non-negative values or exact multiples -- the adjustment converts
  truncation into flooring, which is the equivalence for a positive
  power-of-two divisor."
  [x n]
  (let [s (checked-shift n)]
    #?(:clj (bit-shift-right (long x) s)
       :cljs (let [v (->i64 x)
                   d (js/BigInt (js/Math.pow 2 s))
                   q (/ v d)
                   r (- v (* q d))]
               (wrap (if (and (not= r zero) (< v zero)) (- q one) q))))))

(defn lshr
  "Logical (zero-filling) right shift, over the 64-bit pattern."
  [x n]
  (let [s (checked-shift n)]
    #?(:clj (unsigned-bit-shift-right (long x) s)
       :cljs (wrap (/ (js/BigInt.asUintN 64 (->i64 x))
                      (js/BigInt (js/Math.pow 2 s)))))))

;; ---------------------------------------------------------------------------
;; Rendering

(defn ->string
  "Decimal text, identical on every host.

  `(str v)` is not identical: cljs renders a bigint with an `n` suffix in some
  contexts, and that difference has reached content-addressed output before."
  [x]
  #?(:clj (Long/toString (long x))
     :cljs (.toString (->i64 x))))
