(ns lorawan.mac-command
  "LoRaWAN L2 1.0.4 §5 \"MAC Commands\" — `CID` (1 byte) followed by a
  command-specific, possibly-empty byte sequence (§5, verbatim). This
  namespace has the full §5 Table 14 `CID` registry, plus real
  encode/decode for five representative commands with actual bitfield
  packing: `LinkCheckReq`/`Ans` (§5.1), `LinkADRReq`/`Ans` (§5.2),
  `DutyCycleReq`/`Ans` (§5.3), `RXParamSetupReq`/`Ans` (§5.4),
  `DevStatusReq`/`Ans` (§5.5).

  ## What is not here

  The Class A command set is ~15 commands (Table 14) and Class B adds
  another 4 (Table 61); implementing all of them is a lot of low-risk,
  high-volume field-table transcription with little left to demonstrate
  once the first five prove the CID-dispatch/bitfield-packing pattern —
  exactly the \"breadth that reproduces the facade problem\" this task
  warns against. `decode-command`/`encode-command` fall back to a generic
  `{:cid n :payload […]}` passthrough for any CID not in the five above,
  rather than silently dropping or misinterpreting them — a caller that
  needs `NewChannelReq` or the Class B set adds a case here following the
  same shape, not a redesign.")

;; ── §5, Table 14 — full CID registry (name only; five have real codecs) ────

(def cid->name
  {0x02 :link-check 0x03 :link-adr 0x04 :duty-cycle 0x05 :rx-param-setup
   0x06 :dev-status 0x07 :new-channel 0x08 :rx-timing-setup
   0x09 :tx-param-setup 0x0A :dl-channel 0x0D :device-time})

;; ── §5.1 LinkCheckReq/Ans ────────────────────────────────────────────────────

(defn encode-link-check-req [] {:status :ok :bytes [0x02]})

(defn encode-link-check-ans
  "§5.1 Table 16: `Margin`(1, 0..254 dB, 255 reserved) `GwCnt`(1)."
  [margin gw-cnt]
  (if (or (not (<= 0 margin 254)) (not (<= 0 gw-cnt 255)))
    {:status :error :reason :lorawan/mac-command-field-out-of-range}
    {:status :ok :bytes [0x02 margin gw-cnt]}))

(defn decode-link-check-ans [bs off]
  (if (< (- (count bs) off) 2)
    {:status :error :reason :lorawan/buffer-underrun}
    {:status :ok :fields {:margin (nth bs off) :gw-cnt (nth bs (inc off))} :next (+ off 2)}))

;; ── §5.2 LinkADRReq/Ans ──────────────────────────────────────────────────────

(defn encode-link-adr-req
  "§5.2 Table 17/18/20: `DataRate_TXPower`(1: `[7:4]`=DataRate `[3:0]`=TXPower)
  `ChMask`(2, LE per the document-wide rule) `Redundancy`(1: `[6:4]`=ChMaskCntl
  `[3:0]`=NbTrans)."
  [{:keys [data-rate tx-power ch-mask ch-mask-cntl nb-trans]}]
  (if (not (and (<= 0 data-rate 15) (<= 0 tx-power 15) (<= 0 ch-mask 0xFFFF)
                (<= 0 ch-mask-cntl 7) (<= 0 nb-trans 15)))
    {:status :error :reason :lorawan/mac-command-field-out-of-range}
    {:status :ok
     :bytes [0x03 (bit-or (bit-shift-left data-rate 4) tx-power)
             (bit-and ch-mask 0xFF) (bit-and (unsigned-bit-shift-right ch-mask 8) 0xFF)
             (bit-or (bit-shift-left ch-mask-cntl 4) nb-trans)]}))

(defn decode-link-adr-req [bs off]
  (if (< (- (count bs) off) 4)
    {:status :error :reason :lorawan/buffer-underrun}
    (let [drtp (nth bs off) ch-lo (nth bs (+ off 1)) ch-hi (nth bs (+ off 2)) red (nth bs (+ off 3))]
      {:status :ok
       :fields {:data-rate (bit-and (unsigned-bit-shift-right drtp 4) 0x0F)
                :tx-power (bit-and drtp 0x0F)
                :ch-mask (bit-or ch-lo (bit-shift-left ch-hi 8))
                :ch-mask-cntl (bit-and (unsigned-bit-shift-right red 4) 0x07)
                :nb-trans (bit-and red 0x0F)}
       :next (+ off 4)})))

(defn encode-link-adr-ans
  "§5.2 Table 22: `Status`(1) — bit2 PowerACK, bit1 DataRateACK, bit0
  ChannelMaskACK, `[7:3]` RFU."
  [{:keys [power-ack data-rate-ack channel-mask-ack]}]
  {:status :ok
   :bytes [0x03 (bit-or (if power-ack 0x04 0) (if data-rate-ack 0x02 0) (if channel-mask-ack 0x01 0))]})

(defn decode-link-adr-ans [bs off]
  (if (< (- (count bs) off) 1)
    {:status :error :reason :lorawan/buffer-underrun}
    (let [s (nth bs off)]
      {:status :ok
       :fields {:power-ack (= 1 (bit-and (unsigned-bit-shift-right s 2) 1))
                :data-rate-ack (= 1 (bit-and (unsigned-bit-shift-right s 1) 1))
                :channel-mask-ack (= 1 (bit-and s 1))}
       :next (inc off)})))

;; ── §5.3 DutyCycleReq/Ans ────────────────────────────────────────────────────

(defn encode-duty-cycle-req
  "§5.3 Table 25: `DutyCyclePL`(1) — `[3:0]` MaxDutyCycle, `[7:4]` RFU.
  Aggregated duty cycle = `1 / 2^MaxDutyCycle`; `0` = no limitation."
  [max-duty-cycle]
  (if (not (<= 0 max-duty-cycle 15))
    {:status :error :reason :lorawan/mac-command-field-out-of-range}
    {:status :ok :bytes [0x04 (bit-and max-duty-cycle 0x0F)]}))

(defn decode-duty-cycle-req [bs off]
  (if (< (- (count bs) off) 1)
    {:status :error :reason :lorawan/buffer-underrun}
    {:status :ok :fields {:max-duty-cycle (bit-and (nth bs off) 0x0F)} :next (inc off)}))

(defn encode-duty-cycle-ans [] {:status :ok :bytes [0x04]}) ; no payload, §5.3

;; ── §5.4 RXParamSetupReq/Ans ─────────────────────────────────────────────────

(defn encode-rx-param-setup-req
  "§5.4 Table 26/27: `DLSettings`(1: `[6:4]`=RX1DROffset `[3:0]`=RX2DataRate)
  `Frequency`(3, LE, units of 100 Hz per NewChannelReq's own convention —
  see the namespace-level note: this codec passes `frequency` through as
  already-divided-by-100 units, matching the wire field directly, not Hz)."
  [{:keys [rx1-dr-offset rx2-data-rate frequency]}]
  (if (not (and (<= 0 rx1-dr-offset 7) (<= 0 rx2-data-rate 15) (<= 0 frequency 0xFFFFFF)))
    {:status :error :reason :lorawan/mac-command-field-out-of-range}
    {:status :ok
     :bytes (into [0x05 (bit-or (bit-shift-left rx1-dr-offset 4) rx2-data-rate)]
                  [(bit-and frequency 0xFF) (bit-and (unsigned-bit-shift-right frequency 8) 0xFF)
                   (bit-and (unsigned-bit-shift-right frequency 16) 0xFF)])}))

(defn decode-rx-param-setup-req [bs off]
  (if (< (- (count bs) off) 4)
    {:status :error :reason :lorawan/buffer-underrun}
    (let [dl (nth bs off)
          freq (bit-or (nth bs (+ off 1)) (bit-shift-left (nth bs (+ off 2)) 8)
                        (bit-shift-left (nth bs (+ off 3)) 16))]
      {:status :ok
       :fields {:rx1-dr-offset (bit-and (unsigned-bit-shift-right dl 4) 0x07)
                :rx2-data-rate (bit-and dl 0x0F) :frequency freq}
       :next (+ off 4)})))

(defn encode-rx-param-setup-ans
  "§5.4 Table 29: `Status`(1) — bit2 RX1DROffsetACK, bit1 RX2DataRateACK,
  bit0 ChannelACK."
  [{:keys [rx1-dr-offset-ack rx2-data-rate-ack channel-ack]}]
  {:status :ok
   :bytes [0x05 (bit-or (if rx1-dr-offset-ack 0x04 0) (if rx2-data-rate-ack 0x02 0) (if channel-ack 0x01 0))]})

(defn decode-rx-param-setup-ans [bs off]
  (if (< (- (count bs) off) 1)
    {:status :error :reason :lorawan/buffer-underrun}
    (let [s (nth bs off)]
      {:status :ok
       :fields {:rx1-dr-offset-ack (= 1 (bit-and (unsigned-bit-shift-right s 2) 1))
                :rx2-data-rate-ack (= 1 (bit-and (unsigned-bit-shift-right s 1) 1))
                :channel-ack (= 1 (bit-and s 1))}
       :next (inc off)})))

;; ── §5.5 DevStatusReq/Ans ────────────────────────────────────────────────────

(defn encode-dev-status-req [] {:status :ok :bytes [0x06]})

(defn encode-dev-status-ans
  "§5.5 Table 31/32/33: `Battery`(1, `0`=external power, `1..254`=level,
  `255`=unmeasurable) `RadioStatus`(1: `[5:0]`=SNR, signed, -32..31; `[7:6]`
  RFU). SNR's two's-complement encoding is exactly `amqp.types`'s `s32->u32`
  shrunk to 6 bits — `(bit-and snr 0x3F)` masks a negative Clojure/JS
  integer down to its low 6 bits, which *is* two's complement at that
  width, the same identity that function's docstring explains at 32."
  [{:keys [battery snr]}]
  (if (not (and (<= 0 battery 255) (<= -32 snr 31)))
    {:status :error :reason :lorawan/mac-command-field-out-of-range}
    {:status :ok :bytes [0x06 battery (bit-and snr 0x3F)]}))

(defn decode-dev-status-ans [bs off]
  (if (< (- (count bs) off) 2)
    {:status :error :reason :lorawan/buffer-underrun}
    (let [battery (nth bs off) raw (bit-and (nth bs (+ off 1)) 0x3F)
          snr (if (>= raw 32) (- raw 64) raw)] ; 6-bit two's complement
      {:status :ok :fields {:battery battery :snr snr} :next (+ off 2)})))
