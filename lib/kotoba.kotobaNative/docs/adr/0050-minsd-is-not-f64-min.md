# ADR 0050: MINSD is not `f64-min`

## Status

Accepted.

## Decision

`f64-min` and `f64-max` on x86-64 no longer emit `MINSD`/`MAXSD` alone. They
emit a fourteen-instruction branchless sequence that agrees with the KIR oracle
and with AArch64's `FMIN`/`FMAX` bit-for-bit, on NaN and on signed zeros. The
AArch64 encodings are unchanged: they were already right.

## The measurement

The definition is the KIR interpreter, which is `Math/min`/`Math/max` on the
JVM and `js/Math.min`/`js/Math.max` on cljs. Both arms were read on 2026-09-02
through `kotoba.kir.value/i64-bits-to-f64` and back, and they agreed on every
row:

| a | b | `f64-min` | `f64-max` |
|---|---|---|---|
| NaN | 3.0 | NaN | NaN |
| 3.0 | NaN | NaN | NaN |
| NaN | NaN | NaN | NaN |
| -0.0 | +0.0 | **-0.0** | **+0.0** |
| +0.0 | -0.0 | **-0.0** | **+0.0** |
| -0.0 | -0.0 | -0.0 | -0.0 |
| 1.0 | 2.0 | 1.0 | 2.0 |

Then the same twelve operand pairs were compiled and **executed** for both
operations on both ISAs through amu's `isa_execution_test` loader — AArch64
natively on an M4, x86-64 under Rosetta 2. Forty-eight observations, twenty-four
per ISA (eighteen NaN/signed-zero rows and six ordered ones). Six wrong, all six
inside x86-64's eighteen:

```
x86  f64-min  (  nan,  3.0) expected=9221120237041090560  got=4613937818241073152
x86  f64-min  ( -0.0,  0.0) expected=-9223372036854775808 got=0
x86  f64-min  (  nan, -2.0) expected=9221120237041090560  got=-4611686018427387904
x86  f64-max  (  nan,  3.0) expected=9221120237041090560  got=4613937818241073152
x86  f64-max  (  0.0, -0.0) expected=0                    got=-9223372036854775808
x86  f64-max  (  nan, -2.0) expected=9221120237041090560  got=-4611686018427387904
```

AArch64 was right on all twenty-four of its observations. This was not a
hypothetical divergence noted in a comment; it was a wrong answer on shipped
code, and the comment that recorded it had been read three times as a reason not
to admit `f32-min`.

## Why one instruction cannot do it

`minsd xmm0, xmm1` computes `(a < b) ? a : b`. Every false comparison returns
the **second** operand — and the two cases where the first operand must win are
exactly the cases where the comparison is false:

- either input NaN (all ordered comparisons are false), and
- `(-0.0, +0.0)`, which compare equal.

`MAXSD` has the mirror image of the same hole.

## The sequence

Two masks name the two situations, and each has a fixup that is a bit
operation on the operands themselves:

```
  a == b (ordered)   the only equal inputs whose bits differ are +0.0 and -0.0,
                     so `a|b` is the min and `a&b` is the max. For equal
                     non-zero inputs the bits are identical and both are the
                     identity, so the mask does not have to exclude them.
  a is NaN           the answer is `a`. When only b is NaN, MINSD/MAXSD already
                     returns b, for the same reason it was wrong above.
```

Hence `result = a-is-NaN ? a : (a == b ? a|b : minsd(a,b))`, straight-line:

```
movapd xmm2, xmm0 · movapd xmm3, xmm0 · cmpeqsd xmm2, xmm1
orpd|andpd xmm3, xmm1 · andpd xmm3, xmm2 · movapd xmm4, xmm0
minsd|maxsd xmm0, xmm1 · andnpd xmm2, xmm0 · orpd xmm3, xmm2
movapd xmm0, xmm4 · cmpunordsd xmm0, xmm0
andpd xmm4, xmm0 · andnpd xmm0, xmm3 · orpd xmm0, xmm4
```

Every byte was assembled with `llvm-mc -arch=x86-64 -show-encoding`, not
derived from the manual. The sequence borrows xmm2/xmm3/xmm4, which is safe on
the same grounds xmm0/xmm1 are: no f64 value is live in the SSE bank across an
operation — each one bounces in from a general register and out again.

## Why branchless rather than a jump over a NaN check

This backend emits one flat byte run per operation; a branch would need
label machinery inside the encoder, and a relative displacement written by hand
is the class of mistake this ADR exists to fix. Fourteen straight-line
instructions cost more than one, and `f64-min`/`f64-max` appear in no kernel
object today. Correctness first; if a hot use appears, the shape to reach for
is a jump, not a shorter wrong answer.

## Why the encoding is written twice

`machine_ir.cljc` owns the production path (`emit-program` routes everything
through `compile-kir-module`); `x86_64.cljc`'s stack emitter is reached only by
tests. Both now emit the same bytes, and
`kotoba.native-test/both-x86-emitters-agree-on-f64-min-max` asserts it — a
repair that lands only on the path nobody runs is the failure mode two emitters
for one ISA invites.

## What this does NOT do

`f32-min`/`f32-max` are still refused at admission. The corrected shape
transfers to binary32 unchanged (`CMPEQSS`/`ORPS`/`ANDPS`/`ANDNPS`/`MINSS`/
`CMPUNORDSS`), so what is missing is an admission through kir, sema, gmir, mir,
codegen, verifier and native — seven repositories — not an encoding. The
comments in `machine_ir.cljc`, `kotoba.kir` and `kotoba.verifier` that gave the
x86 NaN behaviour as the *reason* have been corrected to say so.

## Evidence

- `kbb -M:test -n kotoba.native-test -n kotoba.native.machine-ir-test`:
  143 tests, 1653 assertions, 0 failures (before the new goldens).
- Execution, before: SCANNED 48, MISMATCHES 6 — all six on x86-64, none on
  AArch64, which is 24 observations per ISA.
- Execution, after: SCANNED 48, MISMATCHES 0.
