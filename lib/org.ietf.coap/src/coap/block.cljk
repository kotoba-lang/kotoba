(ns coap.block
  "RFC 7959 Block-Wise Transfers — the Block1/Block2 option VALUE encoding
  (§2.1, Figure 5). The option numbers themselves (Block1 = 27, Block2 =
  23) are ordinary CoAP options and go through `coap.message`'s Option
  Number/Delta/Length machinery unchanged; what this namespace owns is the
  three fields packed inside that option's value bytes:

  ```
    0
    0 1 2 3 4 5 6 7
   +-+-+-+-+-+-+-+-+
   |  NUM  |M| SZX |
   +-+-+-+-+-+-+-+-+
   for the last byte, with variable-length NUM above it
  ```

  Read as one big-endian integer, the low 3 bits are SZX (block size,
  §2.2's `2^(SZX+4)` bytes — 16 through 1024), the next bit is M (More: 1
  if further blocks follow this one), and everything above that is NUM
  (the 0-indexed block number). The whole field is 0-3 bytes on the wire —
  0 bytes exactly when NUM=0, M=0, SZX=0 (`coap.message/encode-options`
  handles that: a zero-length option value is legal and simply means every
  field defaulted to zero), 1-3 bytes otherwise depending on how large NUM
  is.

  The classic way to get this wrong is treating NUM, M and SZX as three
  separately-encoded fields with their own byte boundaries — they are not;
  they share one bit-packed integer, and only the WHOLE integer's byte
  LENGTH is variable.")

(def size-exponents
  "SZX -> block size in bytes, RFC 7959 §2.2: `2^(SZX+4)`. SZX 0..6 only —
  7 is reserved (§2.2: 'the value 7 ... is reserved, i.e. MUST NOT be
  sent')."
  (into {} (for [szx (range 7)] [szx (bit-shift-left 1 (+ szx 4))])))

(defn encode
  "`{:num u20 :more? bool :szx 0..6}` -> `{:status :ok :bytes [...]}`, 0-3
  bytes, big-endian, minimal length."
  [{:keys [num more? szx]}]
  (cond
    (not (<= 0 szx 6)) {:status :error :reason :reserved-szx :szx szx}
    (not (<= 0 num 0xFFFFF)) {:status :error :reason :block-number-too-large :num num}
    :else
    (let [v (bit-or (bit-shift-left num 4) (if more? 0x08 0) szx)]
      {:status :ok
       :bytes (cond
                (zero? v) []
                (< v 0x100) [v]
                (< v 0x10000) [(bit-and (unsigned-bit-shift-right v 8) 0xFF) (bit-and v 0xFF)]
                :else [(bit-and (unsigned-bit-shift-right v 16) 0xFF)
                      (bit-and (unsigned-bit-shift-right v 8) 0xFF)
                      (bit-and v 0xFF)])})))

(defn decode
  "`bytes` (an option value, 0-3 bytes) -> `{:status :ok :num n :more? bool
  :szx s :size bytes}`. More than 3 bytes is malformed — RFC 7959's NUM
  tops out at 20 bits, which combined with the 4 low bits never needs a
  4th byte, so a longer value is not 'a very large block number', it's
  bytes that were never a Block option to begin with."
  [bytes]
  (let [bytes (vec bytes) n (count bytes)]
    (if (> n 3)
      {:status :error :reason :block-value-too-long :length n}
      (let [v (reduce (fn [acc b] (+ (* acc 256) b)) 0 bytes)
            szx (bit-and v 0x07)]
        (if (= szx 7)
          {:status :error :reason :reserved-szx}
          {:status :ok
           :num (unsigned-bit-shift-right v 4)
           :more? (pos? (bit-and v 0x08))
           :szx szx
           :size (size-exponents szx)})))))
