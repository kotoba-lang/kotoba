(ns afdx.udp
  "The UDP header (RFC 768) AFDX application data rides inside, below the
  IPv4 header `afdx.ipv4` builds. Also a freely published IETF standard —
  cited with confidence, unlike `afdx.vl`'s MAC-address convention.

  The UDP checksum is computed over a 'pseudo-header' (source IP,
  destination IP, protocol, UDP length — fields that belong to the IP
  layer, not UDP, but are folded into UDP's checksum anyway per RFC 768
  so a misrouted or protocol-confused datagram is caught even though
  those bytes never appear on the wire as part of the UDP segment
  itself) followed by the real UDP header and payload. RFC 768 also
  permits an all-zero UDP checksum meaning 'not computed' — `encode`
  takes an explicit `:checksum?` flag rather than silently defaulting to
  either behaviour."
  (:require [afdx.bytes :as b]))

(def header-length 8)

(defn- pseudo-header
  [src-ip dst-ip udp-length]
  (-> (vec src-ip) (into dst-ip) (conj 0 17) (into (b/u16be udp-length))))

(defn encode
  "`{:src-port :dst-port :payload [octets] :src-ip [4] :dst-ip [4]
  :checksum? bool}` -> `[:ok bytes]`, the 8-octet UDP header + payload.
  `:checksum?` defaults to true; when false the checksum field is 0 (RFC
  768's 'no checksum computed' convention) and `:src-ip`/`:dst-ip` are
  not required."
  [{:keys [src-port dst-port payload src-ip dst-ip checksum?] :or {checksum? true}}]
  (let [udp-length (+ header-length (count payload))]
    (cond
      (not (<= 0 src-port 0xFFFF)) [:error :afdx/port-out-of-range src-port]
      (not (<= 0 dst-port 0xFFFF)) [:error :afdx/port-out-of-range dst-port]
      :else
      (let [header-sans-checksum
            (-> (b/u16be src-port) (into (b/u16be dst-port)) (into (b/u16be udp-length)) (into [0 0]))
            segment-sans-checksum (into header-sans-checksum payload)
            checksum (if checksum?
                       (let [with-pseudo (into (pseudo-header src-ip dst-ip udp-length)
                                                segment-sans-checksum)
                             c (b/checksum16 with-pseudo)]
                         ;; RFC 768: a computed checksum of exactly 0 is
                         ;; transmitted as all-ones, because all-zero on
                         ;; the wire means "no checksum" — 0 and "no
                         ;; checksum" would otherwise be indistinguishable.
                         (if (zero? c) 0xFFFF c))
                       0)]
        [:ok (-> (subvec header-sans-checksum 0 6) (into (b/u16be checksum)) (into payload))]))))

(defn decode
  "`bytes` (+ `src-ip`/`dst-ip` from the IPv4 header, needed for checksum
  verification) -> `[:ok {:src-port :dst-port :length :checksum
  :payload}]`.

  `[:error :afdx/frame-too-short {:length n :minimum 8}]`,
  `[:error :afdx/udp-length-mismatch {:declared :available}]`,
  `[:error :afdx/udp-checksum-mismatch {:verify-sum n}]` — skipped when
  the declared checksum is 0 (RFC 768's 'not computed')."
  [bytes src-ip dst-ip]
  (let [bs (vec bytes) n (count bs)]
    (if (< n header-length)
      [:error :afdx/frame-too-short {:length n :minimum header-length}]
      (let [udp-length (b/rd-u16be bs 4)
            declared-checksum (b/rd-u16be bs 6)]
        (cond
          (> udp-length n) [:error :afdx/udp-length-mismatch {:declared udp-length :available n}]

          (and (pos? declared-checksum)
               (not= 0 (b/checksum16 (into (pseudo-header src-ip dst-ip udp-length)
                                            (subvec bs 0 udp-length)))))
          [:error :afdx/udp-checksum-mismatch
           {:verify-sum (b/checksum16 (into (pseudo-header src-ip dst-ip udp-length)
                                             (subvec bs 0 udp-length)))}]

          :else
          [:ok {:src-port (b/rd-u16be bs 0) :dst-port (b/rd-u16be bs 2)
                :length udp-length :checksum declared-checksum
                :payload (subvec bs header-length udp-length)}])))))
