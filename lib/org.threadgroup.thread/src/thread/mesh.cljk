(ns thread.mesh
  "6LoWPAN Mesh Addressing header (RFC 4944 §5.2) — carries a hop-by-hop
  originator/final-destination address pair distinct from the IEEE
  802.15.4 MAC frame's own source/destination addresses, so an IPv6
  packet can be link-layer forwarded across several 802.15.4 hops (each
  decrementing `hops-left`) while the *mesh-layer* endpoints stay fixed.
  Thread's routers use this to forward packets they are not themselves
  the final destination of.

  Source: RFC 4944 (IETF, freely published), §5.2:

       0                   1                   2
       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
      |1 0|V|F|HopsLft| originator address, final address
      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

  `V`/`F` select the originator/final address width (16-bit short or
  64-bit extended — see 'Least confident value' below); `HopsLft` is a
  4-bit hop counter, with the reserved value `0xF` meaning 'the real hop
  count does not fit in 4 bits, read it from a Deep Hops Left octet
  appended immediately after the dispatch byte, before the addresses'
  (RFC 4944 §5.2, the 'Deep Hops Left' extension).

  ## Least confident value in this repository

  **The polarity of `V` and `F`.** RFC 4944 states the *existence* of a
  1-bit originator-address-mode flag and a 1-bit final-address-mode flag
  clearly, but this codec's memory of which bit value (0 or 1) selects
  16-bit vs. 64-bit is the single least-attested fact in this library.
  **This implementation's choice, stated so a caller can check it against
  a real capture: `v? true` / `f? true` means the originator/final
  address is the SHORT (16-bit) form; `false` means EXTENDED (64-bit).**
  If a real Thread capture disagrees, only this polarity choice needs to
  flip — the header shape, field order, and Deep Hops Left extension
  around it are independently well-attested (three ways: RFC text, and
  Contiki-NG's `os/net/mac/framer/frame802154.c`-adjacent 6LoWPAN mesh
  code and OpenThread's `src/core/thread/mesh_forwarder.hpp` broadly
  agreeing on the field *set*, if not on a byte-for-byte polarity this
  library could re-verify against.")

(def deep-hops-sentinel 0xF)

(defn- addr-width [short?] (if short? 2 8))

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))
(defn- u64be [n]
  (vec (reverse (loop [x n i 0 acc []]
                  (if (= i 8) acc (recur (quot x 256) (inc i) (conj acc (int (mod x 256)))))))))
(defn- rd-u64be [bs off]
  (reduce (fn [acc b] #?(:clj (+' (*' acc 256) b) :cljs (+ (* acc 256) b)))
          0 (subvec (vec bs) off (+ off 8))))

(def ^:private max-short 0xFFFF)
(def ^:private max-extended 0xFFFFFFFFFFFFFFFF)

(defn- addr-max [short?] (if short? max-short max-extended))

(defn build
  "`{:v? :f? :hops-left :originator-addr :final-addr}` -> `[:ok bytes]` |
  `[:error reason ...]`. `hops-left` above 14 automatically triggers the
  Deep Hops Left extension byte — the caller never sets the sentinel
  0xF directly."
  [{:keys [v? f? hops-left originator-addr final-addr]}]
  (cond
    (not (<= 0 hops-left 0xFF))
    [:error :thread.mesh/hops-left-out-of-range hops-left]

    (not (<= 0 originator-addr (addr-max v?)))
    [:error :thread.mesh/originator-address-out-of-range originator-addr]

    (not (<= 0 final-addr (addr-max f?)))
    [:error :thread.mesh/final-address-out-of-range final-addr]

    :else
    (let [deep? (>= hops-left deep-hops-sentinel)
          hops-field (if deep? deep-hops-sentinel hops-left)
          dispatch (bit-or 0x80
                            (bit-shift-left (if v? 1 0) 5)
                            (bit-shift-left (if f? 1 0) 4)
                            (bit-and hops-field 0x0F))
          pack-addr (fn [short? a] (if short? (u16be a) (u64be a)))]
      [:ok (vec (concat [dispatch]
                         (when deep? [(bit-and hops-left 0xFF)])
                         (pack-addr v? originator-addr)
                         (pack-addr f? final-addr)))])))

(defn parse
  [bs]
  (let [bs (vec bs) n (count bs)]
    (if (< n 1)
      [:error :thread.mesh/header-too-short n]
      (let [b0 (nth bs 0)]
        (if (not= 0x80 (bit-and b0 0xC0))
          [:error :thread.mesh/not-mesh-dispatch b0]
          (let [v? (bit-test b0 5)
                f? (bit-test b0 4)
                hops-field (bit-and b0 0x0F)
                deep? (= hops-field deep-hops-sentinel)
                off (atom 1)
                min-len (+ 1 (if deep? 1 0) (addr-width v?) (addr-width f?))]
            (if (< n min-len)
              [:error :thread.mesh/header-too-short n]
              (let [hops-left (if deep? (let [v (nth bs @off)] (swap! off inc) v) hops-field)
                    take-addr! (fn [short?]
                                 (let [w (addr-width short?)
                                       v (if short? (rd-u16be bs @off) (rd-u64be bs @off))]
                                   (swap! off + w) v))
                    originator-addr (take-addr! v?)
                    final-addr (take-addr! f?)]
                [:ok {:v? v? :f? f? :hops-left hops-left
                      :originator-addr originator-addr :final-addr final-addr}
                 @off]))))))))
