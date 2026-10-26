# ADR-0098 — Guest session restore: packed front from Kotoba

Date: 2026-08-25

## Status

Accepted for a **discriminating guest session-restore slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest session is green only when
`kbb -M:compositor guest-session` prints `AIUEOS_COMPOSITOR_GUEST_SESSION_OK`:**
KERNEL.ELF serial has
`AIUEOS_GUEST_SESSION_OK restored-front=2 packed=2 kotoba-front=2 hit=2`,
Kotoba restored packed front 2, empty packed 0 and unknown packed 3
refused, `kotoba_aiueos_wm_hit` used that front, and hosted JVM serial
`AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-session` is the measurement. Restore that
returns 2 for packed 0 is leftover `:always-front`. Restore that
returns 0 for packed 2 is leftover `:empty-session`. Restore that
returns 3 for packed 3 is leftover `:unknown-surface`. wm-hit ignoring
the restored front is leftover `:restore-ignored`. QEMU/firmware/serial
unanswered is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM gpu/wm.** `kbb -M:compositor gpu` /
  `guest-ime` / `guest-wm` / `guest-broker` stay green **without**
  this serial line. Those gates must not start requiring `GUEST_SESSION_OK`.
- **This is not a native component runtime, and not P5 physical boot.**
  Leftover after this slice is still `:native-compositor-absent`.
- **CACAO write, chain-to-anchor, and physical boot remain.** The
  Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0013 Phase 6 names guest session restore. Hosted
`window-session-state` already restores. Guest KERNEL.ELF did not call
a Kotoba unpack for the sealed packed session word. C already hit-tests
windows (`wm-hit`) and paints (mechanism). WHICH front the sealed
session restores is a compositor decision, so it is a Kotoba object
(`session-restore.kotoba`) listed on kotoba-native
`kernel-object-entries` as `aiueos-session-restore`. Compiled at amu
`9cf3a0a` with the native allow-list; do not wholesale-advance amu.
JVM loads `elf64.clj` ahead of `elf64.cljc`.

ADR-0096 leftover named native component runtime. Session restore is
the next QEMU-proven kernel-object slice. USB install (ADR-0097) is a
different track.

## Decision

1. ABI `[packed] -> restored front window id or 0`. Admit only front 1
   or 2. Boot packed session is front 2.
2. C calls `kotoba_aiueos_session_restore(2)`, `(0)`, and `(3)`, then
   `kotoba_aiueos_wm_hit(2, front, 100, 80)`. Do not hardcode front in
   C. Do not `qemu_exit`.
3. Gate is `kbb -M:compositor guest-session` via default UEFI smoke
   (`run-uefi-2d!` with no extra env). It does not need dbus/`gdbus`.
4. SPA `#desktop` names `kbb -M:compositor guest-session`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (native
component runtime, P5). Goal not complete.

## Measurement

Recorded by `kbb -M:compositor guest-session` on this branch.
QEMU != P5.
