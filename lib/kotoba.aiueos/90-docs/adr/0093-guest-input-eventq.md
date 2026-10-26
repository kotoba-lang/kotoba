# ADR-0093 — Guest input: KERNEL.ELF consumes a virtio-keyboard used-ring event

Date: 2026-08-23

## Status

Accepted for a **discriminating guest input slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest input is green only when
`kbb -M:compositor guest-input` prints `AIUEOS_COMPOSITOR_GUEST_INPUT_OK`:**
KERNEL.ELF serial has `AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0`,
the desktop envelope was copied from a virtio-input used-ring event
(not the `#ifdef AIUEOS_INPUT_SMOKE_SYNTHETIC` fill), and hosted JVM
serial `AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-input` is the measurement. C filling
keycode 30 into the envelope is leftover `:synthetic-smoke`. A used
ring that never advances is leftover `:eventq-empty`. QEMU/firmware/serial
unanswered is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM input.** `kbb -M:compositor wm` /
  `guest-wm` / `guest-paint` stay green **without** this serial line.
  Those gates must not start requiring `GUEST_INPUT_OK`.
- **This is not HMP `sendkey`.** Under `-display none`, HMP sendkey
  hits the emulated console/PS2 path, not virtio-keyboard. The injector
  is QMP `input-send-event` with no `device` (broadcast). QEMU 10.1
  treats `device` as a display console; `device=kbd0` aborts with
  `qemu-fixed-text-console.device`. `send-key` is the PS2 path and is
  not this gate.
- **This is not a laptop HID.** Headless QMP is the measurement
  injector. A physical keyboard is P5 and UNVERIFIED. QEMU ≠ P5.
- **This is not two virtio-gpu resources, not a permission broker, and
  not a native component runtime.** Leftover after this slice is still
  `:native-compositor-absent`.
- **CACAO write, chain-to-anchor, and physical boot remain.** The
  Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0092 greened guest paint and named leftover
`:trusts-caller-for [:virtio-input-not-synthetic]`. The UEFI smoke
already attaches `virtio-keyboard-pci` and sets up a modern event
queue, then `#ifdef AIUEOS_INPUT_SMOKE_SYNTHETIC` copies a hardcoded
EV_KEY into the browser envelope. That is not device completion.

Which bytes enter the envelope is compositor input. Copying from a
used descriptor is C mechanism. Inventing the event in C is leftover.

## Decision

1. Same UEFI QEMU smoke (`smoke-qemu-uefi.sh`). No new `.sh`. New argv
   `kbb -M:compositor guest-input` — not folded into `guest-paint`
   / `gpu` / `wm`. `AIUEOS_GUEST_INPUT=1` rebuilds without the
   synthetic ifdef and injects via QMP.
2. Default gpu / guest-wm / guest-paint / guest-ime boots keep
   `AIUEOS_INPUT_SMOKE_SYNTHETIC=1` so they stay green without this
   line. They print `GUEST_INPUT leftover=synthetic-smoke`.
3. C posts four eventq descriptors, polls the used ring for EV_KEY,
   and copies that event. Do not `qemu_exit` on leftover.
4. SPA `#desktop` names `kbb -M:compositor guest-input`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (permission
broker, native component runtime, one virtio-gpu resource, P5). Goal
not complete.

## Measurement

**2026-08-23 this Mac:** `kbb -M:compositor guest-input` printed
`AIUEOS_COMPOSITOR_GUEST_INPUT_OK` leftover `[]` with
`AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0`. Receipt
`:reason :guest-input-eventq`. QEMU ≠ P5.
