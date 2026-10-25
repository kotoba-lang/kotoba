(ns arinc429.bits
  "Bit-level primitives shared by the rest of this library.

  ARINC 429 is a 32-bit word, and a 32-bit word is precisely the size at
  which JVM Clojure and ClojureScript disagree about what `bit-or` means.
  On the JVM, `bit-and`/`bit-or`/`bit-shift-left` operate on 64-bit longs,
  so a word with bit 32 (the parity bit) set is just a large positive
  number. In JavaScript, the same operators first coerce both operands to
  a *signed* 32-bit integer (`ToInt32`) — so the exact same bit pattern,
  with bit 32 set, becomes a **negative** number under ClojureScript. A
  round-trip test that never sets bit 32 will never see this; the parity
  bit is set on very close to half of all real words, so it is not an edge
  case, it is the common case.

  `u32` is the fix: `unsigned-bit-shift-right x 0` is Clojure's spelling of
  JavaScript's `x >>> 0`, which coerces to *unsigned* 32-bit and is a
  no-op on the JVM for any value already in `0..0xFFFFFFFF`. Every function
  in this library that produces a word applies it exactly once, at the
  end, rather than trying to keep every intermediate value non-negative.")

(def word-mask
  "0xFFFFFFFF as a JVM long. `bit-and` with this truncates a value that
  (through a bug) grew past 32 bits back down to 32 bits, on the JVM where
  `bit-and`/`bit-or` do not truncate on their own the way JavaScript's do."
  0xFFFFFFFF)

(defn u32
  "Canonicalise `x` to the unsigned 32-bit integer it represents, portably.
  Apply this once, at the boundary where a word leaves this library
  (`pack-word`'s return value) — not after every intermediate shift/or."
  [x]
  (unsigned-bit-shift-right (bit-and x word-mask) 0))

(defn popcount32
  "Number of set bits in the low 32 bits of `x` (`x` must already be
  canonical, i.e. the output of `u32`). Used for odd-parity computation."
  [x]
  (loop [n (u32 x) i 0 c 0]
    (if (= i 32)
      c
      (recur (unsigned-bit-shift-right n 1) (inc i) (+ c (bit-and n 1))))))

(defn reverse-byte
  "Mirror the 8 bits of `b` (`b` in 0..255): bit 0 <-> bit 7, bit 1 <-> bit
  6, and so on. An involution — `(reverse-byte (reverse-byte b))` is `b`.

  This is the ARINC 429 label's defining quirk, and it is the exact shape
  of `org-modbus`'s reflected CRC polynomial (`0xA001` vs `0x8005`): one
  field in the protocol is bit-mirrored relative to how every other field
  in the same word is read, and treating it like the others is the single
  most common ARINC 429 implementation bug. See `arinc429.label` for what
  it means here specifically."
  [b]
  (loop [n (bit-and b 0xFF) i 0 r 0]
    (if (= i 8)
      r
      (recur (unsigned-bit-shift-right n 1) (inc i)
             (bit-or (bit-shift-left r 1) (bit-and n 1))))))

(defn field
  "Extract a `width`-bit field starting at bit `shift` (0-indexed, ARINC
  bit `shift + 1`) out of canonical word `w`."
  [w shift width]
  (bit-and (unsigned-bit-shift-right w shift) (dec (bit-shift-left 1 width))))
