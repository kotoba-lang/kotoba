(ns matter.protocol
  "The Matter protocol (exchange) header — carried inside a
  `matter.message`-framed packet's payload, immediately before the
  `matter.tlv`-encoded application payload. This is where Matter's
  request/response exchange tracking (Exchange ID, Initiator/
  Acknowledgment/Reliability flags) and interaction-model dispatch
  (Protocol ID, Protocol Opcode) live.

  ## Provenance

  Same caveat as `matter.message`: the Matter specification is a CSA
  member document, so this is a reconstruction, not a quotation — the
  field set corroborated across public descriptions of Matter's exchange
  layer and `connectedhomeip`'s `messaging/ExchangeMessageDispatch.h`/
  `PayloadHeader.h`. **Every concrete byte sequence in this library's
  tests is `;; constructed, not a published spec vector`.**

  ## Exchange Flags (1 byte):

    bit 0  I    Initiator — this exchange's originating message
    bit 1  A    Acknowledgment present — a 4-byte Acknowledged Message
                Counter follows the header fields below
    bit 2  R    Reliability — this message requires acknowledgment
    bit 3  SX   Secured Extensions present (not decoded here — see
                README 'Not here')
    bit 4  V    Vendor ID present — a 2-byte Vendor ID precedes Protocol
                ID, scoping it as vendor-specific rather than a
                standard Matter protocol
    bits 5-7    Reserved

  ## Field order on the wire:

    Exchange Flags(1) | Protocol Opcode(1) | Exchange ID(2) | [Vendor
    ID(2), iff V] | Protocol ID(2) | [Acknowledged Message Counter(4),
    iff A] | rest (the TLV application payload, opaque here — see
    `matter.tlv`)")

(defn- u16le [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-u16le [bs off] (bit-or (bit-and (nth bs off) 0xFF)
                                  (bit-shift-left (bit-and (nth bs (inc off)) 0xFF) 8)))
(defn- u32le [n] [(bit-and n 0xFF)
                   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 24) 0xFF)])
(defn- rd-u32le [bs off]
  (unsigned-bit-shift-right
   (bit-or (bit-and (nth bs off) 0xFF)
           (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 8)
           (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 16)
           (bit-shift-left (bit-and (nth bs (+ off 3)) 0xFF) 24))
   0))

(defn build-exchange-flags
  [{:keys [initiator? ack-present? reliable? secured-extensions? vendor-id-present?]}]
  [:ok (bit-or (bit-shift-left (if initiator? 1 0) 0)
               (bit-shift-left (if ack-present? 1 0) 1)
               (bit-shift-left (if reliable? 1 0) 2)
               (bit-shift-left (if secured-extensions? 1 0) 3)
               (bit-shift-left (if vendor-id-present? 1 0) 4))])

(defn parse-exchange-flags
  [b]
  [:ok {:initiator? (bit-test b 0)
        :ack-present? (bit-test b 1)
        :reliable? (bit-test b 2)
        :secured-extensions? (bit-test b 3)
        :vendor-id-present? (bit-test b 4)}])

(defn encode
  "`{:initiator? :ack-present? :reliable? :vendor-id-present? :protocol-
  opcode :exchange-id :vendor-id :protocol-id :ack-counter :payload}` ->
  `[:ok bytes]` | `[:error reason ...]`."
  [{:keys [protocol-opcode exchange-id vendor-id protocol-id ack-counter payload]
    :or {payload []} :as m}]
  (let [[_ eflags] (build-exchange-flags m)
        [_ peflags] (parse-exchange-flags eflags)
        {:keys [ack-present? vendor-id-present?]} peflags]
    (cond
      (not (<= 0 protocol-opcode 0xFF)) [:error :matter.protocol/opcode-out-of-range protocol-opcode]
      (not (<= 0 exchange-id 0xFFFF)) [:error :matter.protocol/exchange-id-out-of-range exchange-id]
      (not (<= 0 protocol-id 0xFFFF)) [:error :matter.protocol/protocol-id-out-of-range protocol-id]
      (and vendor-id-present? (nil? vendor-id)) [:error :matter.protocol/missing-vendor-id]
      (and vendor-id-present? (not (<= 0 vendor-id 0xFFFF)))
      [:error :matter.protocol/vendor-id-out-of-range vendor-id]
      (and ack-present? (nil? ack-counter)) [:error :matter.protocol/missing-ack-counter]
      (and ack-present? (not (<= 0 ack-counter 0xFFFFFFFF)))
      [:error :matter.protocol/ack-counter-out-of-range ack-counter]

      :else
      [:ok (vec (concat [eflags (bit-and protocol-opcode 0xFF)] (u16le exchange-id)
                         (when vendor-id-present? (u16le vendor-id))
                         (u16le protocol-id)
                         (when ack-present? (u32le ack-counter))
                         payload))])))

(defn decode
  [bs]
  (let [bs (vec bs) n (count bs)]
    (if (< n 6)
      [:error :matter.protocol/header-too-short n]
      (let [[_ eflags] (parse-exchange-flags (nth bs 0))
            {:keys [ack-present? vendor-id-present?] :as ef} eflags
            protocol-opcode (nth bs 1)
            exchange-id (rd-u16le bs 2)
            off (atom 4)
            need (+ 4 (if vendor-id-present? 2 0) 2 (if ack-present? 4 0))]
        (if (< n need)
          [:error :matter.protocol/header-too-short n]
          (let [vendor-id (when vendor-id-present? (let [v (rd-u16le bs @off)] (swap! off + 2) v))
                protocol-id (let [v (rd-u16le bs @off)] (swap! off + 2) v)
                ack-counter (when ack-present? (let [v (rd-u32le bs @off)] (swap! off + 4) v))]
            [:ok (cond-> {:exchange-flags ef :protocol-opcode protocol-opcode
                          :exchange-id exchange-id :protocol-id protocol-id
                          :payload (subvec bs @off n)}
                   vendor-id-present? (assoc :vendor-id vendor-id)
                   ack-present? (assoc :ack-counter ack-counter))]))))))
