(ns bacnet.npdu
  "BACnet Network Protocol Data Unit — ASHRAE 135 Clause 6.

  All BACnet multi-byte fields are **big-endian**, the opposite convention
  from OPC UA's little-endian binary encoding (`org-opcfoundation-ua`) — a
  detail worth stating plainly since a codec ported between the two
  protocols by habit will get every multi-byte field backwards.

  Layout (Figure 6-1):

  ```
  Version (1)  Control (1)  [DNET(2) DLEN(1) DADR(DLEN)]
               [SNET(2) SLEN(1) SADR(SLEN)]  [Hop Count(1)]  NSDU
  ```

  The Control octet (Clause 6.2.2) is the field most implementations get
  half right:

  ```
  bit:  7    6      5           4      3           2         1 0
        NLM  rsvd   dst-present rsvd   src-present  expects-  priority
                                                     reply
  ```

  - bit 7: 1 if the NSDU is a **network layer message** (routing control —
    Who-Is-Router-To-Network and friends), 0 if it is an ordinary APDU.
    This library only decodes the APDU case; a network-layer message is
    reported as such (`:network-layer-message? true`) with its payload left
    undecoded, rather than silently misreading routing-control bytes as if
    they were an APDU.
  - bit 5: destination address present. If set, DNET/DLEN/DADR follow, and
    critically the **Hop Count octet appears after both address blocks**
    (source included), not immediately after DADR — a decoder that reads
    Hop Count right after DADR gets it right only when there is no source
    address, and silently reads a source-address byte as Hop Count when
    there is one.
  - bit 3: source address present. DLEN/SLEN of 0 (`DADR`/`SADR` absent)
    means 'broadcast on that network' for the destination, but a **source**
    address is never legitimately absent when bit 3 is set — SLEN 0 with
    the source-present bit set is a malformed frame, not a valid
    zero-length source, and is rejected as such.
  - bit 2: this NSDU expects a reply (meaningful only when carrying an
    APDU that is itself a confirmed request).
  - bits 1-0: network priority — 0 normal, 1 urgent, 2 critical-equipment,
    3 life-safety.")

(defn- u8 [n] (bit-and n 0xFF))
(defn- be16 [n] [(u8 (unsigned-bit-shift-right n 8)) (u8 n)])
(defn- rd16 [bs i] (+ (* 256 (nth bs i)) (nth bs (inc i))))
(defn- safe-nth [bs i] (when (< i (count bs)) (nth bs i)))

(def protocol-version 0x01)

(defn- addr-block [addr]
  (into [(count addr)] addr))

(defn encode
  "`opts` is `{:destination {:dnet n :dadr [bytes]} ; dadr [] = broadcast on dnet
                :source {:snet n :sadr [bytes]}
                :expects-reply? bool
                :priority 0-3
                :network-layer-message? bool}` (all keys optional) and
  `nsdu` is the payload bytes (an APDU, or a network-layer message body if
  `:network-layer-message?` is set). Hop count defaults to 255 (the maximum,
  per Clause 6.2.2) when a destination is present and no `:hop-count` is
  given, and is omitted entirely when there is no destination — routers
  decrement it, and a frame with no destination never crosses a router."
  [{:keys [destination source expects-reply? priority network-layer-message? hop-count]} nsdu]
  (let [priority (or priority 0)]
    (if-not (<= 0 priority 3)
      [:error :bacnet/priority-out-of-range]
      (let [dst? (some? destination)
            src? (some? source)
            control (bit-or (if network-layer-message? 0x80 0x00)
                             (if dst? 0x20 0x00)
                             (if src? 0x08 0x00)
                             (if expects-reply? 0x04 0x00)
                             (bit-and priority 0x03))
            dst-bytes (if dst?
                        (into (be16 (:dnet destination)) (addr-block (:dadr destination)))
                        [])
            src-bytes (if src?
                        (if (empty? (:sadr source))
                          [:error :bacnet/source-address-required]
                          (into (be16 (:snet source)) (addr-block (:sadr source))))
                        [])]
        (if (and src? (= :error (first src-bytes)))
          src-bytes
          (let [hc (if dst? [(u8 (or hop-count 255))] [])]
            {:status :ok
             :bytes (into [protocol-version control]
                          (concat dst-bytes src-bytes hc nsdu))}))))))

(defn decode
  "Parses an NPDU. Returns `{:status :ok :destination {..} :source {..}
  :expects-reply? bool :priority n :network-layer-message? bool
  :hop-count n-or-nil :nsdu [bytes]}`."
  [bs]
  (cond
    (< (count bs) 2) [:error :bacnet/frame-too-short]
    (not= (nth bs 0) protocol-version) [:error :bacnet/unsupported-version]
    :else
    (let [control (nth bs 1)
          nlm? (bit-test control 7)
          dst? (bit-test control 5)
          src? (bit-test control 3)
          expects-reply? (bit-test control 2)
          priority (bit-and control 0x03)]
      (loop [i 2 destination nil source nil]
        (cond
          (and dst? (nil? destination))
          (if (<= (+ i 3) (count bs))
            (let [dnet (rd16 bs i)
                  dlen (nth bs (+ i 2))
                  dadr-start (+ i 3)]
              (if (<= (+ dadr-start dlen) (count bs))
                (recur (+ dadr-start dlen)
                       {:dnet dnet :dadr (vec (subvec (vec bs) dadr-start (+ dadr-start dlen)))}
                       source)
                [:error :bacnet/frame-too-short]))
            [:error :bacnet/frame-too-short])

          (and src? (nil? source))
          (if (<= (+ i 3) (count bs))
            (let [snet (rd16 bs i)
                  slen (nth bs (+ i 2))
                  sadr-start (+ i 3)]
              (cond
                (zero? slen) [:error :bacnet/source-address-required]
                (<= (+ sadr-start slen) (count bs))
                (recur (+ sadr-start slen)
                       destination
                       {:snet snet :sadr (vec (subvec (vec bs) sadr-start (+ sadr-start slen)))})
                :else [:error :bacnet/frame-too-short]))
            [:error :bacnet/frame-too-short])

          :else
          (let [hop-count (when dst? (safe-nth bs i))
                nsdu-start (if dst? (inc i) i)]
            (if (and dst? (nil? hop-count))
              [:error :bacnet/frame-too-short]
              {:status :ok
               :destination destination
               :source source
               :expects-reply? expects-reply?
               :priority priority
               :network-layer-message? nlm?
               :hop-count hop-count
               :nsdu (vec (subvec (vec bs) nsdu-start (count bs)))})))))))
