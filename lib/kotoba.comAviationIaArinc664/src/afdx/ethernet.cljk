(ns afdx.ethernet
  "The Ethernet II header AFDX rides on: 6-octet destination MAC, 6-octet
  source MAC, 2-octet EtherType. No 802.1Q tag, no FCS — AFDX end systems
  send untagged frames (VL separation is carried in the destination MAC,
  see `afdx.vl`, not a VLAN tag) and the Frame Check Sequence is the
  NIC's job, not a software codec's."
  (:require [afdx.bytes :as b]))

(def ethertype-ipv4 0x0800)

(defn encode
  "`{:dst-mac [6 octets] :src-mac [6 octets] :ethertype n :payload
  [octets]}` -> `[:ok bytes]`, `[:error :afdx/bad-mac {:which :dst/:src
  :length n}]` if either MAC is not exactly 6 octets."
  [{:keys [dst-mac src-mac ethertype payload]}]
  (cond
    (not= 6 (count dst-mac)) [:error :afdx/bad-mac {:which :dst :length (count dst-mac)}]
    (not= 6 (count src-mac)) [:error :afdx/bad-mac {:which :src :length (count src-mac)}]
    :else
    [:ok (-> (vec dst-mac) (into src-mac) (into (b/u16be ethertype)) (into payload))]))

(defn decode
  "`bytes` -> `[:ok {:dst-mac :src-mac :ethertype :payload}]`, or
  `[:error :afdx/frame-too-short {:length n :minimum 14}]`."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 14)
      [:error :afdx/frame-too-short {:length n :minimum 14}]
      [:ok {:dst-mac (subvec bs 0 6)
            :src-mac (subvec bs 6 12)
            :ethertype (b/rd-u16be bs 12)
            :payload (subvec bs 14 n)}])))
