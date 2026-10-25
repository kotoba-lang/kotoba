(ns matter.message
  "The Matter message header — the outermost framing every Matter UDP/TCP/
  BLE packet starts with, before the protocol (exchange) header
  (`matter.protocol`) and the TLV application payload (`matter.tlv`).
  Matter's transport independence is why this repository has no
  dependency on the shared IEEE 802.15.4 MAC layer the other two
  repositories in this task build/reuse — this header rides directly
  over UDP/TCP/BLE, never over a raw 802.15.4 frame.

  ## Provenance

  The Matter specification is a CSA member document; nothing here is a
  spec quotation. The **field set** (a Message Flags byte carrying a
  protocol version and a Source-Node-ID-present flag and a destination-
  ID-size selector; a 16-bit Session ID; a Security Flags byte carrying a
  session type and control/extensions/privacy bits; a 32-bit Message
  Counter; an optional 64-bit Source Node ID; an optional 64-bit
  Destination Node ID or 16-bit Destination Group ID) is corroborated
  across public descriptions of Matter's message layer and the
  open-source (Apache-2.0) `connectedhomeip` reference implementation's
  `lib/core/PacketHeader.h`/`.cpp`. **The exact bit position of each
  subfield within the Message Flags and Security Flags octets is this
  repository's own reconstruction** — see 'Least confident value' below.
  All multi-byte fields are little-endian, matching Matter's wire
  convention throughout (`connectedhomeip`'s header encode/decode uses
  `chip::Encoding::LittleEndian` uniformly). **Every concrete byte
  sequence in this library's tests is `;; constructed, not a published
  spec vector`.**

  ## Message Flags (1 byte):

    bits 3-0  Version           protocol version (0 for this generation)
    bit  4    S                 Source Node ID present
    bits 6-5  DSIZ              0 none / 1 64-bit Destination Node ID /
                                 2 16-bit Destination Group ID / 3 reserved
    bit  7    Reserved (must be 0)

  ## Security Flags (1 byte):

    bits 1-0  Session Type      0 Unicast / 1 Group
    bits 4-2  Reserved
    bit  5    C                 Control Message
    bit  6    MX                Message Extensions present (not decoded
                                 here — see README 'Not here')
    bit  7    P                 Privacy

  ## Field order on the wire:

    Message Flags(1) | Session ID(2) | Security Flags(1) | Message
    Counter(4) | [Source Node ID(8), iff S] | [Destination Node ID(8) iff
    DSIZ=1, or Destination Group ID(2) iff DSIZ=2] | rest (the protocol
    header + TLV payload, opaque to this namespace)

  ## Least confident value in this repository

  **The bit positions within Message Flags and Security Flags** — that
  Version/S/DSIZ exist as fields of the Message Flags octet, and that
  Session-Type/C/MX/P exist as fields of the Security Flags octet, is
  well corroborated; *which bits* each occupies is this library's own
  choice, made self-consistent and stated explicitly here rather than
  asserted with false confidence. If a real Matter capture disagrees,
  only the bit-position constants in this file need to change — the
  field set and their presence rules (S gates Source Node ID, DSIZ gates
  which of the two destination forms appears) are the part this
  library's confidence rests on.")

;; ── little-endian helpers ───────────────────────────────────────────────

(defn- u16le [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-u16le [bs off] (bit-or (bit-and (nth bs off) 0xFF)
                                  (bit-shift-left (bit-and (nth bs (inc off)) 0xFF) 8)))
(defn- u32le [n] [(bit-and n 0xFF)
                   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 24) 0xFF)])
(defn- rd-u32le [bs off]
  ;; unsigned-bit-shift-right ... 0 at the end: a Message Counter whose
  ;; top byte has its high bit set would otherwise come back NEGATIVE
  ;; under ClojureScript's 32-bit signed bit-or/bit-shift-left (the exact
  ;; shape `org-ethercat`'s `rd-u32le` documents this same fix for). No
  ;; effect on the JVM, which already produces a nonnegative Long here.
  (unsigned-bit-shift-right
   (bit-or (bit-and (nth bs off) 0xFF)
           (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 8)
           (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 16)
           (bit-shift-left (bit-and (nth bs (+ off 3)) 0xFF) 24))
   0))
(defn- u64le [n]
  ;; quot/mod, not bit-shift — a Node ID with its top bit set is a value
  ;; the JVM reader promotes to BigInt, which rejects bit-ops outright
  ;; (`Numbers.bitOpsCast` throws). Same pattern as `org-csa-iot-zigbee`'s
  ;; `ieee802154.mac/u64le` and `org-threadgroup-thread`'s `thread.mesh`.
  (loop [x n i 0 acc []]
    (if (= i 8) acc (recur (quot x 256) (inc i) (conj acc (int (mod x 256)))))))
(defn- rd-u64le [bs off]
  (reduce (fn [acc b] #?(:clj (+' (*' acc 256) b) :cljs (+ (* acc 256) b)))
          0 (reverse (subvec (vec bs) off (+ off 8)))))

;; ── vocabulary ──────────────────────────────────────────────────────────

(def dsiz-modes {:none 0 :node-id 1 :group-id 2})
(def dsiz-mode-by-code (into {} (map (fn [[k v]] [v k]) dsiz-modes)))

(def session-types {:unicast 0 :group 1})
(def session-type-by-code (into {} (map (fn [[k v]] [v k]) session-types)))

;; ── Message Flags ───────────────────────────────────────────────────────

(defn build-message-flags
  [{:keys [version source-node-id? dsiz] :or {version 0 dsiz :none}}]
  (cond
    (not (<= 0 version 0x0F)) [:error :matter.message/version-out-of-range version]
    (not (contains? dsiz-modes dsiz)) [:error :matter.message/reserved-dsiz dsiz]
    :else [:ok (bit-or (bit-and version 0x0F)
                        (bit-shift-left (if source-node-id? 1 0) 4)
                        (bit-shift-left (bit-and (dsiz-modes dsiz) 0x03) 5))]))

(defn parse-message-flags
  [b]
  (let [dsiz-code (bit-and (unsigned-bit-shift-right b 5) 0x03)]
    (if-not (contains? dsiz-mode-by-code dsiz-code)
      [:error :matter.message/reserved-dsiz dsiz-code]
      [:ok {:version (bit-and b 0x0F)
            :source-node-id? (bit-test b 4)
            :dsiz (dsiz-mode-by-code dsiz-code)}])))

;; ── Security Flags ──────────────────────────────────────────────────────

(defn build-security-flags
  [{:keys [session-type control? message-extensions? privacy?] :or {session-type :unicast}}]
  (if-not (contains? session-types session-type)
    [:error :matter.message/reserved-session-type session-type]
    [:ok (bit-or (bit-and (session-types session-type) 0x03)
                 (bit-shift-left (if control? 1 0) 5)
                 (bit-shift-left (if message-extensions? 1 0) 6)
                 (bit-shift-left (if privacy? 1 0) 7))]))

(defn parse-security-flags
  [b]
  (let [st-code (bit-and b 0x03)]
    (if-not (contains? session-type-by-code st-code)
      [:error :matter.message/reserved-session-type st-code]
      [:ok {:session-type (session-type-by-code st-code)
            :control? (bit-test b 5)
            :message-extensions? (bit-test b 6)
            :privacy? (bit-test b 7)}])))

;; ── full header ─────────────────────────────────────────────────────────

(defn encode
  "`{:version :source-node-id? :dsiz :session-id :session-type :control?
  :message-extensions? :privacy? :message-counter :source-node-id
  :dest-node-id :dest-group-id :payload}` -> `[:ok bytes]` | `[:error
  reason ...]`. `:payload` is the (opaque here) protocol header + TLV
  application payload that follows."
  [{:keys [session-id message-counter source-node-id dest-node-id dest-group-id payload]
    :or {payload []} :as m}]
  (let [[fst mflags] (build-message-flags m)]
    (if (= fst :error)
      [fst mflags]
      (let [[_ pmflags] (parse-message-flags mflags)
            {:keys [source-node-id? dsiz]} pmflags
            [sst sflags] (build-security-flags m)]
        (if (= sst :error)
          [sst sflags]
          (cond
            (not (<= 0 session-id 0xFFFF)) [:error :matter.message/session-id-out-of-range session-id]
            (not (<= 0 message-counter 0xFFFFFFFF)) [:error :matter.message/counter-out-of-range message-counter]
            (and source-node-id? (nil? source-node-id)) [:error :matter.message/missing-source-node-id]
            (and (= dsiz :node-id) (nil? dest-node-id)) [:error :matter.message/missing-dest-node-id]
            (and (= dsiz :group-id) (nil? dest-group-id)) [:error :matter.message/missing-dest-group-id]
            (and (= dsiz :group-id) (not (<= 0 dest-group-id 0xFFFF)))
            [:error :matter.message/dest-group-id-out-of-range dest-group-id]

            :else
            [:ok (vec (concat [mflags] (u16le session-id) [sflags] (u32le message-counter)
                               (when source-node-id? (u64le source-node-id))
                               (when (= dsiz :node-id) (u64le dest-node-id))
                               (when (= dsiz :group-id) (u16le dest-group-id))
                               payload))]))))))

(defn decode
  [bs]
  (let [bs (vec bs) n (count bs)]
    (if (< n 8)
      [:error :matter.message/header-too-short n]
      (let [[fst mflags :as fparsed] (parse-message-flags (nth bs 0))]
        (if (= fst :error)
          (vec fparsed)
          (let [{:keys [source-node-id? dsiz]} mflags
                [sst sflags :as sparsed] (parse-security-flags (nth bs 3))]
            (if (= sst :error)
              (vec sparsed)
              (let [need (+ 8 (if source-node-id? 8 0)
                            (case dsiz :none 0 :node-id 8 :group-id 2))]
                (if (< n need)
                  [:error :matter.message/header-too-short n]
                  (let [session-id (rd-u16le bs 1)
                        message-counter (rd-u32le bs 4)
                        off (atom 8)
                        source-node-id (when source-node-id? (let [v (rd-u64le bs @off)] (swap! off + 8) v))
                        dest-node-id (when (= dsiz :node-id) (let [v (rd-u64le bs @off)] (swap! off + 8) v))
                        dest-group-id (when (= dsiz :group-id) (let [v (rd-u16le bs @off)] (swap! off + 2) v))]
                    [:ok (cond-> {:message-flags mflags :session-id session-id
                                  :security-flags sflags :message-counter message-counter
                                  :payload (subvec bs @off n)}
                           source-node-id? (assoc :source-node-id source-node-id)
                           (= dsiz :node-id) (assoc :dest-node-id dest-node-id)
                           (= dsiz :group-id) (assoc :dest-group-id dest-group-id))]))))))))))
