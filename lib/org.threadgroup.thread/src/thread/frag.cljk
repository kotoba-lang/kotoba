(ns thread.frag
  "6LoWPAN fragmentation headers (RFC 4944 §5.3) — FRAG1 (first fragment)
  and FRAGN (subsequent fragments). An IEEE 802.15.4 frame's payload is a
  few dozen bytes at most; an IPv6 datagram routinely is not, so anything
  6LoWPAN carries that would not fit in one MAC frame is split across
  several, each carrying one of these headers so the receiver can
  reassemble them by `datagram-tag` and `datagram-offset`.

  Source: RFC 4944 (IETF, freely published), §5.3:

    FRAG1 (first fragment, 4-byte header):

       0                   1                   2
       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |1 1 0 0 0|    datagram_size    |  datagram_tag |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

    FRAGN (subsequent fragment, 5-byte header — one extra octet,
    `datagram_offset`, in units of 8 octets):

       0                   1                   2                   3
       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |1 1 1 0 0|    datagram_size    |  datagram_tag |datagram_offset|
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  `datagram_size` is the total size of the *unfragmented* datagram (11
  bits, 0..2047 — an 802.15.4 payload cannot legally address a bigger
  IPv6 packet than that on the wire without a Fragment Header, so 11 bits
  was enough); it is the same value in every fragment of one datagram.
  `datagram_tag` (16 bits) is an opaque per-source label a receiver uses
  to tell fragments of different, interleaved datagrams from the same
  peer apart. `datagram_offset` is in units of 8 octets — the first
  FRAGN's offset is never 0 (that would duplicate FRAG1's own data).")

(defn build-frag1
  "`{:datagram-size u11 :datagram-tag u16}` -> `[:ok header-bytes(4)]` |
  `[:error reason ...]`. Caller appends the payload fragment after."
  [{:keys [datagram-size datagram-tag]}]
  (cond
    (not (<= 0 datagram-size 0x7FF))
    [:error :thread.frag/datagram-size-out-of-range datagram-size]

    (not (<= 0 datagram-tag 0xFFFF))
    [:error :thread.frag/datagram-tag-out-of-range datagram-tag]

    :else
    [:ok [(bit-or 0xC0 (bit-and (unsigned-bit-shift-right datagram-size 8) 0x07))
          (bit-and datagram-size 0xFF)
          (bit-and (unsigned-bit-shift-right datagram-tag 8) 0xFF)
          (bit-and datagram-tag 0xFF)]]))

(defn parse-frag1
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) 4)
      [:error :thread.frag/header-too-short (count bs)]
      (let [b0 (nth bs 0)]
        (if (not= 0xC0 (bit-and b0 0xF8))
          [:error :thread.frag/not-frag1-dispatch b0]
          [:ok {:datagram-size (bit-or (bit-shift-left (bit-and b0 0x07) 8) (nth bs 1))
                :datagram-tag (bit-or (bit-shift-left (nth bs 2) 8) (nth bs 3))}
           4])))))

(defn build-fragn
  "`{:datagram-size u11 :datagram-tag u16 :datagram-offset u8}` -> `[:ok
  header-bytes(5)]` | `[:error reason ...]`."
  [{:keys [datagram-size datagram-tag datagram-offset]}]
  (cond
    (not (<= 0 datagram-size 0x7FF))
    [:error :thread.frag/datagram-size-out-of-range datagram-size]

    (not (<= 0 datagram-tag 0xFFFF))
    [:error :thread.frag/datagram-tag-out-of-range datagram-tag]

    (not (<= 0 datagram-offset 0xFF))
    [:error :thread.frag/datagram-offset-out-of-range datagram-offset]

    :else
    [:ok [(bit-or 0xE0 (bit-and (unsigned-bit-shift-right datagram-size 8) 0x07))
          (bit-and datagram-size 0xFF)
          (bit-and (unsigned-bit-shift-right datagram-tag 8) 0xFF)
          (bit-and datagram-tag 0xFF)
          (bit-and datagram-offset 0xFF)]]))

(defn parse-fragn
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) 5)
      [:error :thread.frag/header-too-short (count bs)]
      (let [b0 (nth bs 0)]
        (if (not= 0xE0 (bit-and b0 0xF8))
          [:error :thread.frag/not-fragn-dispatch b0]
          [:ok {:datagram-size (bit-or (bit-shift-left (bit-and b0 0x07) 8) (nth bs 1))
                :datagram-tag (bit-or (bit-shift-left (nth bs 2) 8) (nth bs 3))
                :datagram-offset (nth bs 4)}
           5])))))
