(ns ospf.lsu
  "The Link State Update packet body, OSPF packet type 4, 'LSU' below
  (RFC 2328 Appendix A.3.5).

  Wire layout of the body, quoted:

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                            # LSAs                             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                                                               |
       +-                            LSAs                            +-+
       |                              ...                              |

  and: '# LSAs: The number of LSAs included in this update. ... The body
  of the Link State Update packet consists of a list of LSAs. Each LSA
  begins with a common 20 byte header, described in Section A.4.1.'

  This library treats every LSA body — the bytes of a full LSA beyond its
  20-octet `ospf.lsa` header — as opaque. That's a deliberate scope cut,
  not an oversight: the task is a wire codec for the five OSPF *packet*
  types plus the LSA header all five of them carry, not a decoder for
  every one of the five *LSA* types (router-LSA, network-LSA, two flavors
  of summary-LSA, AS-external-LSA), each of which has its own body
  layout in RFC 2328 Appendix A.4.2 through A.4.5. What this namespace
  gets exactly right is the *framing*: the LSA header's own `:length`
  field (A.4.1: 'length of the complete LSA including header') tells a
  caller precisely how many bytes to walk past to reach the next LSA in
  the list, so a caller that does understand a given LS type can slice
  the opaque body back out and parse it, and a caller that doesn't can
  still walk every LSA in the update to reach the ones it cares about."
  (:require [ospf.bytes :as b]
            [ospf.lsa :as lsa]))

(def count-field-length
  "# LSAs is 4 octets."
  4)

(defn encode
  "`lsas` is a sequence of `{:header <ospf.lsa header map> :body <opaque
  byte sequence>}`. `:header`'s `:length` must already equal
  `(+ ospf.lsa/header-length (count body))` — this namespace does not
  compute it for the caller, since a caller that owns the LSA body is the
  one that knows its length."
  [lsas]
  (vec (concat (b/u32->bytes (count lsas))
               (mapcat (fn [{:keys [header body]}] (concat (lsa/encode header) body))
                       lsas))))

(defn- decode-lsas [bs n]
  (loop [bs bs n n acc []]
    (if (zero? n)
      [:ok {:lsas acc :rest bs}]
      (let [[status result] (lsa/decode bs)]
        (cond
          (= :error status) [:error result]

          (< (get-in result [:header :length]) lsa/header-length)
          [:error :ospf/lsa-length-too-short]

          (> (get-in result [:header :length]) (+ lsa/header-length (count (:rest result))))
          [:error :ospf/lsa-length-exceeds-packet]

          :else
          (let [body-length (- (get-in result [:header :length]) lsa/header-length)
                body (subvec (:rest result) 0 body-length)
                remainder (subvec (:rest result) body-length)]
            (recur remainder (dec n) (conj acc {:header (:header result) :body body}))))))))

(defn decode
  "Decode an LSU body from all of `bs`. Returns `[:ok <vector of
  {:header :body} maps>]` or a named error:
  `:ospf/lsu-too-short` (fewer than 4 octets, or the #LSAs count field
  claims more LSAs than the remaining bytes can possibly hold — each
  needs at least a full 20-octet header),
  `:ospf/lsa-header-too-short` (a truncated header mid-list),
  `:ospf/lsa-length-too-short` (an LSA header's own `:length` field is
  less than 20, which cannot describe a well-formed LSA), or
  `:ospf/lsa-length-exceeds-packet` (that field claims more bytes than
  the packet actually has left), or `:ospf/lsu-trailing-bytes` (bytes
  left over after all #LSAs entries have been consumed — the #LSAs count
  and the actual list disagree)."
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) count-field-length)
      [:error :ospf/lsu-too-short]
      (let [n (b/bytes->u32 (bs 0) (bs 1) (bs 2) (bs 3))
            body (subvec bs count-field-length)]
        (if (> (* n lsa/header-length) (count body))
          [:error :ospf/lsu-too-short]
          (let [[status result] (decode-lsas body n)]
            (cond
              (= :error status) [:error result]
              (seq (:rest result)) [:error :ospf/lsu-trailing-bytes]
              :else [:ok (:lsas result)])))))))
