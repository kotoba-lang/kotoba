(ns afdx.ipv4
  "The IPv4 header (RFC 791 §3.1) AFDX carries UDP inside. Unlike
  `afdx.vl`'s destination-MAC convention, this namespace rests on a
  freely published IETF standard, not a paywalled ARINC document — the
  field layout and checksum algorithm here are cited with confidence.

  No options (IHL is always 5, a 20-octet header) — AFDX end systems
  do not use IP options, and supporting them would add a variable-length
  field this library's callers have no use for.

  ```
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |Version|  IHL  |Type of Service|          Total Length        |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |         Identification       |Flags|      Fragment Offset    |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |  Time to Live |    Protocol   |         Header Checksum       |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                       Source Address                          |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  |                    Destination Address                        |
  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
  ```"
  (:require [afdx.bytes :as b]))

(def header-length 20)
(def protocol-udp 17)

(defn encode
  "`{:tos :identification :flags :fragment-offset :ttl :protocol
  :src-ip [4] :dst-ip [4] :payload [octets]}` -> `[:ok bytes]`, the
  20-octet header (checksum computed over it, field set to 0 during that
  computation per RFC 1071) followed by `:payload`.

  `:tos` `:identification` `:flags` `:fragment-offset` `:protocol`
  default to 0/0/0/0/`protocol-udp` — AFDX traffic is UDP, and every
  other field here is administrative rather than AFDX-specific.
  `:ttl` has no library default: a caller should decide it, not inherit
  one silently. Total Length is computed from `(+ header-length (count
  payload))`, never taken from the caller."
  [{:keys [tos identification flags fragment-offset ttl protocol src-ip dst-ip payload]
    :or {tos 0 identification 0 flags 0 fragment-offset 0 protocol protocol-udp}}]
  (cond
    (not= 4 (count src-ip)) [:error :afdx/bad-ip {:which :src :length (count src-ip)}]
    (not= 4 (count dst-ip)) [:error :afdx/bad-ip {:which :dst :length (count dst-ip)}]
    (not (<= 0 ttl 255)) [:error :afdx/ttl-out-of-range ttl]
    :else
    (let [total-length (+ header-length (count payload))
          flags+frag (bit-or (bit-shift-left (bit-and flags 0x7) 13)
                              (bit-and fragment-offset 0x1FFF))
          header-sans-checksum
          (-> [0x45 (bit-and tos 0xFF)]
              (into (b/u16be total-length))
              (into (b/u16be identification))
              (into (b/u16be flags+frag))
              (conj (bit-and ttl 0xFF) (bit-and protocol 0xFF) 0 0)
              (into src-ip)
              (into dst-ip))
          checksum (b/checksum16 header-sans-checksum)
          header (-> (subvec header-sans-checksum 0 10)
                     (into (b/u16be checksum))
                     (into (subvec header-sans-checksum 12 20)))]
      [:ok (into header payload)])))

(defn decode
  "`bytes` -> `[:ok {:version :ihl :tos :total-length :identification
  :flags :fragment-offset :ttl :protocol :checksum :src-ip :dst-ip
  :payload}]`.

  `[:error :afdx/frame-too-short {:length n :minimum 20}]`,
  `[:error :afdx/not-ipv4 version]` if the version nibble is not 4,
  `[:error :afdx/ip-options-unsupported ihl]` if IHL is not 5 (this
  namespace does not parse options),
  `[:error :afdx/ipv4-checksum-mismatch {:computed :declared}]`,
  `[:error :afdx/ipv4-length-mismatch {:declared :available}]`."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (cond
      (< n header-length) [:error :afdx/frame-too-short {:length n :minimum header-length}]

      :else
      (let [version (bit-and (unsigned-bit-shift-right (nth bs 0) 4) 0xF)
            ihl (bit-and (nth bs 0) 0xF)]
        (cond
          (not= 4 version) [:error :afdx/not-ipv4 version]
          (not= 5 ihl) [:error :afdx/ip-options-unsupported ihl]

          :else
          (let [verify-sum (b/checksum16 (subvec bs 0 header-length))]
            (if (not= 0 verify-sum)
              [:error :afdx/ipv4-checksum-mismatch
               {:declared (b/rd-u16be bs 10) :verify-sum verify-sum}]
              (let [total-length (b/rd-u16be bs 2)
                    flags+frag (b/rd-u16be bs 6)]
                (if (> total-length n)
                  [:error :afdx/ipv4-length-mismatch {:declared total-length :available n}]
                  [:ok {:version version :ihl ihl :tos (nth bs 1)
                        :total-length total-length
                        :identification (b/rd-u16be bs 4)
                        :flags (bit-and (unsigned-bit-shift-right flags+frag 13) 0x7)
                        :fragment-offset (bit-and flags+frag 0x1FFF)
                        :ttl (nth bs 8) :protocol (nth bs 9)
                        :checksum (b/rd-u16be bs 10)
                        :src-ip (subvec bs 12 16) :dst-ip (subvec bs 16 20)
                        :payload (subvec bs header-length total-length)}])))))))))
