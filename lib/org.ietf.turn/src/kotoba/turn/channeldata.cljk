;; kotoba.turn.channeldata — RFC 8656 §12.4 ChannelData framing: the
;; lightweight binary format TURN uses to carry relayed application data
;; once a channel is bound, distinct from a full STUN message. Pure/
;; portable `.cljc`, zero I/O, same `kotoba.bytes` byte-vector convention
;; (vector<int 0..255>) as `kotoba.turn.stun` — no reader conditionals, the
;; exact same code runs on the JVM and in ClojureScript.
;;
;; Wire format (RFC 8656 §12.4, Figure 5): a 4-byte header — 2-byte Channel
;; Number (big-endian, must satisfy `kotoba.turn.allocation/channel-number-
;; valid?`), 2-byte Length (big-endian) — followed by exactly `Length` bytes
;; of Application Data. Per the RFC text:
;;   "The Length field specifies the length in bytes of the application
;;    data field (i.e., it does not include the size of the ChannelData
;;    header). Note that 0 is a valid length."
;; Padding: "Over TCP and TLS-over-TCP, the ChannelData message MUST be
;; padded to a multiple of four bytes ... The padding is not reflected in
;; the length field ... Over UDP, the padding is not required but MAY be
;; included." This namespace has no notion of transport (it operates on an
;; already-extracted ChannelData message, not a raw socket buffer), so
;; `encode` always appends the padding — same call either transport makes,
;; and matches the 4-byte-boundary padding convention `kotoba.turn.stun/
;; push-attr` already uses for STUN attribute values (padding bytes,
;; uncounted by the length field). `decode` reads exactly `Length` bytes of
;; data and ignores anything after — it neither requires nor rejects
;; trailing padding, consistent with the RFC's "MAY be included" over UDP.
(ns kotoba.turn.channeldata
  (:require [kotoba.bytes :as b]
            [kotoba.turn.allocation :as alloc]))

(defn encode
  "Encode a ChannelData message: `channel-num` (must satisfy
   `kotoba.turn.allocation/channel-number-valid?`) + `payload` (a byte
   vector). Returns the framed byte vector (header + payload + 4-byte-
   boundary padding), or `nil` if `channel-num` is out of range — an
   invalid channel number is never silently encoded onto the wire."
  [channel-num payload]
  (when (alloc/channel-number-valid? channel-num)
    (let [payload (vec payload)
          len (count payload)
          pad (mod (- 4 (mod len 4)) 4)]
      (-> []
          (into (b/u16->bytes channel-num))
          (into (b/u16->bytes len))
          (into payload)
          (into (repeat pad 0))))))

(defn decode
  "Decode a ChannelData message from `framed` (a byte vector). Returns
   `{:channel-number n :data byte-vector}`, or `nil` on malformed/
   too-short input: fewer than 4 header bytes, or a declared Length that
   runs past what's actually present in `framed`. Never throws — same
   nil-on-failure idiom `kotoba.turn.stun`'s boolean-returning verify
   functions use (`verify-message-integrity`/`verify-fingerprint`), rather
   than the exception-throwing idiom its `decode-header`/`attributes`
   parsers use, since a demultiplexed datagram that merely LOOKS malformed
   is an expected, non-exceptional occurrence a listener must handle every
   packet, not a program error."
  [framed]
  (let [framed (vec framed) n (count framed)]
    (when (>= n 4)
      (let [channel-num (b/bytes->u16 (subvec framed 0 2))
            len (b/bytes->u16 (subvec framed 2 4))
            end (+ 4 len)]
        (when (<= end n)
          {:channel-number channel-num
           :data (subvec framed 4 end)})))))
