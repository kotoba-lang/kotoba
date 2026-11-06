# CMOS RTC probe under QEMU (JUN-813, ADR-0286 Amendment 8), 2026-11-06

Question: what does the probe the operator will run on the 6600H report, and is its reading right? Labels: **[measured]** I ran it, the number is in
`native-rtc-qemu.json` here (gate `rtc`, `PASS_NATIVE_RTC_PROBE_QEMU`, QEMU 10.0.3 TCG on the Mac, `-nic none`, no NVMe, no fw_cfg). **[read]** from code or docs, not
executed. **[not done]** nobody has checked.

## What is verified, and what is not

**The 6600H's RTC is NOT VERIFIED.** Nothing in this directory is a board measurement: UTC or local, century register, battery, binary/BCD and 12/24-hour mode, TSC
rate, and the UDP delivery of the probe's records on the board are all **[not done]** until the operator follows `docs/runbook-6600h-rtc-probe.md`. QEMU's RTC is whatever
`-rtc` says; the gate shows the probe and its decoder are right on it, not what a board does.

## What was built

`rtc-probe` in `os/aiueos/native/update.kotoba` (next to `rtc-now`; it reuses `rtc-now`, `rtc-unix` and the BCD helpers for the conversion and the cross-check, and has its own register reader, update-flag wait and snapshot logic), called from `nvme-report` in `native/desktop.kotoba`
before the QEMU-only hook; twelve KDBG records 0xc400..0xc40b through the debug link `nic/log`, the same records kept in context words 1498..1535 for the gate. It is **in
`update.kotoba`, not a new module**: a new module would change the expected module count of every profile in `build-native-desktop-macos.py` (51 now), which other
changes edit; `update.kotoba` is already in every desktop graph. Ports 0x70/0x71 only: index writes with bit 7 clear, data reads, no RTC data write, no disk, no fw_cfg
(the gate boots have no NVMe device and no fw_cfg file). Every spin is bounded by a TSC deadline. Segment 0 of the kernel is 2,563,328 bytes in this build [measured, ELF program
header]; the freshness evidence recorded 2,542,208 for #1275 (a different tree, so not a clean delta).

## The gate (five RTC settings, as the `fresh` gate used) [measured]

| Boot (RTC given to QEMU) | Face value A -> B (decoded on the host from the raw registers) | Verdict | Flags | TSC per RTC second | rtc-now |
| -- | -- | -- | -- | -- | -- |
| default (follows the host clock) | 2026-11-06T14:50:40 -> 14:50:41 | yes | 0x10000 (century plausible) | 1.0031e9 | 1793976641, status 0 |
| `base=2026-11-06T12:34:56,clock=vm` | 2026-11-06T12:35:02 -> 12:35:03 (base + 6 s virtual) | yes | 0x10000 | 1.0012e9 | 1793968503, 0 |
| `base=2028-02-29T23:59:50` | 2028-02-29T23:59:55 -> 23:59:56 | yes | 0x10000 | 1.0008e9 | 1835481596, 0 |
| `base=2100-03-01T00:00:00` | **2000-03-01**T00:00:07 -> 00:00:08 | no, below the floor | 0x10010 | 1.0026e9 | 0, status 3 |
| `base=2025-01-01` | 2025-01-01T00:00:07 -> 00:00:08 | no, below the floor | 0x10010 | 1.0019e9 | 0, status 3 |

In every boot register B read 0x02 (24-hour, BCD), register D 0x80 (valid RTC power), register A 0x26 (divider 010), century register 0x32 = 0x20, the hypervisor bit 1.
For 2100 QEMU leaves register 0x32 at 0x20, so the face value is the year 2000 (the 2-digit-year limit of Amendment 6, the same as its `fresh` evidence); the probe says "no"
for the right reason (below the build floor). The second read was one RTC second after the first and the TSC distance is the QEMU TCG TSC rate (about 1.00 GHz) in all five.
The update-in-progress self-check saw the flag and saw it cleared (1) in all five; the spin counts to the flag (0.28 to 3.4 million) and to the seconds change (1.8 to 2.1 million)
vary with TCG speed and are in the receipt.

Asserted per boot by the gate (`check-native-rtc-qemu.py`): the independent host decoder (`rtc_probe_decode.py`, `datetime`, not the kernel's code) reproduces the guest's
conversion of both snapshots; the flags it can recompute from the registers (register D, invalid field, build floor, no/odd seconds advance, SET bit) equal the guest's;
the guest-only flags (flag stuck, no two equal snapshots, `rtc-now` disagrees, wait broken) are 0; `rtc-now` is usable exactly when the probe says so; the second read is 1 to 2 s
after the first; the TSC per RTC second is in 0.5e9..2e9; the registers equal the base plus the virtual time since reset (0 to 900 s; the default RTC the host clock around launch).
Also: the decoder against `datetime` on synthetic registers QEMU never produces (binary, 12-hour AM/PM edge cases, century 0xFF assumed 20, 2100, 99 year) and ten invalid
register sets that it must refuse; the desktop still draws; the verifier self-test still reads 7 / [15, 1, 7].

## Negative controls (each must fail the gate) [measured]

| Control | How | Result |
| -- | -- | -- |
| (i) skip the update-in-progress wait | `update.kotoba` `pr-idle` made to return 1 at once; kernel rebuilt (`--profile rtc`), gate run by the builder | **fails**: `AssertionError: ('rtc-default-host', 'guest-only failure flags set', '0x200')`: the probe's own self-check caught the flag set and still set after its "wait" (flag 512, verdict no). KERNEL.ELF sha256 cdf3dc4e95740d6375770a6be465b57c26ae526bae66f0c3cc71b527a14211f1 |
| (ii) mis-decode BCD | `bcd` made to treat the high nibble as hex (x16, not x10); kernel rebuilt, gate run | **fails** in `check_boot` ("the guest and the host decoder disagree"): `flagsAgree`, `conversionAgrees` and `verdictAgrees` all False (the guest saw an invalid field, flag 8, and `rtc-now` status 2, where the registers decode fine). KERNEL.ELF sha256 d1864fb20bccdb3e956b3825f0be016a9229b9b78a38d3629f70840408d22a2a |
| (iii) tampered reports, no rebuild | in the gate, on a real report: a BCD nibble of the seconds register changed; the guest's conversion shifted 18 minutes; the verdict inverted; register D bit 7 cleared; register B SET bit on snapshot B; one record dropped | **each is detected** (flags/conversion/verdict disagree, or no complete report) |

Both mutated sources were restored (byte-identical to the committed `update.kotoba`) before the final runs.

## Regressions (full builder runs on this tree) [measured]

The probe runs in every debug-entry boot, so the profiles that boot it were re-run through the real builder, at most two builds at a time: `nvme`
`PASS_NATIVE_NVME_READ_QEMU`, `fresh` `PASS_NATIVE_FRESH_QEMU`, `update2` `PASS_NATIVE_UPDATE2_QEMU`, `catalog` `PASS_NATIVE_CATALOG_QEMU`, `provision` `PASS_NATIVE_PROVISION_ESP_QEMU`, `rtc` (final run, receipt in this
directory). The probe runs before the QEMU hook so the hook's clock words (365..381) are written after, not before, the probe's `rtc-now` call.

## Packaging for the board (checked on the Mac, no board) [measured]

`amu-full-root.macho package-aiueos-boot KERNEL.ELF --output X --payload boot-payload.bin --pci-resources v1` reproduces the builder's `BOOTX64.EFI` byte for byte
(sha256 13ca88385beaf4efbcaae9e4609add3e0ecaf0e7b28e9dfe1ae5237fc10e6e84). With `--netlog v1 --watchdog v1` added it wrote a 6,062,592-byte image,
sha256 d080f17bbc8a8bd97abd2273d5645dd5b1c50ad1a793947b125de6dd0e30a80f, from KERNEL.ELF sha256 496bc1e049475d79c577f43e4db4835b7e76ff1f886b15ce835c25e3f2fecd97. That image was not booted
anywhere. `sample-decode-qemu.txt` is the decoder's output on the QEMU boot of 2026-11-06T12:34:56 (a log without Mac receive stamps, so no UTC comparison line).

## Not verified

A physical board of any kind; the KDBG UDP delivery (QEMU has no RTL8168, so only the stored copy of the records is read); an RTC in binary or 12-hour mode on a clock
(only synthetic rows reach the decoder's binary/12-hour paths, and the kernel's through the earlier `fresh` rows); UTC-vs-local detection on a real zone offset (the host decoder's
offset arithmetic runs only on synthetic stamps, never on a board); the netlog-packaged image booting; the PXE delivery command for the 6600H (not recorded in the repository);
a battery power-off test; a clock changed while the kernel runs.

## Documents that disagreed with the code

None found for this change. `docs/evidence/awai122-*` READMEs say the images were "packaged with `--pci-resources v1 --netlog v1 --watchdog v1`" but no script in the repository does
that: `build-native-kernel-macos.py` packages with `--pci-resources v1` only, so the netlog packaging step is manual (now written down in the runbook).
