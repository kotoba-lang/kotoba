# Apple Silicon native build and passwordless VM debug (2026-10-26)

These receipts describe a local diagnostic candidate for JUN-417, JUN-93
and JUN-89. All image hashes refer to this AIUEOS checkout and the
source-pinned Mac Amu compiler and Kotoba packager.

- [Font, kernel and EFI](receipt.json): signed Mac native artifacts;
  31 kernel modules and a byte-identical exact-source Linux arm64 comparator.
- [GPT/FAT16 media](media.json): the unmodified Kotoba media-builder built,
  verified and reproduced the 8 MiB disk on Mac. The independent format
  reader and ten named refusal cases passed.
- [QEMU desktop](desktop-qemu.json): the exact Mac disk booted under QEMU TCG.
  Private QMP standard-input/output sent keys and mouse input, observed
  12 named guest states, and captured the [Itonami Goal screenshot](itonami-goal-ab.png).
  No VNC password or manual guest input was involved.

The media SHA-256 is
`dcbb5274789f345d20519aa61137166085fe511d5ad6ec7b42f02bca5ef6b60a`.
This normal profile has a RAM-only Goal and F5 does not commit it. The
separate opt-in local-draft restart gate covers isolated persistence.
The receipts do not establish complete Itonami agent operation,
compiler fixed-point requalification on the expanded FS2 runtime,
release or physical hardware qualification.

The earlier `receipt.json` intentionally records that Mac media was
blocked before FS2 F/E support. The later media and QEMU receipts supersede
that bounded failure. The [integrated default-entry run](../aiueos-mac-integrated-20261026/README.md)
rebuilds every stage with one Mac compiler and verifies the visible Goal
glyphs in QEMU's scanout.
