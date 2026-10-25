(ns profinet.dcp
  "DCP (Discovery and Configuration Protocol), PROFINET IO's
  ARP-and-DHCP-substitute run directly over Ethernet (EtherType `0x8892`,
  no IP) on FrameIDs `0xFEFC`..`0xFEFF` (see `profinet.rt`'s
  `frame-id-ranges`). This is the most testable corner of PROFINET's
  stateless layer — a fixed header followed by TLV blocks — so this
  namespace does it properly rather than sketching all of RT+RTC3.

  ## PDU header, **big-endian throughout** (see `profinet.rt`'s
  endianness note — PROFINET is the mirror image of EtherCAT/CANopen
  here):

    byte 0      ServiceID     which DCP service (Get/Set/Identify/Hello)
    byte 1      ServiceType   Request / Response Success / Response
                              Unsupported
    bytes 2..5  Xid           u32, transaction id the requester picks
                              and the responder echoes back unchanged —
                              this is DCP's ONLY way to match a response
                              to a request, there being no IP/UDP
                              port/session underneath it
    bytes 6..7  ResponseDelay u16 — only meaningful on a multicast
                              Identify request: a hint (in ms) for how
                              widely responders should spread out their
                              unicast replies, so a broadcast domain full
                              of devices does not answer all at once.
                              0 on every other PDU.
    bytes 8..9  DCPDataLength u16 — byte length of everything that
                              follows (the TLV blocks), NOT including
                              this 10-byte header

  ## TLV block, repeated `DCPDataLength` bytes' worth:

    byte 0      Option        which category (IP / Device Properties /
                              Control / ...), see `options`
    byte 1      Suboption     which field within that category
    bytes 2..3  DCPBlockLength u16 — byte length of Value that follows
    bytes ..    Value         DCPBlockLength bytes
    byte (opt)  Pad           ONE extra zero byte, present only if
                              DCPBlockLength is ODD — every block starts
                              at an even offset from the PDU data start.
                              This is the classic DCP parsing trap: a
                              decoder that trusts `DCPBlockLength` alone
                              to find the next block's Option byte reads
                              one byte early on every odd-length block.

  ServiceID / ServiceType values, and the four Option/Suboption
  categories implemented here, are reproduced identically in Wireshark's
  `epan/dissectors/packet-pn-dcp.c` (`pn_dcp_service_id`/
  `pn_dcp_service_type`/`pn_dcp_option`/suboption `VALUE_STRING` tables)
  and rt-labs' open-source PROFINET device stack p-net
  (`github.com/rtlabs-com/p-net`, `src/pf_dcp.c` and
  `src/common/pf_types.h` `pf_dcp_opt_*`/`pf_dcp_sub_*` enums); the
  PROFINET IO specification itself is a paywalled PROFIBUS & PROFINET
  International (profibus.com) membership document not quoted here from
  memory.")

;; ── big-endian helpers ────────────────────────────────────────────────────

(defn- u16be [n] [(bit-and (unsigned-bit-shift-right n 8) 0xFF) (bit-and n 0xFF)])
(defn- rd-u16be [bs off] (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 8)
                                  (bit-and (nth bs (inc off)) 0xFF)))
(defn- u32be [n] [(bit-and (unsigned-bit-shift-right n 24) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
                   (bit-and n 0xFF)])
(defn- rd-u32be [bs off]
  ;; `unsigned-bit-shift-right ... 0` at the end: ClojureScript's
  ;; `bit-shift-left`/`bit-or` are 32-bit SIGNED (JS semantics) — an Xid
  ;; whose top byte has its high bit set (>=0x80, i.e. more than half the
  ;; 32-bit space — e.g. 0xCAFEBABE) would otherwise come back as a
  ;; NEGATIVE host number instead of the intended 0..4294967295 unsigned
  ;; value. No effect on the JVM, where this expression already produces
  ;; a nonnegative Long.
  (unsigned-bit-shift-right
   (bit-or (bit-shift-left (bit-and (nth bs off) 0xFF) 24)
           (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 16)
           (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 8)
           (bit-and (nth bs (+ off 3)) 0xFF))
   0))

;; ── ServiceID / ServiceType ───────────────────────────────────────────────

(def service-ids {:get 3 :set 4 :identify 5 :hello 6})
(def service-id-by-byte (into {} (map (fn [[k v]] [v k]) service-ids)))

(def service-types {:request 0 :response-success 1 :response-unsupported 5})
(def service-type-by-byte (into {} (map (fn [[k v]] [v k]) service-types)))

(def frame-id-for-service
  "`{:service-id :service-type}` -> the FrameID (see `profinet.rt`) that
  PDU rides on."
  {[:hello :request] 0xFEFC
   [:get :request] 0xFEFD [:get :response-success] 0xFEFD [:get :response-unsupported] 0xFEFD
   [:set :request] 0xFEFD [:set :response-success] 0xFEFD [:set :response-unsupported] 0xFEFD
   [:identify :request] 0xFEFE
   [:identify :response-success] 0xFEFF [:identify :response-unsupported] 0xFEFF})

;; ── Option / Suboption ────────────────────────────────────────────────────

(def options
  {:ip 0x01 :device-properties 0x02 :dhcp 0x03 :control 0x05 :device-initiative 0x06 :all 0xFF})
(def option-by-byte (into {} (map (fn [[k v]] [v k]) options)))

(def ip-suboptions {:mac-address 0x01 :ip-parameter 0x02 :full-ip-suite 0x03})
(def device-properties-suboptions
  {:device-vendor 0x01 :name-of-station 0x02 :device-id 0x03 :device-role 0x04
   :device-options 0x05 :alias-name 0x06 :device-instance 0x07 :oem-device-id 0x08})
(def control-suboptions
  {:start-transaction 0x01 :end-transaction 0x02 :signal 0x03 :response 0x04
   :factory-reset 0x05 :reset-to-factory 0x06})
(def device-initiative-suboptions {:device-initiative 0x01})
(def all-suboptions {:all 0xFF})

(def suboptions-by-option
  "option keyword -> that option's suboption table, for round-tripping a
  suboption byte back to a name once the option is known (suboption
  numbering is only meaningful relative to its option, the same
  'field means different things depending on context' shape CANopen's
  SDO command-specifier byte and this frame's own DataStatus have)."
  {:ip ip-suboptions :device-properties device-properties-suboptions
   :control control-suboptions :device-initiative device-initiative-suboptions
   :all all-suboptions})

(defn- reverse-map [m] (into {} (map (fn [[k v]] [v k]) m)))

(defn suboption-name
  "option keyword + suboption byte -> keyword name, or the raw byte if
  this option's table doesn't name it (DHCP suboptions mirror RFC 2132
  option numbers 1-to-1 and are not enumerated here — see 'Not here' in
  the README)."
  [option suboption-byte]
  (if-let [table (get suboptions-by-option option)]
    (get (reverse-map table) suboption-byte suboption-byte)
    suboption-byte))

;; ── TLV block ────────────────────────────────────────────────────────────

(defn encode-block
  "`{:option kw|byte :suboption kw|byte :value [bytes]}` -> `[:ok bytes]`,
  including the trailing pad byte if `(count value)` is odd."
  [{:keys [option suboption value]}]
  (let [opt-byte (if (keyword? option) (get options option) option)
        sub-table (get suboptions-by-option (if (keyword? option) option (get option-by-byte option)))
        sub-byte (if (and (keyword? suboption) sub-table) (get sub-table suboption) suboption)
        value (vec value)]
    (cond
      (nil? opt-byte) [:error :profinet/unknown-dcp-option option]
      (not (<= 0 opt-byte 0xFF)) [:error :profinet/dcp-option-out-of-range opt-byte]
      (nil? sub-byte) [:error :profinet/unknown-dcp-suboption suboption]
      (not (<= 0 sub-byte 0xFF)) [:error :profinet/dcp-suboption-out-of-range sub-byte]
      (not (<= 0 (count value) 0xFFFF)) [:error :profinet/dcp-value-too-long (count value)]
      :else
      (let [pad (if (odd? (count value)) [0] [])]
        [:ok (-> [opt-byte sub-byte] (into (u16be (count value))) (into value) (into pad))]))))

(defn decode-block
  "bytes starting at a block boundary -> `[:ok {:option :suboption :value
  :consumed}]`, where `:consumed` is how many bytes (including any pad)
  the caller should advance by to reach the next block."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 4)
      [:error :profinet/dcp-block-too-short n]
      (let [opt-byte (nth bs 0) sub-byte (nth bs 1)
            len (rd-u16be bs 2)
            pad (if (odd? len) 1 0)]
        (if (< n (+ 4 len pad))
          [:error :profinet/dcp-block-truncated {:need (+ 4 len pad) :have n}]
          (let [option (get option-by-byte opt-byte opt-byte)]
            [:ok {:option option
                  :suboption (suboption-name option sub-byte)
                  :value (subvec bs 4 (+ 4 len))
                  :consumed (+ 4 len pad)}]))))))

(defn encode-blocks
  "`[{:option :suboption :value} ...]` -> `[:ok bytes]`, every block's
  wire bytes concatenated in order, or the first `[:error kw data]` any
  individual block's `encode-block` reports."
  [blocks]
  (reduce (fn [[_ acc] block]
            (let [[st bytes] (encode-block block)]
              (if (= :error st)
                (reduced [:error bytes])
                [:ok (into acc bytes)])))
          [:ok []] blocks))

(defn decode-blocks
  "bytes (the concatenation of all TLV blocks, i.e. a DCP PDU's Data
  field with the 10-byte header already stripped) -> `[:ok [blocks]]`."
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (loop [pos 0 out []]
      (cond
        (= pos n) [:ok out]
        (> pos n) [:error :profinet/dcp-blocks-overran-buffer {:pos pos :total n}]
        :else
        (let [[st block] (decode-block (subvec bs pos n))]
          (if (= :error st)
            [:error block]
            (recur (+ pos (:consumed block)) (conj out (dissoc block :consumed)))))))))

;; ── full PDU ─────────────────────────────────────────────────────────────

(defn encode-pdu
  "`{:service-id kw :service-type kw :xid u32 :response-delay (default 0)
  :blocks [{:option :suboption :value} ...]}` -> `[:ok bytes]`, the
  10-byte header followed by every block."
  [{:keys [service-id service-type xid response-delay blocks] :or {response-delay 0}}]
  (let [sid (get service-ids service-id)
        stype (get service-types service-type)]
    (cond
      (nil? sid) [:error :profinet/unknown-dcp-service-id service-id]
      (nil? stype) [:error :profinet/unknown-dcp-service-type service-type]
      (not (<= 0 xid 0xFFFFFFFF)) [:error :profinet/dcp-xid-out-of-range xid]
      (not (<= 0 response-delay 0xFFFF)) [:error :profinet/dcp-response-delay-out-of-range response-delay]
      :else
      (let [[bst block-bytes] (encode-blocks blocks)]
        (if (= :error bst)
          [:error block-bytes]
          [:ok (-> [sid stype] (into (u32be xid)) (into (u16be response-delay))
                   (into (u16be (count block-bytes))) (into block-bytes))])))))

(defn decode-pdu
  [bytes]
  (let [bs (vec bytes) n (count bs)]
    (if (< n 10)
      [:error :profinet/dcp-pdu-too-short n]
      (let [sid-byte (nth bs 0) stype-byte (nth bs 1)
            xid (rd-u32be bs 2)
            response-delay (rd-u16be bs 6)
            data-length (rd-u16be bs 8)]
        (cond
          (not (contains? service-id-by-byte sid-byte))
          [:error :profinet/unknown-dcp-service-id-byte sid-byte]

          (not (contains? service-type-by-byte stype-byte))
          [:error :profinet/unknown-dcp-service-type-byte stype-byte]

          (not= n (+ 10 data-length))
          [:error :profinet/dcp-pdu-wrong-length {:expected (+ 10 data-length) :actual n}]

          :else
          (let [[blst blocks] (decode-blocks (subvec bs 10 n))]
            (if (= :error blst)
              [:error blocks]
              [:ok {:service-id (get service-id-by-byte sid-byte)
                    :service-type (get service-type-by-byte stype-byte)
                    :xid xid :response-delay response-delay :blocks blocks}])))))))
