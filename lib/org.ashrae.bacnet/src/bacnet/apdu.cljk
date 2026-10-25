(ns bacnet.apdu
  "BACnet Application PDUs — ASHRAE 135 Clause 20.1.

  The PDU type occupies the top 4 bits of the first octet, always:

  ```
  0 Confirmed-Request   4 SegmentACK (not implemented — see README)
  1 Unconfirmed-Request 5 Error
  2 SimpleACK           6 Reject
  3 ComplexACK          7 Abort
  ```

  This library implements the seven service-carrying PDU types; SegmentACK
  is BACnet's segmentation-transport bookkeeping and carries no service
  data, and is out of scope alongside segmentation itself (see README).

  Layouts (each field is exactly the byte count the standard gives it —
  there is no field here whose width is 'implementation defined'):

  Confirmed-Request (20.1.2.1):
    octet 1: type=0000 | SEG | MOR | SA | reserved(0)
    octet 2: reserved(0) | max-segs-accepted(3) | max-apdu-accepted(4)
    octet 3: invoke id
    [octet 4: sequence number, octet 5: proposed window size — iff SEG]
    octet N: service choice
    remaining: service request parameters

  Unconfirmed-Request (20.1.2.3):
    octet 1: type=0001 | reserved(0000)
    octet 2: service choice
    remaining: service request parameters

  SimpleACK (20.1.2.4):
    octet 1: type=0010 | reserved(0000)
    octet 2: original invoke id
    octet 3: service ACK choice — which request this acknowledges

  ComplexACK (20.1.2.5):
    octet 1: type=0011 | SEG | MOR | reserved(00)
    octet 2: original invoke id
    octet 3: service ACK choice
    [octet 4/5: sequence number / window size — iff SEG]
    remaining: service ACK parameters

  Error (20.1.2.9):
    octet 1: type=0101 | reserved(0000)
    octet 2: original invoke id
    octet 3: error choice (the service that failed)
    remaining: error-class (context tag 0, Enumerated) + error-code
               (context tag 1, Enumerated)

  Reject (20.1.2.10):
    octet 1: type=0110 | reserved(0000)
    octet 2: original invoke id
    octet 3: reject reason — a **raw octet**, NOT a tag-encoded Enumerated.
    This is the trap: every other 'reason' byte in BACnet Error/Abort/Reject
    looks superficially similar, and Error's error-code genuinely IS
    tag-encoded two octets away. Reject's reason is not tagged at all —
    treating it as a tag byte and trying to strip a length/value/type
    nibble off it corrupts values 32 and above (where the nibble bits
    stop being coincidentally zero).

  Abort (20.1.2.11):
    octet 1: type=0111 | reserved(000) | server (1 = abort sent by server)
    octet 2: original invoke id
    octet 3: abort reason — also a raw octet, same trap as Reject.

  Max-segments-accepted / max-APDU-length-accepted packing (the octet-2
  table for Confirmed-Request/ComplexACK) follows the widely-implemented
  bacnet-stack encoding: 3-bit max-segs code in bits 6-4, 4-bit max-APDU
  code in bits 3-0, bit 7 reserved. This numeric table (which segment
  count / APDU size each code number stands for) is cited from that
  reference implementation's convention, not re-derived from the standard
  text here — treat the code<->limit mapping as well-established practice
  rather than a verbatim spec quotation."
  (:require [bacnet.tags :as tags]))

(defn- u8 [n] (bit-and n 0xFF))
(defn- safe-nth [bs i] (when (< i (count bs)) (nth bs i)))

;; ── PDU type nibble ───────────────────────────────────────────────────────

(def pdu-types
  {0x0 :confirmed-request
   0x1 :unconfirmed-request
   0x2 :simple-ack
   0x3 :complex-ack
   0x4 :segment-ack
   0x5 :error
   0x6 :reject
   0x7 :abort})

(def pdu-type->nibble (into {} (map (fn [[k v]] [v k])) pdu-types))

;; ── service choice tables (Clause 21) ─────────────────────────────────────
;; Only the services this library encodes/decodes are given full attention;
;; the rest of the table exists so a decoder can at least NAME an unhandled
;; service choice instead of reporting a bare number.

(def confirmed-service-choices
  {12 :read-property 15 :write-property})

(def unconfirmed-service-choices
  {0 :i-am 8 :who-is})

(def confirmed-service->choice (into {} (map (fn [[k v]] [v k])) confirmed-service-choices))
(def unconfirmed-service->choice (into {} (map (fn [[k v]] [v k])) unconfirmed-service-choices))

;; ── max-segments / max-apdu octet (bacnet-stack convention) ──────────────

(defn- max-segs-code [max-segs]
  (cond (<= max-segs 1) 0 (< max-segs 4) 1 (< max-segs 8) 2 (< max-segs 16) 3
        (< max-segs 32) 4 (< max-segs 64) 5 :else 6))

(def max-segs-code->count {0 1 1 2 2 4 3 8 4 16 5 32 6 64})

(defn- max-apdu-code [max-apdu]
  (cond (<= max-apdu 50) 0 (<= max-apdu 128) 1 (<= max-apdu 206) 2
        (<= max-apdu 480) 3 (<= max-apdu 1024) 4 :else 5))

(def max-apdu-code->size {0 50 1 128 2 206 3 480 4 1024 5 1476})

(defn- encode-segs-apdu-octet [max-segs max-apdu]
  (bit-or (bit-shift-left (max-segs-code max-segs) 4) (max-apdu-code max-apdu)))

(defn- decode-segs-apdu-octet [b]
  {:max-segments-accepted (max-segs-code->count (bit-and (unsigned-bit-shift-right b 4) 0x07) 64)
   :max-apdu-length-accepted (max-apdu-code->size (bit-and b 0x0F) 1476)})

;; ── encode ─────────────────────────────────────────────────────────────

(defn encode-confirmed-request
  "`{:invoke-id n :service kw :max-segments-accepted n :max-apdu-length-accepted n
     :segmented? bool :more-follows? bool :segmented-response-accepted? bool
     :sequence-number n :proposed-window-size n}` plus `params` —
  already-encoded service-request parameter bytes (callers build those with
  `bacnet.services`). The sequence-number/window-size octets are only
  present (and only meaningful) when `:segmented?` is true, and — this is
  the field-order trap — they sit BETWEEN invoke-id and service-choice, not
  after service-choice: `invoke-id [seq# window] service-choice params`.
  Segmentation fields are accepted for header completeness; this library
  does not itself split a request across segments (see README), so
  `:segmented?` true with actual multi-segment transport is out of scope."
  [{:keys [invoke-id service max-segments-accepted max-apdu-length-accepted
           segmented? more-follows? segmented-response-accepted?
           sequence-number proposed-window-size]} params]
  (if-let [choice (confirmed-service->choice service)]
    {:status :ok
     :bytes (into [(bit-or (bit-shift-left (pdu-type->nibble :confirmed-request) 4)
                            (if segmented? 0x08 0) (if more-follows? 0x04 0)
                            (if segmented-response-accepted? 0x02 0))
                   (encode-segs-apdu-octet (or max-segments-accepted 1)
                                            (or max-apdu-length-accepted 1476))
                   (u8 invoke-id)]
                  (concat (when segmented?
                            [(u8 (or sequence-number 0)) (u8 (or proposed-window-size 1))])
                          [choice]
                          params))}
    [:error :bacnet/unknown-service]))

(defn encode-unconfirmed-request
  [{:keys [service]} params]
  (if-let [choice (unconfirmed-service->choice service)]
    {:status :ok :bytes (into [(bit-shift-left (pdu-type->nibble :unconfirmed-request) 4) choice]
                               params)}
    [:error :bacnet/unknown-service]))

(defn encode-simple-ack
  [{:keys [invoke-id service]}]
  (if-let [choice (confirmed-service->choice service)]
    {:status :ok
     :bytes [(bit-shift-left (pdu-type->nibble :simple-ack) 4) (u8 invoke-id) choice]}
    [:error :bacnet/unknown-service]))

(defn encode-complex-ack
  "Same seq#/window field-order trap as `encode-confirmed-request`: when
  `:segmented?` is true those two octets sit between invoke-id and
  service-ack-choice."
  [{:keys [invoke-id service segmented? more-follows? sequence-number proposed-window-size]} params]
  (if-let [choice (confirmed-service->choice service)]
    {:status :ok
     :bytes (into [(bit-or (bit-shift-left (pdu-type->nibble :complex-ack) 4)
                            (if segmented? 0x08 0) (if more-follows? 0x04 0))
                   (u8 invoke-id)]
                  (concat (when segmented?
                            [(u8 (or sequence-number 0)) (u8 (or proposed-window-size 1))])
                          [choice]
                          params))}
    [:error :bacnet/unknown-service]))

(def error-classes
  {0 :device 1 :object 2 :property 3 :resources 4 :security 5 :services 6 :vt 7 :communication})
(def error-class->code (into {} (map (fn [[k v]] [v k])) error-classes))

(def error-codes
  ;; Clause 21, a small commonly-hit subset — cited from the standard's
  ;; error-code enumeration by name/number, not exhaustively reproduced.
  {0 :other 15 :invalid-data-type 31 :unknown-object 32 :unknown-property
   9 :inconsistent-parameters 40 :write-access-denied 44 :value-out-of-range})
(def error-code->code (into {} (map (fn [[k v]] [v k])) error-codes))

(defn encode-error
  [{:keys [invoke-id service error-class error-code]}]
  (if-let [choice (confirmed-service->choice service)]
    (let [ec (error-class->code error-class) ex (error-code->code error-code)]
      (if (and ec ex)
        {:status :ok
         :bytes (into [(bit-shift-left (pdu-type->nibble :error) 4) (u8 invoke-id) choice]
                      (into (tags/encode-application-value :enumerated ec)
                            (tags/encode-application-value :enumerated ex)))}
        [:error :bacnet/unknown-error-code]))
    [:error :bacnet/unknown-service]))

(def reject-reasons
  {0 :other 1 :buffer-overflow 2 :inconsistent-parameters 3 :invalid-parameter-data-type
   4 :invalid-tag 5 :missing-required-parameter 6 :parameter-out-of-range
   7 :too-many-arguments 8 :undefined-enumeration 9 :unrecognized-service})
(def reject-reason->code (into {} (map (fn [[k v]] [v k])) reject-reasons))

(defn encode-reject
  [{:keys [invoke-id reason]}]
  (if-let [code (reject-reason->code reason)]
    {:status :ok :bytes [(bit-shift-left (pdu-type->nibble :reject) 4) (u8 invoke-id) code]}
    [:error :bacnet/unknown-reject-reason]))

(def abort-reasons
  {0 :other 1 :buffer-overflow 2 :invalid-apdu-in-this-state
   3 :preempted-by-higher-priority-task 4 :segmentation-not-supported
   9 :out-of-resources 11 :apdu-too-long})
(def abort-reason->code (into {} (map (fn [[k v]] [v k])) abort-reasons))

(defn encode-abort
  [{:keys [invoke-id reason server?]}]
  (if-let [code (abort-reason->code reason)]
    {:status :ok :bytes [(bit-or (bit-shift-left (pdu-type->nibble :abort) 4) (if server? 1 0))
                          (u8 invoke-id) code]}
    [:error :bacnet/unknown-abort-reason]))

;; ── decode ─────────────────────────────────────────────────────────────

(defn decode
  "Dispatches on the PDU type nibble. Returns a map tagged `:pdu-type`, or
  `[:error reason]`. `params`/service-payload bytes are returned undecoded
  (as `:params`/`:payload`) — pairing them with the tag/value decoders in
  `bacnet.tags` or the service parsers in `bacnet.services` is left to the
  caller, the same separation `modbus.pdu` keeps between framing and the
  function-specific payload shape."
  [bs]
  (if (empty? bs)
    [:error :bacnet/empty-apdu]
    (let [b0 (nth bs 0)
          nibble (bit-and (unsigned-bit-shift-right b0 4) 0x0F)
          pdu-type (pdu-types nibble)]
      (case pdu-type
        :confirmed-request
        (if (< (count bs) 4)
          [:error :bacnet/frame-too-short]
          (let [seg? (bit-test b0 3) mor? (bit-test b0 2) sa? (bit-test b0 1)
                {:keys [max-segments-accepted max-apdu-length-accepted]}
                (decode-segs-apdu-octet (nth bs 1))
                invoke-id (nth bs 2)
                ;; seq#/window sit BETWEEN invoke-id and service-choice when
                ;; segmented — see encode-confirmed-request's docstring.
                choice-idx (if seg? 5 3)
                enough? (if seg? (>= (count bs) 6) (>= (count bs) 4))
                choice (when enough? (nth bs choice-idx))
                service (when choice (confirmed-service-choices choice))
                hdr-end (inc choice-idx)]
              (cond
                (not enough?) [:error :bacnet/frame-too-short]
                (nil? service) [:error :bacnet/unknown-service]
                :else {:status :ok :pdu-type :confirmed-request :segmented? seg?
                       :more-follows? mor? :segmented-response-accepted? sa?
                       :max-segments-accepted max-segments-accepted
                       :max-apdu-length-accepted max-apdu-length-accepted
                       :invoke-id invoke-id :service service
                       :sequence-number (when seg? (nth bs 3))
                       :proposed-window-size (when seg? (nth bs 4))
                       :params (vec (subvec (vec bs) hdr-end (count bs)))})))

        :unconfirmed-request
        (if (< (count bs) 2)
          [:error :bacnet/frame-too-short]
          (let [choice (nth bs 1) service (unconfirmed-service-choices choice)]
            (if (nil? service)
              [:error :bacnet/unknown-service]
              {:status :ok :pdu-type :unconfirmed-request :service service
               :params (vec (subvec (vec bs) 2 (count bs)))})))

        :simple-ack
        (if (< (count bs) 3)
          [:error :bacnet/frame-too-short]
          (let [choice (nth bs 2) service (confirmed-service-choices choice)]
            (if (nil? service)
              [:error :bacnet/unknown-service]
              {:status :ok :pdu-type :simple-ack :invoke-id (nth bs 1) :service service})))

        :complex-ack
        (if (< (count bs) 3)
          [:error :bacnet/frame-too-short]
          (let [seg? (bit-test b0 3) mor? (bit-test b0 2)
                invoke-id (nth bs 1)
                choice-idx (if seg? 4 2)
                enough? (if seg? (>= (count bs) 5) (>= (count bs) 3))
                choice (when enough? (nth bs choice-idx))
                service (when choice (confirmed-service-choices choice))
                hdr-end (inc choice-idx)]
              (cond
                (not enough?) [:error :bacnet/frame-too-short]
                (nil? service) [:error :bacnet/unknown-service]
                :else {:status :ok :pdu-type :complex-ack :segmented? seg? :more-follows? mor?
                       :invoke-id invoke-id :service service
                       :sequence-number (when seg? (nth bs 2))
                       :proposed-window-size (when seg? (nth bs 3))
                       :payload (vec (subvec (vec bs) hdr-end (count bs)))})))

        :error
        (if (< (count bs) 3)
          [:error :bacnet/frame-too-short]
          (let [choice (nth bs 2) service (confirmed-service-choices choice)
                d1 (tags/decode-application-value bs 3)]
            (cond
              (nil? service) [:error :bacnet/unknown-service]
              (= :error (first d1)) d1
              :else
              (let [d2 (tags/decode-application-value bs (:next d1))]
                (if (= :error (first d2))
                  d2
                  {:status :ok :pdu-type :error :invoke-id (nth bs 1) :service service
                   :error-class (error-classes (:value d1) :unknown)
                   :error-code (error-codes (:value d2) :unknown)})))))

        :reject
        (if (< (count bs) 3)
          [:error :bacnet/frame-too-short]
          {:status :ok :pdu-type :reject :invoke-id (nth bs 1)
           :reason (get reject-reasons (nth bs 2) :vendor-proprietary)})

        :abort
        (if (< (count bs) 3)
          [:error :bacnet/frame-too-short]
          {:status :ok :pdu-type :abort :server? (bit-test b0 0) :invoke-id (nth bs 1)
           :reason (get abort-reasons (nth bs 2) :vendor-proprietary)})

        :segment-ack [:error :bacnet/segment-ack-not-implemented]
        [:error :bacnet/unknown-pdu-type]))))
