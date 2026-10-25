(ns kotoba.ros.cdr
  "CDR (Common Data Representation) primitives -- the real DDS-XTypes wire
  format ROS 2 uses to serialize every message, alignment-aware,
  little-endian (PLAIN_CDR little-endian, the representation every rosbag2
  SQLite blob and every DDS-RTPS payload byte on the wire actually carries).

  This is deliberately the lowest layer of `org-ros`: `kotoba.ros.msgs`
  builds ROS 2 message shapes on top of exactly these functions, so getting
  alignment right here once means every message shape gets it right for
  free.

  A byte buffer is a plain vector of ints 0-255, built incrementally -- NOT
  `java.nio.ByteBuffer` (JVM-only) and not a mutable byte-array. That keeps
  this namespace true `.cljc`: identical semantics on JVM and ClojureScript,
  no host buffer-capacity limit, and trivial to inspect/diff in a REPL or a
  test assertion (`(= [0 1 0 0] ...)` instead of decoding a byte-array).

  ## Alignment

  CDR requires every primitive of natural size N (1/2/4/8 bytes) to start at
  a byte offset that is a multiple of N, *relative to the start of the
  encapsulated payload* -- not relative to the start of whatever buffer or
  packet the payload happens to live inside. Padding bytes are zero. A
  1-byte type never needs padding. A `string`'s 4-byte length prefix is
  aligned like a uint32, but the UTF-8 body and its null terminator that
  follow are not further aligned (they are 1-byte units).

  ## Encapsulation

  Every serialized ROS 2 message begins with a 4-byte encapsulation header:
  `[0x00 0x01 0x00 0x00]` -- representation-identifier `0x0001`
  (PLAIN_CDR, little-endian) followed by 2 bytes of representation-options
  (unused, always zero). This is the exact 4-byte prefix visible at the
  start of every message blob stored in a rosbag2 SQLite database and is
  documented as part of the DDS-XTypes / OMG CDR encapsulation scheme.
  `encapsulate`/`de-encapsulate` write/strip this header and reset the
  alignment origin to right after it, so alignment inside a message is
  always measured from the header's end, not from wherever the header
  itself started.

  ## Host-specific bit conversion

  IEEE-754 float<->bits and 64-bit two's-complement byte decomposition are
  the only places this namespace cannot stay platform-neutral Clojure: JVM
  has `Float/floatToIntBits`/`Double/doubleToLongBits`, ClojureScript has no
  such primitive-bits reflection and reaches for `js/DataView` instead; JVM
  has real 64-bit `long` bit ops, ClojureScript's bitwise operators coerce
  their operand to Int32 first and silently truncate anything outside
  +-2^31. Both are handled with the narrowest possible `#?(:clj ... :cljs
  ...)` reader-conditional, isolated to a single private helper each --
  the same pattern this codebase's other wire-format library
  (`dag-cbor.core`) uses for its own host-specific byte extraction."
  (:refer-clojure :exclude [read-string]))

;; ---------------------------------------------------------------------------
;; Encapsulation header
;; ---------------------------------------------------------------------------

(def encapsulation-header
  "The 4-byte PLAIN_CDR little-endian representation-identifier +
  representation-options prefix that begins every serialized ROS 2 /
  DDS-XTypes message: `0x00 0x01` = PLAIN_CDR, little-endian;
  `0x00 0x00` = representation-options, unused."
  [0x00 0x01 0x00 0x00])

;; ---------------------------------------------------------------------------
;; Shared byte<->integer conversion (used by both writer and reader)
;; ---------------------------------------------------------------------------

(defn- byte-at
  "The byte at bit-position `s` (a multiple of 8, 0..56) of two's-complement
  integer `n`, as an unsigned 0-255 int. `:clj` bit-shifts a real 64-bit
  `long` (via `unchecked-long` so an in-range or out-of-range/BigInt `n`
  alike reduces to its low 64 bits first, matching two's-complement
  wraparound) -- exact for every `s` this library uses. `:cljs` cannot use
  `bit-and`/`bit-shift-*` for `s` >= 32: JS's bitwise operators coerce their
  operand to Int32 first, silently truncating anything outside +-2^31
  *before* the shift even happens.

  The `:cljs` branch used to do the arithmetic on plain JS numbers, with this
  docstring explaining that division and modulo stay exact up to 2^53 and that
  this is ample for the library's range. It was -- but the line below it
  began by adding 2^64 to any NEGATIVE `n`, which leaves that range
  immediately. Measured 2026-08-25 under nbb, before this change:

    (roundtrip write-i16 read-i16 -30000)  =>  -30720
    (roundtrip write-i32 read-i32 -2000000000)  =>  -1999998976

  -30000 + 2^64 is 18446744073709521616, and doubles are spaced 2048 apart
  there, so the low bytes were gone before the first division. A sixteen-bit
  round trip, in a wire-format codec, on the runtime this file's extension
  claims. The precondition the docstring stated was violated by the
  expression underneath it.

  `js/BigInt` has exact integer arithmetic and a two's-complement primitive
  (`BigInt.asUintN`), so the `:cljs` branch now does what the `:clj` branch
  does rather than an approximation of it."
  [n s]
  #?(:clj (bit-and (unsigned-bit-shift-right (unchecked-long n) s) 0xff)
     :cljs (let [;; `n` arrives as a plain number from the integer writers and
                 ;; as a bigint from `write-f64`, which gets its bits from
                 ;; `DataView.getBigUint64`. Accept both rather than making the
                 ;; float path convert down to a double and back.
                 ;; A JS bigint is a primitive, so `instance?` is false for it;
                 ;; property access boxes it, which is why the constructor check
                 ;; works. Same idiom as `kotoba.kir.cljs-i64/bigint-value?`.
                 bigint? (try (= (.-constructor n) js/BigInt)
                              (catch :default _ false))
                 u (js/BigInt.asUintN
                    64 (if bigint? n (js/BigInt (js/Math.trunc n))))
                 ;; 2^s as a bigint. Not `(bit-shift-left 1 s)`, and not
                 ;; `BigInt(Math.pow(2, s))` -- the first wraps its shift
                 ;; count at 32, and `s` reaches 56 here.
                 divisor (loop [i 0 v (js/BigInt 1)]
                           (if (>= i s) v (recur (inc i) (* v (js/BigInt 2)))))]
             (js/Number (js/BigInt.asUintN 8 (/ u divisor))))))

(defn- bytes->uint
  "Little-endian byte seq `bs` -> unsigned integer, via arithmetic (NOT bit
  ops). `:clj` uses `+'`/`*'` (Clojure's auto-promoting arithmetic), exact
  for every size this library uses -- including a full unsigned 64-bit
  value -- because they transparently promote to BigInt on overflow instead
  of throwing (plain `+`/`*` throw `ArithmeticException` on long overflow)
  or wrapping. ClojureScript has no arbitrary-precision integer type and no
  `+'`/`*'` at all, so `:cljs` uses plain `+`/`*` (JS double arithmetic),
  exact up to 2^53 -- the same documented ceiling as `byte-at` above."
  [bs]
  #?(:clj (reduce (fn [acc b] (+' (*' acc 256) b)) 0 (reverse bs))
     :cljs (reduce (fn [acc b] (+ (* acc 256) b)) 0 (reverse bs))))

(defn- to-signed
  "Reinterpret unsigned integer `uv` (magnitude in [0, full)) as its
  two's-complement signed equivalent, given `half` = 2^(bits-1) and `full`
  = 2^bits."
  [uv half full]
  (if (>= uv half) (- uv full) uv))

(def ^:private half64 #?(:clj 9223372036854775808N :cljs (js/Math.pow 2 63)))
(def ^:private full64 #?(:clj 18446744073709551616N :cljs (js/Math.pow 2 64)))

;; ---------------------------------------------------------------------------
;; UTF-8 <-> byte-vector (the only other host-specific plumbing)
;; ---------------------------------------------------------------------------

(defn- utf8-bytes
  "UTF-8 bytes of string `s` as a plain vector of ints (sign-normalized to
  0-255 on `:clj`, where `String/getBytes` returns signed Java bytes)."
  [s]
  #?(:clj (mapv #(bit-and (long %) 0xff) (.getBytes ^String s "UTF-8"))
     :cljs (vec (.encode (js/TextEncoder.) s))))

(defn- bytes->utf8-str
  "Inverse of `utf8-bytes`: a seq of 0-255 ints -> a UTF-8 string."
  [bs]
  #?(:clj (String. (byte-array (map unchecked-byte bs)) "UTF-8")
     :cljs (.decode (js/TextDecoder.) (js/Uint8Array.from (clj->js (vec bs))))))

;; ---------------------------------------------------------------------------
;; Writer
;; ---------------------------------------------------------------------------

(defn writer
  "A fresh CDR writer: `{:bytes [] :origin 0}`. `:bytes` is the plain
  0-255-int vector built up so far. `:origin` is the byte offset (into
  `:bytes`) alignment is measured from -- `encapsulate` moves it to just
  after the 4-byte header; until then it defaults to 0 (the start of the
  buffer), which is the correct alignment origin for writing CDR primitives
  standalone, without a message-level encapsulation header."
  [] {:bytes [] :origin 0})

(defn- rel-pos [w] (- (count (:bytes w)) (:origin w)))

(defn- pad-to
  "Zero-pad `w` until its origin-relative position is a multiple of `n`.
  `n` <= 1 never needs padding."
  [w n]
  (if (<= n 1)
    w
    (let [r (mod (rel-pos w) n)]
      (if (zero? r) w (update w :bytes into (repeat (- n r) 0))))))

(defn- push [w bs] (update w :bytes into bs))

(defn write-u8 [w v] (push w [(bit-and (long v) 0xff)]))
(def write-i8 write-u8)

(defn write-u16 [w v]
  (let [w (pad-to w 2)] (push w [(byte-at v 0) (byte-at v 8)])))
(def write-i16 write-u16)

(defn write-u32 [w v]
  (let [w (pad-to w 4)]
    (push w [(byte-at v 0) (byte-at v 8) (byte-at v 16) (byte-at v 24)])))
(def write-i32 write-u32)

(defn write-u64 [w v]
  (let [w (pad-to w 8)]
    (push w (mapv (partial byte-at v) [0 8 16 24 32 40 48 56]))))
(def write-i64 write-u64)

(defn write-f32
  "IEEE-754 binary32. The float<->bits conversion is inherently
  host-specific (see namespace docstring); once we have the 32-bit pattern
  as an integer, `write-u32` does the ordinary little-endian byte-splitting
  + alignment work identically on both platforms."
  [w v]
  (let [bits #?(:clj (Float/floatToIntBits (float v))
                :cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
                        (.setFloat32 dv 0 v false)
                        (.getUint32 dv 0 false)))]
    (write-u32 w bits)))

(defn write-f64
  "IEEE-754 binary64. See `write-f32`; same reasoning, doubled width."
  [w v]
  (let [bits #?(:clj (Double/doubleToLongBits (double v))
                :cljs (let [buf (js/ArrayBuffer. 8) dv (js/DataView. buf)]
                        (.setFloat64 dv 0 v false)
                        (.getBigUint64 dv 0 false)))]
    (write-u64 w bits)))

(defn write-bytes
  "Append a literal byte sequence `bs` (each coerced to 0-255) with NO
  alignment -- for raw payloads whose framing is handled by the caller
  (e.g. the encapsulation header itself, or already-length-prefixed data)."
  [w bs]
  (push w (mapv #(bit-and (long %) 0xff) bs)))

(defn write-string
  "CDR string: a uint32 byte-length *including* the null terminator
  (aligned to 4, per `write-u32`), then the UTF-8 bytes, then a single
  0x00 terminator. Neither the UTF-8 bytes nor the terminator need further
  alignment (they are 1-byte units)."
  [w s]
  (let [utf8 (utf8-bytes (str s))]
    (-> w
        (write-u32 (inc (count utf8)))
        (write-bytes utf8)
        (write-u8 0))))

(defn encapsulate
  "Write the 4-byte PLAIN_CDR little-endian encapsulation header, then reset
  the alignment origin to right after it. Call this once, on a fresh
  writer, before writing a top-level ROS 2 message body."
  [w]
  (let [w (write-bytes w encapsulation-header)]
    (assoc w :origin (count (:bytes w)))))

;; ---------------------------------------------------------------------------
;; Reader
;; ---------------------------------------------------------------------------

(defn reader
  "A fresh CDR reader over `bs` (a plain seq/vector of 0-255 ints):
  `{:bytes (vec bs) :pos 0 :origin 0}`. Every `read-*` function takes a
  reader and returns `[value reader']` -- the reader threaded through
  exactly like the writer is."
  [bs] {:bytes (vec bs) :pos 0 :origin 0})

(defn- rel-rpos [r] (- (:pos r) (:origin r)))

(defn- rpad
  [r n]
  (if (<= n 1)
    r
    (let [m (mod (rel-rpos r) n)]
      (if (zero? m) r (update r :pos + (- n m))))))

(defn- take-n [r n]
  (let [bs (subvec (:bytes r) (:pos r) (+ (:pos r) n))]
    [bs (update r :pos + n)]))

(defn read-u8 [r]
  (let [[bs r'] (take-n r 1)] [(first bs) r']))

(defn read-i8 [r]
  (let [[v r'] (read-u8 r)] [(if (> v 127) (- v 256) v) r']))

(defn read-u16 [r]
  (let [r (rpad r 2) [bs r'] (take-n r 2)] [(bytes->uint bs) r']))

(defn read-i16 [r]
  (let [[uv r'] (read-u16 r)] [(to-signed uv 32768 65536) r']))

(defn read-u32 [r]
  (let [r (rpad r 4) [bs r'] (take-n r 4)] [(bytes->uint bs) r']))

(defn read-i32 [r]
  (let [[uv r'] (read-u32 r)] [(to-signed uv 2147483648 4294967296) r']))

(defn read-u64 [r]
  (let [r (rpad r 8) [bs r'] (take-n r 8)] [(bytes->uint bs) r']))

(defn read-i64
  "Signed 64-bit. Inverse of `write-i64`.

  The `:cljs` branch does not go through `read-u64`. Signing via
  `to-signed` means forming the UNSIGNED value first, and for any negative
  i64 that is near 2^64 -- past 2^53, where a ClojureScript number stops being
  exact -- so the subtraction that follows returns a rounded answer. Measured
  2026-08-25: -9007199254740991, itself comfortably inside the exact range,
  came back as -9007199254740992, because its unsigned form on the wire is
  18446744064702352625.

  `BigInt.asIntN` does the two's-complement interpretation without ever
  materialising that number as a double."
  [r]
  #?(:clj (let [[uv r'] (read-u64 r)] [(to-signed uv half64 full64) r'])
     :cljs (let [r (rpad r 8)
                 [bs r'] (take-n r 8)
                 u (reduce (fn [acc b] (+ (* acc (js/BigInt 256)) (js/BigInt b)))
                           (js/BigInt 0) (reverse bs))]
             [(js/Number (js/BigInt.asIntN 64 u)) r'])))

(defn read-f32 [r]
  (let [[bits r'] (read-u32 r)]
    [#?(:clj (Float/intBitsToFloat (unchecked-int bits))
        :cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
                (.setUint32 dv 0 bits false)
                (.getFloat32 dv 0 false)))
     r']))

(defn read-f64
  "IEEE-754 binary64. Inverse of `write-f64`.

  The `:cljs` branch takes the BYTES rather than the integer `read-u64`
  builds. That integer is assembled by `bytes->uint`, which on this runtime is
  plain double arithmetic and therefore exact only to 2^53 -- and a double's
  bit pattern routinely needs all 64. Measured 2026-08-25 before this change,
  3.14159265358979 round-tripped to 3.1415926535896688, and every message
  carrying an orientation or a velocity was wrong in the last few digits.

  There is no integer in this path now, so there is nothing to round."
  [r]
  #?(:clj (let [[bits r'] (read-u64 r)]
            [(Double/longBitsToDouble (unchecked-long bits)) r'])
     :cljs (let [r (rpad r 8)
                 [bs r'] (take-n r 8)
                 buf (js/ArrayBuffer. 8)
                 dv (js/DataView. buf)]
             ;; `write-f64` writes little-endian bytes via `byte-at`, so read
             ;; them back in the same order.
             (dotimes [i 8] (.setUint8 dv i (nth bs i)))
             [(.getFloat64 dv 0 true) r'])))

(defn read-bytes
  "Read `n` raw bytes with NO alignment. Inverse of `write-bytes`."
  [r n]
  (take-n r n))

(defn read-string
  "Inverse of `write-string`: reads the uint32 length (including the null
  terminator), the UTF-8 body, and the terminator, returning `[string
  reader']` (the terminator byte is consumed but not included in the
  returned string)."
  [r]
  (let [[len r] (read-u32 r)
        [bs r] (take-n r len)]
    [(bytes->utf8-str (subvec bs 0 (dec len))) r]))

(defn de-encapsulate
  "Read and validate the 4-byte encapsulation header, then reset the
  alignment origin to right after it -- the reader-side mirror of
  `encapsulate`. Throws `ex-info` if the header is not the PLAIN_CDR
  little-endian one this library writes (big-endian CDR / PL_CDR / XCDR2
  payloads are out of scope for this version)."
  [r]
  (let [[hdr r'] (take-n r 4)]
    (when (not= hdr encapsulation-header)
      (throw (ex-info "kotoba.ros.cdr: unsupported encapsulation header"
                       {:expected encapsulation-header :actual hdr})))
    (assoc r' :origin (:pos r'))))
