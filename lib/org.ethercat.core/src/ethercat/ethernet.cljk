(ns ethercat.ethernet
  "The raw-Ethernet envelope EtherCAT frames ride in — EtherType `0x88A4`
  (`ethercat.frame/ethertype`), no IP, no UDP, addressed by MAC only.
  Same shape as `ch-iec-61850`'s `iec61850.appdu` envelope (dst MAC / src
  MAC / optional 802.1Q tag / EtherType / payload, no FCS — the NIC's
  job, not this library's) since both are 'a fieldbus protocol running
  directly over Ethernet frames', but EtherCAT's payload right after the
  EtherType is `ethercat.frame`'s 2-byte header followed by one or more
  `ethercat.datagram`s, not a BER PDU.

  A real EtherCAT segment's frame carries an *additional* per-slave
  detail this namespace does not attempt to reproduce: the master's
  outgoing frame's source MAC has its multicast bit set (the
  well-known `broadcast look-alike` trick EtherCAT uses so any device
  that is not fully cut-through-aware will still forward it), and the
  destination MAC is conventionally `FF:FF:FF:FF:FF:FF`. This namespace
  packs/unpacks whatever `:dst-mac`/`:src-mac` the caller supplies rather
  than hard-coding those conventions, the same choice `iec61850.appdu`
  makes.")

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))

(defn encode
  "`{:dst-mac [6] :src-mac [6] :vlan {:pcp :dei :vid} (optional)
  :ethertype :payload [bytes]}` -> the full frame as a vector of octets
  (no FCS). `:payload` is `ethercat.frame`'s 2-byte header + datagrams,
  already assembled — this namespace has no opinion on what is inside
  it, mirroring `iec61850.appdu`."
  [{:keys [dst-mac src-mac vlan ethertype payload]}]
  (cond
    (not= 6 (count dst-mac)) [:error :ethercat/bad-mac {:which :dst}]
    (not= 6 (count src-mac)) [:error :ethercat/bad-mac {:which :src}]
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
               (into payload))])))

(defn decode
  "The frame -> `[:ok {:dst-mac :src-mac :vlan (or nil) :ethertype
  :payload}]`, or `[:error kw data]`."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 14)
      [:error :ethercat/frame-too-short {:length n :minimum 14}]
      (let [dst (subvec bs 0 6)
            src (subvec bs 6 12)
            tagged? (and (= 0x81 (nth bs 12)) (= 0x00 (nth bs 13)))
            et-off (if tagged? 16 12)
            vlan (when tagged?
                   (let [tci (rd-u16be bs 14)]
                     {:pcp (bit-and (unsigned-bit-shift-right tci 13) 0x7)
                      :dei (pos? (bit-and tci 0x1000))
                      :vid (bit-and tci 0xFFF)}))]
        (if (< n (+ et-off 2))
          [:error :ethercat/frame-too-short {:length n :minimum (+ et-off 2)}]
          [:ok {:dst-mac dst :src-mac src :vlan vlan
                :ethertype (rd-u16be bs et-off)
                :payload (subvec bs (+ et-off 2) n)}])))))
