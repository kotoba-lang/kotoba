# Native GUI review, 2026-10-28

This is the review regression for kotoba-lang/kotoba#965, following the
historical effects/minimize evidence folders. It includes current main's F6
Lock, F10 passphrase-protected Forget and capability-free ELF source import.
The native GUI is Kotoba/Amu machine code and a bounded framebuffer renderer;
it is not yet a full HTML/CSS browser desktop.

Review fixes preserve F10 and move reduced effects to F1; Forget panel literal
IDs are separate from home labels. AC97 BARs with nonzero high address bits
are refused before 16-bit I/O. The merged library metadata preserves both
sets of original records and passes the source-pin audit.

Native Mac default-descriptor builds and QEMU observations passed:
- desktop GPT 21, ISO 21 and shell materials 9 observations;
- effects 8 each for absent/audio/muted, including blur pixel golden,
  damage/full-raster equality, bounded burst ordering and modal refusal;
- consent 20; draft save/cold restore/refusals 12;
- keystore 11, including Lock full wipe, incorrect Forget passphrase,
  authenticated erasure and no key after reboot;
- real PS/2 titlebar drag/release inertia, displacement [7, 7] pixels.

`home.png` and `itonami-open.png` are screenshots of the running QEMU Cocoa
window using the observed desktop image. No network device or physical disk
was attached; the boot medium uses an ephemeral snapshot. The VM remains in
local diagnostic mode. QMP synthetic inputs are not trusted human consent.

The keystore receipt redacts the ephemeral sealed key blob because its test
passphrase is public. No private RAM dump is published. Original receipt
identity is retained.

No quiet-host/60 Hz, physical display/speaker, production publication,
canonical D2 or shared full Browser/DOM/CSSOM qualification is claimed.
