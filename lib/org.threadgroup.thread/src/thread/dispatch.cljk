(ns thread.dispatch
  "The 6LoWPAN Dispatch byte (RFC 4944 §5.1) — the first octet(s) of a
  6LoWPAN-encapsulated payload (itself the MAC-frame payload of an IEEE
  802.15.4 frame, `ieee802154.mac/decode`'s `:payload`), which says which
  of the several 6LoWPAN header shapes follows: an uncompressed IPv6
  header, LOWPAN_IPHC (`thread.iphc`), a Mesh Addressing header
  (`thread.mesh`), or a Fragmentation header (`thread.frag`).

  Source: RFC 4944 (IETF, freely published) §5.1, Figure 2, 'Dispatch
  Value Bit Pattern':

    Pattern      Header Type
    00  xxxxxx   NALP    — not a LoWPAN frame
    01  000001   IPv6    — uncompressed IPv6 header follows
    01  000010   LOWPAN_HC1 (deprecated by RFC 6282's LOWPAN_IPHC)
    10  xxxxxx   Mesh    — Mesh Addressing header (`thread.mesh`)
    11  000xxx   FRAG1   — first fragment (`thread.frag`)
    11  100xxx   FRAGN   — subsequent fragment (`thread.frag`)

  RFC 6282 §3.1 replaced the 2-bit `01`-prefixed HC1 dispatch with a
  3-bit-prefixed one: `011xxxxx` (0x60-0x7F) is LOWPAN_IPHC
  (`thread.iphc`). Both dispatch schemes are recognised here; Thread
  itself only ever emits LOWPAN_IPHC, never HC1, but a decoder should
  still name HC1 explicitly rather than let it fall through to
  `:reserved`.")

(defn classify
  "The first octet of a 6LoWPAN payload -> a keyword naming its header
  type, or `[:error :thread.dispatch/reserved byte]` if the byte does not
  match any assigned pattern."
  [byte]
  (let [b (bit-and byte 0xFF)]
    (cond
      (= 0 (bit-and (unsigned-bit-shift-right b 6) 0x03)) [:ok :nalp]
      (= b 0x41) [:ok :ipv6]
      (= b 0x42) [:ok :hc1]
      (= 0x03 (bit-and (unsigned-bit-shift-right b 5) 0x07)) [:ok :iphc]   ;; 011xxxxx
      (= 2 (bit-and (unsigned-bit-shift-right b 6) 0x03)) [:ok :mesh]      ;; 10xxxxxx
      (= 0x18 (bit-and (unsigned-bit-shift-right b 3) 0x1F)) [:ok :frag1]  ;; 11000xxx
      (= 0x1C (bit-and (unsigned-bit-shift-right b 3) 0x1F)) [:ok :fragn]  ;; 11100xxx
      :else [:error :thread.dispatch/reserved b])))
