(ns v2gtp.bits
  "Big-endian integer<->byte-vector primitives for the V2GTP header, and the
  one place in this library where 16-bit and 32-bit fields are handled
  differently on purpose.

  V2GTP's PayloadType (2 bytes, max value 0xFFFF = 65535) is small enough
  that `bit-shift-left`/`bit-or` on it never touch the sign bit of a 32-bit
  signed integer, so `bytes->u16`/`u16->bytes` below use them directly —
  that's the 'use bit-and/bit-or/bit-shift-left/unsigned-bit-shift-right'
  approach, and it's correct here.

  PayloadLength (4 bytes, max value 0xFFFFFFFF = 4294967295) is not that
  lucky. `(bit-shift-left 0x80 24)` is `0x80000000`, which as a **signed**
  32-bit integer is negative (-2147483648) — and ClojureScript's bitwise
  operators genuinely are 32-bit signed (they coerce through JavaScript's
  `ToInt32`), the exact trap this workspace has hit repeatedly ('`bit-or`
  ToInt32 coercion producing negatives'). Reconstructing a 4-byte big-endian
  unsigned integer as `(bit-or (bit-shift-left b0 24) (bit-shift-left b1 16)
  (bit-shift-left b2 8) b3)` therefore silently returns a *negative* Long
  under ClojureScript for any PayloadLength >= 0x80000000 (any V2G message
  body 2 GiB or larger — implausible for this protocol, but PayloadLength's
  wire range genuinely goes that high, and 'implausible' is not the same
  claim as 'impossible to construct in a test'), while the identical-looking
  Clojure code on the JVM keeps working (the JVM's `bit-shift-left`/`bit-or`
  operate on 64-bit longs, so there's no overflow to hit).

  `bytes->u32`/`u32->bytes` below sidestep the whole class of bug by doing
  the 32-bit-crossing arithmetic with `*`/`+`/`quot` instead of shifts —
  ordinary numeric multiplication and addition, which is exact on both
  runtimes for every value in the 0..4294967295 range (well inside a JVM
  long, and well inside JavaScript's 2^53 safe-integer double range). Each
  byte is still masked with `bit-and 0xFF` on the way in and out — that part
  of a byte's value never approaches the sign bit, so `bit-and` is exactly
  the right, safe tool for it.")

(defn u16->bytes
  "`n` (0..65535) as a big-endian 2-byte vector."
  [n]
  [(bit-and (unsigned-bit-shift-right n 8) 0xFF)
   (bit-and n 0xFF)])

(defn bytes->u16
  "Two big-endian bytes -> the integer they encode (0..65535)."
  [b0 b1]
  (bit-or (bit-shift-left (bit-and b0 0xFF) 8)
          (bit-and b1 0xFF)))

(defn u32->bytes
  "`n` (0..4294967295) as a big-endian 4-byte vector. `quot` instead of a
  right-shift for the top three bytes — see this namespace's docstring for
  why a shift is the wrong tool for a value that can exceed 2^31-1."
  [n]
  [(bit-and (quot n 16777216) 0xFF)
   (bit-and (quot n 65536) 0xFF)
   (bit-and (quot n 256) 0xFF)
   (bit-and n 0xFF)])

(defn bytes->u32
  "Four big-endian bytes -> the integer they encode (0..4294967295). `*`/`+`
  instead of `bit-shift-left`/`bit-or` — see this namespace's docstring."
  [b0 b1 b2 b3]
  (+ (* (bit-and b0 0xFF) 16777216)
     (* (bit-and b1 0xFF) 65536)
     (* (bit-and b2 0xFF) 256)
     (bit-and b3 0xFF)))

(defn inverse-byte
  "The bitwise complement of `b`, masked to one byte. This is
  `InverseProtocolVersion` — RISE-V2G's reference implementation computes it
  as `protocolVersion ^ 0xFF` (`V2GTPMessage.java`, constructor), i.e. an
  XOR against an all-ones byte, which is exactly `bit-not` restricted to 8
  bits (`bit-not` alone would flip every bit in the runtime's full integer
  width, hence the `bit-and 0xFF` afterward)."
  [b]
  (bit-and (bit-xor b 0xFF) 0xFF))
