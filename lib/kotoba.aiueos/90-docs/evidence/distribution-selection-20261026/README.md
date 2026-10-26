# Same-core distribution selection — 2026-10-26

`PASS_SAME_CORE_DISTRIBUTIONS`: the default `aiueos` build and explicit
`--distribution awai` both passed the common native font/kernel/EFI/media
pipeline with the same pinned Amu ARM Linux compiler. Each reproduced its
kernel/EFI/media, and their font, kernel, EFI and boot media are byte-identical
across distributions. The staged descriptors differ and their exact bytes,
size and SHA-256 are bound in each candidate's `native-desktop.json`.

The comparison and source/compiler/container pins are in
[comparison.json](comparison.json). The initial cached Python alias had changed
to AMD64 and was correctly refused by the native architecture guard; successful
builds used the existing ARM64 image by immutable ID. No emulated compiler or
legacy build fallback bypassed that guard. Unknown CLI/direct-call distribution
IDs refused before output creation. Shell syntax, Python syntax and diff checks
passed.

The AWAI candidate also passed the existing native desktop QEMU input gate:
[native-desktop-qemu.json](native-desktop-qemu.json). It checks actual boot,
sealed PCI/GOP/font, private context, PS/2 input, drawing and immutable boot
media. The distribution metadata does not alter the guest kernel or GUI bytes.

This qualifies candidate selection/staging and same-core reproduction. It is
not installation of the preset's app/node components, an AWAI OS installer
release, a completed shared Browser/CSSOM integration, signed workspace restore,
independent-node operation or physical-machine acceptance. Native build tools
ran in Linux; the QEMU guest boots the AIUEOS kernel directly. Binaries with
private owner dependencies remain local. See [ADR0274](../../adr/0274-awai-os-is-an-aiueos-distribution.md).
