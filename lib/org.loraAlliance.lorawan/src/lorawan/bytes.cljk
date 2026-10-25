(ns lorawan.bytes
  "Shared byte-level helpers. Bytes are `Sequential` collections of ints in
  0..255, in and out — this workspace's `org-modbus` convention.

  ## The little-endian trap this whole library is built around

  LoRaWAN L2 1.0.4 spec, page 8 (\"Document Conventions\", before §1
  Introduction) — verified by full-text extraction of the OASIS-style
  numbered-paragraph PDF, not recalled from memory:

      The octet order for all multi-octet fields SHALL be little endian.
      EUI are 8-octet fields and SHALL be transmitted as little endian.

  Every multi-byte field in a `PHYPayload` — `DevAddr`, `DevEUI`,
  `JoinEUI`, `DevNonce`, `JoinNonce`, `NetID`, `FCnt` — goes on the wire
  **least-significant byte first**. This is the single most common source
  of bugs in LoRaWAN implementations (a `DevAddr` configured as the
  conventionally-written hex string `26011BDA` appears on the wire as the
  four octets `DA 1B 01 26`), for the same reason `org-modbus` singles out
  its reflected CRC polynomial: it *looks* correct — the value round-trips
  against itself — and disagrees with every other implementation. `le-n`/
  `le->int` below are the only place that convention lives; nothing else
  in this library reasons about byte order directly.

  The `Ai`/`B0` AES input blocks that `lorawan.mic`/`lorawan.crypt` build
  (§4.3.3 Table 12, §4.4 Table 13) place `DevAddr` at a fixed byte offset
  inside a 16-byte block, but `DevAddr` there is the same field as
  `FHDR`'s — the document-wide little-endian rule quoted above is not
  scoped to the frame header, and every LoRaWAN implementation this
  library was checked against encodes it little-endian inside `B0`/`Ai`
  too. There's no separate byte order for \"DevAddr inside an AES block\";
  it is one convention, applied everywhere the spec places a multi-octet
  field.")

(defn le-n
  "`n` little-endian bytes of nonnegative integer `x`, extracted by
  repeated `quot`/`mod 256` rather than `bit-shift`/`bit-and`. That choice
  is deliberate, not stylistic: `DevEUI`/`JoinEUI` are 8-octet fields
  (§6.2.1/§6.2.2) and a full 64-bit EUI with its top bit set — a perfectly
  legal one — reads as a Clojure literal larger than `Long/MAX_VALUE`,
  which the JVM reader promotes to `clojure.lang.BigInt`. `bit-shift-
  right`/`unsigned-bit-shift-right` do not accept `BigInt` at all (`Numbers.
  bitOpsCast` throws `IllegalArgumentException`) — this codec found that
  out the hard way, encoding `dev-eui 0xFFFFFFFFFFFFFFFF` in its own test
  suite before this function was fixed. `quot`/`mod` promote correctly
  across `long`/`BigInt` on the JVM with no special-casing needed.

  On ClojureScript there is no arbitrary-precision integer, so values
  above JavaScript's `2^53` safe-integer boundary lose precision the same
  way `amqp.types` documents for AMQP's `ulong`/`timestamp` — a real,
  bounded gap on that one runtime, not a hidden one. `n` up to 8 is safe
  everywhere within that boundary.

  Each byte is coerced with `int` before returning — `(mod BigInt 256)`
  stays a `BigInt` even though its value always fits in a byte, and a
  `BigInt`-typed 0..255 later hits the exact same `bitOpsCast` rejection
  (`bit-xor` in `lorawan.cmac`'s CMAC XOR, in this codec's own first run)
  that motivated avoiding bit-shift here in the first place. `int` is the
  one coercion this file needs on both runtimes — it exists in
  ClojureScript too, unlike `long`."
  [x n]
  (loop [x x i 0 acc []]
    (if (= i n) acc (recur (quot x 256) (inc i) (conj acc (int (mod x 256)))))))

(defn le->int
  "Inverse of `le-n`: the little-endian byte sequence `bs` as a nonnegative
  integer. Reverses to big-endian order, then folds with `+'`/`*'` — not
  `bit-or` of shifted bytes — so a 4-byte field whose top bit is set does
  not run into the sign-extension trap `amqp.types/u32-from-bytes`
  documents. LoRaWAN's DevAddr routinely has bit 31 set (it is the
  network's `AddrPrefix`) and must stay a plain nonnegative device
  address, not go negative.

  The auto-promoting `+'`/`*'` on the JVM branch (not plain `+`/`*`) matter
  for the same reason `le-n` coerces with `int`: reassembling an 8-byte
  `DevEUI`/`JoinEUI` whose value exceeds `Long/MAX_VALUE` (any EUI with
  its top bit set) with plain `*` throws `ArithmeticException: long
  overflow` — `clojure.lang.Numbers/multiply` calls `Math/multiplyExact`
  and does not silently wrap the way native machine multiplication would.
  `*'`/`+'` promote to `BigInt` instead of throwing. ClojureScript has no
  `+'`/`*'` (nbb: \"Unable to resolve symbol\") and no such overflow to
  guard against in the first place — every number is a double regardless
  of magnitude, so plain `+`/`*` is correct there, silently bounded by the
  same 2^53 precision limit this file already documents for `le-n`."
  [bs]
  (reduce (fn [acc b] #?(:clj (+' (*' acc 256) b) :cljs (+ (* acc 256) b))) 0 (reverse bs)))

(defn be-n
  "`n` big-endian bytes of nonnegative integer `x` — used only for the AES
  input blocks in `lorawan.mic`/`lorawan.crypt`, which are byte-order
  explicit per-field layouts, not reflected integers. `le-n` reversed —
  same `BigInt`-safety reason."
  [x n]
  (vec (reverse (le-n x n))))

(defn xor-bytes [a b] (mapv bit-xor a b))

(defn zero-pad
  "`bs` followed by zero bytes out to length `n`. LoRaWAN §4.3.3 calls this
  `pad16` — the FRMPayload is never itself padded on the wire (only the
  last AES keystream block computation pads internally), but `zero-pad` is
  the same operation, reused by `lorawan.crypt`."
  [bs n]
  (into (vec bs) (repeat (max 0 (- n (count bs))) 0)))
