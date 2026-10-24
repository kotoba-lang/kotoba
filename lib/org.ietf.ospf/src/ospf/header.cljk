(ns ospf.header
  "The 24-octet OSPF packet header common to all five packet types
  (RFC 2328 Appendix A.3.1).

  Wire layout, quoted:

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |   Version #   |     Type      |         Packet length         |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          Router ID                            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                           Area ID                             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |           Checksum            |             AuType            |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                       Authentication                          |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                       Authentication                          |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  and, on the Checksum field specifically:

    'The standard IP checksum of the entire contents of the packet,
    starting with the OSPF packet header but excluding the 64-bit
    authentication field. This checksum is calculated as the 16-bit
    one's complement of the one's complement sum of all the 16-bit words
    in the packet, excepting the authentication field. If the packet's
    length is not an integral number of 16-bit words, the packet is
    padded with a byte of zero before checksumming.'

  This namespace only packs and unpacks the 24 fixed octets; it does not
  compute or check the Checksum field, because that requires the body
  bytes that follow the header (Router ID and Area ID are opaque 32-bit
  identifiers here, not real IP addresses — the task doesn't need IP
  semantics for them, only the field width). `ospf.packet` owns
  assembling header + body and wiring the RFC 1071 checksum from
  `ospf.checksum` across the pair, per the field description above."
  (:require [ospf.bytes :as b]))

(def length
  "The OSPF packet header is 24 octets, RFC 2328 Appendix A.3.1."
  24)

(def version
  "OSPF Version 2, the version this specification (and this codec)
  documents. RFC 2328 Appendix A.3.1: 'The OSPF version number. This
  specification documents version 2 of the protocol.'"
  2)

(def packet-types
  "RFC 2328 Appendix A.3.1's Type table."
  {1 :hello
   2 :database-description
   3 :link-state-request
   4 :link-state-update
   5 :link-state-acknowledgment})

(def type-codes
  "`packet-types` inverted: keyword -> wire code."
  (reduce-kv (fn [m code kw] (assoc m kw code)) {} packet-types))

(defn encode
  "Encode a header map's 24 fixed octets. `:authentication` defaults to
  eight zero bytes (AuType 0, Null authentication, is the only
  authentication scheme this library carries data for without
  validating — RFC 2328 Appendix D.1). `:version` defaults to 2, so
  callers never have to supply it; it is accepted rather than hardcoded
  only so that `decode` — which reports the Version # it actually read,
  since a decoder that silently normalised the field could not tell a
  caller it had been handed something other than OSPFv2 — round-trips
  exactly."
  [{:keys [version type packet-length router-id area-id checksum autype
           authentication]
    :or {version 2 authentication [0 0 0 0 0 0 0 0]}}]
  (vec (concat [(bit-and version 0xFF) (type-codes type)]
               (b/u16->bytes packet-length)
               (b/u32->bytes router-id)
               (b/u32->bytes area-id)
               (b/u16->bytes checksum)
               (b/u16->bytes autype)
               authentication)))

(defn decode
  "Decode the 24-octet header from the front of `bs`. Returns
  `[:ok {:header <map> :rest <bytes after the header>}]` or
  `[:error :ospf/packet-too-short]` (fewer than 24 bytes) or
  `[:error :ospf/unknown-packet-type]` (Type is not 1..5)."
  [bs]
  (let [bs (vec bs)]
    (cond
      (< (count bs) length)
      [:error :ospf/packet-too-short]

      (not (contains? packet-types (bs 1)))
      [:error :ospf/unknown-packet-type]

      :else
      [:ok {:header {:version (bs 0)
                     :type (packet-types (bs 1))
                     :packet-length (b/bytes->u16 (bs 2) (bs 3))
                     :router-id (b/bytes->u32 (bs 4) (bs 5) (bs 6) (bs 7))
                     :area-id (b/bytes->u32 (bs 8) (bs 9) (bs 10) (bs 11))
                     :checksum (b/bytes->u16 (bs 12) (bs 13))
                     :autype (b/bytes->u16 (bs 14) (bs 15))
                     :authentication (subvec bs 16 24)}
             :rest (subvec bs 24)}])))
