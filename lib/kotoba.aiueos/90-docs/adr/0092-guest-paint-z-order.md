# ADR-0092 — Guest paint: KERNEL.ELF paints two z-ordered boot rects

Date: 2026-08-23

## Status

Accepted for a **discriminating guest paint slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest paint is green only when
`kbb -M:compositor guest-paint` prints `AIUEOS_COMPOSITOR_GUEST_PAINT_OK`:**
KERNEL.ELF serial has `AIUEOS_GUEST_PAINT_OK boot-overlap=2 raised-overlap=1 key-order=0`,
Kotoba (`kotoba_aiueos_wm_hit`) names the front id, C fills both
boot-desktop rects back-then-front and samples the overlap pixel, and
hosted JVM serial `AIUEOS_COMPOSITOR_WM_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-paint` is the measurement. Painting window
1 last at overlap is leftover `:key-order-paint`. Painting window 2
last after raise-to-1 is leftover `:always-front-paint`. Rects that do
not fit GOP are leftover `:fb-too-small`. A paint that never writes
both rects is leftover `:one-guest-scanout`. QEMU/firmware/serial
unanswered is leftover `:unmeasured` (exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM WM.** `kbb -M:compositor wm` (ADR-0085)
  and `guest-wm` (ADR-0091) stay green **without** this serial line.
  Those gates must not start requiring `GUEST_PAINT_OK`.
- **This is not two virtio-gpu resources.** KERNEL.ELF still has one
  GOP/virtio-gpu desktop surface. Two rects are painted onto that
  surface in z-order. Named leftover: still one virtio-gpu resource.
- **This is not virtio-input from a real pointer.** Named leftover
  `:trusts-caller-for [:virtio-input-not-synthetic]`.
- **This is not a new compositor west repo.** C is fill + sample.
  Kotoba already owns which id is front (`kotoba_aiueos_wm_hit`). Do
  not create `aiueos-desktop`.
- **This is not native Phase 6 compositor and not P5.** Leftover after
  this slice is still `:native-compositor-absent` (virtio-input
  synthetic, permission broker, native component runtime). P5 a real
  machine is UNVERIFIED. QEMU ≠ P5. USB OVMF is forbidden as P5. No
  physical boot was invented.
- **CACAO write, chain-to-anchor, permission broker, native component
  runtime, and physical boot remain.** The Chrome OS-shaped desktop goal
  is **not complete**.

## Context

ADR-0091 greened guest WM z-hit and named leftover `:one-guest-scanout`:
Kotoba decided which of two overlapping rects is front; C did not paint
a second window. Hosted WM already stacks two `window-session-state`
surfaces. Which rect is front at a point is Kotoba (ADR-0015). Filling
pixels is C mechanism. A key-order paint (id 1 on top at overlap) must
not pass.

## Decision

1. Same UEFI QEMU smoke as `gpu` / `guest-wm` (existing
   `smoke-qemu-uefi.sh`). No new `.sh`. New argv
   `kbb -M:compositor guest-paint` — not folded into `guest-wm` /
   `wm` / `gpu`.
2. Reuse `kotoba_aiueos_wm_hit`. No new Kotoba export, no native
   allow-list row, compiler pin stays amu `9cf3a0ac`.
3. C in `framebuffer.c` fills window 1 (`32,32 720×540`) and window 2
   (`96,72 640×480`) back-then-front from the Kotoba front id, then
   samples `(100,80)`. Distinct RGB that survives format-0 vs BGR swap.
4. Two paints: boot front=2 then raise front=1. Overlap must be window
   2's stored color, then window 1's. Do not `qemu_exit` on paint miss
   — `gpu` / `cloud` / `guest-ime` / `guest-wm` stay green without this
   line.
5. SPA `#desktop` names `kbb -M:compositor guest-paint`. One
   document. jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print stays `:native-compositor-absent` (virtio-input
synthetic, permission broker, native component runtime, P5). Goal not
complete.

## Measurement

**2026-08-23 this Mac:** `kbb -M:compositor guest-paint` printed
`AIUEOS_COMPOSITOR_GUEST_PAINT_OK` leftover `[]`. Serial:
`AIUEOS_GUEST_PAINT_OK boot-overlap=2 raised-overlap=1 key-order=0`.
Receipt `:reason :guest-paint-z-order`. Same boot still carries
`guest-wm` / `guest-ime` / virtio-gpu CREATE. QEMU ≠ P5.
