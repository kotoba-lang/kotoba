(ns ospf.checksum
  "The RFC 1071 Internet checksum — the algorithm OSPF's packet-header
  Checksum field uses (RFC 2328 Appendix A.3.1, quoted on `ospf.header`).

  Two implementations live here on purpose, the same discipline
  `modbus.crc` uses for CRC-16/MODBUS: `ones-complement-sum` is the
  definition, folding the carry back in after every 16-bit word so the
  accumulator never exceeds 17 bits; `ones-complement-sum-fast` is the
  RFC's own §4.1 form, which accumulates the full running total and folds
  only once at the end. A property test asserts the two agree over random
  inputs of every length — a stronger statement than either one matching a
  constant somebody remembered — and the RFC's own worked numerical
  example (§3) is asserted directly.

  RFC 1071 §2, quoted:

    \"The checksum field is the 16 bit one's complement of the one's
    complement sum of all 16 bit words in the header. For purposes of
    computing the checksum, the value of the checksum field is zero ...
    In more detail: ... the checksum field itself is cleared, the 16-bit
    1's complement sum is computed over the octets concerned, and the 1's
    complement of this sum is placed in the checksum field. ... To check
    a checksum, the 1's complement sum is computed over the same set of
    octets, including the checksum field. If the result is all 1 bits
    (-0 in 1's complement arithmetic), the check succeeds.\"

  and, on odd-length input: \"If necessary, the last data octet is padded
  on the right with zeros to form a 16 bit word for checksum purposes.\"")

;; ── the definition ───────────────────────────────────────────────────────────

(defn ones-complement-sum
  "The 16-bit one's-complement sum of `bs` (RFC 1071 §2), *before* the
  final one's-complement — i.e. the value the Checksum field is the
  complement of, and the value `verify` expects back as 0xFFFF. An
  odd-length `bs` is padded with a zero byte per §2's last sentence,
  quoted above.

  Folds the running sum back into 16 bits after every word (`sum' =
  (sum & 0xFFFF) + (sum >> 16)`), so the accumulator is always <= 0xFFFF
  going into the next addition and this can never overflow regardless of
  input length. This is the shape to trust; `ones-complement-sum-fast`
  below is checked against it, not the other way around."
  [bs]
  (loop [bs (seq bs) sum 0]
    (cond
      (nil? bs)
      sum

      (nil? (next bs))
      (let [word (bit-shift-left (bit-and (first bs) 0xFF) 8)
            s (+ sum word)]
        (+ (bit-and s 0xFFFF) (unsigned-bit-shift-right s 16)))

      :else
      (let [word (bit-or (bit-shift-left (bit-and (first bs) 0xFF) 8)
                          (bit-and (second bs) 0xFF))
            s (+ sum word)
            folded (+ (bit-and s 0xFFFF) (unsigned-bit-shift-right s 16))]
        (recur (nnext bs) folded)))))

;; ── the RFC's own §4.1 form ──────────────────────────────────────────────────

(defn ones-complement-sum-fast
  "The same value as `ones-complement-sum`, computed the way RFC 1071
  §4.1's C loop does it — accumulate the plain running sum across the
  whole buffer, then fold the carry back in afterward (possibly more than
  once, since a single addition-then-fold can itself carry out again):

    register long sum = 0;
    while (count > 1) { sum += *(unsigned short *)addr++; count -= 2; }
    if (count > 0) sum += *(unsigned char *)addr;
    while (sum >> 16) sum = (sum & 0xffff) + (sum >> 16);
    checksum = ~sum;

  The running total here can reach roughly `(count bs)/2 * 0xFFFF`, which
  for OSPF's largest possible packet (Packet length is 2 octets, so
  <= 65535 bytes) is comfortably under 2^31 and therefore safe as a plain
  integer add on both the JVM and ClojureScript — no per-word fold is
  needed to stay in range the way it is for arbitrarily large buffers."
  [bs]
  (loop [bs (seq bs) sum 0]
    (cond
      (nil? bs)
      (loop [s sum]
        (if (zero? (unsigned-bit-shift-right s 16))
          s
          (recur (+ (bit-and s 0xFFFF) (unsigned-bit-shift-right s 16)))))

      (nil? (next bs))
      (recur nil (+ sum (bit-shift-left (bit-and (first bs) 0xFF) 8)))

      :else
      (recur (nnext bs)
             (+ sum (bit-or (bit-shift-left (bit-and (first bs) 0xFF) 8)
                             (bit-and (second bs) 0xFF)))))))

;; ── generation and verification ─────────────────────────────────────────────

(defn checksum
  "The RFC 1071 checksum of `bs`: the 16-bit one's complement of
  `ones-complement-sum`. This is the value that goes in the wire
  Checksum field."
  [bs]
  (bit-and (bit-not (ones-complement-sum bs)) 0xFFFF))

(defn checksum-bytes
  "`checksum` as two big-endian bytes."
  [bs]
  [(bit-and (unsigned-bit-shift-right (checksum bs) 8) 0xFF)
   (bit-and (checksum bs) 0xFF)])

(defn valid?
  "True when `bs` — which must already include the checksum field at
  whatever offset it was placed in during generation — sums to 0xFFFF,
  RFC 1071 §2's \"all 1 bits (-0 in 1's complement arithmetic)\" success
  condition. This is not `(= 0 (checksum bs))`: summing across a
  checksum field that itself holds the one's complement of the rest is
  what produces all-ones, never zero, when the data is intact.

  The checksum field must sit at an EVEN offset in `bs` for this to hold,
  which is the one place callers get this wrong. RFC 1071 §2's zero pad
  for an odd-length buffer is notional — it exists only while summing — so
  a caller who *appends* a checksum to odd-length data has moved the field
  to an odd offset, the last data octet then pairs with the checksum's
  high byte instead of with the pad, and verification fails on intact
  data. OSPF is unaffected: RFC 2328 Appendix A.3.1 fixes the Checksum
  field at offset 12 of the header, an even offset. Both directions are
  asserted in the test suite."
  [bs]
  (= 0xFFFF (ones-complement-sum bs)))
