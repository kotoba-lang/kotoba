# AWAI-122 stage 2: the installed loader read and hashed on the 6600H (2026-10-31)

The desktop debug entry from this PR (commit 9ce1121be), packaged with
`--pci-resources v1 --netlog v1 --watchdog v1`, was PXE-served from the
operator's Mac to the AMD 6600H and booted at 11:32:30 JST. `kdbg.log` is that
boot's loader OK line and KDBG records (UDP 7799).

| KDBG | value | meaning |
| -- | -- | -- |
| c100..c103 | as in stage 1 | NVMe 04:00.0, 500,118,192 x 512 B, LBA 1 `EFI PART` |
| c110 | `0020010f` | ESP result 15; path 1 = `\EFI\ITONAMI\BOOTX64.EFI`; FAT32 |
| c111 | `005c8200` | file size 6,062,592 bytes |
| c112..c115 | `e8147825…c636e8c4` | SHA-256 of that file |

The digest is exactly the SHA-256 of `dapps-install-netlog.efi`, the image the
operator's Mac served on 2026-10-30 when the loader's `--install v1` wrote the
installed copy (AWAI-120):
`e814782522ddc62f60fc67f8a10c4499a6410df220eedb630d86c1d0c636e8c4`, 6,062,592
bytes. So the kernel found the board's own ESP through its GPT, walked FAT32
and read every byte of the installed loader correctly. The hash of 6 MB took
about 10 s (c103 at 11:32:31, c110 at 11:32:41).

Read only: the driver has no write command. One observation of one board; not
a physical qualification. The GPT CRCs are not checked yet. Receiving a signed
image and writing it are later AWAI-122 stages.

Image: `image.efi` sha256 881b89f646016dbdd02017f491499cfb486bce00163ffe3a04d13f87730dcd10,
`KERNEL.ELF` sha256 140c7512214c419b46fd3f021a6cd489c8f01342e40d0ce5f7ad5cae5d9150c9.
