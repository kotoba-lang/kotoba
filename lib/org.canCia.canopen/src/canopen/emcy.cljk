(ns canopen.emcy
  "EMCY (Emergency) messages, CiA 301 §7.2.7. COB-ID `0x080 + Node-ID` (see
  `canopen.cob-id`), DLC 8, sent once when an error condition is detected
  or cleared — not periodic like heartbeat.

    byte0..1  Emergency Error Code   u16, **little-endian**, CiA 301
                                      Table 26 error-code classes
    byte2     Error Register         u8 bitmask, mirrors Object 0x1001
    byte3..7  Manufacturer-specific  5 bytes, meaning is device-defined

  Emergency Error Code high nibble selects a class (Table 26):

    0x00xx  Error Reset / No Error     0x60xx  Device Software
    0x10xx  Generic Error              0x70xx  (reserved)
    0x2xxx  Current                    0x80xx  Monitoring
    0x3xxx  Voltage                    0x90xx  External Error
    0x4xxx  Temperature                0xF0xx  Additional Functions
    0x5xxx  Device Hardware            0xFFxx  Device Specific

  Error Register bits (Object 0x1001, CiA 301 §7.5.2.7) are a
  contains-not-classifies bitmask — several can be set at once, and bit 0
  MUST be set on every EMCY that signals an error (it is cleared only by
  the error-reset EMCY, code 0x0000):

    bit0  generic          bit4  communication
    bit1  current           bit5  device-profile-specific
    bit2  voltage           bit6  reserved (always 0)
    bit3  temperature       bit7  manufacturer-specific

  Source: field layout and the error-register bit table are reproduced
  identically in CANopenNode's `301/CO_Emergency.h` (`CO_EM_errorStatusBits`
  and the `errorRegister` bit macros) and python-canopen's
  `canopen/emcy.py`; CiA 301 §7.2.7/Table 26 itself is a paywalled CAN in
  Automation document not quoted here from memory.")

;; ── little-endian u16 ────────────────────────────────────────────────────

(defn- u16le [n] [(bit-and n 0xFF) (bit-and (unsigned-bit-shift-right n 8) 0xFF)])
(defn- rd-u16le [bs off] (bit-or (bit-and (nth bs off) 0xFF)
                                  (bit-shift-left (bit-and (nth bs (inc off)) 0xFF) 8)))

;; ── error register bits ──────────────────────────────────────────────────

(def error-register-bits
  {:generic 0 :current 1 :voltage 2 :temperature 3
   :communication 4 :device-profile-specific 5 :manufacturer-specific 7})

(defn error-register->flags
  "u8 -> set of the named bits that are set, e.g. `#{:generic :voltage}`."
  [reg]
  (into #{} (keep (fn [[k bit]] (when (pos? (bit-and reg (bit-shift-left 1 bit))) k))
                   error-register-bits)))

(defn flags->error-register
  "set of bit-name keywords -> u8."
  [flags]
  (reduce (fn [r k] (bit-or r (bit-shift-left 1 (get error-register-bits k 0)))) 0 flags))

;; ── error code class ─────────────────────────────────────────────────────

(def error-code-classes
  "High byte (or, for 0x2xxx..0x9xxx, high nibble) of the Emergency Error
  Code -> class keyword, CiA 301 Table 26."
  {0x00 :error-reset 0x01 :error-reset
   0x10 :generic
   0x20 :current 0x21 :current 0x22 :current 0x23 :current
   0x30 :voltage 0x31 :voltage 0x32 :voltage 0x33 :voltage
   0x40 :temperature 0x41 :temperature 0x42 :temperature 0x43 :temperature
   0x50 :device-hardware
   0x60 :device-software 0x61 :device-software 0x62 :device-software 0x63 :device-software
   0x80 :monitoring 0x81 :monitoring 0x82 :monitoring 0x83 :monitoring
   0x90 :external-error 0x91 :external-error
   0xF0 :additional-functions
   0xFF :device-specific})

(defn error-code-class
  "u16 emergency error code -> class keyword, or `:unknown` if the high
  byte is not in `error-code-classes`."
  [code]
  (get error-code-classes (bit-and (unsigned-bit-shift-right code 8) 0xFF) :unknown))

;; ── codec ────────────────────────────────────────────────────────────────

(defn encode
  "`{:error-code :error-register :manufacturer-data (<=5 bytes)}` -> `[:ok
  bytes]` (8)."
  [{:keys [error-code error-register manufacturer-data]
    :or {manufacturer-data []}}]
  (let [md (vec manufacturer-data)]
    (cond
      (not (<= 0 error-code 0xFFFF)) [:error :canopen/emcy-error-code-out-of-range error-code]
      (not (<= 0 error-register 0xFF)) [:error :canopen/emcy-error-register-out-of-range error-register]
      (> (count md) 5) [:error :canopen/emcy-manufacturer-data-too-long (count md)]
      :else
      [:ok (into (into (u16le error-code) [error-register])
                 (into md (repeat (- 5 (count md)) 0)))])))

(defn decode
  "8 bytes -> `[:ok {:error-code :error-register :manufacturer-data
  :error-code-class :error-register-flags}]`."
  [bytes]
  (let [bs (vec bytes)]
    (if (not= 8 (count bs))
      [:error :canopen/emcy-frame-wrong-length (count bs)]
      (let [code (rd-u16le bs 0)
            reg (nth bs 2)]
        [:ok {:error-code code
              :error-register reg
              :manufacturer-data (subvec bs 3 8)
              :error-code-class (error-code-class code)
              :error-register-flags (error-register->flags reg)}]))))
