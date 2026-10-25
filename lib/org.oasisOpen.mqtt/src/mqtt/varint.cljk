(ns mqtt.varint
  "The MQTT Variable Byte Integer.

  Used for the fixed header's Remaining Length in every MQTT version, and
  for Property Length in MQTT 5.0. MQTT-3.1.1 §2.2.3, MQTT-5.0 §1.5.5: each
  byte carries 7 bits of value, low-order chunk first, with bit 7 (0x80) set
  on every byte except the last to say 'more follows'. The encoding is
  little-endian in the base-128 sense — least-significant 7 bits first —
  which is the opposite of the big-endian 16-bit integers used everywhere
  else in the protocol (Keep Alive, Packet Identifier, string lengths), and
  mixing the two up is the classic way to build a decoder that agrees with
  itself and disagrees with every broker.

  Four bytes is the hard ceiling (MQTT-3.1.1 §2.2.3): the value must fit in
  28 bits, giving a maximum of 268,435,455 (0x0FFFFFFF). A fifth continuation
  byte is malformed input, not merely a large number — a decoder that keeps
  reading past four bytes can be driven into scanning arbitrarily far into
  whatever follows the integer.

  MQTT-3.1.1 §2.2.3 Table 2.4 also gives the size table used below as a
  published test vector: Remaining Length 0/127/128/16383/16384/2097151 map
  to 1/1/2/2/3/3-byte encodings, and 268435455 is the 4-byte maximum.")

(defn encode
  "`n` (a non-negative integer, at most 268435455) as a Variable Byte
  Integer: a vector of 1-4 bytes."
  [n]
  (loop [n n out []]
    (let [b (bit-and n 0x7F)
          n' (unsigned-bit-shift-right n 7)]
      (if (zero? n')
        (conj out b)
        (recur n' (conj out (bit-or b 0x80)))))))

(defn decode
  "Reads a Variable Byte Integer starting at index `i` of the byte sequence
  `bs`. Returns `{:status :ok :value n :next-index j}` where `j` is the
  index just past the integer, or `{:status :incomplete}` if `bs` runs out
  before a byte without the continuation bit is seen, or
  `{:status :error :reason :malformed-variable-byte-integer}` if a fifth
  continuation byte is encountered — the encoding never needs one, so
  seeing one means the input is not a well-formed Variable Byte Integer at
  all, not a value the format simply can't hold."
  [bs i]
  (let [bs (vec bs) n (count bs)]
    (loop [j i value 0 shift 0 k 0]
      (cond
        (= k 4) {:status :error :reason :malformed-variable-byte-integer}
        (>= j n) {:status :incomplete}
        :else
        (let [b (nth bs j)
              value' (bit-or value (bit-shift-left (bit-and b 0x7F) shift))]
          (if (zero? (bit-and b 0x80))
            {:status :ok :value value' :next-index (inc j)}
            (recur (inc j) value' (+ shift 7) (inc k))))))))
