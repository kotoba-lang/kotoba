(ns amqp.types
  "The AMQP 1.0 type system — OASIS AMQP Version 1.0, Part 1 (Type System),
  spec text confirmed 2026-08-30 against
  docs.oasis-open.org/amqp/core/v1.0/os/amqp-core-types-v1.0-os.html
  \"1.6.7 Primitive Type Definitions\".

  Every AMQP value on the wire begins with a *constructor*: either a
  primitive format code, or a described-type constructor `0x00 descriptor
  constructor`. A primitive format code's low nibble names the width class
  (fixed/variable/compound/array) and its high nibble a subcategory that
  picks the actual width — several codes can name the same logical type
  (`uint0`/`smalluint`/`uint` are all \"an unsigned 32-bit integer\", just
  encoded at 0, 1 or 4 bytes). `encode-value` always emits the narrowest
  form that holds the value; `decode-value` normalizes all three back to
  one tag, because the width choice was never semantic — only the value is.

  Bytes are `Sequential` collections of ints in 0..255, in and out, matching
  this workspace's `org-modbus` convention.

  ## Why 64-bit values are bounded to the JS safe-integer range

  `ulong`/`long`/`timestamp` are 8-byte wire fields, but this codec builds
  and reads them as `hi32 * 2^32 + lo32` using ordinary arithmetic rather
  than 64-bit bitwise ops. `bit-shift-left`/`bit-or` are 32-bit and signed
  in JavaScript — shifting or OR-ing across the 32-bit boundary silently
  wraps — so every multi-byte integer here is built from bytes that never
  individually exceed 32 bits, then combined with `*`/`+`, which is exact
  for magnitudes up to 2^53 on both runtimes. Every 64-bit field this
  library actually round-trips (epoch milliseconds, capacity counters) sits
  nowhere near that boundary; a `ulong` near 2^64-1 is a real gap, not a
  hidden one — see the README.

  ## What is not here

  `decimal32`/`decimal64`/`decimal128` (IEEE 754-2008 decimal, binary
  integer decimal encoding) are in the spec's format-code table and in
  nothing this workspace's AMQP performatives use; encoding a base-10
  floating point format nobody can exercise is how a codec acquires
  untested branches nobody notices are wrong. Decoding an unrecognized
  format code — decimal's included — returns `:amqp/unsupported-format-code`
  rather than silently skipping it.")

;; ── byte-level helpers ───────────────────────────────────────────────────────

(defn- u8 [n] (bit-and n 0xFF))

(defn- as-fixnum
  "Coerces a numeric value that is *known* to be a small nonnegative
  magnitude back to a plain JVM `long`, undoing `clojure.lang.BigInt`
  'poisoning' from an unrelated large-magnitude computation upstream — an
  earlier version of this codec's signed-64-bit conversion divided by a
  `0x10000000000000000` (2^64) literal, which does not fit in a `Long`, so
  the *reader* parsed it as `BigInt`, and `mod` against a `BigInt` divisor
  returns a `BigInt` result even when that result's actual value is tiny.
  `bit-and`/`unsigned-bit-shift-right` then throw `IllegalArgumentException:
  bit operation not supported for: class clojure.lang.BigInt` — found by
  this library's own randomised sweep over primitive format codes hitting
  a `:long` near ±2^53, not by inspection (see `signed64->hi-lo`, which
  replaced that conversion with limb arithmetic and needs no `BigInt` at
  all — `as-fixnum` stays because `:ulong`'s wide form, `u64-bytes` below,
  still funnels a value through the same `quot`/`mod`-by-`2^32` split).
  A no-op on ClojureScript, which has only one numeric type and no such
  poisoning to undo."
  [n]
  #?(:clj (long n) :cljs n))

(defn- u32-bytes
  "Four big-endian bytes of a nonnegative integer that fits in 32 bits.
  Extraction only ever touches one 32-bit-or-narrower value at a time, so
  `unsigned-bit-shift-right`/`bit-and` agree between the JVM's 64-bit longs
  and JavaScript's 32-bit bitwise operators — *given* a `long`, which is
  why every call site funnels through `as-fixnum` first rather than
  trusting the caller's numeric type."
  [n]
  (let [n (as-fixnum n)]
    [(bit-and (unsigned-bit-shift-right n 24) 0xFF)
     (bit-and (unsigned-bit-shift-right n 16) 0xFF)
     (bit-and (unsigned-bit-shift-right n 8) 0xFF)
     (bit-and n 0xFF)]))

(defn- u32-from-bytes
  "Inverse of `u32-bytes`. The trailing `unsigned-bit-shift-right … 0` is
  load-bearing on ClojureScript: `bit-or` of four left-shifted bytes can set
  bit 31, and JavaScript's bitwise operators read that as a *sign* bit, so
  the raw `bit-or` result comes back negative for anything >= 0x80000000.
  Shifting right by zero re-reads the same 32 bits as unsigned. On the JVM
  this is a no-op — the value was already a nonnegative 64-bit long."
  [b0 b1 b2 b3]
  (unsigned-bit-shift-right
   (bit-or (bit-shift-left (u8 b0) 24)
           (bit-shift-left (u8 b1) 16)
           (bit-shift-left (u8 b2) 8)
           (u8 b3))
   0))

(defn- u16-bytes [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- u16-from-bytes [b0 b1] (bit-or (bit-shift-left (u8 b0) 8) (u8 b1)))

(defn- u64-bytes
  "Eight big-endian bytes of a **nonnegative** integer within the JS
  safe-integer range — `:ulong`'s wide form only. `:long`/`:timestamp`
  (signed) go through `signed64-bytes` instead, which does not route
  through this function; see that function's docstring for why a signed
  value can't safely share this one. Split into two 32-bit halves with
  `quot`/`mod` — plain arithmetic, exact up to 2^53 on both runtimes —
  then each half goes through the 32-bit-safe `u32-bytes`."
  [n]
  (into (u32-bytes (quot n 0x100000000)) (u32-bytes (mod n 0x100000000))))

(defn- u64-from-bytes
  "Inverse of `u64-bytes` — **`:ulong` only**, same reason. `+'`/`*'`
  (auto-promoting to `BigInt` on overflow) on the JVM, not plain `+`/`*`:
  the high 4 bytes alone can be up to `2^32-1`, and `hi * 2^32` alone
  already exceeds `Long/MAX_VALUE`, which plain `*` (checked, throws
  `ArithmeticException: long overflow` rather than wrapping or promoting)
  cannot represent even for a `:ulong` at the very top of this
  namespace's documented 2^53 bound. ClojureScript has no `+'`/`*'` at
  all (nbb: \"Unable to resolve symbol\") and no such overflow to guard —
  every number is a double regardless of magnitude — so plain `+`/`*`
  there is correct, not a second bug."
  [bs]
  (let [hi (u32-from-bytes (nth bs 0) (nth bs 1) (nth bs 2) (nth bs 3))
        lo (u32-from-bytes (nth bs 4) (nth bs 5) (nth bs 6) (nth bs 7))]
    #?(:clj (+' (*' hi 4294967296) lo)
       :cljs (+ (* hi 4294967296) lo))))

(defn- s32->u32
  "Two's-complement encode a signed 32-bit int as its unsigned bit pattern,
  via arithmetic (`mod`), not a shift — the same reason `u64-bytes` avoids
  shifting past bit 31."
  [n] (mod n 0x100000000))

(defn- u32->s32 [u] (if (>= u 0x80000000) (- u 0x100000000) u))

;; ── signed 64-bit (`long`/`timestamp`) via limb arithmetic ──────────────────
;;
;; `(mod n (long 2^64))` is the textbook two's-complement conversion, and
;; is exactly right on the JVM (`BigInt`, arbitrary precision, no rounding
;; ever). On ClojureScript it is wrong for *every* negative `n`, even a
;; tiny one: `mod` by a divisor of magnitude 2^64 produces a result near
;; 2^64 (≈1.8×10^19), and JS doubles are only exact up to 2^53 — so the
;; result is already corrupted before anything downstream even looks at
;; it. This library's own randomised sweep, run on the ClojureScript
;; path, is what caught it (`amqp.types-test`'s `:timestamp` case; every
;; JVM run passed because `BigInt` has no such boundary). The fix is to
;; never form that ~2^64-magnitude number at all: do the two's-complement
;; subtraction one 32-bit limb at a time, so no intermediate value this
;; function touches ever exceeds `2^32-1`.

(defn- signed64->hi-lo
  "The 64-bit two's-complement bit pattern of signed `n` (`|n| <= 2^53`,
  this namespace's documented bound for `long`/`timestamp`), as `[hi lo]`
  32-bit unsigned halves."
  [n]
  (if (>= n 0)
    [(quot n 0x100000000) (mod n 0x100000000)]
    (let [m (- n) ; magnitude, positive
          hi-abs (quot m 0x100000000)
          lo-abs (mod m 0x100000000)]
      ;; `2^64 - m`, computed as `(2^32 - hi-abs [- 1 if borrowing]) * 2^32
      ;; + (2^32 - lo-abs)` — ordinary manual-long-subtraction borrowing,
      ;; the same technique `RFC 4493`'s CMAC uses one bit at a time
      ;; (`lorawan.cmac/left-shift-1`) rather than 32 bits at a time.
      (if (zero? lo-abs)
        [(- 0x100000000 hi-abs) 0]
        [(- 0xFFFFFFFF hi-abs) (- 0x100000000 lo-abs)]))))

(defn- hi-lo->signed64
  "Inverse of `signed64->hi-lo`."
  [hi lo]
  (if (< hi 0x80000000)
    (+ (* hi 0x100000000) lo)
    (let [lo' (if (zero? lo) 0 (- 0x100000000 lo))
          hi' (if (zero? lo) (- 0x100000000 hi) (- 0xFFFFFFFF hi))]
      (- (+ (* hi' 0x100000000) lo')))))

(defn- signed64-bytes [n]
  (let [[hi lo] (signed64->hi-lo n)] (into (u32-bytes hi) (u32-bytes lo))))

(defn- bytes->signed64 [bs]
  (hi-lo->signed64 (apply u32-from-bytes (subvec (vec bs) 0 4))
                    (apply u32-from-bytes (subvec (vec bs) 4 8))))

;; ── UTF-8 (workspace convention: `bonsai.git-codec`, `org-modbus`'s own
;;    write-up of `(map int "…")` returning zeros under ClojureScript) ────────

(defn- str->utf8-bytes
  "`.getBytes` returns Java's *signed* `byte[]` (-128..127) — every octet
  at or above 0x80 (i.e. every non-ASCII UTF-8 continuation/lead byte)
  comes back negative, e.g. `é`'s `0xC3` is `-61`. `bit-and … 0xFF` masks
  each one back to this codec's 0..255 convention; skipping it made
  `encode-value` reject any non-ASCII string with `:amqp/byte-out-of-range`
  — this library's own round-trip corpus (`\"unicode: é中\"`) is what
  caught it, not an ASCII-only test suite that would never exercise this
  path at all."
  [s]
  #?(:clj  (vec (map #(bit-and (int %) 0xFF) (.getBytes ^String s "UTF-8")))
     :cljs (vec (js/Array.from (.encode (js/TextEncoder.) s)))))

(defn- utf8-bytes->str [bs]
  #?(:clj  (String. (byte-array (map #(unchecked-byte (u8 %)) bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") (js/Uint8Array.from (clj->js bs)))))

;; ── IEEE 754 float32/float64. Reader-conditional host bit-conversion is the
;;    same seam `bonsai.git-codec` uses for UTF-8: a `.cljc` file calling the
;;    platform's own float<->bits primitive, not a reimplementation. ─────────

(defn- f32->u32 [f]
  #?(:clj (Integer/toUnsignedLong (Float/floatToIntBits (float f)))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 4))]
             (.setFloat32 dv 0 f false)
             (.getUint32 dv 0 false))))

(defn- u32->f32 [u]
  #?(:clj (Float/intBitsToFloat (unchecked-int (u32->s32 u)))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 4))]
             (.setUint32 dv 0 u false)
             (.getFloat32 dv 0 false))))

(defn- f64->bytes
  "The 8-byte big-endian IEEE 754 binary64 bit pattern of `f`, built
  *directly* from the two 32-bit halves — never combined into one JS
  number the way an earlier version of this function did (`(+ (* hi
  2^32) lo)`), because that combined value is exactly what
  `signed64->hi-lo`'s note explains loses precision on ClojureScript for
  any negative double. On the JVM, `unsigned-bit-shift-right`/`bit-and`
  read `Double/doubleToLongBits`'s signed 64-bit result correctly
  regardless of its sign — those are genuine bitwise operations on a
  primitive `long`, not arithmetic that could throw or promote to
  `BigInt`, which is why this function needs neither `signed64->hi-lo`
  nor `as-fixnum`."
  [f]
  #?(:clj (let [bits (Double/doubleToLongBits (double f))]
            (into (u32-bytes (unsigned-bit-shift-right bits 32)) (u32-bytes (bit-and bits 0xFFFFFFFF))))
     :cljs (let [dv (js/DataView. (js/ArrayBuffer. 8))]
             (.setFloat64 dv 0 f false)
             (into (u32-bytes (.getUint32 dv 0 false)) (u32-bytes (.getUint32 dv 4 false))))))

(defn- bytes->f64
  "Inverse of `f64->bytes` — reassembles the bit pattern from `hi`/`lo`
  with `bit-shift-left`/`bit-or` (bitwise, exact on a primitive `long`
  regardless of sign) rather than `+`/`*`, for the same reason."
  [bs]
  (let [hi (apply u32-from-bytes (subvec (vec bs) 0 4))
        lo (apply u32-from-bytes (subvec (vec bs) 4 8))]
    #?(:clj (Double/longBitsToDouble (bit-or (bit-shift-left hi 32) lo))
       :cljs (let [dv (js/DataView. (js/ArrayBuffer. 8))]
               (.setUint32 dv 0 hi false)
               (.setUint32 dv 4 lo false)
               (.getFloat64 dv 0 false)))))

;; ── slicing a decode buffer without ever throwing ───────────────────────────

(defn- take-bytes
  "`n` bytes of `bs` starting at `off`, or `:amqp/buffer-underrun` — never an
  index-out-of-bounds exception. Every decoder in this file goes through
  this, so a truncated frame is a named error at the point of truncation,
  not wherever `nth` first walks off the end."
  [bs off n]
  (if (<= (+ off n) (count bs))
    {:status :ok :bytes (vec (subvec (vec bs) off (+ off n))) :next (+ off n)}
    {:status :error :reason :amqp/buffer-underrun :offset off :need n :have (- (count bs) off)}))

;; ── format codes ─────────────────────────────────────────────────────────────
;; code -> [tag decode-fn], where decode-fn reads whatever the code's width
;; class requires (nothing further for fixed-width-0, `width` more fixed
;; bytes, a size prefix for variable/compound/array).

(def null-code 0x40)
(def true-code 0x41)
(def false-code 0x42)
(def boolean-code 0x56)
(def ubyte-code 0x50)
(def ushort-code 0x60)
(def uint0-code 0x43) (def smalluint-code 0x52) (def uint-code 0x70)
(def ulong0-code 0x44) (def smallulong-code 0x53) (def ulong-code 0x80)
(def byte-code 0x51)
(def short-code 0x61)
(def smallint-code 0x54) (def int-code 0x71)
(def smalllong-code 0x55) (def long-code 0x81)
(def float-code 0x72)
(def double-code 0x82)
(def char-code 0x73)
(def timestamp-code 0x83)
(def uuid-code 0x98)
(def vbin8-code 0xA0) (def vbin32-code 0xB0)
(def str8-code 0xA1) (def str32-code 0xB1)
(def sym8-code 0xA3) (def sym32-code 0xB3)
(def list0-code 0x45) (def list8-code 0xC0) (def list32-code 0xD0)
(def map8-code 0xC1) (def map32-code 0xD1)
(def array8-code 0xE0) (def array32-code 0xF0)
(def described-code 0x00)

(declare encode-value decode-value)

(def ^:private array-elem-ctor-code
  {:ubyte ubyte-code :ushort ushort-code :uint uint-code :ulong ulong-code
   :byte byte-code :short short-code :int int-code :long long-code
   :boolean boolean-code :string str32-code :symbol sym32-code
   :binary vbin32-code :timestamp timestamp-code :char char-code})

(defn- encode-array-elem
  "One array element's *bare* payload — no constructor byte, the array's
  single shared constructor already named the width."
  [elem-tag x]
  (case elem-tag
    :ubyte {:status :ok :bytes [x]}
    :byte {:status :ok :bytes [(u8 x)]}
    :ushort {:status :ok :bytes (u16-bytes x)}
    :uint {:status :ok :bytes (u32-bytes x)}
    :ulong {:status :ok :bytes (u64-bytes x)}
    :int {:status :ok :bytes (u32-bytes (s32->u32 x))}
    :long {:status :ok :bytes (signed64-bytes x)}
    :boolean {:status :ok :bytes [(if x 1 0)]}
    :char {:status :ok :bytes (u32-bytes x)}
    :timestamp {:status :ok :bytes (signed64-bytes x)}
    :string (let [bs (str->utf8-bytes x)] {:status :ok :bytes (into (u32-bytes (count bs)) bs)})
    :symbol (let [bs (str->utf8-bytes x)] {:status :ok :bytes (into (u32-bytes (count bs)) bs)})
    :binary {:status :ok :bytes (into (u32-bytes (count x)) x)}))

(defn- encode-array [elem-tag items]
  (if-let [ctor-code (get array-elem-ctor-code elem-tag)]
    (let [encoded (mapv #(encode-array-elem elem-tag %) items)]
      (if-let [err (first (filter #(= :error (:status %)) encoded))]
        err
        (let [body (vec (mapcat :bytes encoded))
              n (count items)
              sz (+ 1 (count body))] ; +1 for the shared element constructor byte
          (if (and (<= n 0xFF) (<= (+ sz 1) 0xFF))
            {:status :ok :bytes (into [array8-code (inc sz) n ctor-code] body)}
            {:status :ok
             :bytes (into (into (into [array32-code] (u32-bytes (+ sz 4))) (u32-bytes n))
                          (into [ctor-code] body))}))))
    {:status :error :reason :amqp/unsupported-array-element-type :tag elem-tag}))

;; ── encode ───────────────────────────────────────────────────────────────────

(defn- encode-uint32*
  "`uint0`/`smalluint`/`uint` — the wide form is always 4 bytes. **Not**
  shared with `ulong`: an earlier version of this function was, and its
  `(>= n 0x100000000)` bound silently capped every `ulong` at 32 bits
  while its `u32-bytes` wide form dropped the top half of anything larger
  that snuck past — found by the randomised primitive-format-code sweep
  (`amqp.types-test`) failing on a `:ulong` above 2^32, not by inspection."
  [zero-code small-code wide-code n]
  (cond
    (not (integer? n)) {:status :error :reason :amqp/not-an-integer}
    (neg? n) {:status :error :reason :amqp/negative-unsigned :value n}
    (>= n 0x100000000) {:status :error :reason :amqp/out-of-range :value n}
    (zero? n) {:status :ok :bytes [zero-code]}
    (<= n 0xFF) {:status :ok :bytes [small-code n]}
    :else {:status :ok :bytes (into [wide-code] (u32-bytes n))}))

(defn- encode-ulong*
  "`ulong0`/`smallulong`/`ulong` — the wide form is 8 bytes (`u64-bytes`),
  bounded to the JS safe-integer range this namespace's docstring already
  documents for `ulong`/`long`/`timestamp` (2^53), not to 2^32."
  [zero-code small-code wide-code n]
  (cond
    (not (integer? n)) {:status :error :reason :amqp/not-an-integer}
    (neg? n) {:status :error :reason :amqp/negative-unsigned :value n}
    (> n 9007199254740992) {:status :error :reason :amqp/out-of-range :value n}
    (zero? n) {:status :ok :bytes [zero-code]}
    (<= n 0xFF) {:status :ok :bytes [small-code n]}
    :else {:status :ok :bytes (into [wide-code] (u64-bytes n))}))

(defn- encode-int* [small-code wide-code n lo hi]
  (cond
    (not (integer? n)) {:status :error :reason :amqp/not-an-integer}
    (or (< n lo) (> n hi)) {:status :error :reason :amqp/out-of-range :value n}
    (<= -128 n 127) {:status :ok :bytes [small-code (u8 n)]}
    :else {:status :ok :bytes (into [wide-code] (u32-bytes (s32->u32 n)))}))

(defn- encode-binary-like [size1-code size4-code bs]
  (let [n (count bs)]
    (cond
      (some #(or (neg? %) (> % 255)) bs) {:status :error :reason :amqp/byte-out-of-range}
      (<= n 0xFF) {:status :ok :bytes (into [size1-code n] bs)}
      (< n 0x100000000) {:status :ok :bytes (into (into [size4-code] (u32-bytes n)) bs)}
      :else {:status :error :reason :amqp/out-of-range :value n})))

(defn- encode-compound [size1-code size4-code items encode-elem]
  (let [encoded (mapv encode-elem items)]
    (if-let [err (first (filter #(= :error (:status %)) encoded))]
      err
      (let [body (vec (mapcat :bytes encoded))
            n (count items) sz (count body)]
        (cond
          (and (zero? n) (= size1-code list8-code)) {:status :ok :bytes [list0-code]}
          (and (<= n 0xFF) (<= (+ sz 1) 0xFF))
          {:status :ok :bytes (into [size1-code (inc sz) n] body)}
          (and (< n 0x100000000) (< sz 0x100000000))
          {:status :ok :bytes (into (into (into [size4-code] (u32-bytes (+ sz 4))) (u32-bytes n)) body)}
          :else {:status :error :reason :amqp/out-of-range})))))

(defn encode-value
  "`[tag & data] -> {:status :ok :bytes […]} | {:status :error :reason …}`.
  See the `describe-value` table below for the full tag vocabulary."
  [v]
  (let [[tag & args] v]
    (case tag
      :null {:status :ok :bytes [null-code]}
      :boolean (let [[b] args] {:status :ok :bytes [(if b true-code false-code)]})
      :ubyte (let [[n] args]
               (if (<= 0 n 255) {:status :ok :bytes [ubyte-code n]}
                   {:status :error :reason :amqp/out-of-range :value n}))
      :byte (let [[n] args]
              (if (<= -128 n 127) {:status :ok :bytes [byte-code (u8 n)]}
                  {:status :error :reason :amqp/out-of-range :value n}))
      :ushort (let [[n] args]
                (if (<= 0 n 0xFFFF) {:status :ok :bytes (into [ushort-code] (u16-bytes n))}
                    {:status :error :reason :amqp/out-of-range :value n}))
      :short (let [[n] args]
               (if (<= -32768 n 32767)
                 {:status :ok :bytes (into [short-code] (u16-bytes (if (neg? n) (+ n 0x10000) n)))}
                 {:status :error :reason :amqp/out-of-range :value n}))
      :uint (let [[n] args] (encode-uint32* uint0-code smalluint-code uint-code n))
      :ulong (let [[n] args] (encode-ulong* ulong0-code smallulong-code ulong-code n))
      :int (let [[n] args] (encode-int* smallint-code int-code n -2147483648 2147483647))
      :long (let [[n] args]
              ;; smalllong/long take the same shape as int/uint above, but
              ;; the wide form is 8 bytes over the arithmetic hi/lo split.
              (cond
                (not (integer? n)) {:status :error :reason :amqp/not-an-integer}
                (<= -128 n 127) {:status :ok :bytes [smalllong-code (u8 n)]}
                (or (< n -9007199254740992) (> n 9007199254740992))
                {:status :error :reason :amqp/out-of-range :value n}
                :else {:status :ok :bytes (into [long-code] (signed64-bytes n))}))
      :float (let [[f] args] {:status :ok :bytes (into [float-code] (u32-bytes (f32->u32 f)))})
      :double (let [[f] args] {:status :ok :bytes (into [double-code] (f64->bytes f))})
      :char (let [[cp] args]
              (if (<= 0 cp 0x10FFFF) {:status :ok :bytes (into [char-code] (u32-bytes cp))}
                  {:status :error :reason :amqp/out-of-range :value cp}))
      :timestamp (let [[ms] args]
                   (cond
                     (or (< ms -9007199254740992) (> ms 9007199254740992))
                     {:status :error :reason :amqp/out-of-range :value ms}
                     :else {:status :ok :bytes (into [timestamp-code] (signed64-bytes ms))}))
      :uuid (let [[bs] args]
              (if (= 16 (count bs)) {:status :ok :bytes (into [uuid-code] bs)}
                  {:status :error :reason :amqp/bad-uuid-length :length (count bs)}))
      :binary (let [[bs] args] (encode-binary-like vbin8-code vbin32-code bs))
      :string (let [[s] args] (encode-binary-like str8-code str32-code (str->utf8-bytes s)))
      :symbol (let [[s] args] (encode-binary-like sym8-code sym32-code (str->utf8-bytes s)))
      :list (let [[items] args] (encode-compound list8-code list32-code items encode-value))
      :map (let [[pairs] args]
             (encode-compound map8-code map32-code
                               (vec (mapcat (fn [[k v]] [k v]) pairs))
                               encode-value))
      :array (let [[elem-tag items] args] (encode-array elem-tag items))
      :described (let [[descriptor value] args
                        de (encode-value descriptor) ve (encode-value value)]
                   (if (= :error (:status de)) de
                       (if (= :error (:status ve)) ve
                           {:status :ok :bytes (into (into [described-code] (:bytes de)) (:bytes ve))})))
      {:status :error :reason :amqp/unknown-tag :tag tag})))

;; ── decode ───────────────────────────────────────────────────────────────────

(defn- decode-binary-like [bs off size-width tag->value]
  (let [sz-r (take-bytes bs off size-width)]
    (if (= :error (:status sz-r)) sz-r
        (let [sz (if (= size-width 1) (nth (:bytes sz-r) 0)
                     (u32-from-bytes (nth (:bytes sz-r) 0) (nth (:bytes sz-r) 1)
                                      (nth (:bytes sz-r) 2) (nth (:bytes sz-r) 3)))
              data-r (take-bytes bs (:next sz-r) sz)]
          (if (= :error (:status data-r)) data-r
              {:status :ok :value (tag->value (:bytes data-r)) :next (:next data-r)})))))

(defn- decode-compound-body [bs off count-of-items decode-elem]
  (loop [i 0 off off acc []]
    (if (= i count-of-items)
      {:status :ok :items acc :next off}
      (let [r (decode-elem bs off)]
        (if (= :error (:status r)) r
            (recur (inc i) (:next r) (conj acc (:value r))))))))

(defn- decode-list-or-map [bs off size-width tag]
  (let [n (* 2 size-width)
        hdr-r (take-bytes bs off n)]
    (if (= :error (:status hdr-r)) hdr-r
        (let [hb (:bytes hdr-r)
              [sz cnt] (if (= size-width 1)
                         [(nth hb 0) (nth hb 1)]
                         [(u32-from-bytes (nth hb 0) (nth hb 1) (nth hb 2) (nth hb 3))
                          (u32-from-bytes (nth hb 4) (nth hb 5) (nth hb 6) (nth hb 7))])
              items-r (decode-compound-body bs (:next hdr-r) cnt decode-value)]
          (if (= :error (:status items-r)) items-r
              ;; `size` covers the count field plus every element's bytes —
              ;; §1.6.7 "size … the number of octets used to encode the
              ;; count and the list elements" — so a decoder that trusted it
              ;; blindly (skip `size` bytes rather than decoding `count`
              ;; values) must land on the same offset this one reached by
              ;; decoding. A mismatch means the encoder lied about size or
              ;; the buffer is corrupt either way, not something to paper
              ;; over by trusting whichever field was more convenient.
              (let [expected-elem-bytes (- sz size-width)
                    actual-elem-bytes (- (:next items-r) (:next hdr-r))]
                (if (not= expected-elem-bytes actual-elem-bytes)
                  {:status :error :reason :amqp/compound-size-mismatch
                   :declared expected-elem-bytes :actual actual-elem-bytes}
                  (if (= tag :map)
                    (if (odd? (count (:items items-r)))
                      {:status :error :reason :amqp/odd-map-entries}
                      {:status :ok
                       :value [:map (mapv vec (partition 2 (:items items-r)))]
                       :next (:next items-r)})
                    {:status :ok :value [:list (:items items-r)] :next (:next items-r)}))))))))

(defn- array-elem-decoder
  "One element decoder for a homogeneous array whose shared constructor is
  `ctor-code`. Every `take-bytes` result is returned as-is on error — the
  earlier version of this used `when`, which turned a real
  `:amqp/buffer-underrun` into a bare `nil` and made `decode-compound-body`
  read `(:status nil)` as `nil` (neither `:ok` nor `:error`), silently
  treating a truncated array as an infinite loop of zero-progress reads.
  Fixed 2026-08-30 before publishing — see the discrimination test."
  [ctor-code]
  (fn [bs off]
    (cond
      (= ctor-code ubyte-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (assoc r :value (nth (:bytes r) 0))))
      (= ctor-code byte-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (assoc r :value (let [b (nth (:bytes r) 0)] (if (>= b 128) (- b 256) b)))))
      (= ctor-code ushort-code) (let [r (take-bytes bs off 2)] (if (= :error (:status r)) r (assoc r :value (u16-from-bytes (nth (:bytes r) 0) (nth (:bytes r) 1)))))
      (= ctor-code uint-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r (assoc r :value (apply u32-from-bytes (:bytes r)))))
      (= ctor-code ulong-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r (assoc r :value (u64-from-bytes (:bytes r)))))
      (= ctor-code int-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r (assoc r :value (u32->s32 (apply u32-from-bytes (:bytes r))))))
      (= ctor-code long-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r (assoc r :value (bytes->signed64 (:bytes r)))))
      (= ctor-code boolean-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (assoc r :value (= 1 (nth (:bytes r) 0)))))
      (= ctor-code char-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r (assoc r :value (apply u32-from-bytes (:bytes r)))))
      (= ctor-code timestamp-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r (assoc r :value (bytes->signed64 (:bytes r)))))
      (= ctor-code str32-code) (decode-binary-like bs off 4 (fn [b] (utf8-bytes->str b)))
      (= ctor-code sym32-code) (decode-binary-like bs off 4 (fn [b] (utf8-bytes->str b)))
      (= ctor-code vbin32-code) (decode-binary-like bs off 4 (fn [b] b))
      ;; unreachable in practice: `decode-array` checks `elem-tag`/this
      ;; decoder for nil before ever calling it, but a bare error map (not a
      ;; thunk) is the right shape if that check is ever loosened.
      :else {:status :error :reason :amqp/unsupported-array-element-type :ctor ctor-code})))

(defn- decode-array [bs off size-width]
  (let [n (* 2 size-width)
        hdr-r (take-bytes bs off n)]
    (if (= :error (:status hdr-r)) hdr-r
        (let [hb (:bytes hdr-r)
              [sz cnt] (if (= size-width 1)
                         [(nth hb 0) (nth hb 1)]
                         [(u32-from-bytes (nth hb 0) (nth hb 1) (nth hb 2) (nth hb 3))
                          (u32-from-bytes (nth hb 4) (nth hb 5) (nth hb 6) (nth hb 7))])
              ctor-r (take-bytes bs (:next hdr-r) 1)]
          (if (= :error (:status ctor-r)) ctor-r
              (let [ctor-code (nth (:bytes ctor-r) 0)
                    elem-tag (case ctor-code
                               (0x50) :ubyte (0x51) :byte (0x60) :ushort (0x70) :uint
                               (0x80) :ulong (0x71) :int (0x81) :long (0x56) :boolean
                               (0x73) :char (0x83) :timestamp
                               (0xB1) :string (0xB3) :symbol (0xB0) :binary
                               nil)
                    dec-elem (array-elem-decoder ctor-code)]
                (if (or (nil? elem-tag) (nil? dec-elem))
                  {:status :error :reason :amqp/unsupported-array-element-type :ctor ctor-code}
                  (let [r (decode-compound-body bs (:next ctor-r) cnt
                                                 (fn [bs off] (dec-elem bs off)))]
                    (if (= :error (:status r)) r
                        ;; size = count-field-width + 1 (the shared element
                        ;; constructor) + every element's bytes.
                        (let [expected (- sz size-width 1)
                              actual (- (:next r) (:next ctor-r))]
                          (if (not= expected actual)
                            {:status :error :reason :amqp/compound-size-mismatch
                             :declared expected :actual actual}
                            {:status :ok :value [:array elem-tag (:items r)] :next (:next r)})))))))))))

(defn decode-value
  "`bs off -> {:status :ok :value [tag …] :next off'} | {:status :error :reason …}`.

  Every branch reads through `take-bytes`, so a frame truncated mid-value
  answers `:amqp/buffer-underrun` at the exact point it ran out, not an
  index exception three functions later."
  [bs off]
  (let [ctor-r (take-bytes bs off 1)]
    (if (= :error (:status ctor-r)) ctor-r
        (let [code (nth (:bytes ctor-r) 0) off (:next ctor-r)]
          (cond
            (= code null-code) {:status :ok :value [:null] :next off}
            (= code true-code) {:status :ok :value [:boolean true] :next off}
            (= code false-code) {:status :ok :value [:boolean false] :next off}
            (= code uint0-code) {:status :ok :value [:uint 0] :next off}
            (= code ulong0-code) {:status :ok :value [:ulong 0] :next off}
            (= code list0-code) {:status :ok :value [:list []] :next off}
            (= code boolean-code)
            (let [r (take-bytes bs off 1)]
              (if (= :error (:status r)) r
                  (let [b (nth (:bytes r) 0)]
                    (if (#{0 1} b) {:status :ok :value [:boolean (= 1 b)] :next (:next r)}
                        {:status :error :reason :amqp/bad-boolean-octet :value b}))))
            (= code ubyte-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r {:status :ok :value [:ubyte (nth (:bytes r) 0)] :next (:next r)}))
            (= code byte-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (let [b (nth (:bytes r) 0)] {:status :ok :value [:byte (if (>= b 128) (- b 256) b)] :next (:next r)})))
            (= code smalluint-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r {:status :ok :value [:uint (nth (:bytes r) 0)] :next (:next r)}))
            (= code smallulong-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r {:status :ok :value [:ulong (nth (:bytes r) 0)] :next (:next r)}))
            (= code smallint-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (let [b (nth (:bytes r) 0)] {:status :ok :value [:int (if (>= b 128) (- b 256) b)] :next (:next r)})))
            (= code smalllong-code) (let [r (take-bytes bs off 1)] (if (= :error (:status r)) r (let [b (nth (:bytes r) 0)] {:status :ok :value [:long (if (>= b 128) (- b 256) b)] :next (:next r)})))
            (= code ushort-code) (let [r (take-bytes bs off 2)] (if (= :error (:status r)) r {:status :ok :value [:ushort (u16-from-bytes (nth (:bytes r) 0) (nth (:bytes r) 1))] :next (:next r)}))
            (= code short-code) (let [r (take-bytes bs off 2)] (if (= :error (:status r)) r (let [u (u16-from-bytes (nth (:bytes r) 0) (nth (:bytes r) 1))] {:status :ok :value [:short (if (>= u 0x8000) (- u 0x10000) u)] :next (:next r)})))
            (= code uint-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r {:status :ok :value [:uint (apply u32-from-bytes (:bytes r))] :next (:next r)}))
            (= code int-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r {:status :ok :value [:int (u32->s32 (apply u32-from-bytes (:bytes r)))] :next (:next r)}))
            (= code float-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r {:status :ok :value [:float (u32->f32 (apply u32-from-bytes (:bytes r)))] :next (:next r)}))
            (= code char-code) (let [r (take-bytes bs off 4)] (if (= :error (:status r)) r {:status :ok :value [:char (apply u32-from-bytes (:bytes r))] :next (:next r)}))
            (= code ulong-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r {:status :ok :value [:ulong (u64-from-bytes (:bytes r))] :next (:next r)}))
            (= code long-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r {:status :ok :value [:long (bytes->signed64 (:bytes r))] :next (:next r)}))
            (= code double-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r {:status :ok :value [:double (bytes->f64 (:bytes r))] :next (:next r)}))
            (= code timestamp-code) (let [r (take-bytes bs off 8)] (if (= :error (:status r)) r {:status :ok :value [:timestamp (bytes->signed64 (:bytes r))] :next (:next r)}))
            (= code uuid-code) (let [r (take-bytes bs off 16)] (if (= :error (:status r)) r {:status :ok :value [:uuid (:bytes r)] :next (:next r)}))
            (= code vbin8-code) (decode-binary-like bs off 1 (fn [b] [:binary b]))
            (= code vbin32-code) (decode-binary-like bs off 4 (fn [b] [:binary b]))
            (= code str8-code) (decode-binary-like bs off 1 (fn [b] [:string (utf8-bytes->str b)]))
            (= code str32-code) (decode-binary-like bs off 4 (fn [b] [:string (utf8-bytes->str b)]))
            (= code sym8-code) (decode-binary-like bs off 1 (fn [b] [:symbol (utf8-bytes->str b)]))
            (= code sym32-code) (decode-binary-like bs off 4 (fn [b] [:symbol (utf8-bytes->str b)]))
            (= code list8-code) (decode-list-or-map bs off 1 :list)
            (= code list32-code) (decode-list-or-map bs off 4 :list)
            (= code map8-code) (decode-list-or-map bs off 1 :map)
            (= code map32-code) (decode-list-or-map bs off 4 :map)
            (= code array8-code) (decode-array bs off 1)
            (= code array32-code) (decode-array bs off 4)
            (= code described-code)
            (let [dr (decode-value bs off)]
              (if (= :error (:status dr)) dr
                  (let [vr (decode-value bs (:next dr))]
                    (if (= :error (:status vr)) vr
                        {:status :ok :value [:described (:value dr) (:value vr)] :next (:next vr)}))))
            :else {:status :error :reason :amqp/unsupported-format-code :code code})))))
