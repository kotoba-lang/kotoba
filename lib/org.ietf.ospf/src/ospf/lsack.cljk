(ns ospf.lsack
  "The Link State Acknowledgment packet body, OSPF packet type 5, 'LSAck'
  below (RFC 2328 Appendix A.3.6).

  RFC 2328: 'The format of this packet is similar to that of the Data[base]
  Description packet. The body of both packets is simply a list of LSA
  headers.' Unlike the DD packet, there is no fixed-length prefix before
  the list — the body is nothing but a run of `ospf.lsa` headers, one per
  acknowledged LSA, to the end of the packet."
  (:require [ospf.lsa :as lsa]))

(defn encode [headers] (vec (mapcat lsa/encode headers)))

(defn decode
  "Decode an LSAck body from all of `bs`. Returns `[:ok <vector of
  header maps>]` or `[:error :ospf/lsa-header-too-short]` for a
  truncated trailing header."
  [bs]
  (loop [bs (vec bs) acc []]
    (if (empty? bs)
      [:ok acc]
      (let [[status result] (lsa/decode bs)]
        (if (= :error status)
          [:error result]
          (recur (:rest result) (conj acc (:header result))))))))
