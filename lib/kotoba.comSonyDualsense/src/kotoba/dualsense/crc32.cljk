(ns kotoba.dualsense.crc32
  "Portable CRC-32 (IEEE 802.3 / zlib / PKZIP — reflected polynomial
  0xEDB88320, init 0xFFFFFFFF, final XOR 0xFFFFFFFF).

  From scratch, no `java.util.zip.CRC32` — that class does not exist in
  ClojureScript, and this library must stay portable across JVM /
  ClojureScript / SCI / GraalVM like every other kotoba-lang capability.
  A plain bit-loop (8 shifts per byte) is used rather than a lookup table;
  the inputs this library feeds it (single ~64-82 byte HID reports) are
  tiny, so table-driven speed is not worth the extra state.

  The Sony DualSense uses this exact CRC32 to validate/sign Bluetooth HID
  reports (see `kotoba.dualsense.input`/`kotoba.dualsense.output`), each
  time with a different one-byte seed folded in ahead of the report bytes.
  This namespace only implements the checksum itself; the DualSense-
  specific seed convention lives in the input/output namespaces.")

(def ^:private poly
  "The reflected form of the standard CRC-32 polynomial (0x04C11DB7
  bit-reversed), used by zlib, PKZIP, Ethernet (IEEE 802.3), and — via the
  Linux `hid-playstation` driver's `crc32_le` — the DualSense Bluetooth
  wire protocol."
  0xEDB88320)

(def ^:private init
  "Initial CRC register value before any bytes are folded in."
  0xFFFFFFFF)

(defn- crc32-byte
  "Fold one byte (0-255) into the running CRC register `crc`, 1 bit at a
  time. `unsigned-bit-shift-right` (not `bit-shift-right`) is used for
  every shift so this behaves identically on the JVM (64-bit Long, no sign
  issue at 32 bits) and in ClojureScript (32-bit signed int bitwise ops —
  a plain right-shift would sign-extend and corrupt the register once bit
  31 is set)."
  [crc byte]
  (loop [c (bit-xor crc (bit-and byte 0xFF))
         i 0]
    (if (= i 8)
      c
      (recur (if (odd? (bit-and c 1))
               (bit-xor (unsigned-bit-shift-right c 1) poly)
               (unsigned-bit-shift-right c 1))
             (inc i)))))

(defn crc32
  "Standard CRC-32 (IEEE 802.3 / zlib / PKZIP) of `byte-seq`, a seq of ints
  0-255. Returns a non-negative uint32 (0..0xFFFFFFFF) in both Clojure and
  ClojureScript — the final `unsigned-bit-shift-right _ 0` normalizes away
  the 32-bit-signed-int sign bit that ClojureScript's bitwise ops would
  otherwise leave set whenever bit 31 of the checksum is 1.

  `(crc32 (map int \"123456789\"))` is the standard CRC-32 check value
  `0xCBF43926` — the canonical vector used to validate any CRC-32
  implementation (see the RevEng CRC catalogue, `crc-32/iso-hdlc`)."
  [byte-seq]
  (unsigned-bit-shift-right
    (bit-xor (reduce crc32-byte init byte-seq) 0xFFFFFFFF)
    0))
