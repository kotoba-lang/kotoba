# ADR-0096 — Guest permission broker: clipboard admit from Kotoba

Date: 2026-08-25

## Status

Accepted for a **discriminating guest permission-broker slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest broker is green only when
`kbb -M:compositor guest-broker` prints `AIUEOS_COMPOSITOR_GUEST_BROKER_OK`:**
KERNEL.ELF serial has
`AIUEOS_GUEST_BROKER_OK clipboard=1 picker=0 kotoba-clip=1 kotoba-pick=0`,
clipboard was admitted and file-picker refused after Kotoba
`kotoba_aiueos_broker_admit(1, 1) == 1` and
`kotoba_aiueos_broker_admit(2, 1) == 0`, and hosted JVM serial
`AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-broker` is the measurement. Kotoba admitting
picker on a clipboard-only grant is leftover `:always-grant`. Refusing
clipboard is leftover `:deny-all`. QEMU/firmware/serial unanswered is
leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM gpu/wm.** `kbb -M:compositor gpu` /
  `guest-ime` / `guest-wm` / `guest-scanout-two` stay green **without**
  this serial line. Those gates must not start requiring `GUEST_BROKER_OK`.
- **This is not a native component runtime, and not P5 physical boot.**
  Leftover after this slice was `:native-compositor-absent` (session restore, native component runtime, P5). Session restore is ADR-0098.
- **CACAO write, chain-to-anchor, and physical boot remain.** The
  Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0013 Phase 6 names clipboard/file-picker permission brokers.
`kotoba-lang/grant` (`grant.broker`) is the hosted broker. Guest
KERNEL.ELF did not call a Kotoba admit for clipboard vs picker.
C already has a clipboard scratch (mechanism). WHETHER the op runs is
a grant decision, so it is a Kotoba object (`broker-admit.kotoba`)
listed on kotoba-native `kernel-object-entries` as `aiueos-broker-admit`.
Compiled at amu `9cf3a0a` with the native allow-list; do not
wholesale-advance amu. JVM loads `elf64.clj` ahead of `elf64.cljc`.

## Decision

1. ABI `[op granted-op] → 1 admit or 0 refuse`. op 1 = clipboard, op 2
   = file-picker. Admit only when op equals granted-op and op is 1 or 2.
2. Boot grant is clipboard-only (`granted-op = 1`). C calls
   `kotoba_aiueos_broker_admit(1, 1)` and
   `kotoba_aiueos_broker_admit(2, 1)`. Copy the clipboard scratch only
   when the first returns 1. Do not hardcode admit in C. Do not
   `qemu_exit`.
3. Gate is `kbb -M:compositor guest-broker` via default UEFI smoke
   (`run-uefi-2d!` with no extra env). It does not need dbus/`gdbus`.
4. SPA `#desktop` names `kbb -M:compositor guest-broker`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print after this slice stayed `:native-compositor-absent`
(session restore then native component runtime, P5). Session restore is ADR-0098.

## Measurement

Recorded by `kbb -M:compositor guest-broker` on this branch.
QEMU ≠ P5.
