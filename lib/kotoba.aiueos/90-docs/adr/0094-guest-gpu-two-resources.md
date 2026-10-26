# ADR-0094 — Guest gpu-two: two virtio-gpu 2D resources from Kotoba count

Date: 2026-08-24

## Status

Accepted for a **discriminating guest gpu-two slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest gpu-two is green only when
`kbb -M:compositor guest-gpu-two` prints `AIUEOS_COMPOSITOR_GUEST_GPU_TWO_OK`:**
KERNEL.ELF serial has `AIUEOS_GUEST_GPU_TWO_OK resources=2 flush=2 kotoba-n=2`,
two virtio-gpu 2D resources were created and flushed after Kotoba
`kotoba_aiueos_wm_hit(2, 2, 100, 80) == 2`, and hosted JVM serial
`AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-gpu-two` is the measurement. C hardcoding
resource count `2` is leftover `:one-resource`. Only one scanout despite
two resources is leftover `:one-scanout` (after this slice). QEMU/firmware/serial
unanswered is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM gpu.** `kbb -M:compositor gpu` /
  `guest-input` / `guest-paint` stay green **without** this serial line.
  Those gates must not start requiring `GUEST_GPU_TWO_OK`.
- **This is not a second SET_SCANOUT.** Scanout 0 stays on resource 1.
  Multi-scanout is a later leftover.
- **This is not a permission broker, not a native component runtime, and
  not P5 physical boot.** Leftover after this slice is still
  `:native-compositor-absent` with `:one-scanout`.
- **CACAO write, chain-to-anchor, and physical boot remain.** The
  Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0093 greened guest input and named leftover
`:trusts-caller-for [:one-virtio-gpu-resource]`. The UEFI smoke already
creates one virtio-gpu 2D resource for scanout 0. Guest WM/paint already
use Kotoba `kotoba_aiueos_wm_hit` for two overlapping boot rects.

How many GPU 2D resources to create is a compositor decision. Reusing
the existing WM hit export for count keeps C as mechanism-only (ADR-0015).

## Decision

1. Same UEFI QEMU smoke (`smoke-qemu-uefi.sh`). No new `.sh`. New argv
   `kbb -M:compositor guest-gpu-two` — not folded into `gpu` /
   `guest-input`. No extra env (same KERNEL.ELF boot as `gpu`).
2. After resource 1 CREATE/ATTACH/SET_SCANOUT/XFER/FLUSH, if
   `kotoba_aiueos_wm_hit(2, 2, 100, 80) == 2`, C CREATE/ATTACH/XFER/FLUSH
   resource 2 (no second SET_SCANOUT). Do not hardcode `2` in C without
   the Kotoba gate.
3. Default gpu / guest-wm / guest-paint / guest-input boots may print
   `GUEST_GPU_TWO leftover=one-resource` when the second path fails; they
   must not `qemu_exit` on that leftover.
4. SPA `#desktop` names `kbb -M:compositor guest-gpu-two`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (permission
broker, native component runtime, one virtio-gpu scanout, P5). Goal
not complete.

## Measurement

**2026-08-24 this Mac:** `kbb -M:compositor guest-gpu-two` printed
`AIUEOS_COMPOSITOR_GUEST_GPU_TWO_OK` leftover `[]` with
`AIUEOS_GUEST_GPU_TWO_OK resources=2 flush=2 kotoba-n=2`. Receipt
`:reason :guest-gpu-two-resources`. QEMU ≠ P5.
