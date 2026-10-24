(ns rtsp.interleaved
  "Interleaved (embedded) binary data — [RFC 2326] §10.12 — the framing
  that lets RTP/RTCP packets share the same TCP connection as RTSP's own
  text messages, quoted here verbatim:

    \"Stream data such as RTP packets is encapsulated by an ASCII dollar
    sign (24 hexadecimal), followed by a one-byte channel identifier,
    followed by the length of the encapsulated binary data as a binary,
    two-byte integer in network byte order. The stream data follows
    immediately afterwards, without a CRLF, but including the
    upper-layer protocol headers. Each $ block contains exactly one
    upper-layer protocol data unit, e.g., one RTP packet.\"

  So a frame on the wire is: `$` (0x24) | channel (1 byte) | length
  (u16 big-endian) | exactly `length` bytes of payload — no CRLF
  anywhere in it, unlike every text message this codec's other
  namespaces produce. Getting the length field's endianness or width
  wrong is the same class of bug `rtp.rtcp`'s README documents for
  RTCP's 32-bit-words-minus-one length: a header that *looks* consistent
  but silently desynchronizes the entire remaining stream, because
  nothing about a wrong length here throws — it just makes the next
  frame start at the wrong byte.")

(def marker
  "The ASCII `$`, decimal 36 (hex 0x24) — the RFC states the codepoint in
  hex explicitly (\"24 hexadecimal\") because the interleaved marker must
  never be confused with the char `$` in some other encoding; this
  library works in raw octets throughout, so it is simply the integer 36."
  0x24)

(defn encode
  "`{:channel 0..255 :data <byte-vector, <= 65535 bytes>}` -> the framed
  byte vector `$ channel len-hi len-lo data...`, or a named error if
  `channel` or the payload length is out of the field's range — this
  namespace refuses to silently truncate a channel id or wrap a length
  around 65536, either of which would frame data under someone else's
  channel or corrupt the following frame's start."
  [{:keys [channel data]}]
  (cond
    (not (<= 0 channel 255)) [:error :rtsp/interleaved-channel-out-of-range {:channel channel}]
    (not (<= 0 (count data) 0xFFFF)) [:error :rtsp/interleaved-length-out-of-range {:length (count data)}]
    :else
    (into [marker channel
           (bit-and (unsigned-bit-shift-right (count data) 8) 0xFF)
           (bit-and (count data) 0xFF)]
          data)))

(defn decode
  "`vector<int 0..255>` starting at an interleaved frame ->
  `[:ok {:channel .. :data [...]} consumed]` or a named error.
  `[:error :rtsp/interleaved-incomplete-header]` if fewer than 4 bytes
  are available (marker + channel + 2-byte length); `[:error
  :rtsp/interleaved-not-a-frame]` if the first byte is not `$`;
  `[:error :rtsp/interleaved-incomplete-payload {:need .. :have ..}]` if
  the declared length runs past the end of `bs` — the caller (a
  streaming reader) should wait for more bytes rather than treat this as
  a permanent failure."
  [bs]
  (cond
    (< (count bs) 4) [:error :rtsp/interleaved-incomplete-header]
    (not= (nth bs 0) marker) [:error :rtsp/interleaved-not-a-frame {:byte (nth bs 0)}]
    :else
    (let [channel (nth bs 1)
          len (bit-or (bit-shift-left (nth bs 2) 8) (nth bs 3))
          total (+ 4 len)]
      (if (> total (count bs))
        [:error :rtsp/interleaved-incomplete-payload {:need total :have (count bs)}]
        [:ok {:channel channel :data (subvec (vec bs) 4 total)} total]))))
