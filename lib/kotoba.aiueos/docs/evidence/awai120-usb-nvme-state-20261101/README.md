# AWAI-120 USB HID and NVMe app-state evidence, 2026-11-01

`receipt.json` binds the signed native Mac compiler, 49-module source lock,
reproduced kernel/EFI and the integrated QEMU result. `restored.png` is the
actual cold-restored framebuffer: Goal `aba`, key locked and Approved 0.

The ten observations cover USB keyboard and relative mouse/button input with
PS/2 disabled, queued-key consent refusal, state creation/save (including a
sealed key and independently verified signed outbox), cold restore,
uncommitted-crash restore, corrupt published-slot refusal, unpublished-slot
rejection, invalid primary/backup GPT CRC refusal and absent USB hardware.
The existing ATA local-draft cold/crash/refusal gate also passes.

The observer uses private temporary fixtures and checks the original boot
file, FAT copies and ESP write bounds. It does not grant human consent or
qualify 6600H, hubs, wireless receivers, Bluetooth, canonical D2, encrypted
backup, physical power-loss safety or a production release. Full local build
outputs remain in the task workspace; no private dependency source or key is
included in this evidence directory.
