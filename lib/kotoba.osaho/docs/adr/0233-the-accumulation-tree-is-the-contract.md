# ADR 0233 — The accumulation tree is the contract

Status: accepted (2026-09-02)

## Context

kotoba-gmir ADR 0010 declares `kernel-dot-f32`: fold `count` products of two
f32 regions into one binary32 value. The interpreter here has to answer it,
because it is the oracle every backend is checked against.

Answering "the dot product" is not enough. Floating-point addition is not
associative, so `a · b` is not one number — it is one number per order of
summation. An emitter whose AVX2 arm and scalar arm sum in different orders
produces two different answers on two machines from one source, and the
difference appears only on the inputs where a rounding falls differently. The
oracle has to name the order, or it cannot tell those two emitters apart.

## Decision

The tree, written here because this is the definition:

```
four lane accumulators, all +0.0
while eight or more elements remain:
    lane k += a[i+k] * b[i+k]        for k = 0..3   (the "lower" half)
    lane k += a[i+4+k] * b[i+4+k]    for k = 0..3   (the "upper" half)
    i += 8
sum = (lane0 + lane1) + (lane2 + lane3)
for each remaining element: sum += a[i] * b[i]
```

Three choices in it are decisions.

**Eight at a time with four lanes, not four at a time.** That is the order a
256-bit register forces: eight products, then two 128-bit lane-wise adds. A
scalar sequence can imitate a vector; a vector cannot imitate an arbitrary
scalar order. Fixing the vector's order is what lets both arms of an emitter be
bit-identical *by construction* rather than by measurement.

**Lower before upper.** Same reason. It is also the subtlest part of the tree,
because it is invisible below sixteen elements: with one block a lane has
exactly two addends, and `(0+x)+y` equals `(0+y)+x` since IEEE addition is
commutative. A test that pins it needs two blocks.

**`(lane0 + lane1) + (lane2 + lane3)`, not a left-to-right chain.** The
reference `dot_scalar` and `dot_avx2` in aiueos `os/aiueos/kernel/qwen35_infer.c`
use *different* trees from each other — four at a time with the pairwise
reduction, versus eight at a time with a `volatile`-forced left-to-right chain
— so one had to be chosen. This is the vector one's loop with the scalar one's
reduction, and the second half is not arbitrary: `(s0+s1)+(s2+s3)` is two
`haddps` on 128 bits, an instruction the AVX arm already has, while a
left-to-right chain needs three lane extractions.

## The checks

Seven, in the emitter's order, all unsigned: each length within 65536; neither
base null; the count within `65536/4`; then `count * 4` within each length.

The element limit is checked **before** `count * 4` is formed, and that
ordering is the point of it: a count of 2^62 scaled by four wraps to zero, and
a wrapped span passes every length check there is.

## Two boundaries, stated rather than hidden

**NaN payloads.** A NaN result is reported as the canonical quiet NaN, because
`f32-to-i64-bits` collapses every NaN to one pattern on both hosts. x86 does
not: an invalid operation yields the "real indefinite" QNaN with the sign bit
*set*, and a propagated NaN keeps its source payload. Oracle and machine agree
that a NaN result is a NaN and do not agree on its payload. Any receipt built
on this has to carry that.

**Double rounding.** On the JVM the operands are `Float` and the arithmetic
promotes to `double` before `as-f32` narrows it back. That is exact for *one*
operation — 2·24+2 ≤ 53, so the double result rounds to the same float the
hardware produces — and it is the same argument the scalar f32 family here
already relies on. It would not hold for a fused multiply-add, which is one of
the reasons ADR 0010 declines to declare one.

## Fuel

One unit per element. The interpreter really does that much work, and a fold
charging one unit total would let a 16384-element dot product run inside the
fuel a single addition is given. A caller who wants a long dot product raises
`:fuel`, the way a caller who wants a long loop already does.

## Consequences

The operation joins `lower`'s `kernel-operations`, so a module containing one
is kernel-native and the constant oracle is never started on it. Every real
call site will pass literals for the lengths, so a folder has every structural
reason to try — and the attempt would trap on the missing image and abort the
compile of a valid program.

It is **not** a member of `kernel-memory-profile`. That map is
`op -> [ceiling width]` for operations that move one element at `base + index`,
and this one names two regions, no index, and a count of elements to fold.

## Verification

`kbb -M:test`: 233 tests / 999 assertions, 0 failures across the whole
suite; `kotoba.kir-kernel-dot-f32-test` is 15 tests / 43 assertions.

Four independent breaks, each shown to turn the right assertion red by name:

| break | what went red |
|---|---|
| reduce the lanes left to right | `one-full-block-uses-four-lanes-lower-then-upper` — "the answer is the contract's tree" |
| take the upper half before the lower | `the-lower-half-is-added-before-the-upper-half` — by that name |
| delete the element-limit check | `the-count-is-bounded-before-it-is-scaled`, all four assertions |
| drop it from `lower`'s `kernel-operations` | `a-literal-dot-product-is-not-constant-folded` errored *inside `lower`*, at the `kernel-memory-unavailable` trap — which is the described failure exactly |

The two tree tests carry their own controls: each asserts that the rejected
tree gives a *different* answer on the same inputs, so the test cannot pass by
being about nothing. That mattered — the first draft's eight-element vector
made `((s0+s1)+s2)+s3` agree with `(s0+s1)+(s2+s3)`, and the control caught its
own vacuity before the test could be landed as a check on nothing.
