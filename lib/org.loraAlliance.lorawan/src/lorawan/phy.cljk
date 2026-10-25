(ns lorawan.phy
  "LoRaWAN L2 1.0.4 Specification (LoRa Alliance, TS001-1.0.4, © 2020),
  §4 \"MAC Frame Formats\" — the structural byte layout only: `MHDR`,
  `FHDR`, `MACPayload`, `PHYPayload`. No cryptography lives here — the MIC
  (§4.4) is computed by `lorawan.mic` and this namespace treats it as an
  opaque 4-byte field, and FRMPayload encryption (§4.3.3) is
  `lorawan.crypt`'s job; a data-frame codec that actually validates a MIC
  and decrypts a payload is `lorawan.frame`, one layer up.

  ```
  PHYPayload := MHDR | MACPayload | MIC          (data frames, §4.1 Table 2)
             := MHDR | Join-Request | MIC        (§6.2.5 Table 53)
             := MHDR | Join-Accept | MIC          (§6.2.6 Table 54, encrypted)
  MACPayload := FHDR | FPort(0..1) | FRMPayload(0..N)   (§4.3 Table 10)
  FHDR       := DevAddr(4) | FCtrl(1) | FCnt(2) | FOpts(0..15)  (§4.3.1 Table 6)
  ```

  `DevAddr` and `FCnt` are little-endian on the wire — see
  `lorawan.bytes`'s docstring for the spec citation and why that matters.
  `FCnt` on the wire is the *low 16 bits* of the end-device's 32-bit frame
  counter (§4.3.1.5): \"Frame counters are 32 bits wide. The `FCnt` field
  SHALL correspond to the least-significant 16 bits.\" Reconstructing the
  full 32-bit counter from traffic (rollover detection) is a Network
  Server's job this codec does not do — it round-trips exactly what is on
  the wire, an unsigned 16-bit value."
  (:require [lorawan.bytes :as b]))

;; ── MHDR — §4.2, Table 3 ─────────────────────────────────────────────────────

(def ftype->code
  {:join-request 0 :join-accept 1
   :unconfirmed-data-up 2 :unconfirmed-data-down 3
   :confirmed-data-up 4 :confirmed-data-down 5
   :rfu 6 :proprietary 7})
(def code->ftype (into {} (map (fn [[k v]] [v k])) ftype->code))

(defn encode-mhdr
  "§4.2 Table 3: bits `[7:5]` FType, `[4:2]` RFU (zero), `[1:0]` Major.
  `major` defaults to `0` (\"LoRaWAN R1\", §4.2.2 Table 5 — the only
  assigned value; 1..3 are RFU)."
  ([ftype] (encode-mhdr ftype 0))
  ([ftype major]
   (if-let [code (get ftype->code ftype)]
     {:status :ok :byte (bit-or (bit-shift-left code 5) (bit-and major 0x03))}
     {:status :error :reason :lorawan/unknown-ftype :ftype ftype})))

(defn decode-mhdr
  "Returns `{:status :ok :ftype … :major …}`. There is no error case here —
  every 3-bit `FType` pattern and every 2-bit `Major` pattern is defined
  (`:rfu`/`3` included) — an MHDR byte cannot be malformed by itself, only
  the frame it introduces can be."
  [byte]
  {:status :ok
   :ftype (code->ftype (bit-and (unsigned-bit-shift-right byte 5) 0x07))
   :major (bit-and byte 0x03)})

;; ── FCtrl — §4.3.1, Table 7 (downlink) / Table 8 (uplink) ───────────────────

(defn encode-fctrl
  "`dir` is `:uplink` or `:downlink` — the two directions define different
  bit 6 (`ADRACKReq` vs RFU) and bit 4 (`ClassB` vs `FPending`) meanings,
  §4.3.1 Tables 7/8. `fopts-len` is bits `[3:0]`, 0..15 (§4.3.1.6)."
  [dir {:keys [adr adr-ack-req ack class-b f-pending fopts-len]
        :or {adr false adr-ack-req false ack false class-b false f-pending false fopts-len 0}}]
  (if (not (<= 0 fopts-len 15))
    {:status :error :reason :lorawan/bad-fopts-len :value fopts-len}
    (let [bit7 (if adr 0x80 0)
          bit6 (if (= dir :uplink) (if adr-ack-req 0x40 0) 0) ; downlink bit 6 is RFU = 0
          bit5 (if ack 0x20 0)
          bit4 (if (= dir :uplink) (if class-b 0x10 0) (if f-pending 0x10 0))]
      {:status :ok :byte (bit-or bit7 bit6 bit5 bit4 (bit-and fopts-len 0x0F))})))

(defn decode-fctrl [dir byte]
  {:status :ok
   :fields (cond-> {:adr (= 0x80 (bit-and byte 0x80))
                     :ack (= 0x20 (bit-and byte 0x20))
                     :fopts-len (bit-and byte 0x0F)}
             (= dir :uplink) (assoc :adr-ack-req (= 0x40 (bit-and byte 0x40))
                                     :class-b (= 0x10 (bit-and byte 0x10)))
             (= dir :downlink) (assoc :f-pending (= 0x10 (bit-and byte 0x10))))})

;; ── FHDR — §4.3.1, Table 6 ───────────────────────────────────────────────────

(defn encode-fhdr
  "`dev-addr` a 32-bit unsigned int, `fcnt` the 16-bit wire counter, `fopts`
  0..15 already-encoded MAC-command bytes (§5 — piggybacked commands are
  never encrypted, per §4.3.1.6/§5's own text: \"Piggybacked MAC commands
  SHALL always be sent without encryption\"). `fctrl-byte` is the caller's
  already-encoded `FCtrl` (via `encode-fctrl`) so its `fopts-len` can be
  cross-checked against `(count fopts)` here rather than trusted blindly."
  [{:keys [dev-addr fctrl-byte fcnt fopts]}]
  (let [fopts (or fopts [])
        declared-len (bit-and fctrl-byte 0x0F)]
    (cond
      (not= declared-len (count fopts))
      {:status :error :reason :lorawan/fopts-len-mismatch
       :declared declared-len :actual (count fopts)}
      (> (count fopts) 15) {:status :error :reason :lorawan/bad-fopts-len :value (count fopts)}
      :else
      {:status :ok
       :bytes (-> (b/le-n dev-addr 4)
                  (conj fctrl-byte)
                  (into (b/le-n fcnt 2))
                  (into fopts))})))

(defn decode-fhdr
  "`bs` starting at `off`. Reads `FCtrl`'s `FOptsLen` first to know how many
  trailing bytes belong to `FOpts` — the field itself never says its own
  length; the length lives one field back, in the header everyone reads to
  get here. `dir` is needed to interpret `FCtrl`'s direction-dependent
  bits (see `decode-fctrl`)."
  [dir bs off]
  (if (< (- (count bs) off) 7)
    {:status :error :reason :lorawan/buffer-underrun :need 7 :have (- (count bs) off)}
    (let [dev-addr (b/le->int (subvec (vec bs) off (+ off 4)))
          fctrl-byte (nth bs (+ off 4))
          fctrl (decode-fctrl dir fctrl-byte)
          fcnt (b/le->int (subvec (vec bs) (+ off 5) (+ off 7)))
          fopts-len (get-in fctrl [:fields :fopts-len])
          fopts-end (+ off 7 fopts-len)]
      (if (> fopts-end (count bs))
        {:status :error :reason :lorawan/buffer-underrun :need fopts-len :have (- (count bs) (+ off 7))}
        {:status :ok
         :dev-addr dev-addr :fctrl (:fields fctrl) :fcnt fcnt
         :fopts (vec (subvec (vec bs) (+ off 7) fopts-end))
         :next fopts-end}))))

;; ── MACPayload — §4.3, Table 10 ──────────────────────────────────────────────

(defn encode-macpayload
  "FHDR bytes, then `FPort` if `frm-payload` (already-encrypted, or empty)
  is nonempty — §4.3.1: \"If the frame payload field is not empty, the
  port field SHALL be present.\" An explicit `:fport 0` with a nonempty
  payload is legal (`FPort 0` means \"FRMPayload is MAC commands\", §4.3.2)
  and different from omitting FPort, which this function does automatically
  whenever `frm-payload` is empty — callers never pass `:fport nil` to mean
  \"omit\"; they simply don't include a payload."
  [fhdr-bytes {:keys [fport frm-payload]}]
  (let [frm-payload (or frm-payload [])]
    (if (and (seq frm-payload) (nil? fport))
      {:status :error :reason :lorawan/missing-fport}
      (-> fhdr-bytes
          (into (if (seq frm-payload) [(bit-and fport 0xFF)] []))
          (into frm-payload)))))

(defn decode-macpayload
  "Splits the FHDR out (via `decode-fhdr`) and returns the raw remaining
  bytes as `:fport` (`nil` if absent) plus `:frm-payload` — still
  encrypted/opaque at this layer. `lorawan.frame` is where FPort selects
  `NwkSKey` vs `AppSKey` (§4.3.3 Table 11) and the payload actually gets
  decrypted."
  [dir bs off]
  (let [fhdr (decode-fhdr dir bs off)]
    (if (= :error (:status fhdr)) fhdr
        (let [rest-bytes (subvec (vec bs) (:next fhdr) (count bs))]
          {:status :ok
           :dev-addr (:dev-addr fhdr) :fctrl (:fctrl fhdr) :fcnt (:fcnt fhdr) :fopts (:fopts fhdr)
           :fport (when (seq rest-bytes) (first rest-bytes))
           :frm-payload (if (seq rest-bytes) (vec (rest rest-bytes)) [])
           :next (count bs)}))))

;; ── PHYPayload — §4.1, Table 2 ───────────────────────────────────────────────

(defn encode-phypayload
  "`mhdr-byte` (from `encode-mhdr`), `body-bytes` (a `MACPayload`, a
  Join-Request payload, or an already-encrypted Join-Accept payload), and
  `mic-bytes` (exactly 4 — `lorawan.mic`'s job, not this namespace's)."
  [mhdr-byte body-bytes mic-bytes]
  (if (not= 4 (count mic-bytes))
    {:status :error :reason :lorawan/bad-mic-length :length (count mic-bytes)}
    {:status :ok :bytes (-> [mhdr-byte] (into body-bytes) (into mic-bytes))}))

(defn decode-phypayload
  "Splits `bs` into `:mhdr` (decoded), `:body` (everything between the
  1-byte MHDR and the trailing 4-byte MIC — still an opaque `MACPayload`/
  `Join-Request`/`Join-Accept`, further decoded by the caller once it knows
  which) and `:mic`. `:lorawan/frame-too-short` if under 5 bytes — the
  minimum possible frame is MHDR + zero-length body + MIC."
  [bs]
  (if (< (count bs) 5)
    {:status :error :reason :lorawan/frame-too-short :length (count bs)}
    (let [mhdr (decode-mhdr (nth bs 0))]
      {:status :ok
       :mhdr mhdr
       :body (vec (subvec (vec bs) 1 (- (count bs) 4)))
       :mic (vec (subvec (vec bs) (- (count bs) 4) (count bs)))})))
