# AWAI-122 stage 4: a verified image installed on the 6600H's ESP (2026-10-31)

Board: AMD 6600H (RTL8168, NVMe YXF800E3-256GT, FAT32 ESP), direct cable to the operator's Mac. Debug desktop
image of PR #1119 (9f67ec503), packaged `--pci-resources v1 --netlog v1` without the watchdog so a reset could
not cut the install short: image SHA-256 `6d939f59c1b4276fe9b9148c7be3e58b01162acd3679e61930fe420b7fe4ce17`,
KERNEL.ELF `3dea81779b179e8f1de056b46342938c27f022a9d3ec9c4d153e9493d469e88f`. The operator approved
writing the real ESP.

## What was installed

The loader already installed on 2026-10-30 (`dapps-install-netlog.efi`, 6,062,592 bytes, SHA-256
`e814782522ddc62f60fc67f8a10c4499a6410df220eedb630d86c1d0c636e8c4`), signed with the image-signing key as
version 3. What the board boots is therefore unchanged, while the whole write path runs on the real disk:
UPDATE.BIN created, image written, read back, entries swapped.

## Run

| time | record | meaning |
|---|---|---|
| 17:08:11 | `c118 07010f07` | verifier self-test passed |
| 17:08:21 | `c110 …20010f`, `c112..c115 e8147825…` | ESP found (FAT32), `\EFI\ITONAMI\BOOTX64.EFI` hashes to the installed loader |
| 17:08:24 | `c001` | signed ping answered (desktop loop up) |
| 17:09:16 | `c120 …0f`, `c121 …03`, `c122 005c8200005c8200`, `c124..c127 e8147825…` | stream verified: version 3, 6,062,592 of 6,062,592 bytes, digest = manifest |
| 17:09:16 | `c130 …0f0f` | install result 15 (stream 15) |
| 17:09:16 | `c131 005c820000000bf0`, `c132 …0bf0` | after the swap BOOTX64.EFI starts at cluster 0xbf0 (the staging chain), size 6,062,592 |
| 17:09:16 | `c133..c136 e8147825…` | the ESP walk after the swap hashes BOOTX64.EFI to the manifest digest |
| 17:09:31 | `c002` | signed reboot, PXE server stopped beforehand |
| 17:10:37 | `LOADER_INST`, `LOADER_OK` | the board booted the newly written BOOTX64.EFI from NVMe |

The install took 52 s from the command (5,922 datagrams in 31.7 s while writing; the rest is the NVMe
re-probe, the ESP walk before and after, and the read-back hash).

`kdbg.log`: the records from 17:08:00 to 17:11:00 (the repeated heartbeats listed once).

Not covered: the image content did not change (a functional update is the next run); FSInfo's free count
is not updated; Ed25519 only; no rollback protection beyond version >= 1; the boot order is still PXE
first (stage 5).
