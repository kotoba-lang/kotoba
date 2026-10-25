(ns kotoba.dualsense.output
  "Encode Sony DualSense (PS5 controller) HID output reports. Pure data
  in, pure data out: reports are plain vectors of ints 0-255. This
  namespace only *encodes* — it never decodes an output report and never
  writes to a device; a host-side caller (e.g. hid4java) sends the
  returned byte vector to the controller.

  ## Byte-offset provenance and confidence

  As with `kotoba.dualsense.input`, every offset here is cross-checked
  against the mainline Linux kernel's `struct dualsense_output_report_*`
  (`drivers/hid/hid-playstation.c`), the most authoritative public
  reference available:

  - **High confidence** (kernel-confirmed field positions *and*
    behavior): the USB output report ID (`0x02`), the Bluetooth output
    report ID/header (`0x31` + sequence/tag bytes) and CRC-32 framing —
    note the *output* CRC seed is `0xA2` (`output-crc-seed`), a different
    byte from the `0xA1` seed used for *input* reports — rumble motor
    bytes, and the LED/lightbar RGB bytes.
  - **Best-effort, deliberately minimal** (not in the mainline kernel
    driver at all): the adaptive-trigger control. Sony's real adaptive-
    trigger firmware supports a large, poorly-documented catalogue of
    effects (weapon, vibration, multi-region resistance profiles, …)
    reverse-engineered piecemeal across various community projects, with
    byte offsets and mode numbers that are *not* consistent between
    sources and that the mainline Linux driver does not implement at all
    as of this writing. This library implements only two modes — `:off`
    and `:feedback` (uniform resistance) — placed at an offset within the
    kernel struct's unclaimed/reserved region, using an enable-bit
    convention borrowed from community tooling rather than the kernel.
    Treat this entire feature as unverified against hardware; it is not
    a subset of a well-established encoding, it is this library's own
    minimal placeholder for a much larger effect space.

  See the repo README's Confidence section for the full breakdown."
  (:require [kotoba.dualsense.crc32 :as crc32]))

;; ---------------------------------------------------------------------------
;; Report framing
;; ---------------------------------------------------------------------------

(def usb-report-id 0x02)
(def bt-report-id 0x31)
(def usb-report-size 63)
(def bt-report-size 78)

(def output-crc-seed
  "One-byte seed folded in ahead of the report bytes before computing the
  Bluetooth output-report CRC-32 (`PS_OUTPUT_CRC32_SEED` in
  hid-playstation.c). Deliberately different from
  `kotoba.dualsense.input/input-crc-seed` (`0xA1`) — input and output
  reports are signed with different seeds; using the input seed here
  would produce a CRC the controller rejects."
  0xA2)

(def ^:private common-size 47)

;; Offsets are relative to the start of the kernel's
;; `dualsense_output_report_common` struct: USB byte = offset + 1 (after
;; the report-ID byte), BT byte = offset + 3 (after report-ID + seq_tag +
;; tag bytes).
(def ^:private off-valid-flag0 0)
(def ^:private off-valid-flag1 1)
(def ^:private off-motor-right 2)  ; "weak" motor (DualShock4-compat naming)
(def ^:private off-motor-left 3)   ; "strong" motor
(def ^:private off-trigger-r2-mode 10)      ; best-effort placement, see namespace docstring
(def ^:private off-trigger-r2-strength 11)  ; best-effort placement
(def ^:private off-trigger-l2-mode 21)      ; best-effort placement
(def ^:private off-trigger-l2-strength 22)  ; best-effort placement
(def ^:private off-lightbar-red 44)
(def ^:private off-lightbar-green 45)
(def ^:private off-lightbar-blue 46)

(def ^:private flag0-compatible-vibration 0x01)
(def ^:private flag0-haptics-select 0x02)
(def ^:private flag0-enable-r2-effect 0x04) ; community convention, not in mainline kernel driver
(def ^:private flag0-enable-l2-effect 0x08) ; community convention, not in mainline kernel driver
(def ^:private flag1-lightbar-control-enable 0x04)

(def ^:private trigger-mode->byte
  "Minimal adaptive-trigger mode encoding — see namespace docstring for
  why this is a deliberately small subset, best-effort placed."
  {:off 0x00 :feedback 0x01})

;; ---------------------------------------------------------------------------
;; Shared 47-byte common block (identical between USB and BT framing)
;; ---------------------------------------------------------------------------

(defn- encode-common
  "Build the 47-byte common block shared by USB and Bluetooth output
  reports: LED RGB (`:led {:r :g :b}`), rumble
  (`:rumble {:strong :weak}`), and a minimal adaptive-trigger control per
  trigger (`:trigger-l2`/`:trigger-r2` `{:mode :off|:feedback :strength}`).
  Any omitted key leaves that field's enable bit clear (0) — the
  controller ignores fields whose `valid_flag*` bit is not set, so a
  partial map only touches the subsystems it names."
  [{:keys [led rumble trigger-l2 trigger-r2]}]
  (let [r2-mode (:mode trigger-r2 :off)
        l2-mode (:mode trigger-l2 :off)
        flag0 (cond-> 0
                (some? rumble) (bit-or flag0-compatible-vibration flag0-haptics-select)
                (not= r2-mode :off) (bit-or flag0-enable-r2-effect)
                (not= l2-mode :off) (bit-or flag0-enable-l2-effect))
        flag1 (cond-> 0 (some? led) (bit-or flag1-lightbar-control-enable))
        common (-> (vec (repeat common-size 0))
                   (assoc off-valid-flag0 flag0)
                   (assoc off-valid-flag1 flag1)
                   (assoc off-trigger-r2-mode (get trigger-mode->byte r2-mode 0x00))
                   (assoc off-trigger-r2-strength (:strength trigger-r2 0))
                   (assoc off-trigger-l2-mode (get trigger-mode->byte l2-mode 0x00))
                   (assoc off-trigger-l2-strength (:strength trigger-l2 0)))
        common (if rumble
                 (assoc common
                        off-motor-right (:weak rumble 0)
                        off-motor-left (:strong rumble 0))
                 common)
        common (if led
                 (assoc common
                        off-lightbar-red (:r led 0)
                        off-lightbar-green (:g led 0)
                        off-lightbar-blue (:b led 0))
                 common)]
    common))

;; ---------------------------------------------------------------------------
;; Public encode
;; ---------------------------------------------------------------------------

(defn encode-usb-output
  "Encode a 63-byte USB output report (report ID 0x02). `opts` is
  `{:led {:r :g :b} :rumble {:strong :weak}
    :trigger-l2 {:mode :off|:feedback :strength} :trigger-r2 {...}}`,
  every key optional. Returns a vector of 63 ints 0-255; never writes to
  a device."
  [opts]
  (vec (concat [usb-report-id] (encode-common opts) (repeat 15 0))))

(defn encode-bt-output
  "Encode a 78-byte Bluetooth output report (report ID 0x31) with a
  trailing little-endian CRC-32 (seed `output-crc-seed`, `0xA2`) computed
  over every preceding byte of the report. `opts` is the same map as
  `encode-usb-output`. `:bt-seq` (default 0, wrapped to 0-15) sets the
  4-bit sequence number the kernel driver increments once per report
  sent — a stateless caller can leave it at the default; a caller
  managing a live connection should increment it per send the way the
  kernel driver does, since some Bluetooth stacks reject frames whose
  sequence is not advancing. The low nibble of that header byte (the
  \"tag\" sub-field) is always 0, matching the kernel driver's own
  behavior. Never writes to a device."
  [opts & {:keys [bt-seq] :or {bt-seq 0}}]
  (let [seq-tag (bit-shift-left (bit-and bt-seq 0x0F) 4)
        header [bt-report-id seq-tag 0x10]
        body (vec (concat header (encode-common opts) (repeat 24 0)))
        crc (crc32/crc32 (cons output-crc-seed body))
        crc-bytes [(bit-and crc 0xFF)
                   (bit-and (unsigned-bit-shift-right crc 8) 0xFF)
                   (bit-and (unsigned-bit-shift-right crc 16) 0xFF)
                   (bit-and (unsigned-bit-shift-right crc 24) 0xFF)]]
    (vec (concat body crc-bytes))))
