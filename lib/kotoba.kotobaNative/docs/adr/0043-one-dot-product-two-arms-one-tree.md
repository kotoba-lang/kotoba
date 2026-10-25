# ADR 0043 — One dot product, two arms, one tree

Status: accepted (2026-09-02)

## Context

kotoba-gmir ADR 0010 declares `kernel-dot-f32`; kotoba-kir ADR 0233 fixes its
accumulation tree; kotoba-mir ADR 0015 selects it for x86-64 and gives it the
call-argument tier. This is the sequence.

ADR 0038 landed the VEX encoders and `docs/avx2-guard-sequence.md` landed the
feature check "so the SIMD work can paste it rather than rediscover it". Both
said, in as many words, that they added no encoding and selected nothing. This
is the caller they were landed for.

## Decision

One opaque MC instruction: bounds checks → AVX2 guard → one of two arms →
result. Not a lowering into smaller operations, for the reason ADR 0010 gives:
what this exists to select is a *choice between two instruction sequences made
at run time*, and no composition of one-element operations can express that.

**The two arms are bit-identical by construction.** Each maintains four lane
accumulators — four lanes of one XMM register in the AVX2 arm, four separate
XMM registers in the scalar one — and adds the same products into each in the
same order:

```
while eight or more elements remain:
    lane k += a[i+k]   * b[i+k]      for k = 0..3   (lower half)
    lane k += a[i+4+k] * b[i+4+k]    for k = 0..3   (upper half)
sum = (lane0 + lane1) + (lane2 + lane3)
then a scalar tail for count mod 8
```

Each lane is an *independent* chain of the same additions in the same
sequence, and interleaving between independent chains cannot change a result.
That is the whole argument, and it is why "bit-identical" is a property of the
construction rather than a claim to be measured.

Two encoding facts make it cheap. `XMM1` *is* the lower half of `YMM1`, so the
lower half needs no extraction — only the upper half moves, into `XMM2`. And
`HADDPS x,x` yields `[s0+s1, s2+s3, …]`, so two of them put `(s0+s1)+(s2+s3)`
in lane 0: the pairwise reduction is two instructions where a left-to-right
chain would need three lane extractions. That is why ADR 0233 chose the
pairwise tree, and this is where the choice is paid for.

**No FMA in v1.** `vfmadd231ps` rounds once where `vmulps` + `vaddps` round
twice, so it computes a *different value*, and it is a separate feature bit
(leaf 1 ECX[12]) an AVX2 CPU is not required to have. A third arm would be a
third answer.

## Clobber discipline

R9 is the context register and is untouched. R10, R11 and the whole XMM/YMM
file are scratch, because no allocator in this repository allocates one.
Everything else the sequence writes is pushed and popped by the sequence
itself: RAX, RCX and RDX because `cpuid` writes them unconditionally, and RBX
because `cpuid` writes it **and** it is callee-saved.

That last one is not a courtesy. `kotoba.mir/saved-registers` derives a
function's frame saves from a `tree-seq` over the *instruction maps*, so a
register a byte sequence clobbers without naming is a register nothing saves.

**The operands are rescued to the stack before the guard runs.** They may be
allocated to any of the four registers `cpuid` destroys, and only two scratch
registers exist to hold five values. So the sequence pushes the three it still
needs, runs the guard, and pops them into R10/R11/RBX afterwards. `test` sets
ZF before the pops and POP does not touch the flags, which is what lets the
branch happen after six of them — the property `x86-kernel-lock` already
relies on.

## Three things the shape was forced into

**The guard's failures are "jump over a jump".** The layout pass has `ja`,
`jae`, `jz` and `jmp` at rel32 width and has no `jb` or `jne`. Three extra
bytes each on a sequence that runs once per call, against adding a layout
encoding to another repository — the trade is obvious in this direction.

**The loops are bottom-tested** for the same reason: `jmp check; body: …;
check: cmp reg, k; jae body`, with `cmp reg, 1` + `jae` standing in for "reg is
not zero", unsigned.

**`count * 4` is two doublings, not a shift.** These encoders have `add` and do
not have a shift-by-immediate, and the count is already bounded by the element
ceiling so neither doubling can wrap.

## The element ceiling is checked before the scale

`element-limit` is `maximum / 4`, derived rather than written down, and it is
checked *before* `count * 4` is formed. That ordering is the point of having
it: a count of 2^62 scaled by four wraps to zero, and a wrapped span passes
every length check there is.

## Verification

`kbb -M:test`: 279 tests / 3476 assertions, 0 failures across the whole
suite.

**Every byte run in the goldens was assembled and read back** with
`llvm-mc --disassemble --triple=x86_64-unknown-linux-gnu` (LLVM 22.1.7) — the
prologue and checks, the 71-byte guard, both arms, and the tail — not derived
from the manual and trusted.

Five breaks, each shown to turn the right assertion red by name:

| break | what went red |
|---|---|
| emit a VEX instruction before the guard answers | `dot-f32-executes-no-vex-instruction-before-the-guard-answers` |
| scalar arm reduces left-to-right | "addss xmm0,xmm1 / addss xmm2,xmm3 / addss xmm0,xmm2" |
| scalar arm takes the upper half first | "eight elements into four accumulators, lower half then upper" |
| check the element ceiling after the scale | "a count of 2^62 scaled by four wraps to zero…" |
| drop the sign extension | `dot-f32-sign-extends-its-answer` |

The last one is worth recording, because the first attempt at it **passed**.
The assertion was a bare two-byte `48 63` run, and `movsxd` occurs elsewhere in
a compiled function — and the *break* had also hit the wrong site, because
`(x86-movsxd dst)` appears twice in this file and the first occurrence belongs
to the scalar f32 family. A weak assertion and a misplaced break cancelled into
a green suite. Both were fixed: the assertion is now the whole tail run
(`pop rbx` / `mov dst,r10` / `movsxd dst`), and the break targets this
sequence's own site.

## What is not verified here

**Nothing in this repository has been executed.** A green suite here is
encodings, not behaviour. Whether the guard answers correctly, and whether the
two arms agree on a real machine, belongs to execution under QEMU TCG or to
K16 on real hardware — this workstation is an Apple M4 and Rosetta exposes no
AVX, so there is no machine here to answer about.

## The next stream: fused dequantisation

`kernel-dot-f32` reads two f32 regions. A transformer's weights are not f32 —
they are Q4_K, Q8_0, IQ3_XXS blocks, and the reason to fuse dequantisation into
the dot product is that materialising an f32 copy of a 10 GiB weight region is
the memory traffic the kernel exists to avoid.

What that stream needs, and what this one deliberately does not have:

- **A read-only data section reachable from a kernel object.** IQ3_XXS is a
  *grid* — 256 packed 8-value entries — and it is a constant, not an operand.
  Today a kernel object has exactly one relocation into its own `.data`
  (`verify-kotoba-kernel-object.py`), which is the shape a grid table would
  have to fit or the shape that would have to change first.
- **`vpmovzxbw`, `vpmaddubsw`, `vpmaddwd`, `vcvtdq2ps`, `vpsrlw`, `vpand`** —
  already in `x86-avx-forms` from ADR 0038, and unused until now. They are the
  integer half of a dequantising dot product.
- **A block-scale operand.** Every one of these formats carries a per-block
  f16 or f32 scale beside its packed weights, so the operation's shape is not
  two regions and a count — it is a region, a scale layout, and a block count.
  That is a different operation, not a flag on this one.
- **An oracle for each format.** `kotoba-kir` would need the block decode, and
  it must agree with `qwen35_quant.c` (vendored from llama.cpp @3173a564)
  bit for bit, because the point of the exercise is to reproduce a known model's
  output and not merely to compute something plausible.
