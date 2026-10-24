# ADR 0010 — A dot product is one operation, not a loop over loads

Status: accepted (2026-09-02)

## Context

Every memory operation this contract declares moves one element. The guest
writes the loop; the backend selects one instruction per iteration. That is the
right shape for a device register file, and it is the wrong shape for the one
computation the K16 profile exists to run.

An f32 dot product over two regions is what a transformer's matvec is made of.
On a machine with AVX2 it is eight lanes per iteration; on a machine without it
is scalar SSE. Choosing between those two is not something a guest loop can
express, and it is not something a backend can recover from a guest loop
without recognising loops — which is a different program from this one.

So the choice has to be made where the operation is named. This declares the
operation.

## Decision

`:gmir/kernel-dot-f32`, carrying two regions and one element count:

```clojure
:gmir/kernel-dot-f32 #{:gmir/op :gmir/dst :gmir/base :gmir/length
                       :gmir/second-base :gmir/second-length
                       :gmir/count :gmir/maximum}
```

`:gmir/dst` receives the binary32 bit pattern of the sum, **sign-extended from
bit 31** — the canonical f32 word of ADR-kotoba-floating-point-on-native, so
`f32-from-bits` accepts it without a conversion. A zero-extended result would
be the odd one out in that family, and worse: `f32-from-bits` refuses a word
outside signed-i32 range, so a zero-extended negative pattern would be a value
the machine produces and the oracle rejects.

Four things about the shape are decisions rather than transcription.

**`:gmir/base`/`:gmir/length` stay the FIRST region's names.** They are not
renamed to `:gmir/first-base`. Anything downstream that reads `:gmir/base`
looking for a base still finds one; the second pair is named for its position.

**Lengths count BYTES; `:gmir/count` counts ELEMENTS.** The slice family made
that split for its own reasons (ADR 0285) and this is not that family, but the
split is right here for a plainer one: the lengths describe regions a caller
declared, and callers declare regions in bytes, while the count describes how
many four-byte elements of them to read.

**`:gmir/maximum` is 65536, pinned as a single value.** Both lengths are
bounded by it. It is the largest tier `kernel-window-maxima` already declares,
so it costs the same `cmp r64, imm32` every other ceiling costs; it is pinned
rather than drawn from that set for the reason the lock pair's 4096 is pinned —
one spelling of the operation names one ceiling, and a second has to be added
deliberately.

**`kernel-dot-f32-element-limit` is DERIVED** as `maximum / 4` rather than
written down. It is what keeps `count * 4` from wrapping a 64-bit multiply
before it is compared against a length, and a stale copy of it would be a
silent hole rather than a visible disagreement.

## What is deliberately not here

**No `-fma` spelling.** FMA is `cpuid` leaf 1 ECX bit 12, a separate feature
that an AVX2 CPU is not required to have, and `vfmadd231ps` computes a
different value from `vmulps` followed by `vaddps` — one rounding instead of
two. An operation that answers differently depending on a feature bit is two
operations. If a fused spelling is wanted it is a second entry with its own
accumulation tree, not a flag on this one.

**No f64 twin.** Nothing has asked for one, and the reduction tree an f64
version would use is a separate decision — its lane count differs, so it is not
this operation at another width.

**No ceiling above 65536.** A dot product over a ten-gigabyte weight region is
what the slice carrier (ADR 0285) exists for, and deciding that here would be
answering ADR 0285's question in the wrong place.

## Consequences

`kotoba.mir` renames this into MIR wholesale like every other operation, and
must admit it for the x86-64 target only — the sequence it selects is AVX2 and
SSE, and an AArch64 counterpart would be NEON with a different reduction, which
is a different operation and not a translation of this one.

The operation is not a member of `kernel-window-operations`, `slice-operations`
or `kernel-atomic-ops`, and carries no `:gmir/index`; the tests assert those
absences so it cannot drift into a family whose bounds do not describe it.

Verified: `kbb -M:test`, 22 tests / 256 assertions, 0 failures (was
18/227). Both new gates were shown to discriminate: deleting the ceiling clause
turns the ceiling assertions red by name, and deleting the three new operand
names from the register scan turns exactly the three operand assertions red by
name.
