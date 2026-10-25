(ns canopen.cob-id
  "The 11-bit standard CAN identifier CANopen (CiA 301) packs its
  Communication Object Identifier onto, and the Predefined Connection Set
  that assigns a fixed identifier range to every CANopen communication
  object.

  Bit layout, MSB to LSB, 11 bits total (CiA 301 §7.1.2, 'Structure of the
  COB-ID'):

    10..7  Function Code   4 bits — which kind of object this is
     6..0  Node-ID         7 bits — which node it is to/from (1..127;
                                    0 is not a valid CANopen node-id)

  `cob-id = (function-code << 7) | node-id`. This is the CAN identifier
  equivalent of J1939's `PF`/`PS`/`SA` split in `org-sae-j1939`'s
  `j1939.identifier`, but CAN**open** rides the 11-bit *base* (standard)
  frame, not the 29-bit *extended* frame J1939 uses — a fundamentally
  different identifier space, not just a narrower field.

  **The trap this namespace exists to avoid**: four of the sixteen function
  codes (0000 NMT, 0001 SYNC/EMCY, 0010 TIME) are only *partially*
  node-addressed. NMT's node-id byte travels in the *payload*, not the
  identifier (COB-ID is always exactly 0x000). SYNC and TIME are pure
  broadcasts with the node-id field held at 0 — CANopen node-ids start at 1,
  so 0x080 and 0x100 are unambiguous even though they share the same 11-bit
  shape as a per-node COB-ID. EMCY, by contrast, *does* use the node-id
  field (0x081..0x0FF) despite sharing function code 0001 with SYNC — an
  implementation that assumes 'same function code, same addressing rule'
  gets EMCY wrong the moment it tries to derive a node-id from 0x080.

  Sources: this table (predefined connection set) is reproduced identically
  across every open CANopen stack this was checked against —
  python-canopen's `canopen/objectdictionary` COB-ID conventions,
  CANopenNode's `301/CO_NMT_Heartbeat.h` / `CO_SDOserver.h` constants, and
  Wireshark's `packet-canopen.c` dissector — because CiA 301 itself is a
  paywalled CAN in Automation membership document not quoted here from
  memory.")

;; ── the 11-bit identifier ────────────────────────────────────────────────

(def max-cob-id "2^11 - 1, the full standard-frame identifier space." 0x7FF)
(def max-node-id "CANopen node-ids run 1..127. 0 is reserved (broadcast/none)." 127)
(def max-function-code "4-bit field: 0..15." 15)

(defn pack-cob-id
  "`{:function-code 0..15 :node-id 0..127}` -> `[:ok cob-id]`, an 11-bit
  unsigned integer. `:node-id` 0 is accepted (SYNC/TIME/NMT all encode it
  that way) even though 0 is not a valid *device* node-id — this function
  packs bits, it does not judge whether the resulting COB-ID names a real
  device."
  [{:keys [function-code node-id]}]
  (cond
    (not (<= 0 function-code max-function-code))
    [:error :canopen/function-code-out-of-range function-code]

    (not (<= 0 node-id max-node-id))
    [:error :canopen/node-id-out-of-range node-id]

    :else
    [:ok (bit-or (bit-shift-left (bit-and function-code 0xF) 7)
                 (bit-and node-id 0x7F))]))

(defn unpack-cob-id
  "11-bit COB-ID -> `[:ok {:function-code :node-id}]`."
  [cob-id]
  (if-not (<= 0 cob-id max-cob-id)
    [:error :canopen/cob-id-out-of-range cob-id]
    [:ok {:function-code (bit-and (unsigned-bit-shift-right cob-id 7) 0xF)
          :node-id (bit-and cob-id 0x7F)}]))

;; ── predefined connection set, CiA 301 §7.1 ─────────────────────────────
;; function-code -> {object base-cob-id addressing}. `:addressing` is
;; `:broadcast` (node-id field always 0, no device targets it directly),
;; `:node` (base + node-id, node-id 1..127), or `:payload` (NMT — the
;; node-id being controlled travels in the data bytes, not the identifier).

(def predefined-connection-set
  "function-code -> {:object kw :base int :addressing kw}"
  {0  {:object :nmt         :base 0x000 :addressing :payload}
   1  {:object :sync        :base 0x080 :addressing :broadcast}   ; EMCY shares
   2  {:object :time        :base 0x100 :addressing :broadcast}
   3  {:object :pdo1-tx     :base 0x180 :addressing :node}
   4  {:object :pdo1-rx     :base 0x200 :addressing :node}
   5  {:object :pdo2-tx     :base 0x280 :addressing :node}
   6  {:object :pdo2-rx     :base 0x300 :addressing :node}
   7  {:object :pdo3-tx     :base 0x380 :addressing :node}
   8  {:object :pdo3-rx     :base 0x400 :addressing :node}
   9  {:object :pdo4-tx     :base 0x480 :addressing :node}
   10 {:object :pdo4-rx     :base 0x500 :addressing :node}
   11 {:object :sdo-tx      :base 0x580 :addressing :node}        ; server->client
   12 {:object :sdo-rx      :base 0x600 :addressing :node}        ; client->server
   14 {:object :heartbeat   :base 0x700 :addressing :node}})      ; NMT error control

;; EMCY shares function-code 1 with SYNC but IS node-addressed (0x081..0x0FF,
;; never 0x080 itself — that value is SYNC). Kept as a second table entry
;; rather than folded into `predefined-connection-set` above so a
;; function-code -> object lookup stays a total function; `object->cob-id`
;; and `cob-id->object` below both special-case it.
(def emcy-function-code 1)
(def emcy-base 0x080)

(defn object->function-code
  "Object keyword (`:nmt` `:sync` `:emcy` `:time` `:pdo1-tx` ... `:sdo-rx`
  `:heartbeat`) -> function code, or nil if unknown."
  [object]
  (if (= object :emcy)
    emcy-function-code
    (some (fn [[fc {:keys [object] :as e}]] (when (= object (:object e)) fc))
          predefined-connection-set)))

(defn object->cob-id
  "Object keyword + node-id (ignored for `:sync`/`:time`, required and
  0-excluded for everything else) -> `[:ok cob-id]`.

  `:nmt` always yields `[:ok 0x000]` regardless of `node-id` — the target
  node for an NMT command lives in the command's payload byte, not here;
  see `canopen.nmt/encode-command`."
  ([object] (object->cob-id object 0))
  ([object node-id]
   (case object
     :nmt [:ok 0x000]
     :sync [:ok 0x080]
     :time [:ok 0x100]
     :emcy (if (<= 1 node-id max-node-id)
             [:ok (+ emcy-base node-id)]
             [:error :canopen/node-id-out-of-range node-id])
     (if-let [entry (some (fn [[_ e]] (when (= object (:object e)) e))
                          predefined-connection-set)]
       (if (<= 1 node-id max-node-id)
         [:ok (+ (:base entry) node-id)]
         [:error :canopen/node-id-out-of-range node-id])
       [:error :canopen/unknown-object object]))))

(defn cob-id->object
  "Best-effort inverse: 11-bit COB-ID -> `[:ok {:object :node-id}]`.
  `:node-id` is 0 (meaningless) for `:nmt`/`:sync`/`:time`."
  [cob-id]
  (let [[st fields] (unpack-cob-id cob-id)]
    (if (= :error st)
      [:error fields]
      (let [{:keys [function-code node-id]} fields]
        (cond
          (= cob-id 0x000) [:ok {:object :nmt :node-id 0}]
          (= cob-id 0x080) [:ok {:object :sync :node-id 0}]
          (= cob-id 0x100) [:ok {:object :time :node-id 0}]
          (and (= function-code emcy-function-code) (pos? node-id))
          [:ok {:object :emcy :node-id node-id}]

          (contains? predefined-connection-set function-code)
          (let [{:keys [object addressing]} (get predefined-connection-set function-code)]
            (if (and (= addressing :node) (pos? node-id))
              [:ok {:object object :node-id node-id}]
              [:error :canopen/cob-id-not-node-addressed cob-id]))

          :else [:error :canopen/unknown-function-code function-code])))))
