(ns afdx.frame
  "The full AFDX frame: Ethernet (`afdx.ethernet`) + IPv4 (`afdx.ipv4`) +
  UDP (`afdx.udp`) + application data + a trailing 1-octet Sequence
  Number (`afdx.sequence`).

  **Provenance note on the SN's position**: that the AFDX Sequence Number
  is appended as the LAST octet of the UDP payload — after the
  application data, still inside the UDP datagram — rather than being a
  separate protocol field of its own, is reconstructed from public AFDX
  tutorials/overview papers, same caveat as `afdx.vl`. Everything below
  the trailing SN byte (Ethernet/IPv4/UDP) rests on freely published IETF
  RFCs, not on that reconstruction.

  This namespace's `encode`/`decode` compose the four layers; it does
  not duplicate any of their field logic."
  (:require [afdx.ethernet :as eth]
            [afdx.ipv4 :as ipv4]
            [afdx.udp :as udp]
            [afdx.vl :as vl]
            [afdx.sequence :as afdx-sn]))

(defn encode
  "`{:vl-id :src-mac [6] :src-ip [4] :dst-ip [4] :src-port :dst-port
  :application-data [octets] :sn 1-255 :ttl}` -> `[:ok bytes]`, a
  complete AFDX frame ready to hand to a NIC (which supplies its own
  preamble/FCS — not this library's job).

  The destination MAC is derived from `:vl-id` (`afdx.vl/vl-id->dst-mac`)
  — callers do not supply it directly, so a frame's VL and its
  destination address cannot silently disagree. `:ttl` defaults to 1
  (AFDX traffic does not cross IP routers in the ARINC 664 P7 profile;
  callers with a real reason to route further can override it)."
  [{:keys [vl-id src-mac src-ip dst-ip src-port dst-port application-data sn ttl]
    :or {ttl 1}}]
  (let [[vs dst-mac] (vl/vl-id->dst-mac vl-id)]
    (cond
      (= :error vs) [vs dst-mac]
      (not (afdx-sn/valid-sn? sn)) [:error :afdx/sn-out-of-range sn]
      :else
      (let [udp-payload (conj (vec application-data) sn)
            [us udp-bytes] (udp/encode {:src-port src-port :dst-port dst-port
                                        :payload udp-payload :src-ip src-ip :dst-ip dst-ip})]
        (if (= :error us)
          [us udp-bytes]
          (let [[is ip-bytes] (ipv4/encode {:ttl ttl :src-ip src-ip :dst-ip dst-ip :payload udp-bytes})]
            (if (= :error is)
              [is ip-bytes]
              (eth/encode {:dst-mac dst-mac :src-mac src-mac
                           :ethertype eth/ethertype-ipv4 :payload ip-bytes}))))))))

(defn decode
  "The inverse of `encode`: `bytes` -> `[:ok {:vl-id :src-mac :dst-mac
  :src-ip :dst-ip :src-port :dst-port :application-data :sn :ttl}]`, or
  the first layer's `[:error ...]` — Ethernet, then IPv4, then UDP, then
  the trailing-SN split — whichever fails first."
  [bytes]
  (let [[es {:keys [dst-mac src-mac ethertype payload] :as eth-r}] (eth/decode bytes)]
    (cond
      (= :error es) [es eth-r]
      (not= eth/ethertype-ipv4 ethertype) [:error :afdx/not-ipv4-ethertype ethertype]
      :else
      (let [[is {:keys [ttl src-ip dst-ip payload] :as ip-r}] (ipv4/decode payload)]
        (cond
          (= :error is) [is ip-r]
          (not= ipv4/protocol-udp (:protocol ip-r)) [:error :afdx/not-udp-protocol (:protocol ip-r)]
          :else
          (let [[us {:keys [src-port dst-port payload] :as udp-r}] (udp/decode payload src-ip dst-ip)]
            (cond
              (= :error us) [us udp-r]
              (empty? payload) [:error :afdx/udp-payload-empty payload]
              :else
              (let [sn (last payload)
                    application-data (vec (butlast payload))]
                (if-not (afdx-sn/valid-sn? sn)
                  [:error :afdx/sn-out-of-range sn]
                  (let [[vs vl-id] (vl/dst-mac->vl-id dst-mac)]
                    (if (= :error vs)
                      [vs vl-id]
                      [:ok {:vl-id vl-id :src-mac src-mac :dst-mac dst-mac
                            :src-ip src-ip :dst-ip dst-ip
                            :src-port src-port :dst-port dst-port
                            :application-data application-data :sn sn :ttl ttl}])))))))))))
