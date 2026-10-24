(ns mil1553.status
  "The Status Word's 16-bit payload — an RT's response, immediately
  following the Command Word (and any data words) it answers:

  ```
  bit  1  2  3  4  5 | 6  | 7 | 8  | 9 10 11 | 12  | 13   | 14        | 15   | 16
       RT Address    | ME | I | SR | Reserved| BCR | Busy | Subsystem | DBCA | Terminal
       (5 bits)      |(1) |(1)| (1)| (3, =0) | (1) | (1)  | Flag (1)  | (1)  | Flag (1)
  ```

  RT Address: the RESPONDING terminal's own address, echoed back — a
  receiver checks this against the address it just commanded to detect a
  different RT answering (or, on a broadcast, that the wrong RT answered
  at all — no RT should answer a broadcast, so any Status Word following
  one is itself an anomaly `mil1553.message` flags).

  ME (Message Error): the RT detected an error in the message it just
  received (bad word count, illegal command, etc.) — this bit does not
  by itself say WHAT was wrong, so `mil1553.status` exposes it as a flag,
  not a reason code.

  I (Instrumentation): distinguishes a Status Word from a Command Word
  when a bus monitor cannot rely on Sync polarity alone (both use
  `sync-command-status`) — set to 0 in a Status Word by convention, 1 is
  reserved for a Command Word whose bit 7 a terminal deliberately sets;
  this namespace just reads/writes the bit, it does not enforce that
  convention.

  SR (Service Request): the RT has something to tell the bus controller
  (used with polling mode codes).

  Reserved (bits 9-11): conventionally 0; not otherwise interpreted here.

  BCR (Broadcast Command Received): set when the message this Status
  Word answers was a broadcast — since broadcasts do not normally get a
  Status Word response on the bus at all, a Status Word carrying BCR=1
  is typically the RT's own internally-latched record of the last
  broadcast, polled later, not an immediate bus response.

  Busy: the RT cannot respond to this command right now.

  Subsystem Flag: an RT subsystem (not the 1553 terminal itself) has a
  fault.

  DBCA (Dynamic Bus Control Acceptance): set only in response to the
  'Dynamic Bus Control' mode code, meaning the RT accepts control of the
  bus.

  Terminal Flag: the RT terminal hardware itself has a fault.

  Field order and names here are the standard 1553B Status Word layout
  as consistently repeated across public unclassified sources (see
  `mil1553.word`'s provenance note — same sourcing, and the one this
  library is most confident about among the three task libraries).")

(defn pack
  "`{:rt-address 0-31 :message-error? :instrumentation? :service-request?
  :broadcast-received? :busy? :subsystem-flag? :dbca? :terminal-flag?}`
  (booleans default false) -> `[:ok payload]`."
  [{:keys [rt-address message-error? instrumentation? service-request?
           broadcast-received? busy? subsystem-flag? dbca? terminal-flag?]}]
  (if-not (<= 0 rt-address 31)
    [:error :mil1553/rt-address-out-of-range rt-address]
    (let [b (fn [x] (if x 1 0))]
      [:ok (bit-or (bit-shift-left rt-address 11)
                   (bit-shift-left (b message-error?) 10)
                   (bit-shift-left (b instrumentation?) 9)
                   (bit-shift-left (b service-request?) 8)
                   ;; bits 9-11 (field-local), the 3-bit reserved gap, stay 0
                   (bit-shift-left (b broadcast-received?) 4)
                   (bit-shift-left (b busy?) 3)
                   (bit-shift-left (b subsystem-flag?) 2)
                   (bit-shift-left (b dbca?) 1)
                   (b terminal-flag?))])))

(defn unpack
  "16-bit Status Word `payload` -> `[:ok {...}]` with the same keys
  `pack` takes, booleans decoded back to `true`/`false`, plus `:reserved`
  (the raw 3-bit reserved field, exposed rather than discarded — a
  non-zero reserved field is diagnostic of a device that does not follow
  the convention, not this library's business to hide)."
  [payload]
  (if-not (<= 0 payload 0xFFFF)
    [:error :mil1553/payload-out-of-range payload]
    (let [flag (fn [shift] (= 1 (bit-and (unsigned-bit-shift-right payload shift) 1)))]
      [:ok {:rt-address (bit-and (unsigned-bit-shift-right payload 11) 0x1F)
            :message-error? (flag 10)
            :instrumentation? (flag 9)
            :service-request? (flag 8)
            :reserved (bit-and (unsigned-bit-shift-right payload 5) 0x7)
            :broadcast-received? (flag 4)
            :busy? (flag 3)
            :subsystem-flag? (flag 2)
            :dbca? (flag 1)
            :terminal-flag? (flag 0)}])))
