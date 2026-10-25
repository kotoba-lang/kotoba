# com-sony-dualsense

[![CI](https://github.com/kotoba-lang/com-sony-dualsense/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/com-sony-dualsense/actions/workflows/ci.yml)

**Sony DualSense (PS5 controller) HID protocol, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) vendor-protocol library:
decode input reports (sticks, triggers, buttons, D-pad, touchpad, motion,
battery) and encode output reports (LED, rumble, adaptive-trigger
feedback) as plain EDN — no USB/Bluetooth device I/O, no filesystem I/O.
Device I/O is a host-side concern (e.g. a Java HID binding like
[hid4java](https://github.com/gary-rowe/hid4java)); this library only does
byte-array-in / byte-array-out protocol decode/encode.

Namespace root: `kotoba.dualsense`. No network, no I/O. Portable `.cljc`
across JVM / ClojureScript / SCI / GraalVM — the from-scratch
`kotoba.dualsense.crc32` avoids `java.util.zip.CRC32` for exactly this
reason.

## Maturity

| | |
|---|---|
| Role | vendor protocol (decode-only input, encode-only output) |
| Tests | 31 tests, 111 assertions, all green |
| Hardware validation | **none** — see Confidence below |

## Contract

```clojure
(require '[kotoba.dualsense.input :as input]
         '[kotoba.dualsense.output :as output])

;; decode — bytes is a plain vector of ints 0-255, however you got it off
;; the wire (hid4java, javax.usb, whatever the host uses)
(input/decode-usb-report usb-bytes)
;; => {:sticks {:lx 0.0 :ly 1.0 :rx 0.0 :ry 0.0}
;;     :triggers {:l2 0.0 :r2 0.0}
;;     :buttons #{:cross}
;;     :dpad :n
;;     :seq 12
;;     :counter 0
;;     :touch [{:contact? false :id 0 :x 0 :y 0} {...}]
;;     :battery {:level 8 :charging? false :usb? false}
;;     :gyro {:x 0 :y 0 :z 0}
;;     :accel {:x 0 :y 0 :z 0}
;;     :connection :usb}

(input/decode-bt-report bt-bytes)          ; same shape + :crc-valid?

;; encode — never writes to a device, just builds the byte vector
(output/encode-usb-output
  {:led {:r 0 :g 128 :b 255}
   :rumble {:strong 200 :weak 40}
   :trigger-r2 {:mode :feedback :strength 128}})

(output/encode-bt-output {:led {:r 255 :g 0 :b 0}} :bt-seq 3)  ; + CRC-32 trailer
```

## Confidence

Sony publishes no official DualSense HID spec — everything here is
community-reverse-engineered. Every offset in this library is
cross-checked against the mainline Linux kernel's `hid-playstation`
driver (`drivers/hid/hid-playstation.c`, `struct dualsense_input_report`
/ `struct dualsense_output_report_common`), which is the most
authoritative public source available since it ships in production Linux
and is maintained against real hardware. **That said, nothing in this
library has been independently validated against a physical DualSense in
this environment.** Confidence varies by field:

### High confidence (well-established across every source, kernel-confirmed)

- Report IDs (USB `0x01` / BT `0x31` input, USB `0x02` / BT `0x31` output)
- The 4 analog stick axes and their center/full-deflection bytes
- The 2 analog triggers (L2/R2)
- All main digital buttons (face buttons, L1/R1/L2/R2 digital, L3/R3,
  Create/Options, PS, touchpad-click, mute) and the D-pad hat switch
- The Bluetooth CRC-32 algorithm and its seed byte for **input** reports
  (`0xA1`) — note the **output**-report seed is a different byte (`0xA2`);
  see `kotoba.dualsense.output`'s docstring
- Rumble motor bytes and LED/lightbar RGB bytes on the output report

### Best-effort / community-sourced — needs real-hardware validation

- **Gyro/accelerometer**: byte positions match the kernel struct (3× int16
  LE each, gyro immediately followed by accel), but this library does not
  attempt to convert raw units to physical ones (deg/s, g) — the
  per-LSB scale is not in the kernel struct and varies across sources.
- **Touchpad finger tracking**: the contact-byte / 12-bit-coordinate
  packing mirrors the kernel's bitfield layout, but has not been
  exercised against a real finger touch.
- **Battery/charging bits**: level + charging-status sub-field match the
  kernel's decode, but `:usb?` (USB-power-present) is *derived* from the
  charging-status value, not a literal hardware bit — the DualSense
  kernel driver exposes no separate cable-detect bit (unlike the older
  DualShock4 driver).
- **Adaptive-trigger effect encoding** (output): this is the least
  certain field in the whole library. Sony's real adaptive-trigger
  firmware supports a large, poorly-documented effect catalogue (weapon,
  vibration, multi-region resistance, …) that the mainline Linux driver
  does not implement at all. This library implements only two modes,
  `:off` and `:feedback` (uniform resistance) — a deliberately minimal
  placeholder, not a subset of a verified full encoding, placed at an
  offset in the kernel struct's unclaimed region using an enable-bit
  convention borrowed from community tooling rather than the kernel
  itself.

If you wire this to real hardware, treat every field in the second list
as "probably works, unconfirmed" and the adaptive-trigger encoding in
particular as "will very likely need correcting against a live device."

## Why

Every `com-<vendor>-<product>` library in this org does one thing: turn a
specific vendor's wire format into pure EDN and back, with zero I/O and
zero opinion about what the data means downstream. That discipline is
what lets a teleop bridge (or any other consumer) depend on
`com-sony-dualsense` without also depending on a USB stack, an event
loop, or this library's opinions about control mapping — those all live
one layer up, where the actual DualSense-to-robot bridge is built.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test   # cognitect test-runner
kbb -M:lint   # clj-kondo, --fail-level error
```
