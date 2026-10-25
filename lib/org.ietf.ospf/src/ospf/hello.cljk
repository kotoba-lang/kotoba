(ns ospf.hello
  "The Hello packet body, OSPF packet type 1 (RFC 2328 Appendix A.3.2).

  Wire layout of the body (i.e. the bytes after the 24-octet common
  header), quoted:

        0                   1                   2                   3
        0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                        Network Mask                           |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |         HelloInterval         |    Options    |    Rtr Pri    |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                     RouterDeadInterval                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                      Designated Router                        |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                   Backup Designated Router                    |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                          Neighbor                             |
       +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
       |                              ...                              |

  and, on the trailing list: 'Neighbor: The Router IDs of each router
  from whom valid Hello packets have been seen recently on the network.'
  There is no count field for the neighbor list — it runs to the end of
  the packet, four octets (one Router ID) at a time."
  (:require [ospf.bytes :as b]))

(def fixed-length
  "Network Mask (4) + HelloInterval (2) + Options (1) + Rtr Pri (1) +
  RouterDeadInterval (4) + Designated Router (4) + Backup Designated
  Router (4) = 20 octets, before the variable-length neighbor list."
  20)

(defn encode
  [{:keys [network-mask hello-interval options rtr-pri router-dead-interval
           designated-router backup-designated-router neighbors]
    :or {neighbors []}}]
  (vec (concat (b/u32->bytes network-mask)
               (b/u16->bytes hello-interval)
               [(bit-and options 0xFF) (bit-and rtr-pri 0xFF)]
               (b/u32->bytes router-dead-interval)
               (b/u32->bytes designated-router)
               (b/u32->bytes backup-designated-router)
               (mapcat b/u32->bytes neighbors))))

(defn decode
  "Decode a Hello body from all of `bs` (the whole packet body — a Hello
  packet has no trailer after the neighbor list, so unlike the other four
  packet types this doesn't return a `:rest`). Returns `[:ok <map>]` or
  `[:error :ospf/hello-too-short]` (fewer than 20 octets) or
  `[:error :ospf/neighbor-list-misaligned]` (the bytes after the fixed
  part aren't a whole number of 4-octet Router IDs)."
  [bs]
  (let [bs (vec bs)]
    (cond
      (< (count bs) fixed-length)
      [:error :ospf/hello-too-short]

      (not (zero? (mod (- (count bs) fixed-length) 4)))
      [:error :ospf/neighbor-list-misaligned]

      :else
      [:ok {:network-mask (b/bytes->u32 (bs 0) (bs 1) (bs 2) (bs 3))
            :hello-interval (b/bytes->u16 (bs 4) (bs 5))
            :options (bs 6)
            :rtr-pri (bs 7)
            :router-dead-interval (b/bytes->u32 (bs 8) (bs 9) (bs 10) (bs 11))
            :designated-router (b/bytes->u32 (bs 12) (bs 13) (bs 14) (bs 15))
            :backup-designated-router (b/bytes->u32 (bs 16) (bs 17) (bs 18) (bs 19))
            :neighbors (mapv (fn [i]
                                (b/bytes->u32 (bs i) (bs (+ i 1)) (bs (+ i 2)) (bs (+ i 3))))
                              (range fixed-length (count bs) 4))}])))
