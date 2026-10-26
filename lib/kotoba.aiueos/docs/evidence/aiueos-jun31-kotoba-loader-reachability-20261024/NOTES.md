# JUN-31: reachability of the ADR-0131 `AIUEOS_KOTOBA_LOADER_EFI` slot (2026-10-24)

Question this tick answered: can the existing `.kotoba` UEFI loader group reach
the machine-checked slot that `build-uefi.sh`'s K16 pure-native profile refuses
on (`REFUSED foreign-code: uefi/main.c`), and what is left before it replaces
the C loader. Measured on branch `hermes/jun31-image-route-node-free-20261022`
(merged to origin/main at `f481e9e`), amu checkout `74ca4aa6` (JUN-29 seed
runner), host `bin/amu` route `--jvm-free`.

## 1. The loader group did not compile at all (drift), and one fix restores it

`amu compile os/aiueos/uefi/loader-probe.kotoba --source-path os/aiueos/kotoba
--target x86_64-aiueos-uefi-v1 --artifact image --jvm-free` failed with exit 65
(`compile-before-fix.log`):

```
:kotoba.error/subset-reject source="elf.kotoba"
"if test is :i64, and a number is never truthy: compare it ... or answer :bool"
```

Cause: `aiueos.uefi.elf/admit` computed two 0/1 flags and used them as `if`
tests (the entry-in-segment-0 clause, reason 42, and the segment-overlap clause,
reason 43). The current Kotoba subset rejects an `:i64` truthiness test, so
main's loader sources no longer built against current amu.

Fix (semantics-preserving, in `os/aiueos/kotoba/aiueos/uefi/elf.kotoba`): the
same two clauses spelled as nested comparisons. The probe's discriminating
verdicts are unchanged — the smoke asserts each mutation answers its own reason
and it still reports `verdicts="0 2 5 24 23 41"` (`smoke-qemu-uefi-loader-
after-fix.log`).

## 2. The slot is satisfiable today: a real Kotoba/Amu PE32+ exists

After the fix, the compile succeeds and amu's own packager emits the artifact
(`compile-restored-probe.log`, `pe32plus-check-restored.log`):

```
BOOTX64.EFI 40,448 bytes
sha256 031ec2abac4428f5f970d738788aa27308e9b9b2cf6bd70766a1096eedd1039c
MZ / PE\0\0  machine 0x8664  sections 3  optional magic 0x20b (PE32+)
subsystem 10 (EFI application)  entry_rva 0x1000
provenance: :builder :kotoba-compiler/v1, :target :x86_64-aiueos-uefi-v1,
  :source-sha256 ad87506f..., :kir-sha256 257b7480..., :fuel-metering :on
```

Wiring it into the machine-checked slot changes the profile's measured answer
(`pure-native-slot-absent.log` vs `pure-native-slot-filled-restored.log`):

```
slot absent : exit 3, REFUSED foreign-code: uefi/main.c, loader=refused
slot filled : exit 0, loader=copied, kernel=linked, bootable=no
gate        : AIUEOS_K16_PURE_NATIVE_OK scanned=93 kotoba=93 stubs=0
              foreign=0 unattested=0
```

`bootable=no` is the honest state and nothing here claims otherwise: the probe
DECIDES which kernel may run; it does not load one (see §4).

Note the gate's own state moved since ADR-0131's measurement: `scanned=93
kotoba=93 foreign=0 unattested=0` (was 99 / 47 / 32 / 20). The unattested
provenance gap ADR-0131 recorded has closed on main.

## 3. A cleanup commit had clobbered half the loader probe

`8e58e52` ("cleanup: preserve uncommitted tracked changes (24 files)",
2026-09-05, whose own message says "NOT auto-merged ... the working tree they
came from may be far behind it") rewrote `os/aiueos/uefi/loader-probe.kotoba`
and `os/aiueos/kotoba/aiueos/uefi/integrity.kotoba` back to the ADR-0180
stage, silently dropping the ADR-0197 wiring (`memory`: markers P/W — a
firmware-allocated page written and read back, the five placement clauses) and
the integrity digest markers (g/h). No commit since has touched either file.

Restored both from `2c34fd7`. With the restore, the probe again reaches all
fourteen markers (`smoke-qemu-uefi-loader-canonical.log`):

```
BOOTX64.EFI 40448 bytes
exit=33 debugcon="KHSCNAbcdefPWghZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41"
window 0 4 3 6 7 / digest 0 4   (serial.log)
```

`os/aiueos/scripts/smoke-qemu-uefi-loader.cljk` follows: `default-markers`
back to `KHSCNAbcdefPWghZ`, with the 8e58e52 provenance noted in place.

## 4. Fuel metering, measured

amu now meters fuel (`:fuel-metering :on`) and the default budget is too small
for the digest path — SHA-256 over 176 bytes runs as x86-64 with a 512-byte
state. Controlled comparison, identical qemu invocation, identical sources:

```
no --fuel     : debugcon="KHSCNAbcdefPW"  then dead — no gh, no Z,
                QEMU exit 0 (never reached isa-debug-exit)
                (smoke-qemu-uefi-loader-restored-probe.log)
--fuel 8000000: debugcon="KHSCNAbcdefPWghZ", QEMU exit 33
                (restored-probe-fuel8000000-debug.log / -serial.log)
```

The smoke therefore now compiles with `--fuel 8000000`, with the measurement
recorded at the flag.

## 5. What is left before a bootable C-free K16 (unchanged, now narrowed)

- The loader group has `console`, `elf`, `memory`, `integrity` and the probe
  composition. Still missing per ADR-0180's own list: `fs` (read the kernel
  from the ESP), `exit` (`ExitBootServices`) and the load-and-jump
  (`kernel-jump-to` executing) — i.e. the probe decides and reports but cannot
  hand a kernel its memory map and jump.
- The pure-native kernel link carries `ld.lld: warning: cannot find entry
  symbol aiueos_kernel_entry; not setting start address` — the linked
  `aiueos-k16-pure-native-kernel.elf` (445,992 bytes) has no entry symbol, so
  even with a loading loader the jump target is missing.
- JUN-31 item 2 (a bootable kernel with no C in the acceptance path) is
  therefore still NOT MET; this tick moved the loader blocker from "no
  Kotoba/Amu PE32+ exists" (ADR-0131's wording, no longer true) to the three
  named modules plus the kernel entry symbol.

## Files

| file | what |
|---|---|
| `compile-before-fix.log` / `compile-after-fix.log` | the subset reject and the fix's clean compile |
| `BOOTX64.EFI` (+ `.provenance.edn` / `.publication.edn`) | the amu-produced PE32+ slot artifact, 40,448 B |
| `pe32plus-check.log` / `pe32plus-check-restored.log` | PE header measurements (25,600 B pre-restore variant; 40,448 B restored) |
| `smoke-qemu-uefi-loader-after-fix.log` | QEMU/OVMF smoke after the elf fix only: verdicts unchanged |
| `smoke-qemu-uefi-loader-restored-probe.log` | restored probe, default fuel: stops after PW |
| `restored-probe-fuel8000000-*` | restored probe with fuel budget: full markers, serial window/digest lines |
| `smoke-qemu-uefi-loader-canonical.log` | the smoke as it now stands, passing |
| `pure-native-slot-absent.log` / `pure-native-slot-filled.log` / `pure-native-slot-filled-restored.log` | the ADR-0131 slot: refused / copied / copied with the restored probe |
