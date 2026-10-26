# ADR-0084 — Guest virtio-gpu 2D create/flush is a second compositor argv; P5 stays UNVERIFIED

Date: 2026-08-22

## Status

Accepted for a **discriminating slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` compositor / Desktop 面.
**Guest 2D is green only when `kbb -M:compositor gpu` prints
`AIUEOS_COMPOSITOR_GPU_2D green`:** KERNEL.ELF serial contains
`AIUEOS_VIRTIO_GPU_CREATE result=ok` **and**
`AIUEOS_VIRTIO_GPU_FLUSH result=ok`.

This file records the attempt. The receipt from `kbb -M:compositor gpu`
is the measurement. QMP `query-pci` is not this gate.

Not executable, and stated here rather than at the end:

- **This is not a window manager.** No IME, no decoration protocol, no
  z-stack in the guest. `#desktop` hosted surfaces (ADR-0079) remain a
  named partial JVM face.
- **`kbb -M:compositor smoke` does not green 2D.** That gate still
  admits SPA + window-session-state + query-pci under `-display none`.
- **GET_DISPLAY_INFO / GOP-once is not 2D.** Display-info stays the floor
  existing UEFI smokes grep. `gpu` is red if that line is present without
  CREATE+FLUSH (`:gpu-2d-create-flush-absent`).
- **P5 a real machine is UNVERIFIED.** QEMU ≠ P5. See below. That does
  not complete the Chrome OS-shaped desktop goal.
- **IME, TLS CertVerify, CACAO write, and physical boot remain.**

## Context

ADR-0079 landed a compositor *process* and listed virtio-gpu on PCI.
Root goal completion forbids finishing while Desktop is only that named
partial if the original 成立 includes a real desktop. The missing
discriminator was guest 2D create/flush (or equivalent scanout of a
session framebuffer), not "PCI device listed".

`window-session-state` stays the hosted surface library. kami.webgpu.ir
stays the hosted viewport. No Three.js. No CSS-as-compositor.

P1b phone bind must keep `-display none` without a GPU device and
without a guest keyboard. 2D is a **second argv**: `kbb -M:compositor gpu`
reuses `os/aiueos/scripts/smoke-qemu-uefi.sh` (virtio-vga, same virtio-gpu
protocol) **without** `AIUEOS_TEST_NET`.

C in `os/aiueos/kernel/pci.c` is mechanism: descriptor fill, MMIO kick,
wait for `used->index`. The 32×32 resource is one 4KiB backing page so
CREATE/FLUSH can complete. Pixel contents are not a WM.

## Decision

1. After GET_DISPLAY_INFO succeeds, the guest issues RESOURCE_CREATE_2D,
   ATTACH_BACKING, SET_SCANOUT (best-effort), TRANSFER_TO_HOST_2D, and
   RESOURCE_FLUSH on the same controlq. Display-info failure still
   refuses `virtio_gpu()`. 2D failure does **not** un-admit display-info
   and does **not** `qemu_exit`.
2. Serial names the result:
   `AIUEOS_VIRTIO_GPU_CREATE result=ok|absent` and
   `AIUEOS_VIRTIO_GPU_FLUSH result=ok|absent`.
3. `kbb -M:compositor gpu` admits only both `result=ok` lines.
   PCI-only is `:pci-device-listed-does-not-count`. Missing QEMU/OVMF
   serial is exit 3, not a pass.
4. Hosted `#desktop` is not guest scanout. IME stays leftover.

## P5 probe (2026-08-22) — UNVERIFIED

Searched on this operator Mac. **No physical aiueos boot was invented.**

| What was searched | Finding | Why it is not P5 |
|---|---|---|
| This host | MacBook Air M4 (`Mac16,12`), hostname used as QEMU host | The Mac is the hypervisor, not a guest boot receipt |
| `diskutil list`, `/Volumes`, USB | Attached USB 1TB: EFI + APFS volume `260317` (models/data) + Ubuntu installer (`casper`) dated 2025-02-17 | No aiueos ESP / KERNEL.ELF / recovery image. Flashing or booting the Ubuntu installer is not an aiueos P5 |
| aiueos README | "Every gate above is QEMU/OVMF. There is no real-machine qualification yet" | Self-report; QEMU remains the only measured boot |
| aiueos ADR-0019 | USB OVMF transport | Root ADR-2608221625 **forbids** counting USB OVMF as P5 |

QEMU UEFI (this ADR's 2D gate) is a QEMU marker. P5 requires a physical
machine booting the image with P1 or P2 remaining. **UNVERIFIED.**

## Consequences

README Desktop can say guest 2D create/flush is proven **on QEMU** when
`compositor gpu` is green, and must still say **not a WM**, IME leftover,
P5 UNVERIFIED. The Chrome OS-shaped desktop goal is not complete.
