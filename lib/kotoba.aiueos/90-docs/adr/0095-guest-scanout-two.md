# ADR-0095 — Guest scanout-two: second virtio-gpu scanout from Kotoba bind

Date: 2026-08-25

## Status

Accepted for a **discriminating guest scanout-two slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest scanout-two is green only when
`kbb -M:compositor guest-scanout-two` prints `AIUEOS_COMPOSITOR_GUEST_SCANOUT_TWO_OK`:**
KERNEL.ELF serial has
`AIUEOS_GUEST_SCANOUT_TWO_OK scanouts=2 resource-0=1 resource-1=2 kotoba-n=2`,
scanout 1 was `SET_SCANOUT` onto resource 2 after Kotoba
`kotoba_aiueos_scanout_bind(2, enabled) == 2`, and hosted JVM serial
`AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-scanout-two` is the measurement. C hardcoding
bind count `2` is leftover `:one-scanout`. QEMU/firmware/serial unanswered
is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM gpu.** `kbb -M:compositor gpu` /
  `guest-gpu-two` stay green **without** this serial line.
  Those gates must not start requiring `GUEST_SCANOUT_TWO_OK`.
- **This is not a permission broker, not a native component runtime, and
  not P5 physical boot.** Leftover after this slice is still
  `:native-compositor-absent`.
- **CACAO write, chain-to-anchor, and physical boot remain.** The
  Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0094 greened two virtio-gpu 2D resources and named leftover
`:one-scanout` (scanout 0 stayed on resource 1). QEMU `virtio-vga`
defaulted to `max_outputs=1`, so GET_DISPLAY_INFO could not admit a
second mode. Bind count is a compositor decision, so it is a Kotoba
object (`scanout-bind.kotoba`) listed on kotoba-native
`kernel-object-entries` as `aiueos-scanout-bind`. C SET_SCANOUT is
mechanism. Compiled at amu `9cf3a0a` with the native allow-list;
do not wholesale-advance amu.

## Decision

1. QEMU `-device virtio-vga,disable-legacy=on,max_outputs=2`. Count
   enabled modes from GET_DISPLAY_INFO; do not return on the first.
2. After ADR-0094 resource 2 CREATE/FLUSH sets `gpu_2d_two_ok`, if
   `kotoba_aiueos_scanout_bind(2, enabled) == 2`, C `SET_SCANOUT`
   scanout_id=1 resource_id=2. Do not hardcode `2` in C without the
   Kotoba gate. Do not `qemu_exit` if that SET_SCANOUT fails.
3. Default gpu / guest-gpu-two boots may print
   `GUEST_SCANOUT_TWO leftover=one-scanout` when the second scanout
   fails; they must not `qemu_exit` on that leftover.
4. SPA `#desktop` names `kbb -M:compositor guest-scanout-two`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (native
component runtime, P5; permission broker is ADR-0096). Goal not complete.

## Measurement

Recorded by `kbb -M:compositor guest-scanout-two` on this branch.
QEMU ≠ P5.

QEMU 10.1 (`virtio-gpu-base.c`) sets `enabled_output_bitmask = 1` at
realize. `max_outputs=2` only reserves scanouts. Extra heads become
enabled when a UI frontend calls `ui_info` with a non-zero size.
`-display none` never does; GET_DISPLAY_INFO stays one enabled mode;
Kotoba correctly returns 0; leftover is `:one-scanout`. cocoa on this
QEMU only `ui_info`s the front window (head 0). JSON `outputs[].xres`
is not a 10.1 property. The `guest-scanout-two` gate sets
`AIUEOS_GUEST_SCANOUT_TWO=1`, which starts a unix-tmpdir session bus
(macOS launchd session socket is empty), `-display dbus,gl=off`, and
`gdbus` `SetUIInfo` on `/org/qemu/Display1/Console_0` and `Console_1`
before GET_DISPLAY_INFO. Default UEFI smoke stays `-display none`.
