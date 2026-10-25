(ns thread.iphc
  "LOWPAN_IPHC — RFC 6282's IPv6 header compression, the part of 6LoWPAN
  this repository exists for. An uncompressed IPv6 header is 40 bytes;
  an IEEE 802.15.4 payload is on the order of 100 bytes total. IPHC
  elides everything a compressor can either derive from context (the
  version — IPv6 is the only thing 6LoWPAN carries, so it is never
  written down at all) or reconstruct from a small amount of state
  (traffic class/flow label mode bits, a stateless or stateful address
  compression scheme keyed off link-local/context prefixes and the
  link-layer address).

  Source: RFC 6282 (IETF, freely published), primarily §3.1 (the 2-byte
  LOWPAN_IPHC dispatch and field-presence rules), §3.1.1 (Traffic Class
  and Flow Label), §3.2.1-3.2.2 (stateless/stateful unicast address
  compression and the link-local/context prefix + Interface Identifier
  reconstruction) and §3.2.3 (stateless multicast address compression).
  This is the RFC this task's own instructions name as the part of this
  workspace's IoT trio that is 'freely published... with real worked
  examples' — the highest-confidence provenance of the three repositories
  built alongside this one.

  ## The 16-bit LOWPAN_IPHC dispatch (byte0 . byte1, both on the wire):

    byte0: 0 1 1 |  TF   | NH | HLIM  |
    byte1: CID | SAC |  SAM  | M | DAC |  DAM  |

    TF (Traffic Class / Flow Label, 2 bits) — see `pack-tf`/`unpack-tf`
    NH (Next Header, 1 bit): 0 = an inline Next Header octet follows;
       1 = the next header is compressed via LOWPAN_NHC, which this
       library does not decode (see README 'Not here') — `:payload`
       is handed back to the caller starting at whatever LOWPAN_NHC or
       payload bytes follow the addresses, undecoded.
    HLIM (Hop Limit, 2 bits): 00 inline (1 octet) / 01 = 1 / 10 = 64 /
       11 = 255
    CID (Context Identifier Extension, 1 bit): if 1, one extra octet
       (SCI in bits 7-4, DCI in bits 3-0) follows byte1
    SAC/SAM: source address compression (stateless/stateful) and mode
    M/DAC/DAM: multicast flag, destination address compression
       (stateless/stateful) and mode

  Field order on the wire, matching the order RFC 6282 §3.1 lists them
  in: `[byte0 byte1] [CID octet if CID=1] [TF octets] [NH octet if NH=0]
  [HLIM octet if HLIM=00] [source-address inline octets]
  [destination-address inline octets] [rest]`.

  ## Scope inside address compression

  Implemented: stateless (SAC=0/DAC=0) unicast compression against the
  link-local prefix fe80::/64, stateful (SAC=1/DAC=1) unicast compression
  against a caller-supplied 64-bit context prefix, and stateless
  (DAC=0) multicast compression (all four DAM forms). **Not
  implemented: stateful (DAC=1) multicast compression** — RFC 6282
  §3.2.3's context-based multicast form is the one address-compression
  corner this library does not cover; `encode`/`decode` return
  `[:error :thread.iphc/multicast-context-compression-not-implemented]`
  for `m? true dac? true` rather than silently mishandling it.

  `encode` **refuses to elide an address it cannot losslessly
  reconstruct** — every `pack-*-address` function checks the requested
  compression mode against the actual address bytes and returns
  `:thread.iphc/address-not-elidable` rather than silently truncating a
  128-bit address a caller mistakenly believes fits the requested mode.")

;; ── shared byte helpers (IPv6/6LoWPAN fields are BIG-endian — the
;;    opposite convention from the little-endian IEEE 802.15.4 MAC frame
;;    this payload rides inside; see README) ────────────────────────────

(defn- zero16 [] (vec (repeat 16 0)))
(defn- link-local-prefix [] [0xFE 0x80 0 0 0 0 0 0])
(def ^:private nhc-fixed [0x00 0x00 0x00 0xFF 0xFE 0x00])

(defn- iid-from-link-layer
  "8-byte Interface Identifier derived from a link-layer address (RFC
  4291 App. A 'Modified EUI-64' for a 64-bit address — flip the
  Universal/Local bit, byte 0 XOR 0x02 — or the 6LoWPAN short-address
  convention `0000:00FF:FE00:XXXX` for a 16-bit one)."
  [ll-bytes]
  (let [ll (vec ll-bytes)]
    (case (count ll)
      2 (vec (concat nhc-fixed ll))
      8 (vec (cons (bit-xor (first ll) 0x02) (rest ll)))
      nil)))

;; ── Traffic Class / Flow Label (RFC 6282 §3.1.1) ───────────────────────

(def tf-modes {:full 0 :flow-only 1 :tc-only 2 :elided 3})
(def tf-mode-by-code (into {} (map (fn [[k v]] [v k]) tf-modes)))
(def tf-length {:full 4 :flow-only 3 :tc-only 1 :elided 0})

(defn pack-tf
  [{:keys [tf ecn dscp flow-label] :or {ecn 0 dscp 0 flow-label 0}}]
  (cond
    (not (contains? tf-modes tf)) [:error :thread.iphc/reserved-tf-mode tf]
    (not (<= 0 ecn 3)) [:error :thread.iphc/ecn-out-of-range ecn]
    (not (<= 0 dscp 0x3F)) [:error :thread.iphc/dscp-out-of-range dscp]
    (not (<= 0 flow-label 0xFFFFF)) [:error :thread.iphc/flow-label-out-of-range flow-label]
    :else
    [:ok (case tf
           :full [(bit-or (bit-shift-left ecn 6) (bit-and dscp 0x3F))
                  (bit-and (unsigned-bit-shift-right flow-label 16) 0x0F)
                  (bit-and (unsigned-bit-shift-right flow-label 8) 0xFF)
                  (bit-and flow-label 0xFF)]
           :flow-only [(bit-or (bit-shift-left ecn 6) (bit-and (unsigned-bit-shift-right flow-label 16) 0x0F))
                       (bit-and (unsigned-bit-shift-right flow-label 8) 0xFF)
                       (bit-and flow-label 0xFF)]
           :tc-only [(bit-or (bit-shift-left ecn 6) (bit-and dscp 0x3F))]
           :elided [])]))

(defn unpack-tf
  [tf-code bs]
  (if-not (contains? tf-mode-by-code tf-code)
    [:error :thread.iphc/reserved-tf-mode tf-code]
    (let [tf (tf-mode-by-code tf-code) bs (vec bs)]
      [:ok (case tf
             :full {:tf tf :ecn (bit-and (unsigned-bit-shift-right (nth bs 0) 6) 0x03)
                    :dscp (bit-and (nth bs 0) 0x3F)
                    :flow-label (bit-or (bit-shift-left (bit-and (nth bs 1) 0x0F) 16)
                                        (bit-shift-left (nth bs 2) 8) (nth bs 3))}
             :flow-only {:tf tf :ecn (bit-and (unsigned-bit-shift-right (nth bs 0) 6) 0x03)
                         :dscp 0
                         :flow-label (bit-or (bit-shift-left (bit-and (nth bs 0) 0x0F) 16)
                                             (bit-shift-left (nth bs 1) 8) (nth bs 2))}
             :tc-only {:tf tf :ecn (bit-and (unsigned-bit-shift-right (nth bs 0) 6) 0x03)
                       :dscp (bit-and (nth bs 0) 0x3F) :flow-label 0}
             :elided {:tf tf :ecn 0 :dscp 0 :flow-label 0})])))

;; ── Hop Limit ───────────────────────────────────────────────────────────

(def hlim-modes {:inline 0 :hop-1 1 :hop-64 2 :hop-255 3})
(def hlim-mode-by-code (into {} (map (fn [[k v]] [v k]) hlim-modes)))
(def hlim-fixed-value {:hop-1 1 :hop-64 64 :hop-255 255})

;; ── unicast address compression, RFC 6282 §3.2.1-3.2.2 ─────────────────
;; Shared by source (SAC/SAM) and destination-when-unicast (DAC/DAM).

(defn pack-unicast-address
  "`{:stateful? :mode :addr :context-prefix :link-layer-addr}` -> `[:ok
  inline-bytes]` | `[:error reason ...]`. `addr` is the full 16-byte
  address; `context-prefix` (8 bytes) is required when `:stateful?` and
  `:mode` isn't 0; `link-layer-addr` (2 or 8 bytes) is required when
  `:mode` is 3."
  [{:keys [stateful? mode addr context-prefix link-layer-addr]}]
  (let [addr (vec addr)
        prefix (if stateful? context-prefix (link-local-prefix))]
    (cond
      (not= 16 (count addr)) [:error :thread.iphc/address-wrong-length (count addr)]

      (and stateful? (= mode 0))
      (if (= addr (zero16)) [:ok []] [:error :thread.iphc/address-not-elidable addr])

      (and (not stateful?) (= mode 0)) [:ok addr]

      (= mode 1)
      (if (= (subvec addr 0 8) prefix) [:ok (subvec addr 8 16)]
          [:error :thread.iphc/prefix-mismatch addr])

      (= mode 2)
      (if (and (= (subvec addr 0 8) prefix) (= (subvec addr 8 14) nhc-fixed))
        [:ok (subvec addr 14 16)]
        [:error :thread.iphc/address-not-elidable addr])

      (= mode 3)
      (let [derived (iid-from-link-layer link-layer-addr)]
        (if (and (= (subvec addr 0 8) prefix) (= (subvec addr 8 16) derived))
          [:ok []]
          [:error :thread.iphc/address-not-elidable addr]))

      :else [:error :thread.iphc/reserved-address-mode mode])))

(defn unpack-unicast-address
  [{:keys [stateful? mode inline-bytes context-prefix link-layer-addr]}]
  (let [prefix (if stateful? context-prefix (link-local-prefix))
        inline-bytes (vec inline-bytes)]
    (cond
      (and stateful? (= mode 0)) [:ok (zero16)]
      (and (not stateful?) (= mode 0)) [:ok inline-bytes]
      (= mode 1) [:ok (vec (concat prefix inline-bytes))]
      (= mode 2) [:ok (vec (concat prefix nhc-fixed inline-bytes))]
      (= mode 3) [:ok (vec (concat prefix (iid-from-link-layer link-layer-addr)))]
      :else [:error :thread.iphc/reserved-address-mode mode])))

(def unicast-inline-length
  "mode -> inline byte count, for the two cases that don't depend on
  `stateful?` (mode 1/2/3 are fixed-width; mode 0 differs — 16 for
  stateless, 0 for stateful 'unspecified' — so callers branch on
  `stateful?` for mode 0 themselves)."
  {1 8 2 2 3 0})

;; ── multicast address compression, RFC 6282 §3.2.3, stateless only ─────

(defn pack-multicast-address
  [{:keys [mode addr]}]
  (let [addr (vec addr)]
    (cond
      (not= 16 (count addr)) [:error :thread.iphc/address-wrong-length (count addr)]
      (not= 0xFF (nth addr 0)) [:error :thread.iphc/not-multicast addr]

      (= mode 0) [:ok addr]

      (= mode 1)
      ;; 48 bits inline: FFXX::00XX:XXXX:XXXX — scope byte (idx 1) +
      ;; 8 zero bytes (idx 2..9) + one more fixed zero (idx 10) + 5
      ;; inline group-ID bytes (idx 11..15).
      (if (= (subvec addr 2 11) (vec (repeat 9 0)))
        [:ok (vec (concat [(nth addr 1)] (subvec addr 11 16)))]
        [:error :thread.iphc/address-not-elidable addr])

      (= mode 2)
      (if (= (subvec addr 2 13) (vec (repeat 11 0)))
        [:ok (vec (concat [(nth addr 1)] (subvec addr 13 16)))]
        [:error :thread.iphc/address-not-elidable addr])

      (= mode 3)
      (if (and (= (nth addr 1) 0x02) (= (subvec addr 2 15) (vec (repeat 13 0))))
        [:ok [(nth addr 15)]]
        [:error :thread.iphc/address-not-elidable addr])

      :else [:error :thread.iphc/reserved-address-mode mode])))

(defn unpack-multicast-address
  [{:keys [mode inline-bytes]}]
  (let [ib (vec inline-bytes)]
    (cond
      (= mode 0) [:ok ib]
      (= mode 1) [:ok (vec (concat [0xFF (nth ib 0)] (repeat 9 0) (subvec ib 1 6)))]
      (= mode 2) [:ok (vec (concat [0xFF (nth ib 0)] (repeat 11 0) (subvec ib 1 4)))]
      (= mode 3) [:ok (vec (concat [0xFF 0x02] (repeat 13 0) [(nth ib 0)]))]
      :else [:error :thread.iphc/reserved-address-mode mode])))

(def multicast-inline-length {0 16 1 6 2 4 3 1})

;; ── full header ─────────────────────────────────────────────────────────

(defn- dispatch-bytes [{:keys [tf nh hlim cid? sac? sam m? dac? dam]}]
  [(bit-or 0x60
           (bit-shift-left (tf-modes tf) 3)
           (bit-shift-left (if (= nh :elided) 1 0) 2)
           (hlim-modes hlim))
   (bit-or (bit-shift-left (if cid? 1 0) 7)
           (bit-shift-left (if sac? 1 0) 6)
           (bit-shift-left (bit-and sam 0x03) 4)
           (bit-shift-left (if m? 1 0) 3)
           (bit-shift-left (if dac? 1 0) 2)
           (bit-and dam 0x03))])

(defn encode
  "See namespace docstring for the field map shape. `:next-header` is
  required and used verbatim when `:nh :inline`; when `:nh :elided` it is
  ignored (LOWPAN_NHC, not decoded here, is assumed already present at
  the front of `:payload`). Returns `[:ok bytes]` | `[:error reason
  ...]`."
  [{:keys [tf ecn dscp flow-label nh next-header hlim hop-limit
           cid? sci dci
           sac? sam src-addr src-context-prefix src-link-layer-addr
           dac? m? dam dst-addr dst-context-prefix dst-link-layer-addr
           payload]
    :or {payload [] nh :inline hlim :inline cid? false sac? false dac? false m? false
         ecn 0 dscp 0 flow-label 0}}]
  (cond
    (and m? dac?)
    [:error :thread.iphc/multicast-context-compression-not-implemented]

    (and (= nh :inline) (not (<= 0 next-header 0xFF)))
    [:error :thread.iphc/next-header-out-of-range next-header]

    (and (= hlim :inline) (not (<= 0 hop-limit 0xFF)))
    [:error :thread.iphc/hop-limit-out-of-range hop-limit]

    (and cid? (not (<= 0 sci 0x0F)))
    [:error :thread.iphc/context-id-out-of-range sci]

    (and cid? (not (<= 0 dci 0x0F)))
    [:error :thread.iphc/context-id-out-of-range dci]

    :else
    (let [[tst tf-bytes] (pack-tf {:tf tf :ecn ecn :dscp dscp :flow-label flow-label})]
      (if (= tst :error)
        [tst tf-bytes]
        (let [[sst src-inline]
              (pack-unicast-address {:stateful? sac? :mode sam :addr src-addr
                                      :context-prefix src-context-prefix
                                      :link-layer-addr src-link-layer-addr})]
          (if (= sst :error)
            [sst src-inline]
            (let [[dst dst-inline]
                  (if m?
                    (pack-multicast-address {:mode dam :addr dst-addr})
                    (pack-unicast-address {:stateful? dac? :mode dam :addr dst-addr
                                            :context-prefix dst-context-prefix
                                            :link-layer-addr dst-link-layer-addr}))]
              (if (= dst :error)
                [dst dst-inline]
                [:ok (vec (concat (dispatch-bytes {:tf tf :nh nh :hlim hlim :cid? cid? :sac? sac?
                                                    :sam sam :m? m? :dac? dac? :dam dam})
                                   (when cid? [(bit-or (bit-shift-left sci 4) dci)])
                                   tf-bytes
                                   (when (= nh :inline) [next-header])
                                   (when (= hlim :inline) [hop-limit])
                                   src-inline
                                   dst-inline
                                   payload))]))))))))


(defn decode
  "`bytes` `{:src-context-prefix :src-link-layer-addr :dst-context-prefix
  :dst-link-layer-addr}` (the state the receiver needs for stateful/
  elided-address reconstruction — passed in because a codec has no
  notion of 'the neighbor table', only bytes) -> `[:ok frame-map]` |
  `[:error reason ...]`.

  Implemented as a sequence of steps against local atoms (`off` for the
  read cursor, `err` as a poison value once any step fails) rather than
  one deeply nested `let`/`if` tree — the field set here has real
  data dependencies (TF's length depends on TF's own code; the source
  address's length depends on SAC/SAM; the destination's depends on all
  of M/DAC/DAM), so the steps must run in order, but nothing about that
  requires nesting five conditionals nine deep to express."
  [bs {:keys [src-context-prefix src-link-layer-addr
              dst-context-prefix dst-link-layer-addr]}]
  (let [bs (vec bs) n (count bs)]
    (if (< n 2)
      [:error :thread.iphc/header-too-short n]
      (let [b0 (nth bs 0) b1 (nth bs 1)]
        (if (not= 0x60 (bit-and b0 0xE0))
          [:error :thread.iphc/not-iphc-dispatch b0]
          (let [tf-code (bit-and (unsigned-bit-shift-right b0 3) 0x03)
                nh (if (bit-test b0 2) :elided :inline)
                hlim-code (bit-and b0 0x03)
                cid? (bit-test b1 7)
                sac? (bit-test b1 6)
                sam (bit-and (unsigned-bit-shift-right b1 4) 0x03)
                m? (bit-test b1 3)
                dac? (bit-test b1 2)
                dam (bit-and b1 0x03)]
            (cond
              (not (contains? hlim-mode-by-code hlim-code))
              [:error :thread.iphc/reserved-hlim-mode hlim-code]

              (and m? dac?)
              [:error :thread.iphc/multicast-context-compression-not-implemented]

              :else
              (let [hlim (hlim-mode-by-code hlim-code)
                    off (atom 2)
                    err (atom nil)
                    sci (atom nil) dci (atom nil)
                    tf-map (atom nil) next-header (atom nil) hop-limit (atom nil)
                    src-addr (atom nil) dst-addr (atom nil)
                    fail! (fn [e] (reset! err e))
                    need! (fn [k] (when (and (nil? @err) (< n (+ @off k)))
                                    (fail! [:error :thread.iphc/header-too-short n])))]
                (when cid?
                  (let [cb (nth bs @off)]
                    (reset! sci (bit-and (unsigned-bit-shift-right cb 4) 0x0F))
                    (reset! dci (bit-and cb 0x0F)))
                  (swap! off inc))

                (let [tf-len (tf-length (tf-mode-by-code tf-code))]
                  (need! tf-len)
                  (when (nil? @err)
                    (let [[tst tf-v] (unpack-tf tf-code (subvec bs @off (+ @off tf-len)))]
                      (if (= tst :error)
                        (fail! [tst tf-v])
                        (do (reset! tf-map tf-v) (swap! off + tf-len))))))

                (when (nil? @err)
                  (if (= nh :inline)
                    (do (reset! next-header (nth bs @off)) (swap! off inc))
                    (reset! next-header nil))
                  (if (= hlim :inline)
                    (do (reset! hop-limit (nth bs @off)) (swap! off inc))
                    (reset! hop-limit (hlim-fixed-value hlim))))

                (when (nil? @err)
                  (let [src-len (if (and (not sac?) (= sam 0)) 16 (unicast-inline-length sam 0))]
                    (need! src-len)
                    (when (nil? @err)
                      (let [[sst sv] (unpack-unicast-address
                                       {:stateful? sac? :mode sam
                                        :inline-bytes (subvec bs @off (+ @off src-len))
                                        :context-prefix src-context-prefix
                                        :link-layer-addr src-link-layer-addr})]
                        (if (= sst :error)
                          (fail! [sst sv])
                          (do (reset! src-addr sv) (swap! off + src-len)))))))

                (when (nil? @err)
                  (let [dst-len (if m? (multicast-inline-length dam)
                                    (if (and (not dac?) (= dam 0)) 16 (unicast-inline-length dam 0)))]
                    (need! dst-len)
                    (when (nil? @err)
                      (let [[dst-st dv] (if m?
                                           (unpack-multicast-address
                                            {:mode dam :inline-bytes (subvec bs @off (+ @off dst-len))})
                                           (unpack-unicast-address
                                            {:stateful? dac? :mode dam
                                             :inline-bytes (subvec bs @off (+ @off dst-len))
                                             :context-prefix dst-context-prefix
                                             :link-layer-addr dst-link-layer-addr}))]
                        (if (= dst-st :error)
                          (fail! [dst-st dv])
                          (do (reset! dst-addr dv) (swap! off + dst-len)))))))

                (or @err
                    [:ok {:tf (:tf @tf-map) :ecn (:ecn @tf-map) :dscp (:dscp @tf-map)
                          :flow-label (:flow-label @tf-map)
                          :next-header @next-header :hlim hlim :hop-limit @hop-limit
                          :cid? cid? :sci @sci :dci @dci
                          :sac? sac? :sam sam :src-addr @src-addr
                          :m? m? :dac? dac? :dam dam :dst-addr @dst-addr
                          :payload (subvec bs @off n)}])))))))))
