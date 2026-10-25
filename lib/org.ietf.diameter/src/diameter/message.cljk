(ns diameter.message
  "RFC 6733 §3 Diameter Header:

  ```
       0                   1                   2                   3
       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |    Version    |                 Message Length                |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      | Command Flags |                  Command Code                 |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                         Application-ID                        |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                      Hop-by-Hop Identifier                    |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |                      End-to-End Identifier                    |
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |  AVPs ...
      +-+-+-+-+-+-+-+-+-+-+-+-+-
  ```

  20 fixed octets, then AVPs (`diameter.avp`) out to Message Length.

  Command Flags: `R P E T r r r r` — R(equest)/P(roxiable)/E(rror)/
  T(potentially retransmitted), bits 4-7 reserved. §3: \"These flag bits
  are reserved for future use; they MUST be set to zero and ignored by the
  receiver.\" As with the AVP header's own reserved bits (`diameter.avp`),
  a nonzero reserved nibble is not a decode failure — it's read out
  (`:diameter.message/reserved-flags`, 0..15) so a caller can inspect it,
  not silently discarded and not treated as malformed.

  This namespace does not open a socket, run a peer state machine, or read
  a clock — see the README's \"what this is not\"."
  (:require [diameter.bytes :as b]
            [diameter.avp :as avp]))

(def ^:private r-bit 2r10000000)
(def ^:private p-bit 2r01000000)
(def ^:private e-bit 2r00100000)
(def ^:private t-bit 2r00010000)
(def ^:private reserved-mask 2r00001111)

(def header-length 20)

(defn fail!
  [code message data]
  (throw (ex-info message (assoc data :type code))))

(defn encode-message
  "`{:diameter.message/command-code cc :diameter.message/application-id id
     :diameter.message/hop-by-hop n :diameter.message/end-to-end n
     :diameter.message/avps [...] :diameter.message/request? bool
     :diameter.message/proxiable? bool :diameter.message/error? bool
     :diameter.message/retransmitted? bool
     :diameter.message/reserved-flags int}` -> the message as a vector of
  ints. Version is always 1 (RFC 6733 §3: \"MUST be set to 1\") and is not
  a field the caller supplies. Message Length is computed, not supplied —
  it is always `20 + (count avp-bytes)`, and since every encoded AVP is
  already padded to a 4-octet boundary (`diameter.avp/encode-avp`), the
  result is always a multiple of 4, matching §3: \"the Message Length field
  is always a multiple of 4.\"

  Throws (not `[:error ...]`) on this side's own input being malformed —
  same encode/decode split as `diameter.avp/encode-avp`."
  [{:diameter.message/keys [command-code application-id hop-by-hop end-to-end
                            avps request? proxiable? error? retransmitted?
                            reserved-flags]
    :or {avps [] request? false proxiable? false error? false
         retransmitted? false reserved-flags 0}}]
  (doseq [[label v] [["Command-Code" command-code] ["Application-ID" application-id]
                     ["Hop-by-Hop Identifier" hop-by-hop] ["End-to-End Identifier" end-to-end]]]
    (when (nil? v)
      (fail! :diameter/missing-header-field (str label " is required") {:field label})))
  (when (or (neg? command-code) (> command-code 0xffffff))
    (fail! :diameter/bad-command-code "Command Code is a 24-bit field" {:command-code command-code}))
  (let [avp-bytes (avp/encode-avps avps)
        message-length (+ header-length (count avp-bytes))
        flags (bit-or (if request? r-bit 0)
                       (if proxiable? p-bit 0)
                       (if error? e-bit 0)
                       (if retransmitted? t-bit 0)
                       (bit-and reserved-flags reserved-mask))]
    (when (> message-length 0xffffff)
      (fail! :diameter/message-too-long "Message Length is a 24-bit field" {:length message-length}))
    (-> []
        (into [1])                                    ; Version
        (into (b/uint24->bytes message-length))
        (into [flags])
        (into (b/uint24->bytes command-code))
        (into (b/uint32->bytes application-id))
        (into (b/uint32->bytes hop-by-hop))
        (into (b/uint32->bytes end-to-end))
        (into avp-bytes))))

(defn decode-message
  "Wire bytes -> `[:ok message next-pos]` or `[:error kw]`. Never throws.
  `next-pos` is the offset of the byte immediately after this message's
  Message Length — unlike RADIUS over UDP (one datagram, one packet, and
  trailing bytes are padding to be ignored), Diameter runs over SCTP/TCP
  (RFC 6733 §2.1): a byte stream, where the bytes after one message are
  usually the start of the *next* message, not padding. Returning
  `next-pos` lets a caller decode a stream by repeated calls at
  `next-pos`, rather than this namespace ever reading a socket itself."
  [data]
  (let [bs (vec (b/->ints data))
        n (count bs)]
    (cond
      (< n header-length) [:error :diameter/truncated-header]

      (not= 1 (nth bs 0)) [:error :diameter/unsupported-version]

      :else
      (let [message-length (b/bytes->uint24 (subvec bs 1 4))
            flags (nth bs 4)
            request? (not (zero? (bit-and flags r-bit)))
            proxiable? (not (zero? (bit-and flags p-bit)))
            error? (not (zero? (bit-and flags e-bit)))
            retransmitted? (not (zero? (bit-and flags t-bit)))
            reserved-flags (bit-and flags reserved-mask)
            command-code (b/bytes->uint24 (subvec bs 5 8))
            application-id (b/bytes->uint32 (subvec bs 8 12))
            hop-by-hop (b/bytes->uint32 (subvec bs 12 16))
            end-to-end (b/bytes->uint32 (subvec bs 16 20))]
        (cond
          (< message-length header-length)
          [:error :diameter/message-length-too-short]

          (not (zero? (mod message-length 4)))
          [:error :diameter/message-length-not-aligned]

          (> message-length n)
          [:error :diameter/truncated-message]

          :else
          (let [[status avps] (avp/decode-avps (subvec bs header-length message-length))]
            (if (= :error status)
              [:error avps]
              [:ok
               {:diameter.message/request? request?
                :diameter.message/proxiable? proxiable?
                :diameter.message/error? error?
                :diameter.message/retransmitted? retransmitted?
                :diameter.message/reserved-flags reserved-flags
                :diameter.message/command-code command-code
                :diameter.message/application-id application-id
                :diameter.message/hop-by-hop hop-by-hop
                :diameter.message/end-to-end end-to-end
                :diameter.message/avps avps}
               message-length])))))))
