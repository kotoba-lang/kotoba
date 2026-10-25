(ns bzip2.core
  "bzip2 in portable `.cljc`, both directions.

   ```clojure
   (bzip2.core/compress bytes)              ; => .bz2 stream, level 9
   (bzip2.core/compress bytes {:level 1})
   (bzip2.core/decompress bz2-bytes)
   (bzip2.core/bzip2? bytes)                ; signature sniff, no parsing
   ```

   Bytes in and out are vectors of unsigned 0-255 integers, the convention every
   codec repo in this workspace shares — no byte arrays, no typed arrays in the
   API, so the same calls work on the JVM and on ClojureScript.

   Zero dependencies. bzip2 needs no other codec: its entropy stage is its own
   multi-table Huffman and its integrity check is its own CRC-32 variant."
  (:require [bzip2.decode :as decode]
            [bzip2.encode :as encode]))

(defn bzip2?
  "True when `data` starts with the `BZh<1-9>` signature. A sniff, not a
   validation — the stream can still be truncated or corrupt."
  [data]
  (let [v (vec (take 4 data))]
    (and (= 4 (count v))
         (= 0x42 (nth v 0)) (= 0x5a (nth v 1)) (= 0x68 (nth v 2))
         (>= (nth v 3) 0x31) (<= (nth v 3) 0x39))))

(def compress
  "Compress unsigned bytes into a bzip2 stream. See `bzip2.encode/compress`."
  encode/compress)

(def decompress
  "Decompress a bzip2 stream into unsigned bytes. See `bzip2.decode/decompress`."
  decode/decompress)
