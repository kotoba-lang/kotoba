(ns j1939.tp
  "The J1939-21 Transport Protocol (clause 5.10): how a message longer than
  a single 8-byte CAN frame gets split into TP.DT (Data Transfer) packets
  and reassembled, announced or negotiated by TP.CM (Connection
  Management) control frames.

  Two connection-management modes, both carried on PGN 60416 (0xEC00,
  TP.CM):

    BAM        (Broadcast Announce Message) — the sender just starts
               sending TP.DT packets after one BAM; no flow control, every
               node on the bus receives it, nobody acknowledges it.
    RTS/CTS    (Request To Send / Clear To Send) — a point-to-point
               negotiation: RTS states the size, the receiver CTS's how
               many packets it is ready for, the sender sends that many,
               repeat until EndOfMsgACK.

  TP.DT (Data Transfer) itself is carried on its own PGN, 60160 (0xEB00) —
  a different PGN from TP.CM, not a sub-message of it; the two are
  distinguished on the wire by PGN, not by a byte inside the payload.

  This namespace implements the codec for both control-frame kinds and the
  reassembly state machine `start-session`/`add-data-transfer`. It does
  **not** decide when to send a CTS, retry, or time out an
  in-progress connection — those are transport-*driver* policy, and
  belong on top of this codec, the same way `ptp.offset` computes an
  arithmetic answer without deciding what a clock servo does with it.")

(def pgn-tp-cm  "TP.CM, clause 5.10.1." 60416)
(def pgn-tp-dt  "TP.DT, clause 5.10.2." 60160)

(defn- be16 [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd16 [b0 b1] (bit-or (bit-and b0 0xFF) (bit-shift-left (bit-and b1 0xFF) 8)))
;; PGN and message-size fields in TP.CM are little-endian (clause 5.10.1),
;; the opposite byte order from PTP's header/timestamp fields and from
;; Modbus everywhere — worth calling out explicitly rather than trusting
;; that "big-endian" carries over from the last protocol library written.

(defn- pgn->le3 [pgn] [(bit-and pgn 0xFF)
                        (bit-and (unsigned-bit-shift-right pgn 8) 0xFF)
                        (bit-and (unsigned-bit-shift-right pgn 16) 0xFF)])
(defn- le3->pgn [b0 b1 b2]
  (bit-or (bit-and b0 0xFF)
          (bit-shift-left (bit-and b1 0xFF) 8)
          (bit-shift-left (bit-and b2 0xFF) 16)))

;; ── TP.CM control frames, all 8 bytes, byte 0 selects the kind ─────────────

(def control-byte {:bam 0x10 :rts 0x11 :cts 0x13 :end-of-msg-ack 0x14 :abort 0xFF})
(def ^:private byte->control (into {} (map (fn [[k v]] [v k])) control-byte))

(defn encode-bam
  "`{:pgn :total-size :num-packets}` -> 8 bytes."
  [{:keys [pgn total-size num-packets]}]
  (let [[lo hi] (be16 total-size)]
    (into [(control-byte :bam) lo hi (bit-and num-packets 0xFF) 0xFF]
          (pgn->le3 pgn))))

(defn decode-bam [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (if (not= (control-byte :bam) (nth bs 0))
        [:error :j1939/not-a-bam-frame (nth bs 0)]
        [:ok {:total-size (rd16 (nth bs 1) (nth bs 2))
              :num-packets (nth bs 3)
              :pgn (le3->pgn (nth bs 5) (nth bs 6) (nth bs 7))}]))))

(defn encode-rts
  "`{:pgn :total-size :num-packets :max-packets-per-cts}` -> 8 bytes.
  `:max-packets-per-cts` is the sender's own cap on how many TP.DT packets
  it will send in response to a single CTS — a limit the *sender* states,
  not one the receiver is granting."
  [{:keys [pgn total-size num-packets max-packets-per-cts]}]
  (let [[lo hi] (be16 total-size)]
    (into [(control-byte :rts) lo hi (bit-and num-packets 0xFF)
           (bit-and max-packets-per-cts 0xFF)]
          (pgn->le3 pgn))))

(defn decode-rts [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (if (not= (control-byte :rts) (nth bs 0))
        [:error :j1939/not-a-rts-frame (nth bs 0)]
        [:ok {:total-size (rd16 (nth bs 1) (nth bs 2))
              :num-packets (nth bs 3)
              :max-packets-per-cts (nth bs 4)
              :pgn (le3->pgn (nth bs 5) (nth bs 6) (nth bs 7))}]))))

(defn encode-cts
  "`{:pgn :packets-to-send :next-packet-number}` -> 8 bytes. Bytes 3-4 are
  reserved, sent as 0xFF 0xFF."
  [{:keys [pgn packets-to-send next-packet-number]}]
  (into [(control-byte :cts) (bit-and packets-to-send 0xFF)
         (bit-and next-packet-number 0xFF) 0xFF 0xFF]
        (pgn->le3 pgn)))

(defn decode-cts [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (if (not= (control-byte :cts) (nth bs 0))
        [:error :j1939/not-a-cts-frame (nth bs 0)]
        [:ok {:packets-to-send (nth bs 1)
              :next-packet-number (nth bs 2)
              :pgn (le3->pgn (nth bs 5) (nth bs 6) (nth bs 7))}]))))

(defn encode-end-of-msg-ack [{:keys [pgn total-size num-packets]}]
  (let [[lo hi] (be16 total-size)]
    (into [(control-byte :end-of-msg-ack) lo hi (bit-and num-packets 0xFF) 0xFF]
          (pgn->le3 pgn))))

(defn decode-end-of-msg-ack [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (if (not= (control-byte :end-of-msg-ack) (nth bs 0))
        [:error :j1939/not-an-end-of-msg-ack-frame (nth bs 0)]
        [:ok {:total-size (rd16 (nth bs 1) (nth bs 2))
              :num-packets (nth bs 3)
              :pgn (le3->pgn (nth bs 5) (nth bs 6) (nth bs 7))}]))))

(defn encode-abort [{:keys [pgn reason]}]
  (into [(control-byte :abort) (bit-and reason 0xFF) 0xFF 0xFF 0xFF] (pgn->le3 pgn)))

(defn decode-abort [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (if (not= (control-byte :abort) (nth bs 0))
        [:error :j1939/not-an-abort-frame (nth bs 0)]
        [:ok {:reason (nth bs 1) :pgn (le3->pgn (nth bs 5) (nth bs 6) (nth bs 7))}]))))

(defn decode-tp-cm
  "Any TP.CM frame -> `[:ok {:kind <the byte->control keyword> ...}]`,
  dispatching on byte 0 rather than making the caller try each decoder."
  [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-cm-length (count bs)]
      (let [k (byte->control (nth bs 0))]
        (case k
          :bam (let [[st m] (decode-bam bs)] (if (= st :error) [:error m] [:ok (assoc m :kind :bam)]))
          :rts (let [[st m] (decode-rts bs)] (if (= st :error) [:error m] [:ok (assoc m :kind :rts)]))
          :cts (let [[st m] (decode-cts bs)] (if (= st :error) [:error m] [:ok (assoc m :kind :cts)]))
          :end-of-msg-ack (let [[st m] (decode-end-of-msg-ack bs)]
                            (if (= st :error) [:error m] [:ok (assoc m :kind :end-of-msg-ack)]))
          :abort (let [[st m] (decode-abort bs)] (if (= st :error) [:error m] [:ok (assoc m :kind :abort)]))
          [:error :j1939/unknown-tp-cm-control-byte (nth bs 0)])))))

;; ── TP.DT, clause 5.10.2 ─────────────────────────────────────────────────────
;; Byte 0 is a 1-based sequence number (1..255); bytes 1-7 are up to 7
;; payload bytes, the last packet padded with 0xFF to fill all 8.

(defn encode-data-transfer
  "`{:sequence-number :data}`, `:data` 1..7 bytes -> 8 bytes, padded with
  0xFF."
  [{:keys [sequence-number data]}]
  (cond
    (not (<= 1 sequence-number 255)) [:error :j1939/sequence-number-out-of-range sequence-number]
    (not (<= 1 (count data) 7)) [:error :j1939/data-transfer-payload-out-of-range (count data)]
    :else
    [:ok (into [(bit-and sequence-number 0xFF)]
               (into (mapv #(bit-and % 0xFF) data) (repeat (- 7 (count data)) 0xFF)))]))

(defn decode-data-transfer
  "8 bytes -> `[:ok {:sequence-number n :data (the 7 payload bytes,
  including any 0xFF padding — trimming it needs the session's
  `:total-size`, done by `add-data-transfer` below)}]`."
  [bs]
  (let [bs (vec bs)]
    (if (not= 8 (count bs))
      [:error :j1939/bad-tp-dt-length (count bs)]
      [:ok {:sequence-number (nth bs 0) :data (subvec bs 1 8)}])))

;; ── reassembly ───────────────────────────────────────────────────────────────

(defn start-session
  "`{:pgn :total-size :num-packets :mode (:bam or :rts-cts)}` -> a fresh
  reassembly session, from a decoded BAM or RTS."
  [{:keys [pgn total-size num-packets mode]}]
  {:pgn pgn :total-size total-size :num-packets num-packets :mode mode
   :next-sequence 1 :received-bytes 0 :buffer []})

(defn session-complete? [session]
  (>= (:received-bytes session) (:total-size session)))

(defn session-data
  "The reassembled message, exactly `:total-size` bytes — any 0xFF padding
  trailing the final TP.DT packet was already dropped by
  `add-data-transfer`, which only ever takes as many bytes from a packet
  as the total message still needs."
  [session]
  (:buffer session))

(defn add-data-transfer
  "One decoded TP.DT frame (`{:sequence-number :data}`) folded into
  `session`. `[:error :j1939/tp-sequence-gap {...}]` when the sequence
  number is not exactly the one expected next — covers both a dropped
  packet (a gap) and a duplicate/reordered one, either of which means the
  reassembly can no longer be trusted to be contiguous. `[:error
  :j1939/tp-too-many-packets ...]` when a session that has already
  received `:num-packets` packets gets another one — a peer that keeps
  sending past what it originally announced."
  [session {:keys [sequence-number data]}]
  (cond
    (session-complete? session)
    [:error :j1939/tp-too-many-packets {:num-packets (:num-packets session)}]

    (not= sequence-number (:next-sequence session))
    [:error :j1939/tp-sequence-gap {:expected (:next-sequence session) :got sequence-number}]

    :else
    (let [remaining (- (:total-size session) (:received-bytes session))
          take-n (min remaining 7)]
      (if (< (count data) take-n)
        [:error :j1939/tp-short-data-transfer {:needed take-n :got (count data)}]
        [:ok (-> session
                 (update :buffer into (subvec (vec data) 0 take-n))
                 (update :received-bytes + take-n)
                 (update :next-sequence inc))]))))
