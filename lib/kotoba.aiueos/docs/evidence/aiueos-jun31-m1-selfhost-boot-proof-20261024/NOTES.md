# JUN-31 M1: a selfhost-seed-route kernel image booted to its own exit 43 (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-m1-selfhost-image-wall-20261024`,
slice-2 of its §4): can the **selfhost seed closure** (not kotoba-native, not
`bin/amu`) express, package and boot a kernel that answers the debug console —
i.e. is M1 ("a window-fitting selfhost-built kernel's boot proof: seg0 ≤ 4 KiB /
seg1 ≤ 77,824 B / file ≤ 114,688 B, T/U pass → kernel-jump-to → the kernel's own
exit 43") reachable at all?

**Yes — measured end to end this tick.** `exit=43`, `debugcon="KHSCNAbcdefPWghvonkrxTUMXZB"`
including the kernel's own `B`, `bootall=4`. Machine output and artifacts:
`loader-smoke.log`, `selfhost-kernel.elf-facts.txt`, `selfhost-kernel.seg0.disasm.txt`,
`artifact-hashes.txt`, `selfhost-kernel.KERNEL.ELF`.

## 1. What the previous tick's two walls required

* **W2 (boot ops)**: `boot-fixture.kotoba`'s `(kernel-out-u8 233 66)` /
  `(kernel-out-u32 244 21)` had no spelling in the seed closure (E2101). Fixed in
  amu `seed/74-x86_64-aiueos-object.kotoba` (commit `228455e7b`, topic branch
  `hermes/jun31-seed-boot-ops-20261024`): the two ops enter the route-local
  xk-lib stub/intrinsic mechanism (the ADR 0373 window-intrinsic pattern),
  `XK-INTR-N 4 -> 6`, emitted as `port -> dx, value -> rax, out dx,al /
  out dx,eax` per kotoba-native's `emit-kernel-out`. The ADR 0373 rooted-base
  rule (`xk-check`) now covers the window intrinsics only — a port write's
  operands are a port and a value.
* **W1 (image route)**: the W1 measurement's E7100 was a **stale fixed-point
  compiler**, not a missing route — the image packager (`xi-build`, two PT_LOADs,
  77,824 B sealed-fuel data, `--artifact image`) is already in the seed closure.
  Rebuilding the closure from the W2 source was sufficient; no packaging code
  was added this tick.

## 2. Kernel build, measured (loaderless)

`F1.elf` — the combined compiler's first rebuild generation under
`scripts/seed/selfhost-bootstrap.py` (root compiling the changed `seed/FULL-MANIFEST`,
arm64 Linux podman VM, python:3.12-alpine, no C compiler, no JVM/Node/Graal) —
compiled `os/aiueos/uefi/boot-fixture.kotoba` (source `018a939c…`, the exact
source the reference exit-43 image `e7ee95b9…` was built from) with
`--target x86_64-aiueos-kernel-v1 --artifact image`:

```
{:ok true, :target :x86_64-aiueos-kernel-v1, :format :elf64-exec, :bytes 110872}
```

`selfhost-kernel.KERNEL.ELF` = 110,872 B, sha256 `d6db84da…`. Same size as the
amu-built reference `e7ee95b9…`; **not byte-identical** (the seed x86 emitter is
its own code generator — seg0 is 622 B vs the reference's 144 B; every other
measured fact matches).

ELF facts (`selfhost-kernel.elf-facts.txt`) — all nine fixture-literal window
clauses of `loader-probe.kotoba:20-31` PASS:

```
e_type=2 e_machine=62 e_entry=0x101000 e_phnum=2
ph[0] flags=5 poff=4096  paddr=0x101000 filesz=memsz=622    (<= 4096)
ph[1] flags=6 poff=32768 paddr=0x108000 filesz=memsz=77824  (== 77,824)
pass phnum==2 / s0off==4096 / s1off==32768 / kentry==s0addr /
     s0 filesz==memsz / s1 filesz==memsz / s0mem<=4096 / s1mem<=77824 /
     klen<=114688 (110,872)
```

Disassembly of seg0 (`selfhost-kernel.seg0.disasm.txt`, capstone x86-64) shows
the W2 emission as machine code: the 77-byte entry shim (`cli; lea rsp…; lgdt;
retfq; …; ltr;` saves the jump's image-handle argument to the context, `call`
main) and in main, after the sealed-fuel decrement (`[r9+8]`, `ud2` on
exhaustion):

```
0x10106e: movabs rax, 0xe9      ; port 233
0x10107f: movabs rax, 0x42      ; value 66 = 'B'
0x101090: mov rdx, [rbp-0x10]
0x101097: mov rax, [rbp-0x18]
0x10109e: out dx, al            ; kernel-out-u8 233 66
…
0x1010a6: movabs rax, 0xf4      ; port 244
0x1010b7: movabs rax, 0x15      ; value 21
0x1010d6: out dx, eax           ; kernel-out-u32 244 21
```

## 3. Boot proof, measured

`swap-probe.cljk` (the committed smoke, one variable: the staged kernel) with
this selfhost-built KERNEL.ELF, loader BOOTX64.EFI **byte-identical 50,688 B
`bc0696e1…`** to the green boot-jump / swap / run-1 / run-2 loader, same
QEMU/OVMF:

```
exit=43 debugcon="KHSCNAbcdefPWghvonkrxTUMXZB"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
map="0 5520 48" boot="1 1 0 110872 110872 1052672 1081344 1052672 1081344"
```

* `bootall=4` → `kernel-jump-to kentry image-handle` executed; T/U marks
  (`tfacts=1 uflags=1`) bound this image's own facts; M (usable map), X
  (ExitBootServices EFI_SUCCESS), Z (system table survived) all present.
* `B` (port 0xE9) is the **kernel's own entry** answering — the first measured
  kernel-side console answer from an image the selfhost route emitted.
* `exit=43` = the kernel's `out 0xf4, 21` → `(21 << 1) | 1` — the kernel took
  the machine and ended the run itself, never the loader's fallback 33.
* Placement ran on the image's own facts: `kgot == klen == 110,872`,
  `c0 == s0 == 0x101000`, `c1 == s1 == 0x108000`.

M1 is met by byte measurement. "No emitted object has run in a kernel" is
closed for the **image** route (the object route's `kernel-probe-abi.o` body was
already byte-proven inside a kernel artifact earlier; this is the first
selfhost-emitted image that booted).

## Boundary (say this, do not round it up)

* The compiler that emitted the kernel is **F1**, the fixed point chain's first
  generation (`F1.elf` sha256 `86da3c52…`). The tick's fixed-point rebuild
  (S1=S2=S3, root re-pin) runs separately in amu; M1 is claimed on F1's
  measurement, and the fixed-point numbers land with the amu evidence.
* The **loader** (`BOOTX64.EFI`, `loader-probe.kotoba`) is amu-built and is the
  measurement harness, not a selfhost artifact; the smoke itself is driven by
  kbb + Python/QEMU orchestration. The kernel build path (the artifact under
  test) is C-free and loaderless.
* M2 (desktop/GOP input response) is untouched: it still needs the D1 window
  attribution and D3 handoff owner decisions (ADR-0180/0131), and the
  C-free whole-build gate (JUN-64) remains open (25 `zig cc` calls in the
  object-route build measured earlier).
* JUN-31's acceptance criteria overall remain **NOT MET**; this is the M1
  milestone inside them, not the acceptance itself.
