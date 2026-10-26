# ADR-0260 — The contrast choice survives a reboot

Date: 2026-10-23

## Status

Accepted. Adds the `guest-browser-settings` gate, the first that boots the same volume twice, and the first
persistent write the desktop makes. No new floor. Row C8 ("Settings") of the ChromeOS-grade scorecard stays
`:unachieved`: this is the foundation (a persistent record and a two-boot test) with the high-contrast choice as
its only setting.

**Green only when** `kbb --backend sci --classpath src scripts/compositor-guest.cljk guest-browser-settings`
prints `AIUEOS_COMPOSITOR_GUEST_BROWSER_SETTINGS_OK`: the sign-out gate is green on the second boot's serial, both
boots' `AIUEOS_GUEST_BROWSER_SETTINGS` frames equal the frame model's, boot one had no record and wrote the choice
(`written=1 stored=1`), and boot two read the record (`valid=1 contrast=1`), was sent Alt and not F10, wrote nothing
(`written=0`) and drew the frames boot one drew.

Not, and stated here rather than at the end: a settings window (the choice is changed with F10), a text scale, a
network setting, and a restore at boot: the stage harness starts every boot from the default surface, so the stored
choice is applied by the settings stage, not before the earlier stages.

## Decision

- `kernel/pci.c`: `aiueos_settings_write` and `aiueos_settings_read` -- one bounded record in sector 1034 of the
  object-store volume (above the crash receipt's 1033): magic `AIUESET1`, version, the contrast choice, a reserved
  word and a Kotoba FNV checksum over the preceding 20 bytes. The write requires readback; a sector that is empty,
  torn, foreign or out of range reads as "no settings".
- `kernel/main.c` `browser_settings_stage`: reads the record, applies a stored choice to surface word 2039, and
  writes the record again whenever Kotoba's choice differs from what is stored. Kotoba still decides the choice
  (`hc-toggle`); C only persists a fact and restores it.
- `scripts/compositor-guest.cljk`: for this profile it runs the smoke script twice, the second time with
  `AIUEOS_PRESERVE_BLK_IMAGE=1` (the existing multi-boot switch of the journal-recovery gate) so the volume is the one
  boot one left, and keeps boot one's serial beside boot two's.
- The host injector sends F10 down/up on the first boot and Alt down/up on the second.

## Still open

Everything C8 asks beyond contrast: a settings window, a text scale (I7), a network setting; applying the record at
boot rather than at the settings stage; and more records than one.
