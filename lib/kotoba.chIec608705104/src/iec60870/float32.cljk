(ns iec60870.float32
  "IEEE 754 binary32 (single precision) values as they go on the wire for
  M_ME_TF_1 (type 36, \"measured value, short floating point\"): 4
  little-endian bytes.

  The float↔bit-pattern *reinterpretation* (not the wire byte assembly) is
  the one place this repo leans on a host intrinsic rather than a
  from-scratch bit decomposition — `Float/floatToIntBits`/`intBitsToFloat`
  on the JVM, a scratch `DataView` on JS — the same kind of pragmatic
  platform call `org-modbus`'s `rtu.cljc` makes for hex formatting
  (`Integer/toString` vs `.toString`). What *is* built from
  `bit-and`/`bit-shift-left`/`bit-shift-right` here, on both platforms
  alike, is splitting that 32-bit pattern into 4 little-endian wire bytes
  and reassembling it — the actual codec responsibility of this namespace."
  )

#?(:clj (defn- bits-of [f] (Float/floatToIntBits (float f))))
#?(:cljs
   (defn- bits-of [f]
     (let [view (js/DataView. (js/ArrayBuffer. 4))]
       (.setFloat32 view 0 f false) ;; false = big-endian, matching floatToIntBits' bit-pattern convention
       (.getUint32 view 0 false))))

#?(:clj (defn- float-of [u] (Float/intBitsToFloat (unchecked-int u))))
#?(:cljs
   (defn- float-of [u]
     (let [view (js/DataView. (js/ArrayBuffer. 4))]
       ;; setUint32 does ToUint32 internally, which correctly reinterprets a
       ;; JS number that overflowed into a negative int32 during bit-or
       ;; assembly (see read-float32-le) back to its unsigned bit pattern.
       (.setUint32 view 0 u false)
       (.getFloat32 view 0 false))))

(defn- byte-at
  "One byte of `v`'s two's-complement bit pattern, via an arithmetic
  (sign-preserving) right shift — see `dnp3.objects/byte-at` for why this
  formula is portable across the JVM's 64-bit longs and JS's 32-bit ints
  without a reader-conditional branch: the low 32 bits of a two's-complement
  pattern are identical regardless of how many sign-extension bits sit
  above them."
  [v shift]
  (bit-and (bit-shift-right v shift) 0xFF))

(defn write-float32-le [f]
  (let [u (bits-of f)]
    [(byte-at u 0) (byte-at u 8) (byte-at u 16) (byte-at u 24)]))

(defn read-float32-le [bs i]
  (let [u (bit-or (nth bs i)
                   (bit-shift-left (nth bs (+ i 1)) 8)
                   (bit-shift-left (nth bs (+ i 2)) 16)
                   (bit-shift-left (nth bs (+ i 3)) 24))]
    (float-of u)))
