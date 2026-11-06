# Runbook: give a board the native update path (OSMETA.BIN) and keep its version straight

Status: JUN-942, written from the source and from QEMU/host gates. Nothing here was run on a physical board by this change
(see "What is NOT covered").

The native update path (`native/update.kotoba`, ADR-0286 amendment 4) refuses every network install with result 10 unless
`\EFI\ITONAMI\OSMETA.BIN` is a valid update journal, and refuses (result 9) any signed header whose version is not strictly above
the journal's floor. Nothing at boot or on the network path creates the journal. This runbook is how it gets there, and how you
choose the one number that matters: **N, the version of the image the board is running right now.**

## The layout

The release image builder (`make-release-image.py build --version N`) writes the primary ESP (FAT32, 512-byte clusters) with:

| path | content |
|---|---|
| `\EFI\BOOT\BOOTX64.EFI` | the loader. The removable-media path stays the firmware's boot entry and the universal fallback. |
| `\EFI\ITONAMI\BOOTX64.EFI` | a separate copy of the same loader bytes in its own clusters. The updater reads, hashes and swaps this one (`esp swap` exchanges this entry's clusters with `UPDATE.BIN`); `\EFI\BOOT\BOOTX64.EFI` is never touched by an update. |
| `\EFI\ITONAMI\OSMETA.BIN` | the journal, 20480 bytes, floor = active = N, active-image digest = SHA-256 of `\EFI\ITONAMI\BOOTX64.EFI`. |

The journal is written by `aiueos-provision-esp.py`'s own code (the builder imports it; it is not duplicated), which places the file
the way `native/esp.kotoba` `record-file` requires: a directory entry in the same 512-byte block as `BOOTX64.EFI`'s entry, one
contiguous run of free clusters, the first cluster 4096-aligned, everything inside the GPT's ESP, disjoint from every other file.
Cluster size stays 512 bytes: the alignment costs at most seven clusters (3.5 KiB) skipped in the free area behind the files, so a
larger cluster size or padding would only make the image bigger. If the journal cannot be placed the build refuses (exit non-zero)
and leaves no output file.

`UPDATE.BIN` (staging) and `STATE.BIN` are not created by the builder; the guest creates them on first use in free entries of the
same directory block, which the builder leaves free (the gate checks at least two).

## N: the one number

N is the **version of the image actually running on the board**, the same number that image was signed with
(`aiueos-image.py sign --version N`). The journal is written with floor = active = N and the board then admits exactly the signed
headers whose version is **above** N.

* **N too high** (above the version actually running): the board refuses legitimate updates. Every header with version <= N is
  refused 9, including the real next release if its version is <= N. The floor only moves up through a committed install, so the
  only way back down is `aiueos-provision-esp.py --replace` by an operator.
* **N too low** (below the version actually running): the floor sits under the running image, so the board re-admits older signed
  images (any signed header above the too-low floor), which defeats the rollback protection the floor exists for.
* There is no default and no inference anywhere: `--version` is required by the builder, by `apply-update`, and by the
  provisioner. Passing the wrong number is the operator's error; the tools can only refuse a missing or malformed one.

The floor is hash-checked, not signed (ADR-0286 amendment 4, interim): anyone who can write the disk can rewrite the journal.

## The version ledger: which N for this board

Every `aiueos-image.py sign` appends one line to an append-only operator-side ledger before the signed file is written:

```
{"date": "2026-11-06T14:05:25Z", "digest": "<sha256 of the image>", "file": "signed.bin", "format": "AIUEIMG1", "signer": "<first 16 hex of sha256(public key)>", "version": 7}
```

Default path `~/.itonami/aiueos-image-ledger.jsonl` (file mode 0600, directory 0700), override with `--ledger FILE`. Signing is refused
(nothing written) when the ledger is unusable (symlink, mode not 0600, unwritable, malformed line, partial last line) or already
holds the same digest at a different version. The digest is the SHA-256 of the image bytes, which is what the board's
`\EFI\ITONAMI\BOOTX64.EFI` hashes to when it runs that image.

```
python3 os/aiueos/scripts/aiueos-image.py ledger-lookup --digest <64 hex digits> [--ledger FILE]
```

prints `VERSION N` and the matching records (exit 0). Exit 1: the digest is not in this ledger. Exit 2: unreadable or malformed
ledger. Exit 3: the ledger holds two versions for the digest (edited by hand); do not guess.

The ledger is the operator's own file on the machine that signs. It is not signed, not tamper-evident, and only knows images signed
with this tool after this change. A board that runs an image signed earlier or elsewhere is **not found**: do not provision it with
a guess (see "Deployed board", step 3).

## Fresh board

1. Pick N for this image (a positive integer; every later update must be signed with a larger number).
2. Build: `AIUEOS_IMAGE_VERSION=N sh os/aiueos/scripts/build-release-image.sh` (or `make-release-image.py build ... --version N`
   with the three inputs). The script refuses to start without `AIUEOS_IMAGE_VERSION`. The build verifies the layout itself;
   re-check any image later with `make-release-image.py verify --image IMG --version N`.
3. Tie the loader's digest to N in the ledger: sign the loader you just built with the same number,
   `aiueos-image.py sign --key SEED --version N BOOTX64.EFI loader-vN.signed` (the signed file may also be what you serve; it
   need not be). Without this line a later `ledger-lookup` of this board's digest finds nothing. Record N in your release notes too:
   the journal on the disk is the only other place it lives.
4. Write the disk image to the board's disk with your usual installer/flash tooling (not covered here).
5. First proof the journal is usable: serve a header signed as N (expect `aiueos-remote.py update` to report 9, version not above
   the floor) and a header signed as N + 1 (expect it to verify). Result 10 means the journal was not accepted.

## Deployed board (has `\EFI\ITONAMI\BOOTX64.EFI`, no `OSMETA.BIN`)

1. **Read the digest of the board's `\EFI\ITONAMI\BOOTX64.EFI`.** There is no `esp-read` remote command in `aiueos-remote.py`
   (code check, 2026-11-06). The digest comes from the debug desktop's KDBG records on UDP 7799 at boot
   (`native/desktop.kotoba` `nvme-report`): `c110` is `result | path << 8 | FAT type << 16` and must read `…20010f` (result 15, path
   1 = ITONAMI, FAT32; path 2 means the loader came from `\EFI\BOOT` and the board has no `\EFI\ITONAMI` to provision), and the
   SHA-256 is `c112` + `c113` + `c114` + `c115`, 16 hex digits each, concatenated in that order (see
   `docs/evidence/awai122-esp-read-6600h-20261031/kdbg.log`). Requires the board to run a debug desktop image with `--netlog v1`.
2. **Look the digest up:** `aiueos-image.py ledger-lookup --digest <that digest>`. `VERSION N` is the number to use.
3. **Not found (exit 1)? Stop.** Do not provision with a guess. Find the ledger or signing record of whoever signed that image. As an
   example of a pre-ledger board, `docs/evidence/awai122-esp-install-6600h-20261031` records the 6600H's installed loader
   `e814782522ddc62f60fc67f8a10c4499a6410df220eedb630d86c1d0c636e8c4` as signed with version 3; that is a record from 2026-10-31,
   not a fresh reading of the board. If no record exists the version is unknown: reinstall the board from a builder image with a
   chosen N instead.
4. **Work on the disk, not on the running board.** The provisioner takes a raw disk image or the whole block device; the board must
   not be running from that disk. Copy first and try on the copy:
   `python3 os/aiueos/scripts/aiueos-provision-esp.py COPY.img --version N`. It refuses (exit 2, nothing written) when the disk has no
   valid GPT/ESP, is not FAT32, has no `\EFI\ITONAMI\` or `BOOTX64.EFI`, already has an `OSMETA.BIN` (use `--replace` only as the
   explicit act of lowering or resetting the floor), or cannot place the file.
5. Run the same command with the same N on the real disk (`--block-size 4096` for 4096-byte logical blocks). It prints the file's
   SHA-256, floor = active = N, the active image digest (must equal the digest from step 1) and the byte offset.
6. Boot the board and check as in "Fresh board", step 5.

## What is NOT covered

* **Firmware boot behaviour is NOT VERIFIED.** No claim is made about how real firmware boots this layout. The only hardware record
  (the 6600H, `docs/evidence/awai122-esp-install-6600h-20261031`) boots `\EFI\ITONAMI\BOOTX64.EFI` with PXE first in the boot order;
  the builder creates no UEFI boot variable, and nothing here says which of the two loader paths a given firmware prefers or
  falls back to. The QEMU gates read the disk through the guest's NVMe driver; they do not boot the loader on the disk.
* The provisioner on a real block device, 4096-byte logical blocks and FAT16 are untested (FAT16 is refused by the guest's write
  path anyway). No physical board was provisioned or updated by this change.
* Only the release image's primary ESP carries the layout. The ISO's El Torito image, the install-USB live ESP
  (`make-install-usb-image.py`), the recovery partition, and the hw-probe and physical-qualification media have no
  `\EFI\ITONAMI\` and no journal. An image installed from the installer USB gets the layout only if it is the release image
  built with `--version` (the installer writes the release image; this was not run).
* The ledger is a lookup aid on one machine, not a signed or tamper-evident log, and it knows nothing about images signed before it
  existed or on another machine.
* The floor is hash-checked, not signed. The network pull, the production signer set and Ed25519-only AIUEIMG1 are unchanged and
  not exercised here.
* `aiueos-remote.py` has no command that reads the floor or the journal; the only observable is the install result (9, 10, 15).
