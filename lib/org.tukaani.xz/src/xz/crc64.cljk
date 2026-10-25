(ns xz.crc64
  "CRC-64/XZ (ECMA-182 polynomial, reflected: 0xC96C5795D7870F42) — the *default*
   integrity check of the .xz format, so a reader that skips it is not reading
   .xz.

   64-bit arithmetic is carried as two 32-bit halves rather than as a Clojure
   long, because ClojureScript has no 64-bit integer and `Number` loses the low
   bits above 2^53. Values are `[hi lo]` pairs of unsigned 32-bit integers."
  (:refer-clojure :exclude [bytes]))

(defn- u32 [x] (if (neg? x) (+ x 4294967296) x))

(def ^:private poly-hi 0xc96c5795)
(def ^:private poly-lo 0xd7870f42)

(def ^:private table
  (vec
   (for [n (range 256)]
     (loop [k 0 hi 0 lo n]
       (if (= k 8)
         [hi lo]
         ;; shift right one bit across the pair, then xor the polynomial when the
         ;; bit shifted out was set
         (let [odd? (odd? lo)
               lo'  (u32 (bit-or (unsigned-bit-shift-right lo 1)
                                 (bit-shift-left (bit-and hi 1) 31)))
               hi'  (unsigned-bit-shift-right hi 1)]
           (recur (inc k)
                  (if odd? (u32 (bit-xor hi' poly-hi)) hi')
                  (if odd? (u32 (bit-xor lo' poly-lo)) lo'))))))))

(defn init [] [0xffffffff 0xffffffff])

(defn update-crc
  "Fold `data` into a running `[hi lo]` state."
  [[hi0 lo0] data]
  (loop [s (seq data) hi hi0 lo lo0]
    (if-not s
      [hi lo]
      (let [idx      (bit-and (bit-xor lo (bit-and (first s) 0xff)) 0xff)
            [thi tlo] (nth table idx)
            slo      (u32 (bit-or (unsigned-bit-shift-right lo 8)
                                  (bit-shift-left (bit-and hi 0xff) 24)))
            shi      (unsigned-bit-shift-right hi 8)]
        (recur (next s) (u32 (bit-xor shi thi)) (u32 (bit-xor slo tlo)))))))

(defn final
  "Finalise a running state into the transmitted `[hi lo]` value."
  [[hi lo]]
  [(u32 (bit-xor hi 0xffffffff)) (u32 (bit-xor lo 0xffffffff))])

(defn crc64
  "CRC-64/XZ of `data` → `[hi lo]`."
  [data]
  (final (update-crc (init) data)))

(defn ->le-bytes
  "The 8 little-endian bytes .xz stores a CRC-64 as."
  [[hi lo]]
  [(bit-and lo 0xff)
   (bit-and (unsigned-bit-shift-right lo 8) 0xff)
   (bit-and (unsigned-bit-shift-right lo 16) 0xff)
   (bit-and (unsigned-bit-shift-right lo 24) 0xff)
   (bit-and hi 0xff)
   (bit-and (unsigned-bit-shift-right hi 8) 0xff)
   (bit-and (unsigned-bit-shift-right hi 16) 0xff)
   (bit-and (unsigned-bit-shift-right hi 24) 0xff)])
