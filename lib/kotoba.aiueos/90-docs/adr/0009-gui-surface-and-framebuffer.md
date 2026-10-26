# ADR-0009 - GUI surface and framebuffer path

- Status: implemented for deterministic browser DOM, input, and in-memory
  framebuffer present; proposed for VM virtio-gpu / virtio-input backing
- Date: 2026-06-28

## Context

aiueos needs a GUI story at two levels:

- **Browser/client GUI**: a component renders into a host page or WebView-like
  shell.
- **VM/native GUI**: aiueos boots as `/init` and presents pixels through a
  framebuffer or virtio-gpu device.

Both must follow the same rule as every aiueos surface: manifests request
capabilities, policy confers a narrowed set, and host imports trap if the
capability is absent. The GUI must not become ambient DOM, OS window, clipboard,
socket, or GPU access.

## Decision

The current implemented GUI is the **browser surface**:

- `dom/render` maps to the `aiueos:host/dom-render` provider.
- `dom/event` maps to the `aiueos:host/dom-event` provider.
- `input/event` maps to the `aiueos:host/input-event` provider.
- `framebuffer/present` maps to the `aiueos:host/fb-present` provider.
- `DomSurface` is deterministic host state: a render log plus an injected-event
  FIFO loaded from `:aiueos/dom-events`, an input-event FIFO loaded from
  `:aiueos/input-events`, plus a framebuffer frame log.
- `aiueos run|up --surface browser` selects the active surface.
- `--browser-out out.html` writes the rendered fragments to a static HTML bridge,
  useful as the first WebView/browser handoff artifact.

The future VM/native GUI path is a separate provider set:

| capability | host import | backing provider |
|---|---|---|
| `dom/render` | `dom-render(ptr,len)` | Browser DOM / WebView bridge |
| `dom/event` | `dom-event(ptr,cap)` | Browser event FIFO / future HID bridge |
| `input/event` | `input-event(ptr,cap)` | virtio-input / platform input queue |
| `framebuffer/present` | `fb-present(ptr,len,w,h,stride)` | Linear framebuffer or virtio-gpu scanout |

`dom/*` is semantic UI. `framebuffer/*` is pixels. A component may target one or
both surfaces in `:aiueos/surface`; a robot-only or cloud-only deployment simply
does not offer these GUI capabilities.

## Security properties

- Deny by default: no GUI provider is callable unless policy confers the matching
  capability.
- Surface mismatch is loud: a browser-targeted manifest on `--surface robot`
  is rejected before launch.
- No ambient browser APIs: `dom/render` appends host-owned markup fragments;
  event delivery is fixture/FIFO based in Phase 0.
- No ambient GPU APIs: future framebuffer/virtio-gpu providers expose only
  brokered present/input calls, not arbitrary device access.

## Implementation status

Implemented now:

- Browser provider registry in `src/surface.rs`.
- Runtime-gated `dom-render`, `dom-event`, `input-event`, and `fb-present` host
  imports in `src/host.rs`.
- CLI surface selection and deterministic fixtures:
  `--surface browser`, `--dom-events`, `--input-events`, `--browser-out`.
- QEMU boot plan support for exposing a virtio-gpu device:
  `aiueos vm boot ... --graphics virtio-gpu`.
- Runnable example in `examples/browser/`.
- CLI coverage in `tests/cli.rs`; provider coverage in `tests/browser.rs`.

Named partial (ADR-0079, hosted JVM, 2026-08-22): a compositor *process*
owns `window-session-state` surfaces; the same DADS SPA `#desktop` hosts a
kami.webgpu.ir canvas; QEMU exposes `-device virtio-gpu-pci` with
`-display none`. That is a display session, not a WM.

Not implemented yet:

- guest-side window manager, IME, retained widget tree in the guest.
- P5 physical boot (UNVERIFIED; QEMU is not P5).

Guest virtio-gpu 2D create/flush is ADR-0084 (`kbb -M:compositor gpu`),
not this ADR's original Rust surface. Hosted `#desktop` surfaces remain
ADR-0079. Hosted WM (z-stack + DADS decoration + input routing) is ADR-0085.
IME is leftover. The Chrome OS-shaped desktop goal is not complete.

## Consequences

The GUI is usable today as a deterministic browser/WebView-style surface and as
an in-memory framebuffer present log, not as a native VM display server. The next
increment is to back `framebuffer/present` with a virtio-gpu provider in the
bootable image path.
