(ns v2gtp.frame
  "V2GTP (V2G Transfer Protocol) framing — the transport header ISO 15118-2
  puts in front of every EXI-encoded application message and every SDP
  (SECC Discovery Protocol) request/response, before TLS/TCP carries it.

  Header layout (8 bytes, **big-endian** — RISE-V2G's `V2GTPMessage.java`:
  'The order of a newly created byte buffer is always big endian (see
  [V2G2-085] on page 27)', i.e. this is a cited normative requirement of
  the standard, not an implementation choice):

  | offset | size | field |
  |---|---|---|
  | 0 | 1 | ProtocolVersion |
  | 1 | 1 | InverseProtocolVersion — the bitwise complement of ProtocolVersion |
  | 2 | 2 | PayloadType (`v2gtp.payload-type`) |
  | 4 | 4 | PayloadLength — byte count of what follows |
  | 8 | PayloadLength | Payload |

  ProtocolVersion 1 (0x01) / InverseProtocolVersion 0xFE is ISO 15118-2's
  own pairing; ISO 15118-20 (2nd generation) is out of scope here (this
  library targets ISO 15118-2's V2GTP+EXI stack specifically, not the
  DIN 70121/ISO 15118-20 family) and this frame codec doesn't hardcode
  ProtocolVersion 1 anywhere — it's a field the caller supplies."
  (:require [v2gtp.bits :as bits]))

(def header-length 8)

(defn encode
  "`{:protocol-version int :payload-type int :payload (byte seq)}` -> a
  byte vector: the 8-byte header followed by `payload` unchanged.
  InverseProtocolVersion is **computed** from `:protocol-version`, never
  accepted as a separate input — there is no way to construct a frame whose
  two version bytes disagree with each other through this function, which
  is exactly the invariant `decode` checks on the way back in."
  [{:keys [protocol-version payload-type payload]}]
  (let [payload (vec payload)]
    (-> []
        (conj (bit-and protocol-version 0xFF))
        (conj (bits/inverse-byte protocol-version))
        (into (bits/u16->bytes payload-type))
        (into (bits/u32->bytes (count payload)))
        (into payload))))

(defn decode
  "Byte seq -> `[:ok {:protocol-version :payload-type :payload-length
  :payload :leftover}]` or `[:error kw]`.

  `:leftover` is whatever bytes in `bs` came after this one frame —
  V2GTP frames are meant to be read back-to-back off a TCP stream (SDP,
  the TLS handshake, and every EXI-encoded V2G message all ride this same
  framing), so `decode` takes exactly PayloadLength bytes for `:payload`
  and hands the rest back rather than either discarding trailing bytes or
  refusing to decode a buffer that happens to contain more than one frame.
  `:leftover` is `[]` when `bs` was exactly one frame's worth of bytes.

  Errors: `:v2gtp/header-too-short` (fewer than 8 bytes total — the header
  itself doesn't fit), `:v2gtp/payload-too-short` (the header is intact and
  parses, but fewer than PayloadLength bytes remain after it),
  `:v2gtp/inverse-version-mismatch` (byte 1 isn't the bitwise complement of
  byte 0 — a corrupted or non-V2GTP stream, not a payload problem)."
  [bs]
  (let [bs (vec bs)
        n (count bs)]
    (if (< n header-length)
      [:error :v2gtp/header-too-short]
      (let [pv (nth bs 0)
            ipv (nth bs 1)
            pt (bits/bytes->u16 (nth bs 2) (nth bs 3))
            plen (bits/bytes->u32 (nth bs 4) (nth bs 5) (nth bs 6) (nth bs 7))
            available (- n header-length)]
        (cond
          (not= ipv (bits/inverse-byte pv))
          [:error :v2gtp/inverse-version-mismatch]

          (< available plen)
          [:error :v2gtp/payload-too-short]

          :else
          [:ok {:protocol-version pv
                :payload-type pt
                :payload-length plen
                :payload (subvec bs header-length (+ header-length plen))
                :leftover (subvec bs (+ header-length plen) n)}])))))
