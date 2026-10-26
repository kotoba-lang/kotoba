# 0099 — The live installer, and the QEMU gate that installs with it

Accepted 2026-08-25. Tranche two of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap` (tranche one is
ADR-0097). This closes gate **I3** — under QEMU, not on hardware — and
upgrades **I5** from fake-device-only to a measured full-chain refusal.

**2026-10-18: decision 3's Node half is superseded by owner direction.**
The install chain runs on amu-compiled kotoba (selfhost) only — no node,
nbb or npm at install time or in the build procedure that assembles the
USB. Linux stays an install-time mechanism; the Node/nbb payload this ADR
landed is interim and its replacement is the tracked migration (Linear
JUN-70, slices S1–S5). The decision layer already moved first:
`install-intent-admit.kotoba` is a native kotoba object; the execution
substrate is `kotoba.native.linux-static` (loader-less static ELF,
capability handlers in `tools/linux_static_handlers.kotoba`).

## What landed

- **`scripts/make-live-installer.py`** — builds a Linux UKI (Debian stable
  kernel, systemd stub via `ukify`) whose initramfs is *mechanism only*:
  busybox, a dependency-ordered storage-module list, `lsblk`/`blkid`, and an
  `/init` that mounts kernel filesystems, finds the install-USB payload by
  its fixed GPT partition GUID, extracts the bundle to a tmpfs, and hands
  over. Every decision lives in the payload. Package versions and artifact
  digests land in `live-installer-receipt.json`. Linux remains an
  install-time mechanism, not an aiueos runtime premise (decision 3).
- **`installer/live/install-live.cljs`** — the decision layer: reads the
  intent, keeps exactly one whole disk matching model/transport/capacity and
  never the boot USB (zero and two-plus refuse with named reasons),
  dry-runs for interactive intents, and for unattended intents hands the one
  named device to `install-to-disk.cljs`, which re-verifies everything.
- **`make-install-usb-image.py --live-uki`** — second boot mode for the
  install USB: p1 boots the installer UKI, p2 keeps the release *recovery*
  volume byte-identical (aiueos itself as the independent fallback), p3 the
  payload — now also carrying the node runtime, an npm `nbb` tree, PATH
  shims, and the live orchestration. The receipt's `:boot` section names the
  mode.
- **`scripts/smoke-qemu-install.cljs`** — the I3 gate: four boots, asserted
  together (install; boot the NVMe twice with the USB gone; re-insert the
  USB and require refusal with the disk untouched), plus offline checks
  between boots (installed extent digest == release receipt; target receipt
  present in the last MiB).

## Measured on the way (each of these was a red gate first)

| # | Failure | Cause | Fix |
|---|---|---|---|
| 1 | OVMF fell to the EFI shell | classic `objcopy --add-section` UKI recipe: the current stub's ImageBase is high, fixed VMAs wrap, SizeOfImage did not cover the payload | assemble with `ukify`; verify now parses PE headers and refuses sections beyond SizeOfImage |
| 2 | kernel panic `Failed to execute /init (error -2)` | `#!/bin/sh` shebang before `busybox --install` has created `/bin/sh` | `#!/bin/busybox sh` |
| 3 | init evidence invisible to the serial gate | last `console=` owns `/dev/console` | serial-last for gates; `--display-console` flips it for operator-watched sticks |
| 4 | zero block devices in the live env | second build in the same output dir: leftover `.ko` files satisfied the copied-already test and left `modules.list` EMPTY | extract starts by removing old modules; list regenerates |
| 5 | payload never found | `lsblk` PARTUUID is udev-fed and blank in an udev-less initramfs | probe with `blkid -p -s PART_ENTRY_UUID` |
| 6 | handover died rc=127 | node resolves its libraries from the initramfs; libstdc++/libgcc_s were not in the util-linux closure | ship node's library closure |
| 7 | orchestration died unexplained | no `/tmp` in the rootfs; the inspection report goes through `os.tmpdir()` | `/tmp` in the cpio and in `/init` |
| 8 | `target-serial-mismatch` on the very disk the intent names | sysfs pads serials with trailing spaces, the digest covered the padding | serial digests are over the trimmed form |
| 9 | aiueos stopped after 14 evidence lines on the installed disk | gate booted aiueos at 2048M; every other aiueos gate runs the canonical 128M | per-boot memory: Linux boot 2048M, aiueos boots 128M |

Rows 4 and its neighbours are the workspace's standing lesson in miniature: a
build that could not do its job produced the same green `AIUEOS_LIVE_INSTALLER_OK`
as one that could, until the boot was actually measured. The gate now exists
so that this class cannot come back silently.

## Still red

- **I4** — no physical-NIC driver, no first-boot provisioning, no sshd, and
  therefore no external SSH handshake. Nothing in this tranche claims it.
- **I6/I7** — no physical machine has been probed or installed. The QEMU
  green is evidence for the *chain*, not for the B850M target; the root ADR's
  warning against reading spec-sheet names as probe receipts stands.
- The live console evidence goes to serial by default; a physical operator
  needs a `--display-console` build to see the interactive report.
