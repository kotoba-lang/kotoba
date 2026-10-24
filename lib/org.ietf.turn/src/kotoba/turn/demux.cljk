;; kotoba.turn.demux — RFC 8656 §12.4's datagram classification: a real TURN
;; listener receives raw UDP datagrams on ONE port that can be either a full
;; STUN message or a ChannelData message, and must tell which before parsing
;; either. Pure/portable `.cljc`, zero I/O — this namespace only classifies
;; a byte vector already in hand, it never touches a socket.
;;
;; The bit-level reasoning (so a future reader — or the listener-
;; implementation phase — can check this against the spec without
;; re-deriving it):
;;
;;   * RFC 8489 §5 (STUN header, Figure 2): "The most significant 2 bits of
;;     every STUN message MUST be zeroes. This can be used to differentiate
;;     STUN packets from other protocols when STUN is multiplexed with
;;     other protocols on the same port." Those 2 bits are the top 2 bits of
;;     the message's very first byte (the STUN Message Type field's MSB
;;     byte occupies bits 15..8 of the first 16-bit word, and bits 15..14
;;     are the fixed-zero pair) — so byte0 of any valid STUN message is in
;;     [0x00, 0x3F] (top 2 bits `00`).
;;   * RFC 8656 §12.4 (ChannelData, Figure 5): the message starts with a
;;     2-byte Channel Number. `kotoba.turn.allocation/channel-min`..
;;     `channel-max` is 0x4000-0x7FFF, and every value in that range has top
;;     2 bits `01` (0x4000 = 0100_0000_0000_0000, 0x7FFF =
;;     0111_1111_1111_1111) — so byte0 of a ChannelData message this repo
;;     considers valid is in [0x40, 0x7F] (top 2 bits `01`).
;;
;;   `00` (STUN) and `01` (ChannelData) never overlap, which is exactly why
;;   RFC 8489 constrains STUN's leading bits the way it does — it's
;;   deliberately reserving the other 3/4 of the leading-bits space for
;;   things like TURN channel data. NOTE: RFC 8656 §12 Table 2 additionally
;;   narrows the *formally allocatable* channel-number range to
;;   0x4000-0x4FFF (byte0 in [0x40, 0x4F]) to also coexist with RFC 7983's
;;   finer DTLS-SRTP/ZRTP/RTP first-byte multiplexing table on the same
;;   5-tuple — see the note in `kotoba.turn.allocation`. This namespace
;;   implements the coarser, 2-bit `00`/`01` split (matching
;;   `channel-number-valid?`'s 0x4000-0x7FFF range), not the RFC 7983 table;
;;   a listener that must coexist with DTLS-SRTP on the same port needs the
;;   finer check on top of this one.
;;
;; A datagram too short to contain even one byte, or whose leading bits are
;; `10`/`11`, or that's shorter than the minimum frame size for the pattern
;; it does match (20 bytes for a STUN header, 4 bytes for a ChannelData
;; header), classifies as `:unknown`.
(ns kotoba.turn.demux)

(defn classify-datagram
  "Classify raw datagram `dgram` (a byte vector) as `:stun`, `:channel-data`,
   or `:unknown`, per the leading-2-bits reasoning above. Never throws."
  [dgram]
  (let [dgram (vec dgram)
        n (count dgram)]
    (if (< n 1)
      :unknown
      (let [top2 (bit-and (unsigned-bit-shift-right (bit-and (first dgram) 0xff) 6) 0x03)]
        (cond
          (and (= top2 0x00) (>= n 20)) :stun
          (and (= top2 0x01) (>= n 4)) :channel-data
          :else :unknown)))))
