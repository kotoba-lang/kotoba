# ADR-0090 — Guest IME: KERNEL.ELF Kotoba `k`+`a` → U+304B

Date: 2026-08-23

## Status

Accepted for a **discriminating guest IME slice** of root
`adr-2608221625-aiueos-chromeos-cloud-desktop` Desktop leftover
(README Desktop / compositor unit). **Guest IME is green only when
`kbb -M:compositor guest-ime` prints `AIUEOS_COMPOSITOR_GUEST_IME_OK`:**
KERNEL.ELF serial has `AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0`,
the conversion is Kotoba (`kotoba_aiueos_ime_commit(107, 97)` → `12363`),
and hosted JVM serial `AIUEOS_COMPOSITOR_IME_OK` does **not** count.

This file records the attempt. The receipt from
`kbb -M:compositor guest-ime` is the measurement. Echoing latin
`k`/`a` is leftover `:latin-leak`. A miss of U+304B is leftover
`:vector-miss`. QEMU/firmware/serial unanswered is leftover `:unmeasured`
(exit 3, not a silent pass).

Not executable, and stated here rather than at the end:

- **This is not hosted JVM IME.** `kbb -M:compositor ime` (ADR-0086)
  and `kanji` (ADR-0088) stay green **without** this serial line. Those
  gates must not start requiring `GUEST_IME_OK`.
- **This is not virtio-input from a real keyboard.** The kernel still
  feeds synthetic bytes to the Kotoba object. Named leftover
  `:trusts-caller-for [:virtio-input-not-synthetic]`. That is not this
  gate.
- **This is not mozc and not a new west IME repo.** Conversion is one
  Kotoba object with a tiny vector. concept-lookup found no IME west
  repo; do not create one for this slice.
- **This is not native Phase 6 compositor and not P5.** Leftover after
  this slice is `:native-compositor-absent`. P5 a real machine is
  UNVERIFIED. QEMU ≠ P5. USB OVMF is forbidden as P5. No physical boot
  was invented.
- **CACAO write, chain-to-anchor, native compositor, and physical boot
  remain.** The Chrome OS-shaped desktop goal is **not complete**.

## Context

ADR-0089 greened hosted kami.webgpu (`init!`/`draw!`) and named leftover
`:guest-ime-absent`. Conversion lived only in `aiueos.compositor.ime` on
the JVM. C already copies EV_KEY into the desktop envelope (mechanism).
Which roman letters become which kana is a conversion decision and belongs
in Kotoba (ADR-0015).

## Decision

1. Same UEFI QEMU smoke as `gpu` (existing `smoke-qemu-uefi.sh`). No new
   `.sh`. New argv `kbb -M:compositor guest-ime` — not folded into
   `ime` / `kanji` / `kami` / `gpu`.
2. Object `os/aiueos/kotoba/ime-romaji.kotoba` exports
   `kotoba_aiueos_ime_commit`. Vector: latin `k`(107) + `a`(97) must
   return U+304B (`12363`). Nested `if`, word types only (native maps
   are a backend gap, not a reason to drop the conversion).
3. Compiler pin stays amu `9cf3a0ac`. Native allow-list adds
   `aiueos-ime-commit` in `kotoba-lang/kotoba-native` `elf64.cljc`. Do
   not wholesale-advance amu. Same DHCP/ECDSA pattern.
4. C in `main.c` is call + serial only. Do not `qemu_exit` on IME miss
   — `gpu` / `cloud` stay green without this line.
5. SPA `#desktop` names `kbb -M:compositor guest-ime`. One document.
   jp-go-dds. No second HTML. No liquid-glass. No Three.js.

## Consequences

Hosted leftover print is `:native-compositor-absent` once this slice
lands. virtio-input synthetic-smoke remains. Native Phase 6 compositor
(ADR-0013) remains. P5 remains UNVERIFIED. Goal not complete.

## Measurement

**2026-08-23 this Mac:** `kbb -M:compositor guest-ime` printed
`AIUEOS_COMPOSITOR_GUEST_IME_OK` leftover `[]`. Serial:
`AIUEOS_GUEST_IME_OK committed=u+304b latin-leak=0`. Object SHA-256
`ee11f50c9dfb30d03c820bead466b2f1bf18e4e64f3a2bfda98f5a5dd5d4ca34`.
QEMU ≠ P5.
