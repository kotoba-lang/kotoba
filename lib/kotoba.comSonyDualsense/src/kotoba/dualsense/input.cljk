(ns kotoba.dualsense.input
  "Decode Sony DualSense (PS5 controller) HID input reports into one
  shared EDN input-state map. Pure data in, pure data out: reports are
  plain vectors of ints 0-255 (no `byte[]`/`ByteBuffer`, so this stays
  portable to ClojureScript); this namespace never touches USB/Bluetooth
  I/O — a host-side caller (e.g. hid4java) reads the raw report and hands
  the bytes to `decode-usb-report`/`decode-bt-report`.

  ## Byte-offset provenance and confidence

  Sony publishes no official DualSense HID spec; every byte offset here is
  reverse-engineered by the community. This implementation cross-checks
  every offset against `struct dualsense_input_report` in the mainline
  Linux kernel's `drivers/hid/hid-playstation.c` (`hid-playstation`
  driver) — the most authoritative public reference available, since it
  ships in production Linux and is maintained against real hardware by
  the kernel HID subsystem maintainers.

  That said: **no offset in this file has been independently validated
  against a physical controller in this environment.** Confidence still
  varies by field:

  - **High confidence** (kernel-confirmed *and* consistently documented
    across every community source): report IDs, the 4 analog sticks, the
    2 analog triggers, the digital face/shoulder/menu buttons, the D-pad
    hat switch, and the Bluetooth CRC-32 algorithm/seed for *input*
    reports (`0xA1`).
  - **Best-effort** (kernel-confirmed *field order and sizes*, but the
    interpretation is thinner or the kernel driver itself does not fully
    decode the field): gyro/accel scale (raw units are int16 LE; this
    library does not attempt to convert to physical units since the
    scale-per-LSB is not in the kernel struct and varies by source),
    touchpad 12-bit coordinate packing, and battery/charging bit meaning
    (the kernel decodes battery capacity + a charging-status sub-field,
    but exposes no separate 'plugged into USB' bit for DualSense — `:usb?`
    below is *derived*, not a literal bit; see `decode-battery`).

  See the repo README's Confidence section for the full field-by-field
  breakdown.

  ## Report layout

  USB report ID `0x01` (64 bytes) and Bluetooth report ID `0x31` (78
  bytes, last 4 bytes a CRC-32 trailer) share one field layout, offset by
  a constant +1 (BT has 1 extra header byte after the report ID; USB has
  none). All offsets below are given relative to that shared layout — see
  `struct-offset->usb-byte`/`struct-offset->bt-byte`."
  (:require [kotoba.dualsense.crc32 :as crc32]))

;; ---------------------------------------------------------------------------
;; Report framing
;; ---------------------------------------------------------------------------

(def usb-report-id 0x01)
(def bt-report-id 0x31)
(def usb-report-size 64)
(def bt-report-size 78)

(def input-crc-seed
  "One-byte seed folded in ahead of the report bytes before computing the
  Bluetooth input-report CRC-32 (`PS_INPUT_CRC32_SEED` in
  hid-playstation.c). High confidence — consistent across every source
  and confirmed in the mainline kernel driver. Note this differs from the
  *output*-report seed (`kotoba.dualsense.output/output-crc-seed`,
  `0xA2`) — input and output reports are not signed with the same seed."
  0xA1)

(defn- struct-offset->usb-byte
  "USB byte index for a field at shared-layout offset `s` (report ID is
  byte 0 and outside the shared layout; every field starts at s+1)."
  [s]
  (+ s 1))

(defn- struct-offset->bt-byte
  "Bluetooth byte index for a field at shared-layout offset `s` (BT has
  one extra header byte after the report ID before the shared layout
  begins, so every field is at USB-byte + 1)."
  [s]
  (+ s 2))

(defn- offset [connection s]
  (if (= connection :bluetooth)
    (struct-offset->bt-byte s)
    (struct-offset->usb-byte s)))

;; Shared-layout field offsets (kernel `struct dualsense_input_report`).
(def ^:private off-lx 0)
(def ^:private off-ly 1)
(def ^:private off-rx 2)
(def ^:private off-ry 3)
(def ^:private off-l2 4)
(def ^:private off-r2 5)
(def ^:private off-seq 6)
(def ^:private off-buttons-a 7)
(def ^:private off-buttons-b 8)
(def ^:private off-buttons-c 9)
;; off 10 (kernel `buttons[3]`) and 11-14 (kernel `reserved[4]`) are not
;; decoded: `buttons[3]` carries DualSense Edge-only paddle/FN buttons
;; (irrelevant to a standard controller) and `reserved[4]` is unclaimed.
(def ^:private off-gyro 15)     ; best-effort: 3x int16 LE, x/y/z
(def ^:private off-accel 21)    ; best-effort: 3x int16 LE, x/y/z, immediately after gyro
;; off 27-30 (kernel `sensor_timestamp`, uint32 LE) and 31 (`reserved2`)
;; are not surfaced in the decoded map (not part of this library's output
;; shape); a future version could add a `:sensor-timestamp` key here.
(def ^:private off-touch0 32)   ; best-effort: 4-byte touch point, finger 0
(def ^:private off-touch1 36)   ; best-effort: 4-byte touch point, finger 1
;; off 40-51 (kernel `reserved3[12]`) not decoded.
(def ^:private off-status0 52)  ; best-effort: battery level + charging sub-field

;; ---------------------------------------------------------------------------
;; Byte/bitfield helpers
;; ---------------------------------------------------------------------------

(defn- u8
  "Byte at `idx`, or 0 if `bytes` is shorter than expected (defensive —
  callers should pass a full-length report, but a short/malformed vector
  should decode best-effort rather than throw)."
  [bytes idx]
  (nth bytes idx 0))

(defn- int16-le
  "Signed little-endian int16 at `idx`/`idx+1`."
  [bytes idx]
  (let [u (bit-or (u8 bytes idx) (bit-shift-left (u8 bytes (inc idx)) 8))]
    (if (>= u 0x8000) (- u 0x10000) u)))

(defn- uint32-le
  "Unsigned little-endian uint32 at `idx`..`idx+3`. Built with arithmetic
  (`+`/`*`), not `bit-shift-left`/`bit-or`, so the high byte (which can
  push the value past 2^31) never triggers ClojureScript's 32-bit signed
  bitwise-op coercion."
  [bytes idx]
  (+ (u8 bytes idx)
     (* (u8 bytes (+ idx 1)) 0x100)
     (* (u8 bytes (+ idx 2)) 0x10000)
     (* (u8 bytes (+ idx 3)) 0x1000000)))

(defn- flag?
  "True when any bit in `mask` is set in `byte`."
  [byte mask]
  (not (zero? (bit-and byte mask))))

;; ---------------------------------------------------------------------------
;; Sticks / triggers — high confidence
;; ---------------------------------------------------------------------------

(def default-deadzone
  "Default stick deadzone as a fraction of full deflection (~8%)."
  0.08)

(defn- abs* [x] (if (neg? x) (- x) x))

(defn- apply-deadzone
  "Apply a deadzone to a normalized -1..1 axis value `v`. Values inside
  the deadzone snap to exactly 0.0; values outside are rescaled so the
  remaining travel still reaches -1..1 at full deflection (never a plain
  clip, which would leave a dead outer band unreachable)."
  [v deadzone]
  (let [av (abs* v)]
    (if (< av deadzone)
      0.0
      (let [sign (if (neg? v) -1.0 1.0)
            scaled (/ (- av deadzone) (- 1.0 deadzone))]
        (* sign (min 1.0 scaled))))))

(defn- normalize-stick
  "Normalize a raw uint8 stick axis (0-255, ~128 center) to -1..1, with
  `deadzone` applied. `invert?` flips the sign — used for the Y axes,
  since raw HID Y increases downward but this library's convention is
  that 'stick pushed up' decodes to a *positive* Y."
  [raw deadzone invert?]
  (let [v (/ (- raw 127.5) 127.5)
        v (if invert? (- v) v)]
    (double (apply-deadzone v deadzone))))

(defn- normalize-trigger
  "Normalize a raw uint8 analog trigger (0-255) to 0..1. No deadzone —
  the spec only calls for deadzone on the 4 stick axes."
  [raw]
  (double (/ raw 255.0)))

;; ---------------------------------------------------------------------------
;; D-pad / buttons — high confidence (kernel `DS_BUTTONS0_*`/`DS_BUTTONS1_*`/
;; `DS_BUTTONS2_*`)
;; ---------------------------------------------------------------------------

(def ^:private dpad-table
  {0 :n 1 :ne 2 :e 3 :se 4 :s 5 :sw 6 :w 7 :nw})

(defn- decode-dpad
  "D-pad hat switch from buttons-byte-A's low nibble. 0-7 are the 8
  compass directions; 8-15 all mean neutral/released."
  [buttons-a]
  (get dpad-table (bit-and buttons-a 0x0F) :neutral))

(defn- decode-buttons
  "The digital button set from buttons-bytes A/B/C. Digital `:l2`/`:r2`
  (full trigger press) are distinct from the analog `:triggers` values —
  a controller can report a partial analog pull without the digital
  click, or vice versa near the detent."
  [a b c]
  (cond-> #{}
    (flag? a 0x10) (conj :square)
    (flag? a 0x20) (conj :cross)
    (flag? a 0x40) (conj :circle)
    (flag? a 0x80) (conj :triangle)
    (flag? b 0x01) (conj :l1)
    (flag? b 0x02) (conj :r1)
    (flag? b 0x04) (conj :l2)
    (flag? b 0x08) (conj :r2)
    (flag? b 0x10) (conj :create)
    (flag? b 0x20) (conj :options)
    (flag? b 0x40) (conj :l3)
    (flag? b 0x80) (conj :r3)
    (flag? c 0x01) (conj :ps)
    (flag? c 0x02) (conj :touchpad)
    (flag? c 0x04) (conj :mute)))

;; ---------------------------------------------------------------------------
;; Touchpad — best-effort (community/kernel-informed, not independently
;; hardware-validated)
;; ---------------------------------------------------------------------------

(defn- decode-touch-point
  "One touch-finger slot from its 4 raw bytes. `b0` bit7 set means NOT
  touching (per the kernel's `DS_TOUCH_POINT_INACTIVE`); the remaining 7
  bits of `b0` are a per-contact id/counter. `b1`/`b2`/`b3` pack two
  12-bit coordinates: X = b2's low nibble as the high bits, b1 as the low
  8 bits; Y = b3 as the high 8 bits, b2's high nibble as the low bits.
  This packing mirrors the kernel's `dualsense_touch_point` bitfield
  (`x_hi:4, y_lo:4` sharing one byte) and the equivalent DualShock4 touch
  packing used by most community DS4/DualSense parsers."
  [b0 b1 b2 b3]
  {:contact? (not (flag? b0 0x80))
   :id (bit-and b0 0x7F)
   :x (bit-or (bit-shift-left (bit-and b2 0x0F) 8) b1)
   :y (bit-or (bit-shift-left b3 4) (bit-shift-right (bit-and b2 0xF0) 4))})

;; ---------------------------------------------------------------------------
;; Battery — best-effort (kernel-informed, not independently hardware-
;; validated; `:usb?` is derived, not a literal bit — see docstring)
;; ---------------------------------------------------------------------------

(defn- decode-battery
  "Battery level (0-10, each unit ~10%) and charging state from the
  status byte's low/high nibble. The kernel driver decodes
  `status[0]`'s low nibble as battery capacity and high nibble as a
  charging-status enum (0 = discharging/on battery, 1 = charging,
  2 = full, 0xa/0xb = voltage or temperature error, 0xf = charging
  error) — this is the best-documented part of the status byte, but the
  DualSense kernel driver does not expose a separate 'connected via USB'
  bit the way the older DualShock4 driver does (its `status[0]` has an
  explicit `DS4_STATUS0_CABLE_STATE` bit). `:usb?` here is therefore
  *derived*: the controller can only report charging/full while
  receiving external power, so charging-status in #{1 2} implies a
  cable/dock is present. Treat `:usb?` as inferred, not a literal
  hardware bit — flagged per this library's best-effort-field policy."
  [status0]
  (let [level (min 10 (bit-and status0 0x0F))
        charging-status (bit-and (bit-shift-right status0 4) 0x0F)]
    {:level level
     :charging? (= charging-status 1)
     :usb? (contains? #{1 2} charging-status)}))

;; ---------------------------------------------------------------------------
;; Shared decode
;; ---------------------------------------------------------------------------

(defn- decode-common
  [bytes connection deadzone]
  (let [b (fn [s] (u8 bytes (offset connection s)))
        buttons-a (b off-buttons-a)
        buttons-b (b off-buttons-b)
        buttons-c (b off-buttons-c)
        gyro-off (offset connection off-gyro)
        accel-off (offset connection off-accel)
        touch0-off (offset connection off-touch0)
        touch1-off (offset connection off-touch1)]
    {:sticks {:lx (normalize-stick (b off-lx) deadzone false)
              :ly (normalize-stick (b off-ly) deadzone true)
              :rx (normalize-stick (b off-rx) deadzone false)
              :ry (normalize-stick (b off-ry) deadzone true)}
     :triggers {:l2 (normalize-trigger (b off-l2))
                :r2 (normalize-trigger (b off-r2))}
     :buttons (decode-buttons buttons-a buttons-b buttons-c)
     :dpad (decode-dpad buttons-a)
     :seq (b off-seq)
     ;; Bits[3:7] of buttons-byte-C. The kernel labels these "DualSense
     ;; Edge extra buttons" (FN1/FN2/paddles, bits 4-7) rather than a
     ;; generic counter; exposed as a raw value since this library does
     ;; not model Edge-specific hardware. Not safety-relevant either way.
     :counter (bit-shift-right (bit-and buttons-c 0xF8) 3)
     :touch [(decode-touch-point (u8 bytes touch0-off) (u8 bytes (+ touch0-off 1))
                                  (u8 bytes (+ touch0-off 2)) (u8 bytes (+ touch0-off 3)))
             (decode-touch-point (u8 bytes touch1-off) (u8 bytes (+ touch1-off 1))
                                  (u8 bytes (+ touch1-off 2)) (u8 bytes (+ touch1-off 3)))]
     :battery (decode-battery (b off-status0))
     :gyro {:x (int16-le bytes gyro-off)
            :y (int16-le bytes (+ gyro-off 2))
            :z (int16-le bytes (+ gyro-off 4))}
     :accel {:x (int16-le bytes accel-off)
             :y (int16-le bytes (+ accel-off 2))
             :z (int16-le bytes (+ accel-off 4))}
     :connection connection}))

;; ---------------------------------------------------------------------------
;; Public decode
;; ---------------------------------------------------------------------------

(defn decode-usb-report
  "Decode a 64-byte USB input report (report ID 0x01, `bytes` a vector of
  ints 0-255) into the shared input-state map. `:deadzone` (default
  `default-deadzone`) overrides the stick deadzone fraction."
  [bytes & {:keys [deadzone] :or {deadzone default-deadzone}}]
  (decode-common bytes :usb deadzone))

(defn decode-bt-report
  "Decode a 78-byte Bluetooth input report (report ID 0x31, `bytes` a
  vector of ints 0-255, last 4 bytes a little-endian CRC-32 trailer) into
  the shared input-state map, plus `:crc-valid?`.

  The CRC is computed over `input-crc-seed` (`0xA1`) followed by every
  byte of the report except the trailing 4-byte CRC itself, matching the
  Linux kernel driver's `ps_check_crc32(PS_INPUT_CRC32_SEED, ...)`. A
  failed CRC never throws — fields are still decoded best-effort so a
  caller can decide how to handle a corrupt frame (e.g. drop the frame
  but keep the connection alive)."
  [bytes & {:keys [deadzone] :or {deadzone default-deadzone}}]
  (let [bytes (vec bytes)
        len (count bytes)
        payload (subvec bytes 0 (max 0 (- len 4)))
        expected (if (>= len 4) (uint32-le bytes (- len 4)) -1)
        computed (crc32/crc32 (cons input-crc-seed payload))]
    (assoc (decode-common bytes :bluetooth deadzone)
           :crc-valid? (= expected computed))))
