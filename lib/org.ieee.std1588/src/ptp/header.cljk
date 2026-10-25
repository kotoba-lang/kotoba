(ns ptp.header
  "The common PTP header — IEEE 1588-2019 clause 13.3, \"PTP message
  header\". Every PTP message (Sync, Follow_Up, Delay_Req, Delay_Resp,
  Pdelay_Req, Pdelay_Resp, Announce, Signaling, Management) starts with
  this same 34-byte structure; only the body that follows differs by
  message type. This namespace owns the header only — bodies live in
  `ptp.message`.

  Byte layout, all multi-byte integers big-endian (clause 13.3):

    0      transportSpecific (high nibble) | messageType (low nibble)
    1      reserved (high nibble)          | versionPTP (low nibble)
    2..3   messageLength      UInteger16
    4      domainNumber       UInteger8
    5      reserved           Octet
    6..7   flagField          Octet2
    8..15  correctionField    Integer64, scaled nanoseconds (ptp.timestamp)
    16..19 reserved           UInteger32
    20..27 sourcePortIdentity.clockIdentity  Octet[8]
    28..29 sourcePortIdentity.portNumber     UInteger16
    30..31 sequenceId         UInteger16
    32     controlField       UInteger8 — legacy PTPv1-interop field
    33     logMessageInterval Integer8 (signed)

  34 bytes, always — there is no variable-length part of the header. The
  four `reserved` positions are transmitted as zero and ignored on
  decode (clause 13.3.1: a receiver shall ignore reserved fields, not
  reject a message that carries something else in one)."
  (:require [ptp.timestamp :as ts]))

;; ── byte helpers ─────────────────────────────────────────────────────────────
;; 8- and 16-bit fields fit inside the 32-bit range JavaScript's bitwise
;; operators are exact for, so this namespace uses real bit-and/bit-or/
;; bit-shift-left/unsigned-bit-shift-right directly. The 48- and 64-bit
;; fields (seconds, correctionField) do not, and are handled in
;; `ptp.timestamp` — see that namespace's docstring for why.

(defn- be16 [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd16 [bs i] (bit-or (bit-shift-left (bit-and (nth bs i) 0xFF) 8)
                            (bit-and (nth bs (inc i)) 0xFF)))

;; ── messageType, clause 13.3.2.2 ─────────────────────────────────────────────
;; The low nibble of byte 0. These eleven values (five reserved nibbles) are
;; the same in every PTP stack — there is only one correct reading of
;; clause 13.3.2.2 — and match ptp4l's `msg.h` / ptpd's `msg.h` definitions,
;; which is the practical cross-check used here.

(def message-types
  {0x0 :sync
   0x1 :delay-req
   0x2 :pdelay-req
   0x3 :pdelay-resp
   0x8 :follow-up
   0x9 :delay-resp
   0xA :pdelay-resp-follow-up
   0xB :announce
   0xC :signaling
   0xD :management})

(def message-type->code (into {} (map (fn [[k v]] [v k])) message-types))

;; ── controlField, clause 13.3.2.14 (PTPv1-interop compatibility field) ──────
;; Table 24 in the 2008 edition. A PTPv2 receiver decides what a message is
;; from messageType, not this field — but a PTPv2 sender still has to put
;; the value a PTPv1 boundary clock on the same segment expects, and that
;; value is a pure function of messageType, so it is derived here rather
;; than accepted as caller-supplied data that could disagree with it.

(def ^:private control-field-of
  {:sync 0x00 :delay-req 0x01 :follow-up 0x02 :delay-resp 0x03 :management 0x04})

(defn control-field-for
  "controlField for `message-type`. Every type other than the five named
  above — Announce, Pdelay_Req, Pdelay_Resp, Pdelay_Resp_Follow_Up,
  Signaling — collapses to 0x05, \"all others\"."
  [message-type]
  (get control-field-of message-type 0x05))

;; ── flagField, clause 13.3.2.7 ───────────────────────────────────────────────
;; Two octets, byte 6 then byte 7. Bit positions cross-checked against
;; linuxptp's `ptp_message.h` (ALTERNATE_MASTER/TWO_STEP/UNICAST in the
;; first octet; LEAP61/LEAP59/UTC_OFF_VALID/PTP_TIMESCALE/TIME_TRACEABLE/
;; FREQUENCY_TRACEABLE, the Announce-message flags, in the second). The two
;; profile-specific bits and the reserved bits are intentionally omitted —
;; this library does not interpret them, so accepting and silently
;; discarding them would be worse than not naming them at all.
;;
;; `:two-step` is the one that matters most operationally: it says this
;; Sync's originTimestamp field is a placeholder and the *real* one is
;; coming in a following Follow_Up. Getting the bit backwards makes a
;; two-step master look one-step, and the Follow_Up that would have
;; corrected the timestamp is ignored.

(def flag-bits
  {:alternate-master          [0 0]
   :two-step                  [0 1]
   :unicast                   [0 2]
   :leap61                    [1 0]
   :leap59                    [1 1]
   :current-utc-offset-valid  [1 2]
   :ptp-timescale             [1 3]
   :time-traceable            [1 4]
   :frequency-traceable       [1 5]})

(defn encode-flags [flags]
  (reduce (fn [[o0 o1] f]
            (if-let [[octet bit] (flag-bits f)]
              (if (zero? octet)
                [(bit-or o0 (bit-shift-left 1 bit)) o1]
                [o0 (bit-or o1 (bit-shift-left 1 bit))])
              [o0 o1]))
          [0 0]
          flags))

(defn decode-flags [o0 o1]
  (into #{}
        (keep (fn [[flag [octet bit]]]
                (let [byte (if (zero? octet) o0 o1)]
                  (when-not (zero? (bit-and byte (bit-shift-left 1 bit)))
                    flag))))
        flag-bits))

;; ── sourcePortIdentity, clause 7.5.2.2 ──────────────────────────────────────
;; 8-byte clockIdentity (an EUI-64-shaped value; this library treats it as
;; an opaque byte vector, never as a MAC address) + 2-byte portNumber.
;; Reused both in the header (bytes 20..29) and in the Delay_Resp/
;; Pdelay_Resp bodies' requestingPortIdentity field.

(defn encode-port-identity [{:keys [clock-identity port-number]}]
  (if (not= 8 (count clock-identity))
    [:error :ptp/bad-clock-identity-length (count clock-identity)]
    [:ok (into (vec (map #(bit-and % 0xFF) clock-identity)) (be16 port-number))]))

(defn decode-port-identity [bs off]
  [:ok {:clock-identity (subvec (vec bs) off (+ off 8))
        :port-number (rd16 bs (+ off 8))}])

;; ── header ───────────────────────────────────────────────────────────────────

(defn encode-header
  "`h` is a map:
     :message-type          keyword, a key of `message-types`
     :transport-specific    0..15, default 0
     :version-ptp           0..15, default 2 (the only defined PTPv2 value)
     :message-length        UInteger16 — 34 (this header) plus the body
     :domain-number         0..255
     :flags                 a set drawn from `flag-bits`, default #{}
     :correction            integer nanoseconds; see ptp.timestamp/encode-correction, default 0
     :source-port-identity  {:clock-identity (8 bytes) :port-number 0..65535}
     :sequence-id           0..65535
     :log-message-interval  -128..127 (signed)
   `:control-field` is never accepted here — it is derived from
   `:message-type` (see `control-field-for`), because it is not independent
   data. Returns `[:ok bytes]` (34 of them) or `[:error reason ...]`."
  [{:keys [message-type transport-specific version-ptp message-length
           domain-number flags correction source-port-identity
           sequence-id log-message-interval]
    :or {transport-specific 0 version-ptp 2 flags #{} correction 0}}]
  (let [mt (message-type->code message-type)]
    (cond
      (nil? mt) [:error :ptp/unknown-message-type message-type]
      (nil? message-length) [:error :ptp/missing-message-length]
      (nil? source-port-identity) [:error :ptp/missing-source-port-identity]
      (nil? sequence-id) [:error :ptp/missing-sequence-id]
      (nil? log-message-interval) [:error :ptp/missing-log-message-interval]
      :else
      (let [[corr-status corr-bytes-or-reason & corr-rest] (ts/encode-correction correction)]
        (if (= :error corr-status)
          (into [:error corr-bytes-or-reason] corr-rest)
          (let [[pid-status pid-bytes-or-reason & pid-rest]
                (encode-port-identity source-port-identity)]
            (if (= :error pid-status)
              (into [:error pid-bytes-or-reason] pid-rest)
              (let [[f0 f1] (encode-flags flags)]
                [:ok
                 (-> []
                     (conj (bit-or (bit-shift-left (bit-and transport-specific 0xF) 4)
                                    (bit-and mt 0xF)))
                     (conj (bit-and version-ptp 0xF))
                     (into (be16 message-length))
                     (conj (bit-and domain-number 0xFF))
                     (conj 0)
                     (conj (bit-and f0 0xFF))
                     (conj (bit-and f1 0xFF))
                     (into corr-bytes-or-reason)
                     (into [0 0 0 0])
                     (into pid-bytes-or-reason)
                     (into (be16 sequence-id))
                     (conj (control-field-for message-type))
                     (conj (bit-and log-message-interval 0xFF)))])))))))) 

(defn decode-header
  "The first 34 bytes of `bs` -> `[:ok header-map]`. Bytes past position 33
  are not this function's concern — `ptp.message/decode` slices the body
  off using `:message-length`."
  [bs]
  (let [bs (vec bs)]
    (if (< (count bs) 34)
      [:error :ptp/short-header (count bs)]
      (let [b0 (nth bs 0)
            transport-specific (bit-and (unsigned-bit-shift-right b0 4) 0xF)
            mt-code (bit-and b0 0xF)
            mt (message-types mt-code)]
        (if (nil? mt)
          [:error :ptp/unknown-message-type-code mt-code]
          (let [version-ptp (bit-and (nth bs 1) 0xF)
                message-length (rd16 bs 2)
                domain-number (bit-and (nth bs 4) 0xFF)
                f0 (bit-and (nth bs 6) 0xFF)
                f1 (bit-and (nth bs 7) 0xFF)
                [corr-status correction] (ts/decode-correction (subvec bs 8 16))
                [_pid-status pid] (decode-port-identity bs 20)
                sequence-id (rd16 bs 30)
                control-field (bit-and (nth bs 32) 0xFF)
                log-byte (bit-and (nth bs 33) 0xFF)
                log-message-interval (if (>= log-byte 0x80) (- log-byte 256) log-byte)]
            (if (= :error corr-status)
              [:error :ptp/bad-correction-field]
              [:ok {:message-type mt
                    :transport-specific transport-specific
                    :version-ptp version-ptp
                    :message-length message-length
                    :domain-number domain-number
                    :flags (decode-flags f0 f1)
                    :correction correction
                    :source-port-identity pid
                    :sequence-id sequence-id
                    :control-field control-field
                    :log-message-interval log-message-interval}])))))))
