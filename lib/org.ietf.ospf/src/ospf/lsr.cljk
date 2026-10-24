(ns ospf.lsr
  "The Link State Request packet body, OSPF packet type 3, 'LSR' below
  (RFC 2328 Appendix A.3.4).

  Wire layout of the body, quoted:

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          LS type                              |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                       Link State ID                           |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     Advertising Router                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                              ...                              |

  Note LS type here is drawn as a full 32-bit row of its own — unlike the
  `ospf.lsa` header, where LS type shares a row with LS age and Options
  and is one octet. This is the RFC's own diagram, not a transcription
  error: an LSR entry names the LSA being requested by (LS type, Link
  State ID, Advertising Router), each a full 4-octet field, 12 octets per
  entry, and the body is that triple repeated with no count field (it
  runs to the end of the packet, same shape as the Hello neighbor list).
  RFC 2328: 'Each LSA requested is specified by its LS type, Link State
  ID, and Advertising Router.'"
  (:require [ospf.bytes :as b]))

(def entry-length
  "LS type (4) + Link State ID (4) + Advertising Router (4) = 12 octets."
  12)

(defn encode
  [entries]
  (vec (mapcat (fn [{:keys [ls-type link-state-id advertising-router]}]
                 (concat (b/u32->bytes ls-type)
                         (b/u32->bytes link-state-id)
                         (b/u32->bytes advertising-router)))
               entries)))

(defn decode
  "Decode an LSR body from all of `bs`. Returns `[:ok <vector of maps>]`
  or `[:error :ospf/lsr-misaligned]` when the body isn't a whole number
  of 12-octet entries."
  [bs]
  (let [bs (vec bs)]
    (if (not (zero? (mod (count bs) entry-length)))
      [:error :ospf/lsr-misaligned]
      [:ok (mapv (fn [i]
                   {:ls-type (b/bytes->u32 (bs i) (bs (+ i 1)) (bs (+ i 2)) (bs (+ i 3)))
                    :link-state-id (b/bytes->u32 (bs (+ i 4)) (bs (+ i 5)) (bs (+ i 6)) (bs (+ i 7)))
                    :advertising-router (b/bytes->u32 (bs (+ i 8)) (bs (+ i 9)) (bs (+ i 10)) (bs (+ i 11)))})
                 (range 0 (count bs) entry-length))])))
