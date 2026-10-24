(ns ospf.dd
  "The Database Description packet body, OSPF packet type 2, 'DD' below
  (RFC 2328 Appendix A.3.3).

  Wire layout of the body, quoted:

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |         Interface MTU         |    Options    |0|0|0|0|0|I|M|MS
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     DD sequence number                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     ... (list of LSA headers) ...              |

  and, spelling out the flags byte's bit positions left to right —
  `0 0 0 0 0 I M MS`, i.e. bit 7 (MSB) down to bit 3 are reserved-zero,
  bit 2 is I, bit 1 is M, and bit 0 (LSB) is MS:

    'I-bit: The Init bit. When set to 1, this packet is the first in the
    sequence of Database Description Packets.
    M-bit: The More bit. When set to 1, it indicates that more Database
    Description Packets are to follow.
    MS-bit: The Master/Slave bit. When set to 1, it indicates that the
    router is the master during the Database Exchange process. Otherwise,
    the router is the slave.'

  This diagram is the RFC's own citable source for the bit positions —
  the task explicitly warns not to guess them, and 'guessing' here would
  have meant assuming the more common wire convention of packing the
  first-named flag at the LSB, which is backwards from what the RFC
  actually draws (I is bit 2, not bit 0; MS is bit 0, not bit 2).

  The rest of the packet, after the 8-octet fixed part, is a (possibly
  partial, possibly empty) list of 20-octet `ospf.lsa` headers running to
  the end of the packet — RFC 2328: 'The rest of the packet consists of a
  (possibly partial) list of the link-state database's pieces. Each LSA
  in the database is described by its LSA header.'"
  (:require [ospf.bytes :as b]
            [ospf.lsa :as lsa]))

(def fixed-length
  "Interface MTU (2) + Options (1) + flags (1) + DD sequence number (4) =
  8 octets, before the LSA-header list."
  8)

(def i-bit 0x04)
(def m-bit 0x02)
(def ms-bit 0x01)

(defn- flags-byte [{:keys [init? more? master?]}]
  (bit-or (if init? i-bit 0) (if more? m-bit 0) (if master? ms-bit 0)))

(defn encode
  [{:keys [interface-mtu options dd-sequence-number lsa-headers]
    :or {lsa-headers []}
    :as m}]
  (vec (concat (b/u16->bytes interface-mtu)
               [(bit-and options 0xFF) (flags-byte m)]
               (b/i32->bytes dd-sequence-number)
               (mapcat lsa/encode lsa-headers))))

(defn- decode-lsa-headers
  "Walk `bs` as a run of `ospf.lsa` headers until exhausted. Returns
  `[:ok <vector of header maps>]` or `[:error :ospf/lsa-header-too-short]`
  if a trailing partial header is found (the list is a whole number of
  20-octet headers, or it's malformed)."
  [bs]
  (loop [bs bs acc []]
    (if (empty? bs)
      [:ok acc]
      (let [[status result] (lsa/decode bs)]
        (if (= :error status)
          [:error result]
          (recur (:rest result) (conj acc (:header result))))))))

(defn decode
  "Decode a DD body from all of `bs`. Returns `[:ok <map>]` or
  `[:error :ospf/dd-too-short]` or `[:error :ospf/lsa-header-too-short]`
  (a truncated trailing LSA header)."
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) fixed-length)
      [:error :ospf/dd-too-short]
      (let [flags (bs 3)
            [status headers] (decode-lsa-headers (subvec bs fixed-length))]
        (if (= :error status)
          [:error headers]
          [:ok {:interface-mtu (b/bytes->u16 (bs 0) (bs 1))
                :options (bs 2)
                :init? (not (zero? (bit-and flags i-bit)))
                :more? (not (zero? (bit-and flags m-bit)))
                :master? (not (zero? (bit-and flags ms-bit)))
                :dd-sequence-number (b/bytes->i32 (bs 4) (bs 5) (bs 6) (bs 7))
                :lsa-headers headers}])))))
