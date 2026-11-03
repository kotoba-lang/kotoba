# AWAI-122 stage 1: read-only NVMe on the 6600H (2026-10-31)

The desktop debug entry from kotoba#1084 (merge 4c51024ce), packaged with
`--pci-resources v1 --netlog v1 --watchdog v1`, was served over UEFI PXE from
the operator's Mac (en15, 10.77.0.1) to the AMD 6600H board
(MAC 0c:47:a9:60:9d:34) and booted at 09:20:38 JST. `kdbg.log` is that boot's
loader netlog and the kernel's KDBG records, as received on UDP 7799.

| KDBG | value | meaning |
| -- | -- | -- |
| c100 | `0400000f` | result 15 (every step passed); PCI slot 0x0400 = 04:00.0 |
| c101 | `1dcf32b0` | namespace 1: 500,118,192 blocks |
| c102 | `01040009` | 512-byte blocks (2^9); controller version 1.4.0 |
| c103 | `5452415020494645` | LBA 1 begins `EFI PART` (the disk's GPT header) |
| c104..c105 | `YXF800E3-256GT` | model number (NUL padded) |

The loader's BAR list has the controller's BAR0 at `0xfcd00000`, 16 KiB
(vendor 1d89, device ef25, 04:00.0), which is the window the driver maps.
500,118,192 x 512 bytes is 256.06 GB, the board's 256 GB disk.

The driver sends Identify, Create I/O CQ/SQ and Read only; it has no write
command. The board then booted its installed Itonami OS again once serving
stopped. This is one observation of one controller: it is not a physical
qualification, and GPT/FAT reading, signed-image receipt and writing are
later AWAI-122 stages.

Image: `image.efi` sha256 094d41ec6d970dc6f9fc0f6a84bcbd5ae6b03d8fdd24689ccce7a5bc8bc82664,
`KERNEL.ELF` sha256 163aaa2835d437a2682c01cf5a7dbb6f56da1b86a975fdae43765f0ec68d826e
(built on the Mac from the #1084 source with the pinned amu bootstrap compiler).
