# ADR-0079 — A compositor process owns window-session-state surfaces; that is not a window manager

Date: 2026-08-22

## Status

Accepted and executable **for the hosted JVM named-partial desktop face** of
root `adr-2608221625-aiueos-chromeos-cloud-desktop`. `kbb -M:compositor smoke`
serves the same `apps/session` DADS SPA, a compositor process owns
`window-session-state` surfaces (session iframe + kami guest surface), restore
of `state/desktop.edn` is admitted, restore of a wiped file is refused, and
QEMU is started with `-device virtio-gpu-pci` while `-display none` keeps the
P1b no-keyboard bind path.

Not executable, and stated here rather than at the end:

- **This is not a window manager.** No IME, no decoration protocol.
  Guest virtio-gpu 2D create/flush is a **later, separate argv**
  (`kbb -M:compositor gpu`, ADR-0084). `smoke` still admits PCI
  listing only. Do not read `#desktop` as a WM.
- **HTTP to `#session` with `-display none` is not this gate.** That is P1 / P1b.
  A display session exists when the compositor process owns surfaces and QMP
  `query-pci` names virtio-gpu.
- **This is not bare-metal Phase 6.** Nothing in `os/aiueos/` gained a native
  compositor. P2 (bare-metal net), P4 (itonami), P5 (real machine) remain
  later units. P3 (guest in shell) is ADR-0080, not this compositor gate.
- **`kbb -M:phone-bind smoke` must stay green without a GPU device.**
  Display-present (動線 D) is extra.

## Context

ADR-0078 landed the hosted daily shell. README still said Desktop was P1 SPA
and compositor / virtio-gpu shell was **not yet**. Goal completion forbids
leaving that as the product truth. The Chrome OS analogy is a display session,
not a marketing page.

`kotoba-lang/window-session-state` already owns z-stack, focus, and window
lifecycle. `kami.webgpu.ir` is the GPU IR. aiueos must not invent Three.js or
a second engine. CSS 3D / Canvas 2D cannot be the authoritative 3D viewport;
HTML overlay chrome may stay DADS.

The current guest image still does not implement virtio-gpu 2D create/flush
(ADR-0009 / ADR-0013). The maximum that still changes the Desktop claim is:
compositor process + hosted kami viewport in the same SPA + QEMU virtio-gpu
PCI device with headless display.

## Decision

1. Same SPA. Add fragment `#desktop`. Canvas `#kami-viewport` is the
   `kami.webgpu.ir` scanout host (`navigator.gpu`). Overlay stays DADS.
2. Compositor process (`kbb -M:compositor`) owns `window-session-state`.
   Persist `state/desktop.edn`. Kill/relaunch restores windows. A missing file
   is `empty-desktop`; `restore-admitted?` is false — that is the named red.
3. QEMU argv for this gate is P1b plus `-device virtio-gpu-pci`. Display stays
   `none`. P1b default argv does not grow a GPU device.
4. Gate: `kbb -M:compositor smoke`. Exit 0 only when SPA, surfaces,
   restore, wipe-red, and virtio-gpu PCI are all true.

## Consequences

README Desktop is a **named partial**, not "not yet" and not a WM. Operators
can prove a display session on this Mac. Full Chrome OS-shaped desktop is not
complete: guest-in-shell, bare-metal net, itonami, and a real machine remain.

## Later (2026-08-23)

Hosted WM (two stacked surfaces, DADS decoration, z-order input) is
**ADR-0085** (`kbb -M:compositor wm`). This ADR stays the compositor
*process* + PCI listing gate. Do not read ADR-0079 as if it were already a WM.
