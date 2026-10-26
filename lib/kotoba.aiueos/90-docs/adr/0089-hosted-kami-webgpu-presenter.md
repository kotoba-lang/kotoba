# ADR-0089 — Hosted kami.webgpu presenter: init!/draw! on #kami-viewport

Date: 2026-08-23

## Status

Accepted for a **discriminating hosted kami.webgpu presenter slice** of
root `adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Presenter is green only when
`kbb -M:compositor kami` prints `AIUEOS_COMPOSITOR_KAMI_OK`:** the
same DADS `#desktop` SPA loads `/kami-presenter.js`, that bundle calls
`kami.webgpu/init!` then `draw!`, the IR is `kami.webgpu.ir/render-ir`
with ≥1 instance, a sky-only clear is refused, and a browser frame is
admitted (or the browser cannot be answered — leftover `:unmeasured`,
exit 3, not a silent pass).

This file records the attempt. The receipt from
`kbb -M:compositor kami` is the measurement. A canvas that only
`beginRenderPass`-clears the sky (`clear-only-desktop`) is red.
`beginRenderPass` inside the kami.webgpu executor is not that red.

Not executable, and stated here rather than at the end:

- **This is not a second compositor.** `window-session-state` stays the
  hosted surface library. `kotoba-lang/webgpu` (`kami.webgpu` /
  `kami.webgpu.ir`) is the canonical executor. aiueos does not invent
  Three.js, a second HTML document, or liquid-glass.
- **This is not guest virtio-gpu 2D.** That stays
  `kbb -M:compositor gpu` (ADR-0084). Hosted WM stays ADR-0085.
  Hosted IME kana stays ADR-0086. Hosted kanji stays ADR-0088 and stays
  green **without** requiring a kami frame.
- **This is not a guest-side IME and not P5.** Leftover after this slice
  is `:guest-ime-absent`. P5 a real machine is UNVERIFIED. QEMU ≠ P5.
  USB OVMF is forbidden as P5. No physical boot was invented.
- **CACAO write, chain-to-anchor, native Phase 6 compositor, and
  physical boot remain.** The Chrome OS-shaped desktop goal is **not
  complete**.

## Context

ADR-0088 greened hosted kanji (`か` → `加`) and named leftover
`:guest-ime-absent`. `#kami-viewport` on origin/main still sky-cleared
via `beginRenderPass` and reported instance counts without calling
`kami.webgpu/init!` / `draw!`. README Desktop stayed **partial**.

## Decision

1. Same SPA `#desktop` / `#kami-viewport`. One document. Presenter is
   `apps/session/src/aiueos/session/kami_presenter.cljk`, compiled to
   `apps/session/kami-presenter.js` (`kbb -M:kami-presenter`) and
   served as `GET /kami-presenter.js`. Do not inline the 2.1 MB bundle
   into HTML twice.
2. IR is built by `kami.webgpu.ir/render-ir` with ≥1 `ir/instance`.
   `clear-only-ir` (sky, zero instances) is the named red.
   `kami.webgpu` stays off the kernel `:deps` (test / compositor /
   kami-presenter extra-deps only).
3. Gate: `kbb -M:compositor kami`. No QEMU. Do not fold kami into
   `gpu` / `wm` / `ime` / `kanji`. Exit 0 only when SPA kami-face,
   presenter JS is kami.webgpu, IR admitted, clear-only refused, HTTP
   serves the bundle, and a Chrome frame is `engine: kami.webgpu` with
   `instances >= 1`. Exit 3 if the browser cannot be answered.
4. `kbb -M:compositor kanji` and `ime` stay green without a kami
   frame.

## P5 — still UNVERIFIED

No physical aiueos boot was performed or claimed. This operator Mac is
the QEMU host. Attached USB is not an aiueos machine. See ADR-0084.

## Consequences

README Desktop can say the hosted kami.webgpu presenter is proven on
this Mac when `compositor kami` is green, and must still say guest IME
leftover, P5 UNVERIFIED, and the Chrome OS-shaped desktop **goal is not
complete**. ADR-0088 remains the kanji discriminator. This ADR is the
hosted presenter discriminator.
