# ADR-0086 — Hosted IME: romaji→kana in the compositor, latin must not leak

Date: 2026-08-23

## Status

Accepted for a **discriminating hosted IME slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover.
**IME is green only when `kbb -M:compositor ime` prints
`AIUEOS_COMPOSITOR_IME_OK`:** IME-on consumes `k` then `a` (the focused
guest does not receive latin), Enter commits `か`, and IME-off is the
named red (`:ime-bypass` delivers `ka`).

This file records the attempt. The receipt from `kbb -M:compositor ime`
is the measurement. Delivering `ka` to the guest while IME is on is red.
A DADS title bar without `#ime-bar` is red for this gate.
`kbb -M:compositor wm` stays green **without** requiring IME.

Not executable, and stated here rather than at the end:

- **Kanji conversion is ADR-0088.** This slice stays romaji→hiragana.
  Hosted leftover after ADR-0088 is `:guest-ime-absent`.
- **This is not mozc and not a new west repo.** concept-lookup / repo-search
  found no IME repo (2026-08-23). `kuro` remains the terminal model.
  The compositor owns the input method (`aiueos.compositor.ime`).
- **This is not a guest-side IME.** Keys are handled in the hosted JVM
  compositor. Guest virtio-gpu 2D stays ADR-0084. Hosted WM stays ADR-0085.
- **P5 a real machine is UNVERIFIED.** This Mac is the QEMU host. QEMU
  ≠ P5. USB OVMF is forbidden as P5. No physical boot was invented.
- **CertVerify, CACAO write, and physical boot remain.** The Chrome
  OS-shaped desktop goal is **not complete**.

## Context

ADR-0085 greened a hosted window manager and named IME leftover
`:ime-absent`. Daily Japanese typing is still the product face of a
Chrome OS-shaped desktop. Keys that reach the focused guest as latin
while IME is on are the failure mode this gate exists to catch.

## Decision

1. Same SPA `#desktop`. A DADS candidate bar (`#ime-bar`, `#ime-preedit`,
   `#ime-toggle`) sits above the WM stage. One document; not a second HTML.
2. `POST /api/compositor/key` runs `route-key` then persists
   `state/desktop.edn`. IME-on consumes letters into a romaji buffer and
   emits hiragana only on commit. IME-off (`POST /api/compositor/ime`
   `{"on?":false}`) is `:ime-bypass`.
3. Gate: `kbb -M:compositor ime`. No QEMU. Exit 0 only when the SPA
   has the IME bar, on-path `ka`+Enter commits `か` with no latin leak,
   and off-path delivers `ka` (the named red must actually be red).
4. `kbb -M:compositor wm` does not require conversion. Its leftover
   print is `:guest-ime-absent` once ADR-0088 lands.

## P5 — still UNVERIFIED

No physical aiueos boot was performed or claimed. This operator Mac is
the QEMU host. Attached USB is not an aiueos machine. See ADR-0084.

## Consequences

README Desktop can say hosted IME (romaji→kana) is proven on this Mac
when `compositor ime` is green, and must still say guest IME leftover,
P5 UNVERIFIED, and the Chrome OS-shaped desktop **goal is not complete**.
ADR-0085 remains the WM discriminator. ADR-0088 is the kanji discriminator.
This ADR is the kana discriminator.
