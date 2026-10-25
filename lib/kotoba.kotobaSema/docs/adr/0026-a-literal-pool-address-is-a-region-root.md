# ADR-0026: A literal pool address is a region root

- Status: accepted
- Date: 2026-09-02

## Context

A bounded kernel memory operation takes a base that must *name* a region rather
than compute one. `traceable-base?` admitted four roots: an integer literal,
`kernel-boot-info`, a `kernel-subregion` narrowing, and a symbol resolving to a
parameter or to a let binding of one of those.

amu ADR-0299 added a read-only literal pool at the end of `.text`, reached by
`lea` with no relocation, and three heads that produce an address into it:
`(ucs2 "...")`, `(guid "...")` and `(bytes-literal "...")`. None was a root.

Measured 2026-09-02, building a Kotoba `BOOTX64.EFI` that wanted to admit an
ELF header held in its own literal pool:

```
:kotoba.error/kernel-region-provenance
"kernel memory base must name a region, not compute one"
```

both with the literal directly in a base position and with it flowing through
an argument into a callee's base position -- the second half of the rule, which
exists so a caller cannot hand a callee something the callee could not have
written itself.

So an image could obtain the address of bytes **it had emitted itself** and
then not read them with a checked load, while an integer base -- an address the
compiler has never seen -- was admitted.

## Decision

The three heads in `rodata-literal-encodings` are region roots.

That table is reused rather than a second list written out, so a head added to
the pool cannot silently lack the standing its siblings have, and a head
removed cannot keep it.

`bytes-literal-length` is not admitted. It answers a count, and it is already
correctly absent from `rodata-literal-encodings`; admitting it would turn a
number the compiler happens to know into an address, which is the exact
confusion this rule exists to prevent.

**What this does not change.** The caller still spells the window length, and
the backend still emits the same bounds check. For `bytes-literal` the caller
*can* spell the true length -- `(bytes-literal-length H)` over the same text --
and nothing here forces that pairing, exactly as nothing forces an integer base
to be paired with the right length. What is admitted is the ROOT. A wrong
length over-reads inside this image's own `.text`, which is the same failure an
integer base already had, and strictly less reachable than it.

## Evidence

`test/kotoba/compiler/rodata-literal-test/a-literal-pool-address-is-a-region-root`.

With the two lines reverted, 7 assertions fail: the three heads times
{directly in a base position, through an argument into a callee's} plus the let
binding. With them, 0. Both negative controls -- `bytes-literal-length` as a
base, and a base with no traceable root at all -- assert the *literal* refusal
message and stay green in **both** directions, so the suite is not merely
counting admissions.

JVM `kbb -M:test -n kotoba.compiler.rodata-literal-test`: 7 tests, 53
assertions. nbb `run-tests.cljk`: 102 tests, 309 assertions.

## Consequences

- `kotoba.compiler.rodata-literal-test` is now registered in `run-tests.cljk`.
  It had landed unregistered and had never run on ClojureScript. Registering it
  made one pre-existing case red, which is why registering it was worth doing:
  the surrogate case was spelled as a `\uD83D` escape, and the two routes refuse
  that at **different places and so with different words** -- the JVM reader
  builds the surrogate and `rodata-literal-content?` names it, while the
  ClojureScript source reader refuses the escape outright with `source reader
  rejected input`. Both refuse. The case is now spelled as a real surrogate
  character, which is the same assertion on both routes and still goes red if a
  surrogate is ever admitted.
- This is about READ-ONLY memory. It gives a Kotoba UEFI application no address
  it may WRITE, so `AllocatePages`, `HandleProtocol` and `GetMemoryMap` are as
  far out of reach as they were.
