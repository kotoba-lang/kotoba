(ns ospf.packet
  "The full OSPF packet: the 24-octet `ospf.header` plus one of the five
  packet-type bodies, with the RFC 1071 checksum (`ospf.checksum`) wired
  across the pair the way RFC 2328 Appendix A.3.1 specifies it.

  This is the only namespace that computes or checks the Checksum field,
  because doing so needs both the header and the body bytes at once —
  RFC 2328, quoted on `ospf.header` too: 'The standard IP checksum of the
  entire contents of the packet, starting with the OSPF packet header but
  excluding the 64-bit authentication field.' Concretely: the checksum
  covers the first 16 octets of the header (Version # through AuType —
  everything up to but not including the 8-octet Authentication field)
  followed by the whole body, with the Checksum field itself included at
  its normal offset (RFC 1071 §2's generate-with-field-zeroed /
  verify-with-field-as-received symmetry, see `ospf.checksum`).

  This library implements no authentication scheme (AuType 1's simple
  password, AuType 2's cryptographic/MD5 authentication in RFC 2328
  Appendix D) — `:authentication` is carried through as opaque bytes on
  both encode and decode, and `decode-packet` always validates the
  Checksum field regardless of AuType, even though the RFC allows some
  authentication types to omit that check ('The checksum is considered
  to be part of the packet authentication procedure; for some
  authentication types the checksum calculation is omitted.'). A codec
  with no authentication implementation has no basis to selectively skip
  the one integrity check it does have."
  (:require [ospf.bytes :as b]
            [ospf.checksum :as checksum]
            [ospf.dd :as dd]
            [ospf.header :as header]
            [ospf.hello :as hello]
            [ospf.lsack :as lsack]
            [ospf.lsr :as lsr]
            [ospf.lsu :as lsu]))

(def ^:private body-codecs
  {:hello [hello/encode hello/decode]
   :database-description [dd/encode dd/decode]
   :link-state-request [lsr/encode lsr/decode]
   :link-state-update [lsu/encode lsu/decode]
   :link-state-acknowledgment [lsack/encode lsack/decode]})

;; The 16 octets the checksum covers out of the 24-octet header: Version #
;; (1) + Type (1) + Packet length (2) + Router ID (4) + Area ID (4) +
;; Checksum (2) + AuType (2) = 16, stopping just before Authentication.
(def ^:private checksummed-header-length 16)

(defn- checksummed-prefix
  "The 16 octets `ospf.checksum` needs from the header — Version # through
  AuType, with `checksum-value` at the Checksum field's offset — never
  the Authentication field, which the RFC excludes from the sum
  regardless of its content. Building the full 24-octet header via
  `header/encode` and then taking the first 16 keeps this namespace from
  ever having to duplicate the header's own field layout."
  [header type packet-length checksum-value]
  (vec (take checksummed-header-length
             (header/encode (assoc header
                                    :type type
                                    :packet-length packet-length
                                    :checksum checksum-value)))))

(defn encode
  "Encode `{:type :header {...} :body {...}}` (`:header` need not include
  `:packet-length` or `:checksum` — both are computed here) to the full
  wire byte sequence. `:body` is passed straight to the encoder for
  `:type` (`ospf.hello/encode`, `ospf.dd/encode`, ...); its shape is
  whatever that namespace's docstring says.

  Returns `{:bytes <full packet>}`, or `[:error :ospf/unknown-packet-type]`
  if `:type` isn't one of the five in `body-codecs`."
  [{:keys [type header body]}]
  (if-let [[encode-body _] (body-codecs type)]
    (let [body-bytes (vec (encode-body body))
          packet-length (+ header/length (count body-bytes))
          checksum-input (concat (checksummed-prefix header type packet-length 0)
                                  body-bytes)
          cs (checksum/checksum checksum-input)
          full-header (header/encode (assoc header :type type
                                             :packet-length packet-length
                                             :checksum cs))]
      {:bytes (vec (concat full-header body-bytes))})
    [:error :ospf/unknown-packet-type]))

(defn decode
  "Decode a full OSPF packet from `bs`. Returns `[:ok {:header <map>
  :body <decoded body>}]`, or `[:error <reason>]` where `<reason>` is
  one of:

  `:ospf/packet-too-short` — fewer than 24 bytes (can't even hold the
  common header), or fewer bytes total than the header's own
  `:packet-length` field claims.
  `:ospf/unknown-packet-type` — Type is not 1..5 (from `ospf.header`).
  `:ospf/unsupported-version` — Version # is not 2; this codec is
  OSPFv2-only, per RFC 2328 Appendix A.3.1's own description of the
  field.
  `:ospf/length-mismatch` — `:packet-length` doesn't equal the number of
  bytes actually present (after truncating to that many bytes, in case
  `bs` holds a longer buffer with more packets after this one).
  `:ospf/checksum-mismatch` — the RFC 1071 checksum doesn't verify.
  Anything the body decoder for that packet type can return, e.g.
  `:ospf/neighbor-list-misaligned`, `:ospf/lsr-misaligned`,
  `:ospf/lsa-header-too-short`, `:ospf/lsu-trailing-bytes`."
  [bs]
  (let [bs (vec bs)
        [status result] (header/decode bs)]
    (cond
      (= :error status)
      [:error result]

      (not= header/version (get-in result [:header :version]))
      [:error :ospf/unsupported-version]

      (> (get-in result [:header :packet-length]) (count bs))
      [:error :ospf/packet-too-short]

      (< (get-in result [:header :packet-length]) header/length)
      [:error :ospf/length-mismatch]

      :else
      (let [pkt-len (get-in result [:header :packet-length])
            packet (subvec bs 0 pkt-len)
            checksum-input (concat (subvec packet 0 checksummed-header-length)
                                    (subvec packet header/length))]
        (if (not (checksum/valid? checksum-input))
          [:error :ospf/checksum-mismatch]
          (let [type (get-in result [:header :type])
                [_ decode-body] (body-codecs type)
                body-bytes (subvec packet header/length)
                [bstatus bresult] (decode-body body-bytes)]
            (if (= :error bstatus)
              [:error bresult]
              [:ok {:header (:header result) :body bresult}])))))))
