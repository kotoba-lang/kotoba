(ns dicom.numeric
  "Signed-integer and IEEE-754 float decode/encode for the binary VRs
  (`SS` `SL` `FL` `FD`, and the unsigned `US` `UL` this pairs with).

  **The signed conversion is deliberately *not* `(bit-or u32 0)`.** That
  idiom looks like the standard \"force ToInt32\" trick — and it *is*
  correct on ClojureScript, where JavaScript's bitwise operators coerce
  their operand through ToInt32 and `(bit-or 0xFFFFFFFF 0)` really does
  come out `-1`. But on the JVM, `bit-or` operates on 64-bit longs and
  does no such truncation: `(bit-or 0xFFFFFFFF 0)` on the JVM is the
  *positive* number 4294967295, not -1. The same expression is right on
  one runtime and wrong on the other, silently. `u32->i32`/`u16->i16`
  below do the two's-complement conversion with plain arithmetic
  (`if v >= half-range then v - full-range else v`) instead, which gives
  the same answer on both runtimes because it never depends on a native
  integer width.

  Floats go through `java.nio.ByteBuffer`/`js/DataView` — laying the raw
  wire bytes into a byte buffer and asking the platform to reinterpret
  them as IEEE-754, rather than hand-rolling exponent/mantissa bit
  twiddling for a case where both runtimes already have a correct,
  endian-aware primitive for exactly this. This is memory
  reinterpretation, not I/O — no socket, file, or thread is involved.")

(defn u16->i16
  "Two's-complement signed interpretation of a 16-bit unsigned value."
  [u] (if (>= u 0x8000) (- u 0x10000) u))

(defn i16->u16
  "Wire encoding of a signed 16-bit value as its unsigned bit pattern."
  [i] (if (neg? i) (+ i 0x10000) i))

(defn u32->i32
  "Two's-complement signed interpretation of a 32-bit unsigned value."
  [u] (if (>= u 0x80000000) (- u 0x100000000) u))

(defn i32->u32
  "Wire encoding of a signed 32-bit value as its unsigned bit pattern."
  [i] (if (neg? i) (+ i 0x100000000) i))

(defn bytes->f32
  "4 raw wire bytes -> IEEE-754 single-precision float, per `order`."
  [bs order]
  #?(:cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
             (dotimes [i 4] (.setUint8 dv i (bit-and (nth bs i) 0xFF)))
             (.getFloat32 dv 0 (= order :little)))
     :clj (let [bb (java.nio.ByteBuffer/wrap
                     (byte-array (map unchecked-byte bs)))]
            (.order bb (if (= order :little)
                         java.nio.ByteOrder/LITTLE_ENDIAN
                         java.nio.ByteOrder/BIG_ENDIAN))
            (.getFloat bb 0))))

(defn f32->bytes
  "IEEE-754 single-precision `v` -> 4 wire bytes, per `order`."
  [v order]
  #?(:cljs (let [buf (js/ArrayBuffer. 4) dv (js/DataView. buf)]
             (.setFloat32 dv 0 v (= order :little))
             (vec (for [i (range 4)] (.getUint8 dv i))))
     :clj (let [bb (java.nio.ByteBuffer/allocate 4)]
            (.order bb (if (= order :little)
                         java.nio.ByteOrder/LITTLE_ENDIAN
                         java.nio.ByteOrder/BIG_ENDIAN))
            (.putFloat bb (float v))
            (vec (map #(bit-and % 0xFF) (.array bb))))))

(defn bytes->f64
  "8 raw wire bytes -> IEEE-754 double-precision float, per `order`."
  [bs order]
  #?(:cljs (let [buf (js/ArrayBuffer. 8) dv (js/DataView. buf)]
             (dotimes [i 8] (.setUint8 dv i (bit-and (nth bs i) 0xFF)))
             (.getFloat64 dv 0 (= order :little)))
     :clj (let [bb (java.nio.ByteBuffer/wrap
                     (byte-array (map unchecked-byte bs)))]
            (.order bb (if (= order :little)
                         java.nio.ByteOrder/LITTLE_ENDIAN
                         java.nio.ByteOrder/BIG_ENDIAN))
            (.getDouble bb 0))))

(defn f64->bytes
  "IEEE-754 double-precision `v` -> 8 wire bytes, per `order`."
  [v order]
  #?(:cljs (let [buf (js/ArrayBuffer. 8) dv (js/DataView. buf)]
             (.setFloat64 dv 0 v (= order :little))
             (vec (for [i (range 8)] (.getUint8 dv i))))
     :clj (let [bb (java.nio.ByteBuffer/allocate 8)]
            (.order bb (if (= order :little)
                         java.nio.ByteOrder/LITTLE_ENDIAN
                         java.nio.ByteOrder/BIG_ENDIAN))
            (.putDouble bb (double v))
            (vec (map #(bit-and % 0xFF) (.array bb))))))
