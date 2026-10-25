(ns flac.crc
  "The two CRCs a FLAC frame carries.

   CRC-8 (poly 0x07, init 0) covers the frame header up to but not including the
   CRC byte itself. CRC-16 (poly 0x8005, init 0) covers the *entire* frame,
   header and subframes both, up to but not including its own two bytes.

   The decoder in this repo reads past them rather than checking them, but the
   encoder must get them right: `flac -t` verifies both, and a wrong CRC is the
   difference between a file the reference accepts and one it rejects with no
   other symptom."
  (:refer-clojure :exclude [update]))

(def ^:private table-8
  (vec (for [n (range 256)]
         (loop [c n k 0]
           (if (= k 8)
             c
             (recur (bit-and (if (>= c 128) (bit-xor (* 2 c) 0x07) (* 2 c)) 0xff)
                    (inc k)))))))

(def ^:private table-16
  (vec (for [n (range 256)]
         (loop [c (* 256 n) k 0]
           (if (= k 8)
             c
             (recur (mod (if (>= c 32768) (bit-xor (* 2 c) 0x8005) (* 2 c)) 65536)
                    (inc k)))))))

(defn crc8
  "CRC-8 of `data` (unsigned bytes)."
  [data]
  (reduce (fn [c b] (nth table-8 (bit-xor c (bit-and b 0xff)))) 0 data))

(defn crc16
  "CRC-16 of `data` (unsigned bytes)."
  [data]
  (reduce (fn [c b]
            (bit-xor (mod (* 256 c) 65536)
                     (nth table-16 (bit-and (bit-xor (quot c 256) (bit-and b 0xff)) 0xff))))
          0 data))
