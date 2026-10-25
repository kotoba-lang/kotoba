(ns bzip2.crc
  "bzip2's CRC-32 — **not** the CRC-32 in gzip, ZIP or PNG.

   Same polynomial (0x04C11DB7) but the *unreflected* form: bits enter at the
   top of the register, the table is built by shifting left, and nothing is
   bit-reversed. Feed a byte string to this and to `deflate.checksum/crc32` and
   the two disagree on everything. Getting this wrong produces a stream that is
   structurally perfect and fails integrity checking on the last four bytes,
   which is why it lives in its own namespace with this docstring.

   A bzip2 stream also carries a *combined* CRC over its blocks, folded with a
   rotate-left rather than a plain XOR (`combine`).

   All values stay in the unsigned 32-bit domain: ClojureScript's bitwise
   operators return signed int32, so every result is normalised through `u32`."
  (:refer-clojure :exclude [update]))

(defn u32
  "Normalise a bitwise result into the unsigned 32-bit domain."
  [x]
  (if (neg? x) (+ x 4294967296) x))

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

(defn init [] 0xffffffff)

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

(defn final
  "Finish a running CRC — bzip2 stores the ones' complement."
  [state]
  (m32 (bit-not state)))

(defn crc32
  "bzip2's CRC-32 of `data` → unsigned 32-bit integer."
  [data]
  (final (update (init) data)))

(defn combine
  "Fold a block CRC into the stream's combined CRC: rotate the accumulator left
   one bit, then XOR. Not a plain XOR — two blocks with the same CRC in a
   different order must not collide."
  [combined block-crc]
  (m32 (bit-xor (m32 (bit-or (bit-shift-left combined 1)
                             (unsigned-bit-shift-right combined 31)))
                block-crc)))
