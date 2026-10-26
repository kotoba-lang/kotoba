# ADR-0180: A BOOTX64.EFI that decides which kernel may run

- Status: accepted
- Date: 2026-09-02

## Context

`os/aiueos/uefi/main.c` is 1,214 lines of C and it is the whole of K16's
`BOOTX64.EFI`. The K16 pure-native gate (`os/aiueos/scripts/k16-pure-native-gate.cljk`,
ADR-0131) refuses the profile on exactly that file:

```
REFUSED foreign-code: uefi/main.c
```

amu ADR-0299 got a Kotoba UEFI application to boot under OVMF and to name
strings, GUIDs and bytes. It closed with two things it could not do, and both
of them are what a loader is made of: it had no address it could WRITE, so
`AllocatePages`, `HandleProtocol`, `GetMemoryMap` and every other firmware call
with an out-pointer were out of reach; and nothing produced the address of a
Kotoba function, so `kernel-jump-to` stayed encoded and unexecuted.

## Decision

Take the half that needs neither, and take it first.

`main.c` mixes two kinds of work. Allocating pages, opening a volume, reading
16 MiB chunks and copying segments is MECHANISM in ADR-0015's sense. Deciding
**which bytes are allowed to become the kernel**, and **saying what happened**,
is not. Those two are this ADR's scope:

| module | lines | what it replaces in `main.c` |
|---|---|---|
| `aiueos/uefi/console.kotoba` | 103 | `console_ascii` (:186), `debug_string`, the hex writer |
| `aiueos/uefi/elf.kotoba` | 154 | the ELF admission block (:1100-1121) |

They are modules of ONE program, linked by amu's project route
(`--source-path`), not two kernel objects. A kernel object exports one symbol
and cannot call another, and a loader that cannot call a subroutine is not a
loader. Measured 2026-09-02: `--source-path` with `--artifact image` is
accepted for `x86_64-aiueos-uefi-v1`, though amu ADR-0296 records it is still
refused for the *kernel* image target.

**The admission rules are amu's, not `main.c`'s.** Where the two disagreed the
C was looser, and this follows `package-embedded-kernel`
(`src/kotoba/compiler/packaging/pe32plus.cljc:344-351`) so that the loader
admits exactly what the packager emits: two PT_LOAD segments, `filesz == memsz`,
`paddr` at or above 1 MiB and page-aligned, `memsz` at most 1 MiB,
`paddr + memsz` under 1 GiB, flags exactly `[5 6]`, the entry inside segment 0,
and no overlap.

**One rule is stricter than both.** `main.c` casts `kernel_file + elf->phoff` to
a struct pointer and reads it at whatever alignment; on x86-64 that happens to
work. A bounded Kotoba load checks alignment LAST and TRAPS, so an unaligned
`e_phoff` would kill the loader rather than refuse the file. Clause 8 turns
that trap into a verdict, and clause 9 does the same for the table's extent:
both bounds are proved before the first program-header byte is read.

**Printing a number without a buffer.** `OutputString` takes a `CHAR16 *`. With
no writable memory there is no scratch array to build digits in, so the digits
are not built: sixteen one-character literals sit in the pool, `digit-char`
selects one by value, and a number costs one firmware call per digit. When a
writable scratch region exists the buffer form can replace it without changing
a caller.

## Evidence

`os/aiueos/scripts/smoke-qemu-uefi-loader.cljk`, QEMU 10.1 with OVMF
(`edk2-x86_64-code.fd`), q35, TCG, the image on a `fat:rw:` ESP.

```
BOOTX64.EFI 9728 bytes
exit=33 debugcon="KHSCNAbcdefZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41"
AIUEOS_UEFI_LOADER_OK markers=KHSCNAbcdefZ verdicts=0,2,5,24,23,41 entry=0000000000101000
```

and the firmware's own console driver rendered, on the serial line:

```
AIUEOS KOTOBA LOADER
entry  0000000000101000
verdict 0 2 5 24 23 41
```

**The fixture is a real kernel.** The 176 bytes the probe admits are the ELF
header and both program headers of a kernel amu itself produced
(`--target x86_64-aiueos-kernel-v1 --artifact image --fuel 32768`, 110,872
bytes, sha256 `e4a5c9dc3ca03e310d9b8a0924e9e2ce510fb9678335bd2fe6496b7e9c182f1e`).
A header invented to pass would only prove the rules agree with themselves.

**Five refusals, each naming its own clause.** Five copies of those same bytes
with ONE field changed each: `2` magic, `5` machine, `24` segment 0 below 1 MiB,
`23` segment 0 `filesz != memsz`, `41` segment 1 flags. A verdict that merely
went non-zero would not distinguish "the file is wrong" from "the reader is".

### The smoke discriminates

| break | debugcon | verdicts | reading |
|---|---|---|---|
| baseline | `KHSCNAbcdefZ` | `0 2 5 24 23 41` | |
| `paddr` floor 1048576 -> 1024 | `KHSCNAbc_efZ` | `0 2 5 **42** 23 41` | `d` alone goes. The segment now passes clause 4 and is caught two rules later, by the entry-in-segment check |
| ELF magic constant off by one | `KHSCN_b____Z` | `2 2 2 2 2 2` | `A` goes with `c d e f`: everything is refused at the first clause, so nothing downstream is measured any more |
| `put-hex64` divides by 8 | `KHSCNAbcdefZ` | `0 2 5 24 23 41` | every marker holds and `entry` prints `0000000000000040`. The console writer and the admission verdicts fail independently |

## Consequences

- **This does not replace the K16 loader and the gate still refuses.** The K16
  profile also needs the model read, the embedded-release path and `BootNext`.
  `uefi/main.c` is unchanged and every byte of it still runs.
- **`integrity` is landed as source and has NEVER RETURNED ON A CPU** (2026-09-03,
  after BOOT-SCRATCH landed `kernel-scratch-region`). It compiles, the scratch
  region works, and `sha-block` traps with `#UD` inside a UEFI image while the
  same `aiueos.lib.sha256-stream` runs correctly as a kernel object. Bisected
  in the guest: scratch write/read back, a 64-byte `kernel-subregion` of a
  `bytes-literal` read through the library's own window-64 accessor,
  `store32`/`load32`, and `sha-init` all pass; `sha-block` does not. A separate
  probe stored and read back offsets 0, 255, 256, 300, 360, 424, 455 and 511 of
  the scratch state and exited 33, so the whole 512-byte window is sound.

  **The blocker is fuel, and `--fuel` is inert on this route.**
  `sha256-region.kotoba` measures 1,772 fuel per 64-byte block; a UEFI image
  runs on `native-fuel!`'s default of **512** (amu
  `src/kotoba/compiler/nbb/cli.cljs:89`). The flag is read and validated —
  250,000,000 is refused as `native fuel budget is not admitted`, 1,048,576 is
  accepted — and then does not reach the image:

  | `--fuel` | artifact sha256 |
  |---|---|
  | 512 | `714a7509d057b654cb8ae4181284250ce82514626d50e7d25f624cc979872f29` |
  | 1048576 | `714a7509d057b654cb8ae4181284250ce82514626d50e7d25f624cc979872f29` |

  **Byte-identical across a 2048x difference in the declared budget.** A
  200-iteration arithmetic loop completes and a 2,000-iteration one traps,
  identically, under both. A knob that is validated and then discarded looks
  exactly like a knob that works — the failure ADR-2608136000 is about. The
  module is deliberately NOT wired into `loader-probe.kotoba`, so the probe
  stays green on what it can actually demonstrate; wiring it in is two lines
  once the image installs the declared budget.

- **Three of the seven planned modules are BLOCKED, not deferred.** `memory`
  (`AllocatePages`), `fs` (`HandleProtocol`, `OpenVolume`, `Read`) and `exit`
  (`GetMemoryMap`) can now ALLOCATE and INSPECT — BOOT-SCRATCH's
  `kernel-scratch-region` gives a firmware call somewhere to put an
  out-pointer — but cannot PLACE a kernel image, because the page address an
  `AllocatePages` out-pointer yields arrives from a load and the region
  provenance rule refuses a base it cannot trace. FIRMWARE-STORE owns that
  primitive and is writing `uefi/memory.kotoba` as its first consumer, so this
  stream did not duplicate it.
- **`kernel-jump-to` is still unexecuted.** The loader can now compute a
  kernel's entry point and print it. It cannot go there, because it cannot load
  the kernel first.
- kotoba-sema ADR-0026 was needed on the way: the three address-producing rodata
  heads were not region roots, so an image could obtain the address of bytes it
  had emitted itself and then not read them with a checked load.
- The amu that compiles this is NOT on amu main. It is amu `a8e30d5b` with the
  kotoba-sema pin advanced to `e7e13bad`.
