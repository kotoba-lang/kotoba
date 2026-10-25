(ns profinet.rt
  "PROFINET RT (Real-Time) frame layer, EtherType `0x8892` — the FrameID
  that opens every PROFINET frame after the Ethernet header and
  classifies it, and the cyclic-data APDU trailer (Cycle Counter, Data
  Status, Transfer Status) that RT_CLASS_1/2 cyclic-data frames carry.

  ## Endianness

  **Big-endian, throughout — the opposite of EtherCAT and CANopen** (see
  `org-ethercat`'s `ethercat.frame` and `org-can-cia-canopen`'s
  `canopen.sdo` docstrings, which each call out their own little-endian
  convention). FrameID, Cycle Counter, and every multi-byte field in
  `profinet.dcp` are transmitted most-significant-byte-first, matching
  general Ethernet/IEEE 802.3 convention rather than EtherCAT's. Three
  fieldbuses in this workspace, three different answers to 'which byte
  goes first', which is exactly why this is called out explicitly in
  every one of the three rather than assumed.

  ## FrameID ranges (PROFINET IO frame classification)

  FrameID is 2 bytes, and its VALUE — not a sub-field within it — selects
  what kind of frame this is:

    0x0000..0x7FFF  reserved
    0x8000..0xBBFF  cyclic data, RT_CLASS_3 (IRT — isochronous real-time,
                    time-scheduled slots)
    0xBC00..0xBFFF  reserved
    0xC000..0xFBFF  cyclic data, RT_CLASS_1 / RT_CLASS_2 (non-isochronous
                    real-time — the common case, no special switch
                    hardware required)
    0xFC01          Alarm, high priority
    0xFC02..0xFDFF  reserved (future alarm use)
    0xFE01          Alarm, low priority
    0xFE02..0xFEFB  reserved
    0xFEFC          DCP-Hello-ReqPDU     (multicast, device announces
                                          itself on power-up — see
                                          `profinet.dcp`)
    0xFEFD          DCP-Get/Set-PDU      (unicast configuration)
    0xFEFE          DCP-Identify-ReqPDU  (multicast, 'who is out there')
    0xFEFF          DCP-Identify-ResPDU  (unicast response)
    0xFF00..0xFF01  PTCP (clock sync) announce/follow-up
    0xFF20..0xFF2F  fragmentation frame
    0xFF80..0xFFFF  reserved / profile-specific

  Source: this range table is reproduced identically in Wireshark's
  `epan/dissectors/packet-pn-rt.c` (`pn_io_frame_id`
  `VALUE_STRING`/`RVALS` tables) and rt-labs' open-source PROFINET device
  stack p-net (`github.com/rtlabs-com/p-net`, `src/common/pf_types.h` and
  `src/pf_cmina.c` FrameID constants); the PROFINET IO specification
  itself is a paywalled PROFIBUS & PROFINET International (profibus.com)
  membership document not quoted here from memory.

  ## Cyclic-data APDU trailer (RT_CLASS_1/2)

  A cyclic data frame's Data field ends with a small fixed trailer before
  the frame is padded to Ethernet's 64-byte minimum:

    Cycle Counter    u16 — increments each send cycle, wraps
    Data Status      u8  — bitfield, see `pack-data-status`/
                            `unpack-data-status` below
    Transfer Status  u8  — 0x00 = OK; any other value signals the
                            underlying transport (e.g. IRT sync loss)
                            could not guarantee delivery this cycle

  **Data Status bits** (source: rt-labs p-net's `include/pnet_api.h`
  `PNET_DATA_STATUS_BIT_*` macros, cross-checked against Wireshark's
  `packet-pn-rt.c` `pn_io_data_status` bitfield table):

    bit 0  State                      1 = Run (data actively cyclic),
                                       0 = Stop (before parameterisation
                                       completes, or provider stopped)
    bit 1  Redundancy                 1 = Primary AR, 0 = Backup AR
    bit 2  Data Valid                 1 = the Data field content is
                                       valid this cycle, 0 = ignore it
    bit 3  Provider State             1 = Provider is running normally
    bit 4  Station Problem Indicator  1 = a diagnosis/problem is present
                                       somewhere in the station
    bit 5  Ignore                     1 = consumer should ignore this
                                       frame's Data Status entirely
    bits 6..7  reserved, always 0")

;; ── FrameID classification ───────────────────────────────────────────────

(def frame-id-ranges
  "Ordered so the first matching `[lo hi]` wins — used by
  `classify-frame-id`, which walks this in order rather than requiring
  the caller to pick apart the value by hand."
  [[0x8000 0xBBFF :cyclic-rt-class-3]
   [0xBC00 0xBFFF :reserved]
   [0xC000 0xFBFF :cyclic-rt-class-1-or-2]
   [0xFC01 0xFC01 :alarm-high]
   [0xFC02 0xFDFF :reserved]
   [0xFE01 0xFE01 :alarm-low]
   [0xFE02 0xFEFB :reserved]
   [0xFEFC 0xFEFC :dcp-hello-request]
   [0xFEFD 0xFEFD :dcp-get-set]
   [0xFEFE 0xFEFE :dcp-identify-request]
   [0xFEFF 0xFEFF :dcp-identify-response]
   [0xFF00 0xFF01 :ptcp]
   [0xFF20 0xFF2F :fragmentation]
   [0x0000 0x7FFF :reserved]])

(defn classify-frame-id
  "u16 FrameID -> keyword classification, or `:unclassified` if it falls
  in a gap `frame-id-ranges` doesn't cover (there are some — this table
  is not claimed exhaustive down to the byte, see the docstring's own
  'reserved' bands)."
  [frame-id]
  (or (some (fn [[lo hi kw]] (when (<= lo frame-id hi) kw)) frame-id-ranges)
      :unclassified))

;; ── big-endian helpers ────────────────────────────────────────────────────

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))

(defn encode-frame-id [id]
  (if-not (<= 0 id 0xFFFF)
    [:error :profinet/frame-id-out-of-range id]
    [:ok (u16be id)]))

(defn decode-frame-id [bytes]
  (let [bs (vec bytes)]
    (if (not= 2 (count bs))
      [:error :profinet/frame-id-wrong-length (count bs)]
      [:ok (rd-u16be bs 0)])))

;; ── data status bitfield ─────────────────────────────────────────────────

(def data-status-bits
  {:state 0 :redundancy 1 :data-valid 2 :provider-state 3
   :station-problem-indicator 4 :ignore 5})

(defn pack-data-status
  "set of bit-name keywords -> u8."
  [flags]
  (reduce (fn [b k]
            (if (contains? data-status-bits k)
              (bit-or b (bit-shift-left 1 (get data-status-bits k)))
              (reduced [:error :profinet/unknown-data-status-bit k])))
          0 flags))

(defn unpack-data-status
  "u8 -> set of the named bits that are set."
  [byte]
  (into #{} (keep (fn [[k bit]] (when (pos? (bit-and byte (bit-shift-left 1 bit))) k))
                   data-status-bits)))

;; ── cyclic-data APDU trailer ─────────────────────────────────────────────

(defn encode-trailer
  "`{:cycle-counter 0..65535 :data-status (set of keywords)
  :transfer-status 0..255}` -> `[:ok bytes]` (4 bytes: Cycle Counter u16
  BE, Data Status u8, Transfer Status u8)."
  [{:keys [cycle-counter data-status transfer-status]}]
  (let [ds (pack-data-status data-status)]
    (cond
      (not (<= 0 cycle-counter 0xFFFF)) [:error :profinet/cycle-counter-out-of-range cycle-counter]
      (and (vector? ds) (= :error (first ds))) ds
      (not (<= 0 transfer-status 0xFF)) [:error :profinet/transfer-status-out-of-range transfer-status]
      :else [:ok (into (u16be cycle-counter) [ds transfer-status])])))

(defn decode-trailer
  [bytes]
  (let [bs (vec bytes)]
    (if (not= 4 (count bs))
      [:error :profinet/trailer-wrong-length (count bs)]
      [:ok {:cycle-counter (rd-u16be bs 0)
            :data-status (unpack-data-status (nth bs 2))
            :transfer-status (nth bs 3)}])))

;; ── IOxS (IO Provider/Consumer Status) byte ─────────────────────────────
;; One byte per submodule's IOPS or IOCS, packed:
;;   bit 7      DataState    1 = Good, 0 = Bad
;;   bits 6..2  Instance     reserved, conventionally 0
;;   bit 1      reserved, always 0
;;   bit 0      Extension    1 = another IOxS byte follows for this
;;                          submodule, 0 = this is the last one

(defn pack-ioxs
  "`{:good? bool :instance 0..31 :more? bool}` -> `[:ok byte]`."
  [{:keys [good? instance more?] :or {instance 0 more? false}}]
  (if-not (<= 0 instance 31)
    [:error :profinet/ioxs-instance-out-of-range instance]
    [:ok (bit-or (bit-shift-left (if good? 1 0) 7)
                 (bit-shift-left (bit-and instance 0x1F) 2)
                 (if more? 1 0))]))

(defn unpack-ioxs
  [byte]
  (if-not (<= 0 byte 0xFF)
    [:error :profinet/ioxs-out-of-range byte]
    [:ok {:good? (pos? (bit-and byte 0x80))
          :instance (bit-and (unsigned-bit-shift-right byte 2) 0x1F)
          :more? (pos? (bit-and byte 0x01))}]))

(def ioxs-good "The common single-byte 'no extension, data good' value." 0x80)
(def ioxs-bad "The common single-byte 'no extension, data bad' value." 0x00)

;; ── a full cyclic-data RT_CLASS_1/2 frame's Data field ──────────────────

(defn encode-cyclic-data
  "`{:io-data [bytes] :iops-byte u8 :iocs-byte u8 :cycle-counter
  :data-status :transfer-status}` -> `[:ok bytes]`: IO data, then IOPS,
  then IOCS, then the trailer. Real PROFINET IOCRs interleave IOPS/IOCS
  per-submodule throughout the data area rather than trailing it, which
  depends on the configured IOCR layout (out of scope here, same
  'structural knowledge, not the whole configuration model' scoping
  `org-modbus`/`org-can-cia-canopen` use) — this function models the
  simple single-submodule case where that distinction does not arise."
  [{:keys [io-data iops-byte iocs-byte cycle-counter data-status transfer-status]}]
  (let [[tst trailer] (encode-trailer {:cycle-counter cycle-counter
                                        :data-status data-status
                                        :transfer-status transfer-status})]
    (cond
      (not (<= 0 iops-byte 0xFF)) [:error :profinet/ioxs-out-of-range iops-byte]
      (not (<= 0 iocs-byte 0xFF)) [:error :profinet/ioxs-out-of-range iocs-byte]
      (= :error tst) [:error trailer]
      :else [:ok (-> (vec io-data) (conj iops-byte) (conj iocs-byte) (into trailer))])))

(defn decode-cyclic-data
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 6)
      [:error :profinet/cyclic-data-too-short n]
      (let [[tst trailer] (decode-trailer (subvec bs (- n 4) n))]
        (if (= :error tst)
          [:error trailer]
          [:ok (merge {:io-data (subvec bs 0 (- n 6))
                       :iops-byte (nth bs (- n 6))
                       :iocs-byte (nth bs (- n 5))}
                      trailer)])))))
