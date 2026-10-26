# ADR-0085 — Hosted window manager: two stacked surfaces, DADS decoration, z-order input

Date: 2026-08-23

## Status

Accepted for a **discriminating hosted WM slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` compositor / Desktop 面.
**WM is green only when `kbb -M:compositor wm` prints
`AIUEOS_COMPOSITOR_WM_OK`:** two `window-session-state` surfaces stack,
raising the back window changes who is front, overlap hit-test prefers
z-order (not map key order), DADS title bars exist in the same
`apps/session` `#desktop` document, and pointer routing names the
focused guest.

This file records the attempt. The receipt from `kbb -M:compositor wm`
is the measurement. A single notes iframe is red. A JSON dump of surfaces
is red. `kbb -M:compositor gpu` stays the guest 2D gate and is not
this WM.

Not executable, and stated here rather than at the end:

- **IME is ADR-0086 (kana) and ADR-0088 (kanji).** WM green does not
  include IME conversion. After those land, leftover on a boot desktop
  is `:guest-ime-absent`.
- **This is not a native guest WM.** Surfaces live in the hosted JVM
  compositor (`window-session-state`). No second WM was invented.
  `kuro` remains the terminal model. kami-engine remains GPU IR.
- **Guest virtio-gpu 2D stays ADR-0084.** `kbb -M:compositor gpu`
  must stay green. Phone-bind stays `-display none` without a guest
  keyboard.
- **P5 a real machine is UNVERIFIED.** This Mac is the QEMU host. QEMU
  ≠ P5. USB OVMF is forbidden as P5. No physical boot was invented.
- **CertVerify, CACAO write, and physical boot remain.** IME is ADR-0086.
  The Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0079 landed a compositor *process* and said it was **not** a window
manager (no decoration, no z-order proof). ADR-0084 greened guest 2D
create/flush on QEMU and still said not a WM. Desktop was still not 成立.

`kotoba-lang/window-session-state` already owns `open-window`,
`focus-window` / bring-to-front, `z-stack`, `input-router/resolve-target`
→ `[:panel id]`, and `title-bar-contains?`. aiueos must not write a
second compositor. Overlay chrome stays `jp-go-dds` (skill kotoba-uiux).
The same SPA is one document; `#desktop` is a view, not a second HTML.
Window 1's guest is not a nested iframe of `/#session` (that recurses).

Overlap discriminator: boot windows share `{:x 100 :y 80}`. Front-to-back
hits the last-opened surface (id 2). Map key order hits id 1. That is the
red if `hit-window` ignores z-stack.

## Decision

1. Same SPA `#desktop`. Two overlapping `article.wm-window` surfaces with
   DADS title bars (`dds/heading`, `dds/chip-label`, `dds/button`). Kami
   content keeps `id="kami-viewport"`. Guest 1 is `div.wm-guest`, not a
   nested SPA iframe.
2. Compositor owns stacking: `raise` is `window-session-state/focus-window`.
   `hit-window` walks `z-stack` front-to-back. `one-surface-desktop` is
   refused (`:one-surface`). Raise that does not change the front is
   `:z-order-is-noop`.
3. HTTP: `POST /api/compositor/raise` and `POST /api/compositor/pointer`
   persist `state/desktop.edn` and return a flat WM event. SPA clicks
   call those routes.
4. Gate: `kbb -M:compositor wm`. No QEMU. Exit 0 only when two
   surfaces, one-surface red, z-order ≠ key-order, raise changes front,
   occlusion, input-target `[:panel focused]`, DADS SPA face, and HTTP
   raise/pointer agree. IME is not required. Leftover print is
   `:guest-ime-absent` once ADR-0088 lands.
5. Keep `kbb -M:compositor gpu` and phone-bind headless argv.

## P5 — still UNVERIFIED

No physical aiueos boot was performed or claimed. This operator Mac is
the QEMU host. Attached USB is not an aiueos machine. See ADR-0084.

## Consequences

README Desktop can say hosted WM is proven on this Mac when
`compositor wm` is green, and must still say kanji leftover / P5 UNVERIFIED,
and the Chrome OS-shaped desktop **goal is not complete**. ADR-0079
remains the named-partial compositor *process* + PCI listing. ADR-0084
remains guest 2D. This ADR is the WM discriminator.
