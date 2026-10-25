# The AVX2 availability guard, as bytes

A `kernel-dot-f32` emitter must not execute a single VEX-prefixed instruction
before this sequence has answered yes. This file is the sequence, resolved to
bytes, so the SIMD work can paste it rather than rediscover it.

It is written down separately from ADR 0038 (which owns the VEX encoders)
because the guard is not a VEX instruction and does not go through them: it is
four `cpuid` calls, one `xgetbv`, and integer tests.

## The check, and why it is four questions and not one

`cpuid` leaf 7 EBX bit 5 says the CPU implements AVX2. On its own that is not
enough to run one, and each of the other three questions closes a hole that
`cpuid` alone leaves open.

1. **Leaf 0, EAX >= 7.** `cpuid` with a leaf above the CPU's maximum does not
   fault; it returns the highest leaf's data instead. Reading leaf 7 on a CPU
   whose maximum is 6 therefore returns *some* EBX, and bit 5 of it means
   nothing. Ask leaf 0 first.
2. **Leaf 1, ECX bit 27 (OSXSAVE) and bit 28 (AVX).** Bit 28 is the CPU;
   bit 27 is the *operating system* — it reflects CR4.OSXSAVE, which the kernel
   sets when it is prepared to save and restore extended state. Both must be
   set, and bit 27 must be checked **before** step 3, because `xgetbv` itself
   raises `#UD` when CR4.OSXSAVE is clear. On K16 that is a self-inflicted
   fault in the middle of feature detection.
3. **`xgetbv` with ECX = 0, then XCR0 bits 1 and 2.** Bit 1 is the SSE state
   and bit 2 the AVX (upper YMM) state. The CPU can implement AVX2 and the OS
   can have enabled XSAVE while still declining to save the YMM upper halves;
   YMM registers are then not preserved across a context switch, and a kernel
   that uses them anyway computes wrong answers intermittently and only under
   load. `(eax & 6) == 6`.
4. **Leaf 7 subleaf 0, EBX bit 5.** AVX2 proper. The subleaf matters: leaf 7 is
   subleaf-dependent, and a leaf 7 query with whatever happened to be in ECX is
   a different question.

`vfmadd231ps` is **not** covered by any of the four. FMA is leaf 1 **ECX bit
12**, a separate feature that an AVX2 CPU is not required to have. An emitter
that uses FMA tests bit 12 as well, or falls back to `vmulps` + `vaddps`.

## The RBX problem

`cpuid` writes EAX, EBX, ECX and EDX unconditionally. RBX is callee-saved in
SysV, and nothing else in this backend touches it, so `emit-function`'s
prologue never saves it. `x86_64.cljc`'s `emit-kernel-cpuid` already carries
`push rbx` / `pop rbx` around its single `cpuid` for exactly this reason.

The sequence below saves RBX **once**, around all four `cpuid` calls, rather
than four times. Both exits pop it. It is stack-neutral as a whole, so nothing
downstream needs to account for it — but note that it is one push deep in the
middle, which matters if anything is ever inserted here that calls out (nothing
does, and nothing should).

## The bytes

71 bytes. Assembled and disassembled with LLVM 22.1.7,
`llvm-mc --triple=x86_64-unknown-linux-gnu -filetype=obj` then
`llvm-objdump -d --x86-asm-syntax=intel`. Returns 1 in EAX when AVX2 is usable
and 0 otherwise; EAX is zero-extended because every write here is 32-bit.

```
 offset  bytes                 instruction
   0x00  53                    push rbx
   0x01  31 c0                 xor  eax, eax          ; leaf 0
   0x03  31 c9                 xor  ecx, ecx
   0x05  0f a2                 cpuid                  ; eax = max standard leaf
   0x07  83 f8 07              cmp  eax, 7
   0x0a  72 37                 jb   0x43              ; -> fail
   0x0c  b8 01 00 00 00        mov  eax, 1            ; leaf 1
   0x11  31 c9                 xor  ecx, ecx
   0x13  0f a2                 cpuid
   0x15  81 e1 00 00 00 18     and  ecx, 0x18000000   ; bits 27 | 28
   0x1b  81 f9 00 00 00 18     cmp  ecx, 0x18000000
   0x21  75 20                 jne  0x43              ; -> fail
   0x23  31 c9                 xor  ecx, ecx          ; XCR0
   0x25  0f 01 d0              xgetbv                 ; edx:eax = XCR0
   0x28  83 e0 06              and  eax, 6            ; SSE | YMM state
   0x2b  83 f8 06              cmp  eax, 6
   0x2e  75 13                 jne  0x43              ; -> fail
   0x30  b8 07 00 00 00        mov  eax, 7            ; leaf 7
   0x35  31 c9                 xor  ecx, ecx          ; subleaf 0
   0x37  0f a2                 cpuid
   0x39  89 d8                 mov  eax, ebx          ; bit 5 = AVX2
   0x3b  c1 e8 05              shr  eax, 5
   0x3e  83 e0 01              and  eax, 1
   0x41  5b                    pop  rbx
   0x42  c3                    ret
   0x43  31 c0                 xor  eax, eax          ; fail
   0x45  5b                    pop  rbx
   0x46  c3                    ret
```

As a flat vector, in the shape the canned blobs in `x86_64.cljc` already use:

```clojure
[0x53 0x31 0xc0 0x31 0xc9 0x0f 0xa2 0x83 0xf8 0x07 0x72 0x37 0xb8
 0x01 0x00 0x00 0x00 0x31 0xc9 0x0f 0xa2 0x81 0xe1 0x00 0x00 0x00
 0x18 0x81 0xf9 0x00 0x00 0x00 0x18 0x75 0x20 0x31 0xc9 0x0f 0x01
 0xd0 0x83 0xe0 0x06 0x83 0xf8 0x06 0x75 0x13 0xb8 0x07 0x00 0x00
 0x00 0x31 0xc9 0x0f 0xa2 0x89 0xd8 0xc1 0xe8 0x05 0x83 0xe0 0x01
 0x5b 0xc3 0x31 0xc0 0x5b 0xc3]
```

The two `jb`/`jne` displacements (0x37, 0x20, 0x13) are resolved for **this**
byte sequence and this one only. Inserting or removing an instruction changes
them. If the emitter needs to interleave anything, use
`layout/relative-branch` and a label rather than editing the displacements by
hand — the layout pass exists for this and the canned blobs above only get away
with fixed offsets because they are never edited.

## Preferring the operator over the blob

The `xgetbv` in this blob is also available as a Kotoba operator,
`kernel-xgetbv`, so the guard can be written as a `.kotoba` decision function
over `kernel-cpuid-*` and `kernel-xgetbv` instead of pasted as bytes. That is
the better shape — a decision expressed in Kotoba rather than in a blob is the
whole point of the K16 profile — and this file exists for the case where the
emitter needs the sequence inline, inside a primitive it is already emitting.

Whichever shape is used, `xgetbv` must not be reached with OSXSAVE clear.
Neither the operator nor the blob can enforce that; the ordering above is the
enforcement.

## Setting the bit the guard tests: CR4.OSXSAVE and XCR0

Everything above is the READ side. It answers "may I use YMM", and on a
machine where nobody has enabled the extended state the answer is no.

Measured 2026-09-02, QEMU TCG `-cpu max`, aiueos `dot-f32-probe.kotoba`: leaf 1
ECX bit 28 (AVX) and leaf 7 EBX bit 5 (AVX2) are both **set**, and bit 27
(OSXSAVE) is **clear**. The guard therefore refused the vector arm on a machine
that has AVX2 -- correctly, and with nothing in a pure-Kotoba kernel able to
change the answer. Setting it is what the C kernel's
`prepare_bsp_extended_state()` does.

Three operators close that (kotoba-gmir ADR 0012, kotoba-sema ADR 0008,
kotoba-kir ADR 0239, this repo's ADR 0049):

| operator | arity | instruction | pilot bytes |
|---|---|---|---|
| `(kernel-read-cr4)` | 0 | `mov r10, cr4` | `41 0f 20 e2` |
| `(kernel-write-cr4 v)` | 1 | `mov cr4, r10` | `41 0f 22 e2` |
| `(kernel-xsetbv i v)` | 2 | `xsetbv` | `0f 01 d1` |

The **enable** is a second ordered sequence, and it runs before the guard above:

```clojure
;; 1. does the CPU implement XSAVE at all?  leaf 1 ECX bit 26.
;;    Reaching CR4 bit 18 without this raises #GP.
(if (= (bit-and (kernel-cpuid-ecx 1 0) 67108864) 0)
  0
  (let [;; 2. OSFXSR (9) | OSXMMEXCPT (10) | OSXSAVE (18) = 0x40600.
        ;;    Read-modify-write: CR4 already holds bits the firmware set.
        cr4 (kernel-write-cr4 (bit-or (kernel-read-cr4) 263680))
        ;; 3. only now is xsetbv legal at all -- it raises #UD while
        ;;    CR4.OSXSAVE is clear.  XCR0 bit 0 (x87) is always set and
        ;;    cannot be cleared, so the enable ors in SSE (1) | YMM (2) = 6
        ;;    and the register reads back as 7.  Read-modify-write again.
        xcr0 (kernel-xsetbv 0 (bit-or (kernel-xgetbv 0) 6))]
    1))
```

Three constraints none of these operators can enforce, in the order they bite:

1. **`xsetbv` before CR4.OSXSAVE raises #UD.** Same shape as the `xgetbv`
   ordering above, and the same non-enforcement: it is a property of a
   sequence, and each operator is one instruction.
2. **`xsetbv` with a bad value raises #GP** -- a bit XCR0 does not define, bit
   0 (x87) clear, or bit 2 (YMM) set without bit 1 (SSE). `(kernel-xsetbv 0 6)`
   and `(kernel-xsetbv 0 4)` have the same shape and the second faults. A
   literal check in the frontend would not help: the working spelling passes
   `(bit-or (kernel-xgetbv 0) 6)`, whose value is a property of the machine.
3. **Both writes must be read-modify-write.** CR4 and XCR0 already hold values
   the firmware chose. `(kernel-write-cr4 263680)` compiles, runs, and clears
   every other CR4 bit -- PAE, PGE, SMEP, whatever the loader set -- without
   faulting anywhere near the instruction that did it.

Setting bit 2 (YMM) in XCR0 is a promise: the kernel is asserting that it will
save and restore the upper halves of the YMM registers across a context switch.
A kernel that sets the bit and does not keep the promise does not fault. It
computes wrong answers intermittently and only under load, which is the same
failure the guard exists to prevent -- moved one layer down.

## What has not been verified

**Nothing here has been executed.** These bytes were assembled and
disassembled; that establishes that they are the instructions named, not that
the guard answers correctly on any CPU. This workstation is an Apple M4 and
Rosetta exposes no AVX, so the guard cannot even be given a machine to answer
about. Execution belongs to QEMU TCG `-cpu max` or to K16 on real hardware.
Until one of those has run, do not cite this file for anything except the
encodings.
