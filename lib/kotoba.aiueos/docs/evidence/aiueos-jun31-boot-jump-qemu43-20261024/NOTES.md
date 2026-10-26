# JUN-31: boot reached — the kernel's own exit (QEMU 43) through the loader's jump (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-ucs2-literal-align-20261024`):
with the shim-pinned amu rebuilding the image, which element of the boot stage's
U mark fails, and does fixing it carry the run to the kernel's own exit.

Built throughout with the shim-fixed amu lineage
(`/Users/junkawasaki/github/wt/hermes/jun31-pe-shim-pin-20261024`, pin 74ca4aa6 +
the `pe32plus.cljk` shim pad; `bin/amu` nbb route `--jvm-free`), fuel 200,000,000,
OVMF/TCG via `os/aiueos/scripts/smoke-qemu-uefi-loader.cljk`.

## 1. Measured before: the boot line names U's failing element exactly

First run of the tick (control: same tree, only the boot-stage diagnostic line
new — `boot <tfacts> <uflags> <kstat> <kgot> <klen> <s0> <s1> <c0> <c1>`):

```
BOOTX64.EFI 50,176 bytes  KERNEL.ELF 110,872 bytes
exit=33 debugcon="KHSCNAbcdefPWghvonkrxTMZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
map="0 5520 48" boot="1 0 0 110872 110872 1052672 1081344 1052672 1081344"
```

The nine words say, fact by fact:

| word | value | meaning |
|---|---|---|
| tfacts | 1 | parsed placement facts agree with the literals the pages were asked for |
| uflags | 0 | **the U mark's failure — see below** |
| kstat | 0 | `Read` of the whole file answered EFI_SUCCESS |
| kgot / klen | 110,872 / 110,872 | the whole file was read, exactly the measured length |
| s0 / s1 | 1,052,672 / 1,081,344 | `AllocatePages(AllocateAddress)` answered the hints: seg0 at **0x101000**, seg1 at **0x108000** |
| c0 / c1 | 1,052,672 / 1,081,344 | the two `CopyMem` return values |

Both segments were PLACED and COPIED; `c0 == s0`, `c1 == s1`. The only thing
`uflags` refused was its own last clause — it demanded `c0 == 0`, `c1 == 0`,
i.e. it read `CopyMem` as if it returned an EFI_STATUS. **EDK2 `CopyMem`
returns Destination** (`VOID *CopyMem(...)`), which is exactly the measured
value. The check was wrong, not the copy.

X failed independently: with the `map` line printed between `GetMemoryMap` and
`ExitBootServices`, the X mark never appeared (`xstat != 0`). The specific EFI
status was not captured in this run — the fallback's `xstat` diagnostic was
added after it.

## 2. Fix 1: U checks CopyMem's real convention

`uflags` now demands `(equals c0 s0)` and `(equals c1 s1)` — the copy answered
its destination, and the destination is the address `AllocatePages` answered
(which T already ties to the headers' `p_paddr`). One clause in
`os/aiueos/uefi/loader-probe.kotoba`.

## 3. Fix 2: X spends a fresh map key (main.c's exit shape)

`main.c:1209-1221` takes the memory map and exits back to back with nothing in
between — the firmware invalidates the map key whenever the map changes, and
the composition's `map` line print sits between the two calls. The probe keeps
the printed evidence AND main.c's shape by taking the map twice: the first call
answers the `map` line, the second's key is the one spent, with nothing but a
pure `kernel-load-u64-4k` in between. The fallback exit now prints
`xstat <status> <map-refresh status>` on its own serial line whenever
ExitBootServices refuses, so a residual failure names itself.

## 4. Measured after: QEMU 43 — the kernel's own exit

```
BOOTX64.EFI 50,688 bytes  KERNEL.ELF 110,872 bytes
  BOOTX64.EFI sha256 bc0696e1bc4c46aadab3b3fa6386115bff8832af26b578d8f8d9b709a100e330
  KERNEL.ELF  sha256 e7ee95b9f8992b679af7dc10ba14eb0460ead81b508be05fdb6feb43b9b72212
exit=43 debugcon="KHSCNAbcdefPWghvonkrxTUMXZB"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
map="0 5520 48" boot="1 1 0 110872 110872 1052672 1081344 1052672 1081344"
AIUEOS_UEFI_LOADER_OK markers=KHSCNAbcdefPWghvonkrxTUMXZB
  verdicts=0,2,5,24,23,41 entry=0000000000101000 esp=0,0,3,0,0,0
```

All twenty-seven marks, in the contract's order. `B` is written by the KERNEL's
entry (`boot-fixture.kotoba`: `kernel-out-u8 233 66`) and the run ends with the
kernel's `out 0xf4, 21`, which makes QEMU stop with (21 << 1) | 1 = **43**. The
loader's own fallback exit is 33 (16 << 1 | 1) and is reachable only when a
T/U/M/X mark fails, so 43 can only come from a kernel that ran — the jump
arrived at the admitted entry 0x101000 and nowhere else.

The serial console (the firmware's own driver) independently reports the same
decisions: `entry 0000000000101000`, `verdict 0 2 5 24 23 41`, `window 0 4 3 6 7`,
`digest 0 4`, `esp 0 0 3 0 0 0`, `boot 1 1 0 110872 110872 1052672 1081344
1052672 1081344`, `map 0 5520 48`.

## Boundary (say this, do not round it up)

* X's pre-fix refusal is observed as "the X mark never appeared" (`xstat != 0`);
  the exact EFI status was not captured before the diagnostic existed. The
  attribution to the stale map key stands on the single-variable comparison:
  the only X-path change between the two runs is the key refresh (the `uflags`
  clause does not touch X, and the fallback restructure runs after `xstat`).
* 43 proves a **loader-driven jump to an amu-built kernel image** (admit →
  place → copy → ExitBootServices → `kernel-jump-to`), on OVMF/TCG, with every
  decision reported twice (debugcon marks + firmware console lines).
* What 43 does NOT prove: the full AIUEOS kernel (this is the smallest kernel
  whose entry answers — `boot-fixture.kotoba`, two port writes), the GOP
  desktop, real input, the C-free acceptance build, or anything on OCI
  (JUN-34 remains blocked/read-only). JUN-31's acceptance criteria remain
  NOT MET on the C-free build path.
* The smoke asserts exit 43, the twenty-seven marks, verdicts, esp, entry, and
  the map line's shape; its `--expect-*` flags still exist for deliberately
  broken variants.
