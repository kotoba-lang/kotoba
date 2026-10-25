(ns canopen.nmt
  "NMT (Network Management) node control commands and the NMT slave states,
  CiA 301 §7.3.

  **NMT Node Control** (COB-ID always `0x000`, DLC 2, master->slave(s)):

    byte0  Command Specifier (cs)   which state transition to request
    byte1  Node-ID                  0 = all nodes (broadcast); 1..127 = one

  Command Specifier values are single bytes, not a bitfield — CiA 301
  enumerates them directly rather than composing them from sub-fields:

    0x01  Start Remote Node          -> Operational
    0x02  Stop Remote Node           -> Stopped
    0x80  Enter Pre-Operational      -> Pre-Operational
    0x81  Reset Node                 -> Initialising (full app + comm reset)
    0x82  Reset Communication        -> Initialising (comm layer reset only)

  **NMT states** the device reports back (via heartbeat, not NMT Node
  Control — there is no 'query state' request in the base protocol, the
  slave simply announces it):

    0x00  Initialising     (transient — a device does not stay here)
    0x04  Stopped
    0x05  Operational
    0x7F  Pre-Operational

  These state values are deliberately *not* 0/1/2/3 — the non-contiguous
  encoding (0, 4, 5, 127) is CiA 301's own choice and this namespace keeps
  it byte-for-byte rather than remapping to a dense enum, so a captured
  heartbeat byte and this namespace's keywords always mean the same thing.

  **Heartbeat** (CiA 301 §7.2.8.3.1, NMT Error Control service): COB-ID
  `0x700 + Node-ID`, DLC 1, slave->master, sent periodically. The single
  data byte carries the current NMT state in bits 6..0; bit 7 is reserved
  and MUST be 0 on the wire (it is the toggle bit of the *older*,
  deprecated Node Guarding protocol this replaced, and CiA 301 explicitly
  reserves it here rather than reusing it). Boot-up is a heartbeat message
  with state `0x00`, sent once, immediately after entering
  Pre-Operational — not a separate frame format.

  Source: this command/state table is reproduced identically across every
  open CANopen stack checked — CANopenNode's `301/CO_NMT_Heartbeat.h`
  (`CO_NMT_command_t`, `CO_NMT_internalState_t`), python-canopen's
  `canopen/nmt.py`, and Wireshark's `packet-canopen.c` — CiA 301 itself
  being a paywalled document not quoted here from memory.")

;; ── commands ─────────────────────────────────────────────────────────────

(def commands
  "command keyword -> command specifier byte"
  {:start                0x01
   :stop                 0x02
   :enter-pre-operational 0x80
   :reset-node           0x81
   :reset-communication  0x82})

(def command-by-byte (into {} (map (fn [[k v]] [v k]) commands)))

(defn encode-command
  "`{:command kw :target-node 0..127}` -> `[:ok [cs node]]`, the two NMT
  Node Control data bytes. `:target-node` 0 addresses all nodes."
  [{:keys [command target-node]}]
  (cond
    (not (contains? commands command))
    [:error :canopen/unknown-nmt-command command]

    (not (<= 0 target-node 127))
    [:error :canopen/node-id-out-of-range target-node]

    :else
    [:ok [(get commands command) (bit-and target-node 0x7F)]]))

(defn decode-command
  "2 data bytes -> `[:ok {:command :target-node}]`."
  [bytes]
  (let [bs (vec bytes)]
    (cond
      (not= 2 (count bs)) [:error :canopen/nmt-command-wrong-length (count bs)]
      (not (contains? command-by-byte (first bs)))
      [:error :canopen/unknown-nmt-command-specifier (first bs)]
      :else [:ok {:command (get command-by-byte (first bs))
                  :target-node (second bs)}])))

;; ── states ───────────────────────────────────────────────────────────────

(def states
  "state keyword -> heartbeat state byte"
  {:initialising     0x00
   :stopped          0x04
   :operational      0x05
   :pre-operational  0x7F})

(def state-by-byte (into {} (map (fn [[k v]] [v k]) states)))

;; ── heartbeat / boot-up ──────────────────────────────────────────────────

(defn encode-heartbeat
  "`{:state kw}` -> `[:ok [byte]]`, the single heartbeat data byte. Bit 7
  (the old node-guarding toggle bit) is always emitted as 0."
  [{:keys [state]}]
  (if-not (contains? states state)
    [:error :canopen/unknown-nmt-state state]
    [:ok [(bit-and (get states state) 0x7F)]]))

(defn decode-heartbeat
  "1 data byte -> `[:ok {:state kw :toggle-bit-set? bool}]`. A malformed
  producer that leaks the reserved bit 7 is reported, not silently masked
  — `:toggle-bit-set?` true means the byte does not round-trip through
  `encode-heartbeat` unchanged, which is diagnostic on a real bus."
  [bytes]
  (let [bs (vec bytes)]
    (cond
      (not= 1 (count bs)) [:error :canopen/heartbeat-wrong-length (count bs)]
      :else
      (let [b (first bs)
            state-bits (bit-and b 0x7F)
            toggle? (pos? (bit-and b 0x80))]
        (if-not (contains? state-by-byte state-bits)
          [:error :canopen/unknown-nmt-state-byte state-bits]
          [:ok {:state (get state-by-byte state-bits) :toggle-bit-set? toggle?}])))))

(defn boot-up?
  "true when a decoded heartbeat map reports the boot-up message (state
  Initialising, sent once on power-up)."
  [{:keys [state]}]
  (= state :initialising))
