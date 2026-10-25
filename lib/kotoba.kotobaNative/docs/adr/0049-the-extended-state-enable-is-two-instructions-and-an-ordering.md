# ADR 0049: The extended state enable is two instructions and an ordering

## Status

Accepted.

## Decision

Emit three operators on x86-64, on both lowering paths — the machine-IR pilot
(`machine_ir.cljc`'s `x86-privileged`) and the direct emitter (`x86_64.cljc`):

| operator | pilot bytes | direct bytes | instruction |
|---|---|---|---|
| `(kernel-read-cr4)` | `41 0f 20 e2` | `0f 20 e0` | `mov r64, cr4` |
| `(kernel-write-cr4 v)` | `41 0f 22 e2` | `0f 22 e0` | `mov cr4, r64` |
| `(kernel-xsetbv i v)` | `0f 01 d1` | `0f 01 d1` | `xsetbv` |

Reject all three on AArch64, where they join the pinned x86-only list.

## Why

ADR 0041 emitted `kernel-xgetbv` and `docs/avx2-guard-sequence.md` recorded the
ordering it could not enforce: `xgetbv` raises `#UD` unless `CR4.OSXSAVE` is
set. Neither said who sets it, because this backend named CR0 and CR3 and
stopped.

Measured 2026-09-02 under QEMU TCG with `-cpu max`, running aiueos's
`dot-f32-probe.kotoba`: leaf 1 ECX bit 28 (AVX) and leaf 7 EBX bit 5 (AVX2) are
both set, and bit 27 (OSXSAVE) is clear. The guard refused the AVX2 arm on a
machine that has AVX2 — correctly, and with nothing in a pure-Kotoba kernel able
to change the answer. `kernel-dot-f32`, which exists to compare two arms, ran
one of them twice.

## The encodings are not new instructions, they are old ones at a new number

`mov r64, cr` is `0f 20 /r` and `mov cr, r64` is `0f 22 /r`, where the ModRM
`reg` field is the control register number. CR4 is 4, so `reg` = 100 and the
byte differs from CR0's (`reg` = 000) and CR3's (`reg` = 011) in three bits.

That is why the goldens pin CR0 and CR3 beside CR4 rather than CR4 alone. A
ModRM byte off by one names a **different control register** and faults nowhere:
`mov r10, cr0` where `mov r10, cr4` was meant returns a plausible machine word,
and the kernel then writes a value derived from the wrong register back into
CR4.

`xsetbv` is `wrmsr` with a different opcode — index in ECX, value split across
EDX:EAX — so the pilot arm is byte-for-byte `:write-msr` with `0f 30` replaced
by `0f 01 d1`. The test asserts that identity rather than describing it: it
deletes the opcode from each sequence and compares the remainders, and requires
`xsetbv` to be exactly one byte longer.

## Three things no emitter can enforce

1. **`xsetbv` before `CR4.OSXSAVE` raises `#UD`.** Same shape as `xgetbv`'s
   ordering, and unenforceable for the same reason: it is a property of a
   sequence, and each operator is one instruction.
2. **`xsetbv` with a bad value raises `#GP`** — a bit XCR0 does not define, bit
   0 (x87) clear, or bit 2 (YMM) set without bit 1 (SSE). A literal check
   upstream would not help, because the working spelling passes
   `(bit-or (kernel-xgetbv 0) 6)`, whose value is a property of the machine
   (kotoba-kir ADR 0239 declines it for exactly that reason).
3. **Both writes must be read-modify-write.** CR4 and XCR0 already hold values
   the firmware chose. `(kernel-write-cr4 263680)` compiles, runs, and clears
   every other CR4 bit — PAE, PGE, SMEP — without faulting anywhere near the
   instruction that did it.

`docs/avx2-guard-sequence.md` carries all three with the enable sequence
written out.

## Why AArch64 refuses rather than translates

CR4 is an x86 control register and XCR0 is reached by an x86 instruction pair.
AArch64's nearest equivalent — `CPACR_EL1.ZEN` and `ZCR_EL1`, which is how it
answers "may I use SVE" — is a **named** system register reached by `MSR`, with
the register encoded in the instruction rather than passed at run time. There is
no index to pass and no control register to read whole, so an AArch64 operator
would take different arguments. That is a decision for whoever needs one, not a
translation of these.

## Evidence

`kotoba.native.isa-parity-test`, 38 tests / 883 assertions:

- `privileged-x86-operators-are-x86-only-by-design` — all three emit on x86-64
  and are refused by the AArch64 backend;
- `cr4-and-xsetbv-emit-the-published-opcodes-on-both-lowering-paths` — the
  bytes above on the pilot and on the direct emitter, the CR0/CR3 register-number
  pins, the `xsetbv`/`wrmsr` sequence identity, and the absence of an RBX save
  (`xsetbv` writes no general register, so the two bytes `cpuid` needs would have
  nothing to explain them here).

Every sequence was disassembled with
`llvm-mc --disassemble --triple=x86_64-unknown-none --output-asm-variant=1`
(Homebrew LLVM 22.1.7) and read back as the named instructions.

Shown to discriminate, twice, with different failures:

| break | failure |
|---|---|
| `xsetbv` opcode changed to `wrmsr`'s `0f 30` | the pilot golden fails on both paths, and the length assertion fails |
| CR4's ModRM `e2` changed to CR0's `c2` | the `read-cr4` pins fail with `[65 15 32 194]` — the silent case this pin exists for |

Restored, 0 failures. Full suite 319 tests / 4227 assertions.

**Not executed here.** This workstation is an Apple M4 and Rosetta exposes no
AVX. Execution belongs to aiueos under QEMU TCG.
