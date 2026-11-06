# Runbook: read the CMOS RTC of the AMD 6600H board (JUN-813, ADR-0286 Amendment 8)

Purpose: ADR-0286 Amendment 6 judges a signed freshness record against the CMOS RTC, and the owner adopted that clock on 2026-11-06
**subject to the 6600H probe result**. Nothing in the repository measured this board's RTC. This probe prints the facts the decision needs. Run it on
the real board, record the output, and put the result in the Linear issue JUN-813 and in a new evidence directory (section 6).

**Status of every board fact below: NOT VERIFIED.** The only runs so far are under QEMU (`90-docs/evidence/rtc-probe-qemu-20261106/README.md`), where
the RTC is whatever `-rtc` says. Do not copy a QEMU number into a board claim.

| Board fact | Status |
| -- | -- |
| RTC holds UTC or local time | NOT VERIFIED |
| Century register 0x32 exists and holds BCD 20 | NOT VERIFIED |
| Battery keeps the RTC across a full power-off (register D bit 7 set after it) | NOT VERIFIED |
| Binary or BCD (register B bit 2), 12 or 24 hour (bit 1) | NOT VERIFIED (QEMU: BCD, 24 hour) |
| The seconds register advances once per second; the update-in-progress flag behaves | NOT VERIFIED |
| TSC rate (ticks per RTC second) | NOT VERIFIED |
| The probe itself runs on the board and its KDBG records arrive | NOT VERIFIED (the same debug link delivered KDBG 0xc100.. on 2026-10-31) |

## 1. What the probe is, and what it touches

`rtc-probe` in `os/aiueos/native/update.kotoba`, called once by the desktop debug entry (`native/desktop.kotoba`, `nvme-report`) right after the NVMe and
ESP reports and before the QEMU-only hook. It is **read only**: it writes the CMOS *index* port 0x70 (always with bit 7 clear, as `rtc-now` does, so NMI
stays enabled) and reads the data port 0x71. It never writes a data byte to the RTC, never touches a disk, and uses no fw_cfg, so the same code runs on
QEMU and on the board. One side effect to know: reading register 0x0C clears the RTC's pending interrupt flags, which nothing in this kernel uses.

It does, in order: (1) catches the update-in-progress (UIP) flag set, waits for it to clear and checks that it did (a self-test of its own wait);
(2) takes a snapshot of registers 0x00..0x0D and 0x32 only after two back-to-back snapshots agree and UIP is clear before and after; (3) waits for the seconds
register to change, takes a second snapshot the same way (about one second later, taken right after an update, so the TSC distance is one second); (4) asks the
production `rtc-now` (the clock the freshness verdict uses) for its answer and cross-checks it; (5) reports twelve KDBG records, tag 0xc400..0xc40b, UDP 7799.
Every spin is bounded by a TSC deadline (4e9 ticks) so a dead RTC cannot hold the boot past the watchdog.

## 2. Build and package the probe image

Same machine and tools as `docs/evidence/awai122-*` (the pinned Amu bootstrap compiler; paths below are the ones used for the QEMU gate on 2026-11-06, adapt
`--amu-source` and `--owner-repo-root` to your checkout). From the merged `main` (or this branch):

```sh
cd lib/kotoba.aiueos
python3 -I os/aiueos/scripts/build-native-desktop-macos.py \
  --amu-source <amu checkout> --owner-repo-root <kotoba-lang org dir> \
  --qemu /opt/homebrew/bin/qemu-system-x86_64 --qemu-sha256 c2bfa7fb0542f2c48c705676c0e494ddf8122d9ad1a111f2bf0767245bc82a43 \
  --firmware /opt/homebrew/share/qemu/edk2-x86_64-code.fd --firmware-sha256 33090cc07675baa5190d9f1e84bf5176b33bcbfa9bacac522961150cdb6dbb2a \
  --profile rtc --output <build dir>
```

This compiles the kernel and **runs the QEMU gate on that exact build** (`PASS_NATIVE_RTC_PROBE_QEMU` in `<build dir>/qemu/native-rtc-qemu.json`). The builder's
EFI (`<build dir>/kernel/BOOTX64.EFI`) has no netlog; the 6600H runs of 2026-10-31 used a loader packaged with `--pci-resources v1 --netlog v1 --watchdog v1`
(README of `awai122-nvme-read-6600h-20261031`). Package the same kernel the same way with the pinned compiler image, which is the `package-aiueos-boot` the
builder itself calls (it needs the working directory as file descriptor 3 and takes relative names):

```sh
mkdir stage && cd stage
cp <build dir>/kernel/KERNEL.ELF KERNEL.ELF
cp <build dir>/font/aiueos-padded.fnt boot-payload.bin
env -i PATH=/nonexistent <amu checkout>/seed/bootstrap/aarch64-macos/amu-full-root.macho \
  package-aiueos-boot KERNEL.ELF --output rtc-probe-netlog.efi --payload boot-payload.bin \
  --pci-resources v1 --netlog v1 --watchdog v1 3<.
shasum -a 256 KERNEL.ELF rtc-probe-netlog.efi        # record both
```

Checked on 2026-11-06 (Mac, no board): with `--pci-resources v1` only, this command reproduces the builder's `BOOTX64.EFI` byte for byte; with the three
options it wrote a 6,062,592-byte image (SHA-256 of that Mac run is in the evidence README; yours will differ if the build differs). The netlog image was **not**
booted, in QEMU or on the board. `--watchdog v1` resets the board about
every 90-100 s, which re-runs the probe each time and is what the 2026-10-31 runs used; leave it off (as the install run did) if a reset would be harmful.

## 3. Deliver it and read it

Delivery is the same as the awai122 runs: the EFI is served over UEFI PXE from the operator's Mac to the board (direct cable, Mac `en15` = 10.77.0.1 in those
runs; board MAC 0c:47:a9:60:9d:34, UEFI PXE first in the boot order, see `AGENTS.md` "Remote control over the RTL8168 debug link"). **The PXE/TFTP command the
operator used for the 6600H is not recorded in this repository** (the READMEs say "served over UEFI PXE from the operator's Mac"; `os/aiueos/tools/k16-pxe-server.py`
is the repository's PXE server, written for the K16 and not verified here for the 6600H). Use the operator's existing PXE setup and serve `rtc-probe-netlog.efi`.

Start the recorder on the Mac **before** the board boots. It listens on UDP 7799 (the KDBG port), stamps every datagram with the Mac's receive time, and appends to a log:

```sh
python3 lib/kotoba.aiueos/os/aiueos/scripts/rtc_probe_decode.py listen --log kdbg.log
```

If the operator's own netlog receiver already owns UDP 7799, use its log instead; `decode` reads any log with `AIUEOS_KDBG tttt vvvvvvvvvvvvvvvv` lines, but
then there is no `t=` stamp and the UTC comparison in section 4 must be done by hand (compare the face value with `date -u` read at the moment `c405` arrived).
The Mac's clock must be right: check it is NTP-synchronised before the run (System Settings, or `sntp` against a server you trust); the comparison is only as good as that.

Power on (or let the watchdog reset the board). The probe runs after the NVMe and ESP records: expect `c100..c115` first, the ESP hash takes about 10 s, then `c400..c40b`.
Decode when `c40b` has arrived (Ctrl-C the recorder first, or from another shell):

```sh
python3 lib/kotoba.aiueos/os/aiueos/scripts/rtc_probe_decode.py decode kdbg.log          # the last complete report
python3 lib/kotoba.aiueos/os/aiueos/scripts/rtc_probe_decode.py decode kdbg.log --all --json > report.json
```

The decoder is independent of the kernel's conversion (raw registers through Python `datetime`) and prints `host checks: ... agree True`; any `False` is a
kernel or decoder bug to report, not a board fact. If `c400..c40b` never arrive but `c100..` do, the image is not the probe image or the probe faulted (record
which KDBG tags did arrive); if only some of `c400..c40b` arrive, UDP dropped them or the boot was reset first, wait for the next watchdog cycle.

## 4. What to record, and how to read each field

Record, per run: the date and time (Mac `date -u` and local), the `kdbg.log` (it contains no secret), `report.json`, the SHA-256 of `KERNEL.ELF` and the EFI, the
commit the image was built from, whether the watchdog was on, and for the battery test the minutes of power-off. Also photograph or note the firmware setup screen's
clock and time-zone setting if the firmware has one, and the board's OS-visible date if another OS is installed (it may have been the one to set the RTC).

| Field in the decoded report | Read it as | Action |
| -- | -- | -- |
| `snapshot A / B` face value | The RTC's date and time exactly as its registers say, decoded with the mode bits | Compare with the Mac's UTC (next row) |
| `Mac UTC ... face value minus Mac UTC = X s -> reading` | **UTC vs local.** `X` near 0 (within about 30 s): the RTC holds UTC. `X` near a multiple of 900 s (JST is +32400 s): the RTC holds local time or is set that far off; the report names the nearest quarter-hour zone and the residual. A residual over 30 s means the clock is wrong or drifts, not a zone | UTC: record "UTC". Local: record the offset. Amendment 6 tolerates a day on issued-at but nothing on valid-until: a local clock ahead of UTC makes a record look expired up to that many hours early (a 30-day window absorbs 14 h) |
| `register D bit 7 (valid RTC power)` | 1 = the RTC kept power since the last read of that bit; **0 = the battery is dead or was removed**, the registers are untrustworthy | 0 means the clock is unusable (flag 4); do not adopt. Set a new battery and repeat |
| `mode: BCD/binary, 12/24-hour` | Register B bits 2 and 1. QEMU uses BCD, 24 hour. A board using binary or 12-hour mode makes the kernel's binary / 12-hour decode path run on real hardware for the first time (it has only been exercised by synthetic rows) | Record; if not BCD/24, say so in the issue and expect the decoder rows to matter |
| `century register 0x32 ... plausible / NOT plausible` | Does 0x32 hold BCD 19..21? Plausible: the century is read. Not plausible: the register is absent or unused on this chipset, 20 is assumed, which is correct until 2099 and is what the kernel does | Record raw 0x32 (the report lists all registers); not plausible is **not** a failure for this decision |
| `divider 010`, DST bit, SET bit | Register A bits 6..4 should be 010 (32.768 kHz). DST enable is whatever the setup left. **SET bit (register B bit 7) set = updates are halted** (flag 128) and the seconds will not move | Divider not 010 or SET set: the clock is stopped or odd; record it |
| `seconds advanced ... TSC ticks ... GHz` | Two snapshots one RTC second apart; the TSC distance is the TSC frequency if the first snapshot was taken right after an update (the self-check synchronises it). On a 6600H record what it says (a few GHz is the expectation, not a measurement; QEMU TCG prints 1.00 GHz) | An advance other than 1..2 s (flags 32, 64) means the seconds register is stopped or jumping. An unexpected rate is a note, not a verdict input; compare it with the desktop's PIT-calibrated TSC rate |
| `hypervisor bit` | 0 = no hypervisor reported (physical). 1 = a virtual machine | Must be 0 on the board; if 1, this was not the board |
| `rtc-now ... status` | The production freshness clock: 0 ok, 1 unstable, 2 invalid field, 3 earlier than the build floor 2026-11-06 (a reset RTC reads 1970, 1980 or 2000), 5 register D bit 7 clear | Must be 0 for Amendment 6 to work on this board |
| `verdict ... YES / NO (reasons)` and `information` | YES: `rtc-now` would give a usable clock and every cross-check held. NO lists the failing flags (the table in `update.kotoba` and in `rtc_probe_decode.py`). "update flag never seen" in the information list means the board's UIP window was missed within the 4-second search: record the spin counts, it is not a failure | NO with only information flags is not possible; NO always carries a reason |

Flags the decoder prints under "NO": update flag never cleared (1), no two equal snapshots (2), register D bit 7 clear (4), invalid field (8), earlier than the build
floor (16), seconds did not change (32), advance not 1..2 s (64), SET bit (128), `rtc-now` disagrees with the probe (256), the probe's own wait did not clear the flag (512).

### Battery test (one more run, separate from the first)

Register D bit 7 only says the RTC kept power *since it was last read*. To show the battery keeps time through a power-off: after a good run, shut the board down and
remove mains power (unplug the PSU or the board's DC supply) for at least 10 minutes with the CMOS battery fitted, note the real time of power-off and power-on, boot the
probe again and check that the new face value equals the old one plus the real elapsed time (within a few seconds, allowing for the zone you found), and that
register D bit 7 is still 1. A face value that went back to 1970 / 1980 / 2000 / the BIOS default, or register D bit 7 = 0, means the battery did not hold it.

## 5. Decision rule (input for the owner, ADR-0286 Amendment 8)

| Result | What it means for the adopted clock |
| -- | -- |
| verdict YES, `reading` UTC or a zone with offset at most 14 h, register D bit 7 set after the battery test | The RTC is usable under Amendment 6 as written (the day of slack on issued-at covers a local-time clock). Record the zone. |
| register D bit 7 clear, or the face value is reset after a power-off | Dead battery or not retained: the clock is unusable (fail safe is "not fresh"). Fix the battery and re-run before relying on it; the adoption does not hold on this board until then. |
| `reading` unclear (residual over 30 s, not near a zone) | The RTC is wrong or drifts. Record the drift against the Mac over a long gap; a clock that is days off defeats a 30-day window. |
| seconds not advancing, SET bit, UIP stuck | The RTC is stopped or the chipset does something this probe does not understand: report the raw registers; no adoption. |
| Anything where `host checks` is `False` | A bug in the kernel decoder or this tool. Report it with the registers; the registers, not the conversion, are the fact. |

## 6. Where to put the result

Create `docs/evidence/jun813-rtc-6600h-<date>/` with the decoded text (`decode` output), `report.json`, `kdbg.log` (only the lines of the probe boots), the hashes of
`KERNEL.ELF` and the EFI, the build commit, and a `README.md` stating, for each row of the table at the top, the observed value or "still NOT VERIFIED" and what you
ran to see it. Do not edit the QEMU evidence. Change the table in this runbook only through that README's numbers; never from the QEMU output.

## 7. What this does not do

It does not qualify the board, set or correct the RTC, read the UEFI `GetTime` service, or test a clock changed while the OS runs. It measures one board at one time.
It does not wire the freshness verdict to anything (Amendment 6: no `check` is built). The QEMU gate shows the probe and its decoder are right on a virtual RTC with
five settings; the KDBG UDP transmission of the records is not observed under QEMU (no RTL8168 there) and is the one thing only the board run shows.
