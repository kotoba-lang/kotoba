(ns ethercat.datagram
  "The EtherCAT datagram, ETG.1000/ETG.1500 — the addressed read/write
  command that rides inside a frame (see `ethercat.frame`), one or more
  per frame. This is where the 'process image over raw Ethernet' idea
  actually lives: each slave on the ring reads its own header fields as
  the frame passes through, and for a matching command, reads and/or
  writes the `Data` field **in place** before forwarding the frame to
  the next slave — the datagram that leaves the master and the one that
  returns to it are the same bytes, mutated on the way.

  Layout, **little-endian throughout** (10-byte header + Data + 2-byte
  WKC trailer):

    byte 0      Cmd            command code, see `commands` below
    byte 1      Idx            index — an opaque tag the master uses to
                                match a returned datagram to the request
                                that produced it; EtherCAT slaves never
                                interpret it
    bytes 2..5  Address        4 bytes, meaning depends on Cmd — see
                                'Addressing modes' below
    bytes 6..7  Len/flags      11-bit Len, 3-bit reserved, 1-bit C, 1-bit
                                M — see below
    bytes 8..9  IRQ            application-specific interrupt request
                                mask, opaque to this codec
    bytes ..    Data           `Len` bytes
    last 2      WKC            Working Counter — see `ethercat.wkc`

  **Len/flags word** (bytes 6..7, little-endian u16, same 11+reserved
  split shape as the frame header but with two flag bits instead of a
  4-bit type):

    bits 10..0  Len    length of Data in bytes (0..2047)
    bits 13..11 Reserved (3 bits, must be 0)
    bit 14      C (Circulating)  a slave sets this when it recognises the
                                 frame has already been all the way around
                                 the ring once — the frame not returning
                                 to the master is diagnosable from this,
                                 not silently dropped
    bit 15      M (More)         1 = another datagram follows this one in
                                 the same frame; 0 = this is the last

  **Addressing modes**, selected entirely by which Cmd is used:

    device (APRD/APWR/APRW/FPRD/FPWR/FPRW/BRD/BWR/BRW/ARMW/FRMW):
      bytes 2..3  ADP   Auto-increment Position (AP*, BRD/BWR/BRW — see
                        `pack-position-address`) or a Fixed/Configured
                        Station Address (FP*, ARMW/FRMW), depending on
                        which of those two families Cmd belongs to
      bytes 4..5  ADO   byte offset into the addressed slave's memory

    logical (LRD/LWR/LRW):
      bytes 2..5  a single 32-bit Logical Address — not split into two
                  16-bit fields. A slave with an FMMU (Fieldbus Memory
                  Management Unit) mapped over part of this address
                  range reads/writes its corresponding portion of Data;
                  FMMU configuration itself is out of scope here (see
                  'Not here' in the README)

  Auto-increment addressing (AP*) counts DOWN, not up: the master writes
  `-N` (two's complement, `pack-position-address`) to address the Nth
  slave counting from the one physically nearest the master (N=0); each
  slave decrements the field by 1 as the frame passes through, and the
  slave that sees it become 0 responds.

  Source: command codes, the Len/flags bit split, and the AP*
  decrement-to-zero addressing convention are reproduced identically in
  SOEM (`soem/ethercattype.h` — `EC_CMD_*`, and `soem/ethercatmain.c`'s
  `ecx_APRD`/`ecx_FPRD`/etc. wrappers), IgH EtherCAT Master
  (`master/ethernet.h`, `master/datagram.c`), and Wireshark's
  `packet-ecatmb.c`. ETG.1000/1500 themselves are paywalled EtherCAT
  Technology Group membership documents not quoted here from memory.")

;; ── little-endian helpers ────────────────────────────────────────────────

(defn- u16le [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-u16le [bs off] (bit-or (bit-and (nth bs off) 0xFF)
                                  (bit-shift-left (bit-and (nth bs (inc off)) 0xFF) 8)))
(defn- u32le [n] [(bit-and n 0xFF)
                   (bit-and (unsigned-bit-shift-right n 8) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 16) 0xFF)
                   (bit-and (unsigned-bit-shift-right n 24) 0xFF)])
(defn- rd-u32le [bs off]
  ;; `unsigned-bit-shift-right ... 0` at the end: ClojureScript's
  ;; `bit-shift-left`/`bit-or` are 32-bit SIGNED (JS semantics) — a
  ;; Logical Address whose top byte has its high bit set (>=0x80, i.e.
  ;; more than half the 32-bit space) would otherwise come back as a
  ;; NEGATIVE host number instead of the intended 0..4294967295 unsigned
  ;; value. No effect on the JVM, where this expression already produces
  ;; a nonnegative Long.
  (unsigned-bit-shift-right
   (bit-or (bit-and (nth bs off) 0xFF)
           (bit-shift-left (bit-and (nth bs (+ off 1)) 0xFF) 8)
           (bit-shift-left (bit-and (nth bs (+ off 2)) 0xFF) 16)
           (bit-shift-left (bit-and (nth bs (+ off 3)) 0xFF) 24))
   0))

;; ── commands, SOEM ethercattype.h EC_CMD_* ──────────────────────────────

(def commands
  "command keyword -> Cmd byte."
  {:nop  0x00
   :aprd 0x01 :apwr 0x02 :aprw 0x03
   :fprd 0x04 :fpwr 0x05 :fprw 0x06
   :brd  0x07 :bwr  0x08 :brw  0x09
   :lrd  0x0A :lwr  0x0B :lrw  0x0C
   :armw 0x0D :frmw 0x0E})

(def command-by-byte (into {} (map (fn [[k v]] [v k]) commands)))

(def logical-addressed-commands #{:lrd :lwr :lrw})
(def device-addressed-commands #{:aprd :apwr :aprw :fprd :fpwr :fprw :brd :bwr :brw :armw :frmw})

(defn command-addressing-mode
  "`:logical`, `:device`, or nil for `:nop`."
  [command]
  (cond (logical-addressed-commands command) :logical
        (device-addressed-commands command) :device
        :else nil))

;; ── auto-increment position addressing ──────────────────────────────────

(defn pack-position-address
  "Slave position N (0 = nearest the master) -> `[:ok adp]`, the 16-bit
  two's-complement value `(-N) mod 65536` that ADP carries for AP*
  commands. N must be 0..65535."
  [n]
  (if-not (<= 0 n 0xFFFF)
    [:error :ethercat/position-out-of-range n]
    [:ok (bit-and (- n) 0xFFFF)]))

(defn unpack-position-address
  "The inverse: ADP (as received, still counting down — this reports how
  many decrements from 0 it represents, i.e. the ORIGINAL N the master
  wrote, not the live in-flight counter value) -> `[:ok n]`."
  [adp]
  (if-not (<= 0 adp 0xFFFF)
    [:error :ethercat/adp-out-of-range adp]
    [:ok (bit-and (- adp) 0xFFFF)]))

;; ── len/flags word ───────────────────────────────────────────────────────

(def max-data-length 0x7FF)

(defn- pack-len-flags [{:keys [length circulating? more?]}]
  (bit-or (bit-and length 0x7FF)
          (bit-shift-left (if circulating? 1 0) 14)
          (bit-shift-left (if more? 1 0) 15)))

(defn- unpack-len-flags [word]
  {:length (bit-and word 0x7FF)
   :reserved (bit-and (unsigned-bit-shift-right word 11) 0x7)
   :circulating? (pos? (bit-and word 0x4000))
   :more? (pos? (bit-and word 0x8000))})

;; ── datagram codec ───────────────────────────────────────────────────────

(defn encode-datagram
  "`{:command kw :index 0..255
    ;; device-addressed commands:
    :adp 0..65535 :ado 0..65535
    ;; logical-addressed commands (:lrd :lwr :lrw):
    :logical-address 0..4294967295
    :data [bytes] :irq (default 0) :circulating? (default false)
    :more? (default false) :wkc (default 0)}`
  -> `[:ok bytes]`, header + Data + WKC. `:more?` is the master's own
  bookkeeping about whether another datagram follows in this frame — set
  it explicitly (see `ethercat.frame/encode-frame` for the version that
  derives it automatically for a list of datagrams)."
  [{:keys [command index adp ado logical-address data irq circulating? more? wkc]
    :or {irq 0 circulating? false more? false wkc 0}}]
  (let [data (vec data)
        mode (command-addressing-mode command)]
    (cond
      (not (contains? commands command)) [:error :ethercat/unknown-command command]
      (not (<= 0 index 0xFF)) [:error :ethercat/index-out-of-range index]
      (not (<= 0 (count data) max-data-length)) [:error :ethercat/data-too-long (count data)]
      (not (<= 0 wkc 0xFFFF)) [:error :ethercat/wkc-out-of-range wkc]
      (nil? mode) [:error :ethercat/nop-has-no-datagram-payload command]

      (and (= mode :device) (or (nil? adp) (nil? ado)))
      [:error :ethercat/device-addressing-requires-adp-ado command]

      (and (= mode :device) (not (<= 0 adp 0xFFFF)))
      [:error :ethercat/adp-out-of-range adp]

      (and (= mode :device) (not (<= 0 ado 0xFFFF)))
      [:error :ethercat/ado-out-of-range ado]

      (and (= mode :logical) (nil? logical-address))
      [:error :ethercat/logical-addressing-requires-logical-address command]

      (and (= mode :logical) (not (<= 0 logical-address 0xFFFFFFFF)))
      [:error :ethercat/logical-address-out-of-range logical-address]

      :else
      (let [addr-bytes (if (= mode :logical) (u32le logical-address) (into (u16le adp) (u16le ado)))
            len-flags (pack-len-flags {:length (count data) :circulating? circulating? :more? more?})]
        [:ok (-> [(get commands command) (bit-and index 0xFF)]
                  (into addr-bytes)
                  (into (u16le len-flags))
                  (into (u16le irq))
                  (into data)
                  (into (u16le wkc)))]))))

(defn decode-datagram
  "bytes -> `[:ok {:command :index :adp :ado (device) OR :logical-address
  (logical) :data :irq :circulating? :more? :length :wkc}]`. The value
  returned always has EXACTLY the address keys appropriate to `:command`
  — never both, never neither — so a caller cannot accidentally read a
  stale `:adp` from a logical-addressed datagram."
  [bytes]
  (let [bs (vec bytes)
        n (count bs)]
    (cond
      (< n 12) [:error :ethercat/datagram-too-short n]
      (not (contains? command-by-byte (first bs)))
      [:error :ethercat/unknown-command-byte (first bs)]
      :else
      (let [command (get command-by-byte (first bs))
            index (nth bs 1)
            mode (command-addressing-mode command)
            len-flags (unpack-len-flags (rd-u16le bs 6))
            {:keys [length circulating? more?]} len-flags
            expected-total (+ 10 length 2)]
        (cond
          (nil? mode) [:error :ethercat/nop-has-no-datagram-payload command]
          (not= expected-total n)
          [:error :ethercat/datagram-wrong-length {:expected expected-total :actual n}]
          :else
          (let [irq (rd-u16le bs 8)
                data (subvec bs 10 (+ 10 length))
                wkc (rd-u16le bs (+ 10 length))
                addr (if (= mode :logical)
                       {:logical-address (rd-u32le bs 2)}
                       {:adp (rd-u16le bs 2) :ado (rd-u16le bs 4)})]
            [:ok (merge {:command command :index index :data data :irq irq
                         :circulating? circulating? :more? more? :length length :wkc wkc}
                        addr)]))))))
