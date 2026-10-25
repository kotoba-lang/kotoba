# ADR 0066: a dequantized weight never becomes f32 in memory

Status: accepted. Date: 2026-09-02.

## Context

`kernel-dot-f32` (ADR 0043) folds two f32 regions. A transformer's weights are
not f32. In the Qwen3.5 model AIUEOS runs, 866 tensors carry four dominant
encodings — Q8_0, Q4_K, Q6_K and the IQ family — and the f32 ones are a
minority. So using the f32 dot product on a quantized row means materialising
the row somewhere first: four bytes written per weight, read once, discarded.
For a 4096-element row that is 16 KiB of traffic per matvec that exists only
because the operation could not see the codes.

ADR 0043's own closing note said so: *"`kernel-dot-f32` reads two f32 regions.
A transformer's weights are not f32."*

## Decision

One opaque MC instruction per quantization format, built exactly the way
`kernel-dot-f32` is built:

- a `cpuid`/`xgetbv` guard, shared verbatim with the f32 dot product
- an AVX2 arm and a legacy-SSE arm, bit-identical by construction
- the answer is an f32 bit pattern sign-extended in a GPR
- `vzeroupper` before the AVX2 arm returns
- clobbers limited to R10, R11 and the vector file; everything else pushed and
  popped by the sequence
- not in `x86-straight-line-encodings`, not in
  `x86-reciprocal-cache-safe-encodings`
- `x86-only` in `kotoba.mir`, with a pinned reason

**The operand shape is block-scale, not two regions and a count.**

    (kernel-dequant-dot-q8-0 w-base w-length x-base x-length block-count)

A quantized row is a vector of BLOCKS, and the byte stride and the element
stride are different numbers: 34 bytes carry 32 elements in Q8_0, 144 carry
256 in Q4_K, 210 carry 256 in Q6_K. So the count counts blocks, and BOTH spans
are derived from it by that format's own strides and checked against their own
regions. Nothing downstream may assume the two regions have the same length;
they never are.

The block ceiling is `min(65536/block-bytes, 65536/(4*elements))`, derived and
checked BEFORE either product is formed — which is the whole point of having
it, because a block count of 2^60 scaled by 34 wraps to a small number and a
wrapped span passes every length check there is. For all three formats the
f32 side binds, so all three admit exactly 16384 elements, which is what
`kernel-dot-f32` admits.

## The accumulation tree is the contract

`dot_scalar` (`os/aiueos/kernel/qwen35_infer.c:234`): four accumulators, the
lower half of each eight-element group before its upper half, `(s0+s1)+(s2+s3)`
at the end. There is no tail — 32, 256 and 256 are all multiples of eight.

The C has a SECOND tree: `dot_avx2` reduces its four lanes left to right, and
the C picks at run time on `qwen_vector_bits`. This family reproduces the
scalar one and says so, because "matches the C" is not a checkable claim while
the C has two answers.

**No FMA, deliberately.** `y = q*d` then `sum += y*a` is two roundings.
`vfmadd231ps` would fuse the second away and give a MORE accurate answer than
the scalar arm gives, which is the one thing an arm of this pair may not do.

## The half-precision scale is a multiply, not a loop

`fp16_to_f32` in the C has three branches and a normalising loop for
subnormals. The machine does not run that. It computes

    u = (h & 0x7fff) << 13
    bits = sign | (exponent == 31 ? (u & 0x7fffff) | 0x7f800000
                                  : as_bits(as_float(u) * 2^112))

One branch, one binary32 multiply, no loop. Reinterpreting the shifted field as
binary32 lands the right significand at an exponent 112 too low, for normal
halves because the fields line up after a 13-bit shift and for SUBNORMAL ones
because the f32 subnormal it lands on has the same significand at 2^-136 — and
the scaling by 2^112 is exact in both cases. Only exponent 31 needs its own
arm: `0x0F800000` scaled by 2^112 is 2^16, not an infinity.

That substitution is a claim, and it is checked over the WHOLE input space:
`dequant-fp16-agrees-with-the-c` compares the two formulas for all 65536
patterns and prints `SCANNED 65536 DISAGREEMENTS 0`. Sampling would have looked
away from exactly the branches it collapses.

The integer half of the sequence is literally the same bytes in both arms. The
two floating-point instructions differ — `vmulss` against `mulss` — because an
arm that has written a YMM register must not run legacy SSE before
`vzeroupper`. They are the same operation on the same units and compute the
same pattern.

## Register discipline

R10 and R11 hold the two pointers, RBX the block counter, RSI the group
counter, and RAX/RCX/RDX the half-precision temporaries. Five of those are
registers an allocator may own, so all five are pushed — and unlike the f32
dot product, which restores RAX/RCX/RDX immediately after the guard, these
saves must OUTLIVE both arms. The three operand values are therefore pushed on
top of the saves, so they pop off first.

## A row wider than 16384 elements needs two calls, and that is a different tree

The 65536-byte ceiling is `kernel-dot-f32`'s and is shared deliberately, and it
admits 16384 elements for every format here. **The Qwen3.5 FFN dimension is
17408.** So one FFN row cannot be folded by one call.

That is not merely a size limit. Splitting a row into two calls and adding the
two answers is a DIFFERENT accumulation tree from one call over 17408
elements: the second call's four lanes start at +0.0 rather than continuing the
first call's, and the two partial sums are combined by one addition that the
single-call tree does not contain. The answers differ, and the difference is
not a rounding accident -- it is a different reduction.

Whoever folds an FFN row through this family must therefore decide which tree
the model's answer is defined by, and say so where the split is written. Raising
the ceiling is the alternative, and it is a decision about the window
discipline rather than about this operation.

## What is landed and what is not

**Q8_0 is emitted.** Q4_K and Q6_K are declared in `kotoba.gmir`, admitted by
the frontend and the verifier, and IMPLEMENTED IN THE ORACLE — `kotoba.kir`
dequantizes both and is checked element by element against an independent port
of the C. What is missing is the machine code, and it is missing for a reason
that is a property of the formats: a Q4_K block's scale and minimum change
every 32 elements and its nibble half changes with them; a Q6_K block's scale
index changes every 16. Their thirty-two eight-element groups are therefore not
a loop — each takes a different scale field, a different nibble half and a
different bit shift — and the sequence has to be unrolled thirty-two times per
arm. Q8_0's four groups are one loop.

The IQ family -- IQ3_XXS, IQ3_S, IQ4_XS, IQ2_S, 306 of the model's 866 tensors
-- is not declared at all. It decodes through codebook grids that
`qwen35_quant_tables.inc` holds as static const data, and until 2026-09-02 this
dialect had no way to reach such a table from a kernel object. **It has one
now**: BOOT-LITERALS landed a literal pool at the end of `.text` reached by
`lea dst,[rip+disp32]` with no relocation, and measured that a kernel `.o`
carrying one still passes `verify-kotoba-kernel-object.py` with `imports=0
relocations=1`. So the grids are expressible and the IQ formats are the next
increment after the K-quants -- and the highest-value one, since they are the
dominant types. This stream did not attempt them. (Literals are x86-only, which
costs nothing here: so is this whole family.)

`x86-dequant-formats` carries `:emitted?` and the emitter REFUSES the other two
by name, `:dequant-format-not-emitted`. The refusal is asserted by name rather
than as "an exception", because the alternative failure is silent: a `case`
with no arm returns `nil`, and a group body of no bytes is a loop that runs the
right number of times and adds nothing — a working instruction that answers
+0.0 for every row, on every machine, agreeing with itself.

## Evidence

- `test/kotoba/native/dequant_fusion_test.cljk`, 12 tests / 45 assertions. Every
  byte run was read back with
  `llvm-mc --disassemble --triple=x86_64-unknown-linux-gnu --show-encoding`
  (LLVM 22.1.7), not derived from the manual.
- Full suite at this commit: 337 tests / 4671 assertions / 0 failures.
- **Executed in QEMU**, both arms, same artifact:
  `os/aiueos/scripts/smoke-qemu-dequant-dot.cljs` (aiueos, ADR 0165). `-cpu
  max` reports `arm=avx2` and `-cpu qemu64` reports `arm=scalar`, and both
  print `4C800012` — which is what `kotoba.kir` answers for the same bytes,
  and is neither what a left-to-right sum answers (`4C800010`) nor what this
  sequence's own upper-half-first twin answers (`4C800011`).

  **The fixture had to be replaced to make that third number exist.** The
  first one copied `dot-f32-probe`'s `[2^24, 1, 1, ... 1]`, which separates the
  contract from a left-to-right sum and NOT from the twin: with every element
  equal and the accumulator starting at zero, `(0+a)+b` and `(0+b)+a` are the
  same number. Measured 2026-09-02, an emitter with the two `vaddps` swapped
  was built, booted, and printed the expected digits under both CPU models.
  With the replacement fixture the same broken emitter makes `-cpu max` print
  `4C800011` while `-cpu qemu64` prints `4C800012` — the two arms disagree on
  one machine, and the smoke exits 1.
- Break-checked five ways in this repository, each reddening the test named for
  it: dropping `vzeroupper`; the scalar lane assignment as `e div 2`; the
  packed span derived with the element stride; the half-precision constant as
  2^111; the AVX2 arm adding its upper half before its lower. The last of those
  was ALSO carried through to a booted machine, which is the only place the two
  arms can be compared with each other rather than with their own goldens.

One of those five is a finding rather than a demonstration. The lane
assignment `e div 2` initially passed: the test counted how many times each
accumulator was written, and `e div 2` also writes each of the four twice —
the right products in the wrong chains. **The chains are the contract, so the
whole 222-byte group body is now pinned rather than its histogram.**

## What the speed claim is, and is not

The fusion removes an 8:1 instruction ratio in the inner loop. Counted from the
disassembly: eight elements cost 13 instructions vectorised (8 vector
operations plus the 5 that close the loop) and 53 scalar (8 elements of 6 plus
the same 5). That is a static count and it is asserted.

It is NOT a measured speedup. The only machine on this workstation with AVX2 at
all is QEMU TCG — this is an Apple M4 and Rosetta exposes no AVX — and TCG
spends its time translating instructions rather than executing them, so a
256-bit vector operation costs it about what a scalar one costs. Measured
2026-09-02 with `kernel-rdtsc` around a 4096-element fold, after a THROWAWAY
fold that is not timed and with a 256-element fold subtracted to remove the
guard's constant: 88.54 host ticks per element scalar against 56.51
vectorised, a ratio of 1.57. Four runs under changing load gave 1.17, 1.45,
1.55 and 1.57 — the spread is this workstation's load, not the code.
**None of those numbers supports the instruction-count ratio and none is
offered as if it did.** TCG cannot answer this question; silicon can, and this
workspace has none with AVX2.
