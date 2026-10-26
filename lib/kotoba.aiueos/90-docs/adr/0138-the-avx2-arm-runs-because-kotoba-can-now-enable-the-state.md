# ADR 0138 — The AVX2 arm runs, because Kotoba can now enable the state

Status: accepted (2026-09-02)

## Context

ADR 0144 executed `kernel-dot-f32` under QEMU TCG on two CPU models and could
not finish the experiment. Both models printed `4B800004`, the answer
`kotoba.kir` gives, and **both took the scalar arm**:

```
-cpu max: exit=33 console="F4B800004DOT"      (before this change: one nibble)
  max: features=6 ["avx" "avx2"] arm=scalar
```

`-cpu max` reports AVX and AVX2 in CPUID and `CR4.OSXSAVE` **clear**. The guard
therefore refused the vector arm on a machine that has it — correctly. XCR0 says
whether the operating system has agreed to save and restore the YMM register
state across a context switch; a kernel that reads only `cpuid` and uses YMM
anyway does not fault, it computes wrong answers intermittently and only under
load.

Nothing in a pure-Kotoba kernel could set the bit. `kernel-write-cr0` existed,
CR4 did not, and there was no `kernel-xsetbv` anywhere in the surface. What sets
it today is C: `prepare_bsp_extended_state()` in `kernel/qwen35_infer.c`. So
the script exited **2** — not a pass and not a failure, because the AVX2 arm had
not run and nothing measured said anything about it.

## Decision

Three operators landed upstream (kotoba-gmir ADR 0012, kotoba-sema ADR 0008,
kotoba-kir ADR 0239, kotoba-native ADR 0049, kotoba-verifier ADR 0026), and the
probe uses them:

```clojure
(defn enable-extended-state []
  (if (= (bit-and (kernel-cpuid-ecx 1 0) 67108864) 0)
    0
    (let [cr4 (kernel-write-cr4 (bit-or (kernel-read-cr4) 263680))]
      (let [xcr0 (kernel-xsetbv 0 (bit-or (kernel-xgetbv 0) 6))]
        1))))
```

Three ordered steps, each of which faults if taken out of order: `cpuid` leaf 1
ECX bit 26 (XSAVE) must be set before CR4.OSXSAVE, or `mov cr4` raises `#GP`;
CR4.OSXSAVE must be set before `xsetbv`, or it raises `#UD`; and both writes are
read-modify-write, because CR4 already holds bits the UEFI loader set and XCR0
holds whatever the firmware left.

The console gains a second nibble, `<enable><features><eight digits>DOT`. The
feature nibble alone cannot separate "the enable ran and the machine still
reports nothing" from "the machine has no XSAVE, so the enable was skipped" —
on a CPU with neither they print the same digit.

## The measurement

```
-cpu max: exit=33 console="1F4B800004DOT"
-cpu qemu64: exit=33 console="004B800004DOT"
  max: enable=1 features=15 ["osxsave" "avx" "avx2" "xcr0-ymm"] arm=avx2 digits=4B800004
  qemu64: enable=0 features=0 [] arm=scalar digits=4B800004
AIUEOS_DOT_F32_QEMU digits=4B800004 arms-exercised=avx2,scalar models=max,qemu64
AIUEOS_DOT_F32_QEMU_OK both-arms-executed and-agree-with-kotoba-kir exit=33
```

`4B800004` is `(s0+s1)+(s2+s3)` over four lanes taking the lower half of each
eight-element block before the upper, then a four-element scalar tail. A
straight left-to-right sum answers `4B800000` — every 1 lost into the gap above
2^24 — so the constant does not merely say "a dot product happened", it says
**which one**. The two arms are now two different instruction sequences on two
different machines, and they agree bit for bit with each other and with the
reference interpreter.

`enable=0` on `-cpu qemu64` is not a failure: that model is a plain x86-64 with
SSE2 and no XSAVE, which is exactly what the control run needs it to be. The
script now also asserts the two agree — `enable=1` with OSXSAVE clear would mean
the CR4 write did not take, and `enable=0` with OSXSAVE set would mean something
other than this probe set it.

## Shown to discriminate, twice

**Neutering the enable** (`enable-extended-state` returns 0 without writing
anything) reproduces ADR 0144's outcome exactly:

```
  max: enable=0 features=6 ["avx" "avx2"] arm=scalar digits=4B800004
AIUEOS_DOT_F32_QEMU_AVX2_ARM_NOT_EXERCISED enable=max:0,qemu64:0 features=max:6,qemu64:0
EXIT=2
```

**Removing the two writes but keeping the reads** — leaving an unguarded
`(kernel-xgetbv 0)` — kills the guest:

```
-cpu max: exit=0 console=""
error: -cpu max exited 0, expected 33
```

No console output at all and no `isa-debug-exit`, which is `xgetbv` raising
`#UD` because CR4.OSXSAVE is clear. That is the ordering hazard every ADR in
this chain describes, observed on a machine rather than asserted in prose. The
shipped probe never reaches it, because `cpu-features` reads XCR0 only when
OSXSAVE is set.

## What this does NOT say

- **The C kernel is unchanged.** `prepare_bsp_extended_state()` is still what
  the K16 image runs; this is a test variant. Flipping the C call site to a
  Kotoba object is a separate change with its own link-list consequences.
- **No AVX2 arm of anything else has run.** This is `kernel-dot-f32` on twelve
  elements. The Qwen path's `dot_avx2` is still C.
- **TCG is not silicon.** QEMU's AVX2 is an emulation of AVX2. Agreement here is
  evidence about the emitted sequences and about the guard; it is not a
  measurement on real hardware.
- **Nothing was measured about performance.** The AVX2 arm ran; how long it took
  was not recorded, and under TCG it would not mean anything if it had been.
