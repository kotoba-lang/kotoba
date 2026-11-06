# What clock does the native kernel have? (JUN-813, ADR-0286 Amendment 6)

Date: 2026-11-06. Question: Amendment 2 needs a signed "latest" record judged against a clock. Which clocks exist in the tree and on the
machines, who can set each, and is one good enough for the threat?

Labels: **[measured]** = I ran something (under QEMU 10.0.3 TCG on the Mac host, test keys, `-nic none`) and the number is in
`native-fresh-qemu.json` next to this file (the `fresh` gate, `PASS_NATIVE_FRESH_QEMU`). **[read]** = from the code or docs at
`d3b50df04` plus this change, not executed. **[not done]** = nobody has checked.

## Verdict

The native kernel had **no wall clock**. [read] No `.kotoba` module under `os/aiueos/native` or `os/aiueos/kotoba` touches ports 0x70/0x71
(grep for `kernel-in-u8`/`kernel-out-u8` ports: 0xE9 debug, 0xF4 exit, 0xCF8/0xCFC PCI, 0x510/0x511 fw_cfg, 0x61/0x40-0x43 PIT, 0x60/0x64 keyboard,
0x1F0-0x1F7 ATA). The desktop shows no time. The only code that reads the CMOS RTC is the legacy C kernel's `rtc_minute_of_day`
(`kernel/main.c:2743-2790`, ADR-0264), a test stage that first *sets* the RTC to 12:34 and is not in the native kernel's module graph
(`build-native-kernel.py` discovers modules from `native/kernel.kotoba`/`desktop-debug-entry.kotoba`, never `kernel/main.c`) and whose status word 1968 no native
module writes. The one usable wall clock is the **CMOS RTC**. Under QEMU it works and reads what the hypervisor was told [measured]. It is set by firmware, the
hypervisor, or code running on the machine, never by the network, and it survives power-off on real hardware [read: PC architecture; the board is **not measured**]. That suffices for
the stated threat (a mirror or on-path attacker withholding or replaying records, tolerance of days) and does not for an attacker with firmware,
physical or hypervisor control. The design is small, so it is built (about 26 KB of kernel text: segment 0 grew from 2515840 to 2542208 bytes [measured, ELF program header]).

## Inventory

| # | Source | Measures | Survives reboot | Who can set it | QEMU | 6600H | What the code does with it |
| -- | -- | -- | -- | -- | -- | -- | -- |
| 1 | CMOS RTC, ports 0x70/0x71 | **wall clock**, UTC or local (register B/BIOS, unknown to the OS), seconds, 2-digit year plus century register 0x32 | yes (battery) [read] | firmware setup, any code with port I/O (`outb 0x70/0x71`), UEFI `SetTime`, the hypervisor; **not** the network, **not** disk bytes alone | present [measured]: register B = 0x02 (24 h, BCD), century 0x20, seconds advance by one per change, no UIP glitch seen | **[not done]**: no board evidence mentions it (`docs/evidence/awai*` has TSC deltas only) | before this change: nothing in the native kernel; legacy C stage sets then reads it (`kernel/main.c`). Now `rtc-now` in `update.kotoba` (Amendment 6) |
| 2 | TSC (`kernel-rdtsc`, `rdtsc`) | monotonic cycles **since boot**, not a date | no (resets with the CPU) | code with `wrmsr` (ring 0), the hypervisor | TCG: virtual-time based, exactly ~1 GHz [measured: TSC per RTC second between 0.99329e9 and 1.00672e9 over 5 boots, within 0.7% of the PIT-calibrated rate] | invariant TSC in hardware [read] | entropy and nonces (`tcp_stream.kotoba:111,1639,1712`, `kernel/pci.c`, `uefi/main.c:1703` for the data key), deadlines (`update.kotoba:333,342`, `rtl8125-program.kotoba:138`), the desktop frame clock (`desktop.kotoba:150-205`, calibrated, "never label raw TSC ms"), benchmarks (`render_profile.kotoba`, `debug_link.kotoba:724`, probes) |
| 3 | PIT channel 2 (ports 0x40-0x43, 0x61) | a 1.193182 MHz count, used for 20 ms one-shots | no | ring-0 code | present [measured: the calibration gave 1.00004e9 TSC/s in every boot] | present [read: `awai122` evidence boots the same desktop] | calibrates the TSC (`desktop.kotoba:162-192`), USB recovery waits (`xhci.kotoba:71`) |
| 4 | LAPIC timer ticks | monotonic ticks since boot | no | ring-0 code | n/a | n/a | legacy C kernel only: PLC release times (`kernel/apic.c`, `plc_runtime.c`) |
| 5 | UEFI RuntimeServices `GetTime` | the same RTC, through firmware | yes | same as row 1 | n/a | n/a | **no caller anywhere** [read: `GetTime`/`get_time` appears only as an unused struct slot in `dbc-probe/main.c`]. The pointer reaches the kernel (`boot_info.h`, `kernel/main.c:474`) and `kernel/qualification.c` uses variable services only |
| 6 | HPET, ACPI PM timer | monotonic | no | ring-0 code | n/a | n/a | **none** [read: no code; the ACPI reader takes the MADT and a few security tables, ADR-0264] |
| 7 | Network time (SNTP, NTS, HTTP/TLS `Date`) | a stranger's idea of the date | n/a | **whoever is on the path or runs the source**: exactly the attacker Amendment 1 worries about | n/a | n/a | **none** [read: the only network code in `update.kotoba` is the UDP 7795/7796 chunk pull; no NTP; `ipv4_udp.kotoba` is a packet parser; no X.509 date check anywhere in `native/` or `kernel/tls13.c`] |
| 8 | Hosted session `Date` | the browser's clock | n/a | the user's browser | n/a | n/a | `resources/aiueos/session/index.html:3313` (`clock()` in the hosted page); not the kernel |
| 9 | Tokei dapp | would show the TSC clock, uptime and offer `sync-time` | n/a | n/a | n/a | n/a | `distributions/awai/dapps/tokei.json`: `localCoreState: planned`, `sync-time` `state: not-implemented`, native window not-implemented; `native/dapps.kotoba` has no clock text |
| 10 | QEMU `-icount` (ADR-0211) | an instruction **count**, deliberately not time | n/a | n/a | not used here (the gate runs TCG with `clock=vm`) | n/a | benchmark tooling only |

## What I measured (all in `native-fresh-qemu.json`, `PASS_NATIVE_FRESH_QEMU`)

The guest (the real `update.kotoba`, `opt/aiueos/clock` hook) read the CMOS in five boots and waited for three changes of the seconds register:

| Boot | RTC given to QEMU | Guest reading (unix) | Result |
| -- | -- | -- | -- |
| default (no `-rtc`) | host clock | 1793964092 = launch + 9 s | status 0; follows the host wall clock [measured] |
| `base=2026-11-06T12:34:56,clock=vm` | 1793968496 | 1793968508 (+12 s virtual since reset) | status 0 |
| `base=2028-02-29T23:59:50` (leap day, midnight rollover in the 4 s probe) | 1835481590 | 1835481601 (+11 s) | status 0 |
| `base=2100-03-01T00:00:00` | 4107542400 | 951868809 (= 2000-03-01) | status 3 (below the build floor): QEMU leaves register 0x32 at 0x20 for 2100, so the guest sees year 2000. The decoder is right on the registers it read; this is the 2-digit-year limit, and it fails safe |
| `base=2025-01-01` | 1735689600 | 1735689610 | status 3: a reading before the build floor 2026-11-06 is refused, the raw conversion is still exact |

* Seconds register values seen in a row, e.g. `[32,33,34,35]`: +1 per change in all five boots. TSC distance between consecutive changes (two per boot): 1.000008e9 / 1.000023e9, 1.000008e9 / 0.999997e9, 1.000010e9 / 0.999990e9, 1.006716e9 / 0.993296e9, 0.999998e9 / 1.000051e9 (ratio to the PIT-calibrated rate 0.9932 to 1.0067).
* **170 synthetic register rows** (34 rows x 5 boots) through the same decoder: BCD and binary, 24 and 12 hour (12 AM/PM edge cases), century register 0x00/0xFF/0x19/0x20/0x21/0x22, leap days (2028, 2000 yes; 2026, 2100 no), 2038-01-19T03:14:08, end of 2099, and the rows that must decode to 0 (16 of the 34, the epoch included) (BCD nibble > 9, seconds 60, hour 24, 12-hour hour 0 and 13, month 0 and 13, day 0, 31 November, all-0xFF dead RTC): every one equals an independent `datetime`-based oracle (`fresh_oracle.rtc_unix`). The guest's binary-mode and 12-hour code is exercised **only by these rows**; no booted RTC used them.
* 42 freshness-record cases, then the 11 admitted ones again with the RTC 40 days ahead (all expired, verdict 2) and with a pre-floor RTC (all verdict 4, still admitted): all equal the oracle. The test keys are public.
* Nothing is written to the disk; the ESP walk and NVMe probe after the ML-DSA arena still pass; the `AIUEIMG1` self-test still reads 7/[15,1,7]; the desktop still draws.

## Per-claim answers

* *Wall clock or monotonic?* RTC: wall. TSC/PIT/LAPIC: monotonic since boot. [measured and read]
* *Survives reboot?* RTC yes on hardware [read]; QEMU gives it a fresh value from `-rtc` every launch [measured], so "survives reboot" is **not** demonstrated under QEMU. Everything else no.
* *Network attacker sets it?* RTC no, TSC/PIT no; the network sources (row 7) are the attacker's. No kernel code accepts time from the network. [read]
* *Disk-write attacker sets it?* Not by writing bytes: no code derives the RTC from the disk. By replacing `BOOTX64.EFI` they get ring-0 code and can set it, but that attacker already owns the machine (ADR-0286 Amendment 4). [read]
* *6600H.* **Not measured.** The RTC is architectural on the FCH, and OVMF/UEFI on the board reads it, but whether this board's RTC is UTC or local, holds a century register, has a charged battery, or what `Register D bit 7` reads, is unknown until a debug image reads it. The decoder tolerates local time (one day of slack) and a dead battery (build floor, VRT bit). [not done]

## Negative controls (kernels rebuilt with one rule removed, `fresh` gate, `--cases-only`)

| Mutant | Source edit | Result |
| -- | -- | -- |
| (i) accept the image context | `mp-prefix-byte` for kind 2 uses the `AIUEIMG2` bytes | **fails**: 30 of 42 cases differ. Every properly signed case is refused (result 1), and `header-signed-under-image-context` is *accepted* (0x1030f) |
| (ii) accept an expired record | `(> now until)` made unreachable | **fails** on exactly the two expired cases (`expired-one-hour-ago-30-day-lifetime`, `expired-two-months-ago`: verdict 1 instead of 2) |
| (iii) skip the signature count | `ims-final` ignored for kind 2 | **fails** on 11 cases: one-signer, duplicate-signer, unknown-id, ml-half-bad, ed-half-bad, pad-nonzero-first, both tamper-after-signing cases and the three image/catalog-context cases are admitted (result 15) |

## Regressions (full builder runs on the final source)

Each ran the real builder profile on the final source, one QEMU boot sequence per gate, `-nic none`:

* `fresh`: `PASS_NATIVE_FRESH_QEMU` (7 events; the receipt here is from this run).
* `catalog`: `PASS_NATIVE_CATALOG_QEMU`.
* `imgsig`: `PASS_NATIVE_IMGSIG_QEMU`.
* `update2`: `PASS_NATIVE_UPDATE2_QEMU` (the case list gains `fresh-context-both`) and `nvme`: `PASS_NATIVE_NVME_READ_QEMU`. Both **failed once** in the builder run
  ("the desktop must still draw after the update path ran" / "after the probe") while three builds and gates shared the host, and **passed** when the same built
  artifacts were gated alone (`check-native-update2-qemu.py`, `check-native-nvme-qemu.py` run directly). I read that as host-load timing of the 2 s key/frame wait, not as a
  regression: but I did not prove it against a baseline build of the parent commit, so it stays a stated uncertainty.
* Earlier `fresh` run (before the last edits to comments, pins and the update2 case): the same 42 cases and 170 rows.

## Not verified

A physical board (RTC value, mode, battery, century register); an RTC in binary or 12-hour mode on a real clock; RTC persistence across a reboot (QEMU re-reads `-rtc` on each launch);
a clock changed while the guest runs; any consumer (`check`, the desktop, the updates dapp are not built); production signer set; the persisted monotonic state (Amendment 6, designed only);
power loss. Documents that disagree with the code: ADR-0286 Status paragraph ("Design only", "nothing here is implemented") and `distributions/awai/update-policy.json` lines 18 and 20
(see Amendment 6).
