(ns ogg.crc
  "Ogg's CRC-32 (RFC 3533 §6) — a *third* variant of the same polynomial.

   Poly 0x04C11DB7 unreflected, like bzip2's, but with **initial value 0 and no
   final complement**, where bzip2 starts at all-ones and complements the result.
   gzip/ZIP/PNG use the reflected form and disagree with both. Three CRC-32s,
   one polynomial, no interoperability:

   | user | init | reflected | final XOR |
   |---|---|---|---|
   | gzip, ZIP, PNG | 0xFFFFFFFF | yes | 0xFFFFFFFF |
   | bzip2 | 0xFFFFFFFF | no | 0xFFFFFFFF |
   | **Ogg** | **0** | **no** | **none** |

   The checksum covers the whole page including its own header, with the CRC
   field itself zeroed — so a page is checksummed twice on the way out (once to
   compute, once to verify) and the field's position matters.

   All values stay in the unsigned 32-bit domain; ClojureScript's bitwise
   operators return signed int32, so results are normalised through `u32`."
  (:refer-clojure :exclude [update]))

(defn u32 [x] (if (neg? x) (+ x 4294967296) x))
(defn- m32 [x] (u32 (bit-and x 0xffffffff)))

(def ^:private table
  (vec (for [n (range 256)]
         (loop [c (m32 (bit-shift-left n 24)) k 0]
           (if (= k 8)
             c
             (recur (if (>= c 2147483648)
                      (m32 (bit-xor (bit-shift-left c 1) 0x04c11db7))
                      (m32 (bit-shift-left c 1)))
                    (inc k)))))))

(defn update
  "Fold `data` (unsigned bytes) into a running CRC `state`."
  [state data]
  (loop [s (seq data) c state]
    (if-not s
      c
      (recur (next s)
             (m32 (bit-xor (bit-shift-left c 8)
                           (nth table (bit-and (bit-xor (unsigned-bit-shift-right c 24)
                                                        (bit-and (first s) 0xff))
                                               0xff))))))))

(defn crc32
  "Ogg's CRC-32 of `data` → unsigned 32-bit integer. No initial value, no final
   complement."
  [data]
  (update 0 data))
