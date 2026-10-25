(ns afdx.bytes
  "Byte-vector primitives shared by every framing namespace in this
  library: big-endian 16/32-bit read/write, and the Internet checksum
  (RFC 1071) IPv4 and UDP both use.

  Unlike `com-aviation-ia-arinc-429`, which packs everything into a
  single 32-bit integer, AFDX frames are naturally byte sequences —
  Ethernet, IPv4 and UDP are all byte-oriented on the wire. That mostly
  sidesteps ARINC 429's 32-bit-signed-vs-unsigned trap (every individual
  byte here is 0..255, comfortably inside the range where JVM and
  ClojureScript bitwise operators agree), but the Internet checksum's
  running sum is NOT byte-sized — it accumulates 16-bit words and folds
  carries — so `checksum16` still has to be written with the same
  discipline `com-aviation-ia-arinc-429` uses, and is exercised against
  RFC 1071's own worked example in the test suite rather than trusted on
  the strength of a JVM-only run.")

(defn u16be
  "16-bit unsigned integer -> its 2 big-endian octets."
  [n]
  [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])

(defn rd-u16be
  "2 big-endian octets, at `off` in byte-vector `bs` -> the 16-bit
  unsigned integer they encode."
  [bs off]
  (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
          (bit-and (nth bs (inc off)) 0xFF)))

(defn u32be
  "32-bit unsigned integer -> its 4 big-endian octets."
  [n]
  [(bit-and (unsigned-bit-shift-right n 24) 0xFF)
   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
   (bit-and n 0xFF)])

(defn rd-u32be
  "4 big-endian octets, at `off` in byte-vector `bs` -> the 32-bit
  unsigned integer they encode, canonicalised non-negative on both
  runtimes (see `com-aviation-ia-arinc-429`'s `arinc429.bits/u32` for why
  that canonicalisation matters under ClojureScript)."
  [bs off]
  (unsigned-bit-shift-right
   (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 24)
           (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 16)
           (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 8)
           (bit-and (nth bs (+ off 3)) 0xFF))
   0))

(defn checksum16
  "The Internet checksum (RFC 1071 / RFC 791 §3.1 / RFC 768): sum every
  16-bit big-endian word of `bs` (a byte vector, zero-padded by one
  octet if its length is odd — RFC 1071 §4.1's rule), fold the carries
  out of the 16-bit field repeatedly until none remain, then take the
  one's complement.

  Returns the 16-bit checksum. To COMPUTE a checksum, `bs` is the data
  with the checksum field itself set to 0; to VERIFY one, `bs` is the
  data with the checksum field left as received, and the result should
  come back 0 (RFC 1071 §1(B) notes this as the fast verification path,
  used by `afdx.ipv4`/`afdx.udp` instead of re-zeroing and recomputing)."
  [bs]
  (let [padded (if (odd? (count bs)) (conj (vec bs) 0) (vec bs))
        sum (reduce + 0 (map (fn [i] (rd-u16be padded i))
                              (range 0 (count padded) 2)))
        folded (loop [s sum]
                 (if (> s 0xFFFF)
                   (recur (+ (bit-and s 0xFFFF) (unsigned-bit-shift-right s 16)))
                   s))]
    (bit-and (bit-not folded) 0xFFFF)))
