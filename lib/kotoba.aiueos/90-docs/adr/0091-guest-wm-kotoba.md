# ADR-0091 — Guest WM: KERNEL.ELF Kotoba z-hit of two overlapping surfaces

Date: 2026-08-23

## Status

Accepted for a **discriminating guest WM slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest WM is green only when
`kbb -M:compositor guest-wm` prints `AIUEOS_COMPOSITOR_GUEST_WM_OK`:**
KERNEL.ELF serial has `AIUEOS_GUEST_WM_OK two-surfaces z-hit=2 miss-front=1 raise=1 one-surface=0`,
the hit is Kotoba (`kotoba_aiueos_wm_hit`), and hosted JVM serial
`AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-wm` is the measurement. One-surface that
returns a window id is leftover `:one-surface-ignored`. Overlap that
returns 1 (map key order) is leftover `:z-order-ignored`. A point only
in window 1 that still returns 2 is leftover `:always-front`. Raise that
leaves front at 2 is leftover `:raise-is-noop`. QEMU/firmware/serial
unanswered is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM WM.** `kbb -M:compositor wm` (ADR-0085)
  stays green **without** this serial line. That gate must not start
  requiring `GUEST_WM_OK`.
- **This is not two guest scanout surfaces.** KERNEL.ELF still has one
  GOP/virtio-gpu desktop surface. The object decides z-hit; C does not
  paint a second window. Named leftover `:one-guest-scanout`.
- **This is not virtio-input from a real pointer.** Named leftover
  `:trusts-caller-for [:virtio-input-not-synthetic]`.
- **This is not a new compositor west repo.** concept-lookup found
  `window-session-state` (hosted state) and `kami-eizo-compositor` (VFX,
  not this). Do not create `aiueos-desktop`. Reuse those names; this
  object is the guest decision core of the same rects.
- **This is not native Phase 6 compositor and not P5.** Leftover after
  this slice is still `:native-compositor-absent`. P5 a real machine is
  UNVERIFIED. QEMU ≠ P5. USB OVMF is forbidden as P5. No physical boot
  was invented.
- **CACAO write, chain-to-anchor, permission broker, native component
  runtime, and physical boot remain.** The Chrome OS-shaped desktop goal
  is **not complete**.

## Context

ADR-0090 greened guest IME (`k`+`a` → U+304B) and named leftover
`:native-compositor-absent`. Hosted WM (ADR-0085) already stacks two
`window-session-state` surfaces and prefers z-order at `overlap-point`.
That lives in the JVM compositor process. C has one desktop surface.
Which of two overlapping rects is hit is a compositor decision and
belongs in Kotoba (ADR-0015).

## Decision

1. Same UEFI QEMU smoke as `gpu` / `guest-ime` (existing
   `smoke-qemu-uefi.sh`). No new `.sh`. New argv
   `kbb -M:compositor guest-wm` — not folded into `wm` / `gpu` /
   `guest-ime`.
2. Object `os/aiueos/kotoba/wm-hit.kotoba` exports
   `kotoba_aiueos_wm_hit`. Rects are hosted `boot-desktop`. Nested `if`,
   word types only (native maps are a backend gap, not a reason to drop
   the hit-test).
3. Compiler pin stays amu `9cf3a0ac`. Native allow-list adds
   `aiueos-wm-hit` in `kotoba-lang/kotoba-native` `elf64.cljc` and
   `elf64.clj`. Do not wholesale-advance amu. Same DHCP/ECDSA/IME
   pattern.
4. C in `main.c` is call + serial only. Do not `qemu_exit` on WM miss
   — `gpu` / `cloud` / `guest-ime` stay green without this line.
5. SPA `#desktop` names `kbb -M:compositor guest-wm`. One document.
   jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (one guest
scanout, virtio-input synthetic, permission broker, P5). Goal not
complete.

## Measurement

**2026-08-23 this Mac:** `kbb -M:compositor guest-wm` printed
`AIUEOS_COMPOSITOR_GUEST_WM_OK` leftover `[]`. Serial:
`AIUEOS_GUEST_WM_OK two-surfaces z-hit=2 miss-front=1 raise=1 one-surface=0`.
Object SHA-256
`70fac07783c5b2841b76d9d599c03a97a44d290a8ad977f48aa5af39b21efc7f`.
Same serial still has `AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0`.
QEMU ≠ P5.
