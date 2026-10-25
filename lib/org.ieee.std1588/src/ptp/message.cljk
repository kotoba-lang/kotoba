(ns ptp.message
  "A complete PTP message: the 34-byte common header (`ptp.header`)
  followed by the body its messageType calls for — clauses 13.6 (Sync),
  13.7 (Follow_Up), 13.8 (Delay_Req/Delay_Resp), 13.9/13.10 (Pdelay_Req/
  Pdelay_Resp) and 13.5 (Announce, carrying clause 8.6.2's dataset
  comparison fields). Only the seven message types this workspace has any
  use for are implemented — Pdelay_Resp_Follow_Up, Signaling and
  Management are in the specification and nothing here uses them; adding
  untested code paths for completeness is how a protocol library acquires
  bugs nobody finds (org-modbus's README makes the same call about Modbus
  function codes 0x18 and up).

  `encode` computes `:message-length` itself — it is 34 (the header) plus
  the body's fixed length for that message type, never independent data a
  caller could get wrong."
  (:require [ptp.header :as header]
            [ptp.timestamp :as ts]))

;; body length is fixed per message type — clauses 13.6-13.10 for the first
;; six, clause 13.5 for Announce.
(def ^:private body-length
  {:sync 10 :delay-req 10 :follow-up 10
   :delay-resp 20 :pdelay-req 20 :pdelay-resp 20
   :announce 30})

;; ── bodies ───────────────────────────────────────────────────────────────────

(defn- be16 [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd16 [bs i] (bit-or (bit-shift-left (bit-and (nth bs i) 0xFF) 8)
                            (bit-and (nth bs (inc i)) 0xFF)))
(defn- s8 [n] (bit-and n 0xFF))
(defn- rd-s16 [bs i] (let [u (rd16 bs i)] (if (>= u 0x8000) (- u 0x10000) u)))

(defmulti ^:private encode-body (fn [message-type _body] message-type))
(defmulti ^:private decode-body (fn [message-type _bs] message-type))

;; Sync / Delay_Req — clause 13.6/13.8: originTimestamp only.
(doseq [mt [:sync :delay-req]]
  (defmethod encode-body mt [_ {:keys [origin-timestamp]}]
    (let [[st bytes] (ts/encode-timestamp origin-timestamp)]
      (if (= :error st) [:error bytes] [:ok bytes])))
  (defmethod decode-body mt [_ bs]
    (let [[st ts] (ts/decode-timestamp bs)]
      (if (= :error st) [:error ts] [:ok {:origin-timestamp ts}]))))

;; Follow_Up — clause 13.7: preciseOriginTimestamp only.
(defmethod encode-body :follow-up [_ {:keys [precise-origin-timestamp]}]
  (let [[st bytes] (ts/encode-timestamp precise-origin-timestamp)]
    (if (= :error st) [:error bytes] [:ok bytes])))
(defmethod decode-body :follow-up [_ bs]
  (let [[st ts] (ts/decode-timestamp bs)]
    (if (= :error st) [:error ts] [:ok {:precise-origin-timestamp ts}])))

;; Delay_Resp — clause 13.8.2: receiveTimestamp + requestingPortIdentity.
(defmethod encode-body :delay-resp [_ {:keys [receive-timestamp requesting-port-identity]}]
  (let [[tst tbytes] (ts/encode-timestamp receive-timestamp)]
    (if (= :error tst)
      [:error tbytes]
      (let [[pst pbytes] (header/encode-port-identity requesting-port-identity)]
        (if (= :error pst) [:error pbytes] [:ok (into tbytes pbytes)])))))
(defmethod decode-body :delay-resp [_ bs]
  (let [bs (vec bs)
        [tst ts] (ts/decode-timestamp (subvec bs 0 10))
        [_pst pid] (header/decode-port-identity bs 10)]
    (if (= :error tst) [:error ts]
        [:ok {:receive-timestamp ts :requesting-port-identity pid}])))

;; Pdelay_Req — clause 13.9: originTimestamp + 10 reserved bytes.
(defmethod encode-body :pdelay-req [_ {:keys [origin-timestamp]}]
  (let [[st bytes] (ts/encode-timestamp origin-timestamp)]
    (if (= :error st) [:error bytes] [:ok (into bytes (repeat 10 0))])))
(defmethod decode-body :pdelay-req [_ bs]
  (let [[st ts] (ts/decode-timestamp (subvec (vec bs) 0 10))]
    (if (= :error st) [:error ts] [:ok {:origin-timestamp ts}])))

;; Pdelay_Resp — clause 13.10: requestReceiptTimestamp + requestingPortIdentity.
(defmethod encode-body :pdelay-resp [_ {:keys [request-receipt-timestamp requesting-port-identity]}]
  (let [[tst tbytes] (ts/encode-timestamp request-receipt-timestamp)]
    (if (= :error tst)
      [:error tbytes]
      (let [[pst pbytes] (header/encode-port-identity requesting-port-identity)]
        (if (= :error pst) [:error pbytes] [:ok (into tbytes pbytes)])))))
(defmethod decode-body :pdelay-resp [_ bs]
  (let [bs (vec bs)
        [tst ts] (ts/decode-timestamp (subvec bs 0 10))
        [_pst pid] (header/decode-port-identity bs 10)]
    (if (= :error tst) [:error ts]
        [:ok {:request-receipt-timestamp ts :requesting-port-identity pid}])))

;; Announce — clause 13.5: originTimestamp(10) currentUtcOffset(i16)
;; reserved(1) grandmasterPriority1(u8) grandmasterClockQuality(4:
;; clockClass u8, clockAccuracy u8, offsetScaledLogVariance u16)
;; grandmasterPriority2(u8) grandmasterIdentity(8) stepsRemoved(u16)
;; timeSource(u8) = 30 bytes.
(defmethod encode-body :announce
  [_ {:keys [origin-timestamp current-utc-offset grandmaster-priority1
             grandmaster-clock-quality grandmaster-priority2
             grandmaster-identity steps-removed time-source]}]
  (let [[st tbytes] (ts/encode-timestamp origin-timestamp)]
    (if (= :error st)
      [:error tbytes]
      (if (not= 8 (count grandmaster-identity))
        [:error :ptp/bad-clock-identity-length (count grandmaster-identity)]
        (let [{:keys [clock-class clock-accuracy offset-scaled-log-variance]}
              grandmaster-clock-quality]
          [:ok
           (-> tbytes
               (into (be16 current-utc-offset))
               (conj 0) ; reserved
               (conj (s8 grandmaster-priority1))
               (conj (s8 clock-class))
               (conj (s8 clock-accuracy))
               (into (be16 offset-scaled-log-variance))
               (conj (s8 grandmaster-priority2))
               (into (mapv #(bit-and % 0xFF) grandmaster-identity))
               (into (be16 steps-removed))
               (conj (s8 time-source)))])))))
(defmethod decode-body :announce [_ bs]
  (let [bs (vec bs)
        [st ts] (ts/decode-timestamp (subvec bs 0 10))]
    (if (= :error st)
      [:error ts]
      [:ok {:origin-timestamp ts
            :current-utc-offset (rd-s16 bs 10)
            :grandmaster-priority1 (bit-and (nth bs 13) 0xFF)
            :grandmaster-clock-quality
            {:clock-class (bit-and (nth bs 14) 0xFF)
             :clock-accuracy (bit-and (nth bs 15) 0xFF)
             :offset-scaled-log-variance (rd16 bs 16)}
            :grandmaster-priority2 (bit-and (nth bs 18) 0xFF)
            :grandmaster-identity (subvec bs 19 27)
            :steps-removed (rd16 bs 27)
            :time-source (bit-and (nth bs 29) 0xFF)}])))

;; ── whole message ────────────────────────────────────────────────────────────

(defn encode
  "`m` is `(assoc <header fields minus :message-type/:message-length> :message-type mt :body body-map)`.
  Returns `[:ok bytes]` — the 34-byte header plus the body — or the first
  `[:error reason ...]` hit, from the body encoder, `ptp.timestamp`, or
  `ptp.header`, in that order."
  [{:keys [message-type body] :as m}]
  (if (nil? (body-length message-type))
    [:error :ptp/unsupported-message-type message-type]
    (let [[bst & brest] (encode-body message-type body)]
      (if (= :error bst)
        (into [:error] brest)
        (let [bbytes (first brest)
              len (+ 34 (count bbytes))
              [hst & hrest] (header/encode-header (assoc m :message-length len))]
          (if (= :error hst)
            (into [:error] hrest)
            [:ok (into (first hrest) bbytes)]))))))

(defn decode
  "bytes -> `[:ok {:header h :body b}]`. `:message-length` in the header is
  checked against the byte count actually supplied, catching a truncated
  or over-read frame before the body decoder runs on garbage."
  [bs]
  (let [bs (vec bs)
        [hst & hrest] (header/decode-header bs)]
    (if (= :error hst)
      (into [:error] hrest)
      (let [h (first hrest)]
        (cond
          (not= (count bs) (:message-length h))
          [:error :ptp/message-length-mismatch {:declared (:message-length h) :actual (count bs)}]

          (nil? (body-length (:message-type h)))
          [:error :ptp/unsupported-message-type (:message-type h)]

          (< (count bs) (+ 34 (body-length (:message-type h))))
          [:error :ptp/short-body (count bs)]

          :else
          (let [[bst & brest] (decode-body (:message-type h)
                                            (subvec bs 34 (+ 34 (body-length (:message-type h)))))]
            (if (= :error bst)
              (into [:error] brest)
              [:ok {:header h :body (first brest)}])))))))
