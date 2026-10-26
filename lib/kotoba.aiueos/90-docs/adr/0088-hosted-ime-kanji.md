# ADR-0088 — Hosted IME: Space converts kana→kanji; Enter commits

Date: 2026-08-23

## Status

Accepted for a **discriminating hosted kanji slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
`:kanji-absent`. **Kanji is green only when `kbb -M:compositor kanji`
prints `AIUEOS_COMPOSITOR_KANJI_OK`:** IME-on consumes `ka`, Space converts
`か` to first candidate `加` without delivering text to the guest, Enter
commits `加`, and Space that commits kana while the dictionary has `か`
is the named red (`kana-only-desktop`, leftover `:kanji-absent`).

This file records the attempt. The receipt from
`kbb -M:compositor kanji` is the measurement. An IME bar without
`#ime-candidates` is red for this gate only.
`kbb -M:compositor ime` stays the kana discriminator and stays green
**without** requiring conversion.

Not executable, and stated here rather than at the end:

- **This is not mozc and not a new west repo.** concept-lookup /
  repo-search found no IME repo (2026-08-23). The compositor owns a
  tiny reading table (`aiueos.compositor.ime/readings`). Gate uses
  `か` → first candidate `加`.
- **This is not a guest-side IME.** Keys are handled in the hosted JVM
  compositor. Leftover after this slice is `:guest-ime-absent`.
  Guest virtio-gpu 2D stays ADR-0084. Hosted WM stays ADR-0085.
  Hosted kana stays ADR-0086 (`kbb -M:compositor ime`).
- **P5 a real machine is UNVERIFIED.** This Mac is the QEMU host. QEMU
  ≠ P5. USB OVMF is forbidden as P5. No physical boot was invented.
- **Hosted kanji is green.** The kami.webgpu presenter leftover is
  ADR-0089. CACAO write, chain-to-anchor, guest IME, and physical boot
  remain. The Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0086 greened romaji→hiragana and named leftover `:kanji-absent`.
Japanese IME: **Enter commits**; **Space converts**. Space that commits
kana was the named red of that leftover.

## Decision

1. Same SPA `#desktop`. `#ime-candidates` sits in the existing DADS
   `#ime-bar`. One document; not a second HTML. An IME bar without that
   id is red for `kanji` only.
2. `POST /api/compositor/key` Space, when `:kanji?` is true and the
   reading is in `readings`, starts conversion (`:reason :convert`) and
   does not set `:guest-text`. Enter commits the current candidate.
   `:kanji? false` (`kana-only-desktop`) Space commits kana
   (`:reason :kanji-absent`).
3. Gate: `kbb -M:compositor kanji`. No QEMU. Exit 0 only when the
   SPA has `#ime-candidates`, the named red path stays red, and on-path
   `ka`+Space+Enter commits `加` with no latin leak.
4. `kbb -M:compositor ime` does not require conversion. Its leftover
   print is `:guest-ime-absent` once this slice lands.

## P5 — still UNVERIFIED

No physical aiueos boot was performed or claimed. This operator Mac is
the QEMU host. Attached USB is not an aiueos machine. See ADR-0084.

## Consequences

README Desktop can say hosted IME kanji is proven on this Mac when
`compositor kanji` is green, and must still say guest IME leftover, P5
UNVERIFIED, hosted kami.webgpu presenter as ADR-0089, and the Chrome
OS-shaped desktop **goal is not complete**. ADR-0086 remains the kana
discriminator. This ADR is the kanji discriminator.
