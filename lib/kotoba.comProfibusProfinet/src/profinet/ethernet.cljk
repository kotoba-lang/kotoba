(ns profinet.ethernet
  "The raw-Ethernet envelope PROFINET RT frames ride in — EtherType
  `0x8892`, no IP, no UDP, addressed by MAC (and, for cyclic RT data,
  usually multicast MACs derived from a configured 'MAC Address' DCP
  block — see `profinet.dcp`'s `ip-suboptions`). Same shape as
  `ch-iec-61850`'s `iec61850.appdu` and `org-ethercat`'s
  `ethercat.ethernet` (dst MAC / src MAC / optional 802.1Q tag /
  EtherType / payload, no FCS — the NIC's job), but PROFINET's payload
  right after the EtherType is `profinet.rt`'s big-endian FrameID
  followed by either cyclic data (`profinet.rt/encode-cyclic-data`) or a
  DCP PDU (`profinet.dcp/encode-pdu`), never a BER PDU or an EtherCAT
  datagram chain.")

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))

(def ethertype 0x8892)

(defn encode
  "`{:dst-mac [6] :src-mac [6] :vlan {:pcp :dei :vid} (optional)
  :frame-id 0..65535 :payload [bytes]}` -> `[:ok bytes]`, the full frame
  (no FCS). `:frame-id` is packed here (big-endian, per `profinet.rt`)
  rather than left to the caller to prepend, since it always immediately
  follows the EtherType in every PROFINET RT frame."
  [{:keys [dst-mac src-mac vlan frame-id payload]}]
  (cond
    (not= 6 (count dst-mac)) [:error :profinet/bad-mac {:which :dst}]
    (not= 6 (count src-mac)) [:error :profinet/bad-mac {:which :src}]
    (not (<= 0 frame-id 0xFFFF)) [:error :profinet/frame-id-out-of-range frame-id]
    :else
    (let [vlan-octets (when vlan
                         (let [tci (bit-or (bit-shift-left (bit-and (:pcp vlan 0) 0x7) 13)
                                           (bit-shift-left (if (:dei vlan) 1 0) 12)
                                           (bit-and (:vid vlan 0) 0xFFF))]
                           (into [0x81 0x00] (u16be tci))))]
      [:ok (-> (vec dst-mac)
               (into src-mac)
               (into vlan-octets)
               (into (u16be ethertype))
               (into (u16be frame-id))
               (into payload))])))

(defn decode
  "The frame -> `[:ok {:dst-mac :src-mac :vlan (or nil) :ethertype
  :frame-id :payload}]`, or `[:error kw data]`."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 16)
      [:error :profinet/frame-too-short {:length n :minimum 16}]
      (let [dst (subvec bs 0 6)
            src (subvec bs 6 12)
            tagged? (and (= 0x81 (nth bs 12)) (= 0x00 (nth bs 13)))
            et-off (if tagged? 16 12)
            vlan (when tagged?
                   (let [tci (rd-u16be bs 14)]
                     {:pcp (bit-and (unsigned-bit-shift-right tci 13) 0x7)
                      :dei (pos? (bit-and tci 0x1000))
                      :vid (bit-and tci 0xFFF)}))]
        (if (< n (+ et-off 4))
          [:error :profinet/frame-too-short {:length n :minimum (+ et-off 4)}]
          [:ok {:dst-mac dst :src-mac src :vlan vlan
                :ethertype (rd-u16be bs et-off)
                :frame-id (rd-u16be bs (+ et-off 2))
                :payload (subvec bs (+ et-off 4) n)}])))))
