# ADR 0044 — A source key omitted from `gmir-source-keys` deletes an operand

Status: accepted (2026-09-02)

## Context

ADR 0043 landed `kernel-dot-f32` with a green suite: 279 tests, 3476
assertions, every byte run cross-checked against `llvm-mc`. The first program
outside that suite that tried to use it did not compile.

```
(kernel-dot-f32 a 48 b 48 12)
  ->  MIR rejected: use-before-definition
```

The shape with all five operands as *parameters* compiled cleanly and was what
every test in ADR 0043 used. The shape a caller with fixed-size regions
actually writes — three of five operands as literals — did not.

## What happened

`dce-gmir` drops a `:gmir/constant` whose `dst` appears in no source position,
and the source positions come from `gmir-source-keys`, a hand-written vector.
`:gmir/second-base`, `:gmir/second-length` and `:gmir/count` were not in it.

So two of the three literal operands lost their definitions and the operation
went on reading the vregs. The third survived — because `:gmir/length` was
already in the list for every other memory operation.

`gmir-source-keys` already carries a comment about this, written by the sysops
stream, about `:gmir/expected`:

> `:gmir/expected` is here because leaving it out DELETED the instruction's
> comparand. … a compare-exchange against a literal … lost the definition of
> its comparand and kept reading the vreg.

The same defect, one stream later, found the same way. That comment also
explains why nothing upstream catches it, and the explanation is unchanged:
GMIR's `validate!` checks that an operand *is* a virtual register, not that
anything defines it, and MIR's `select-target` does not check definition order
either. It surfaces in the conservative allocator's
`validate-ssa-definition-order` — **which only runs when the scanner has
already given up**, so the same program under less register pressure reaches an
allocator with an undefined operand instead of a rejection.

## Decision

The three keys join `gmir-source-keys`, and also the two MIR-level source-key
lists — `a64-source-keys` and `a64-source-registers-mir` — which are named for
AArch64 and are not only read by it: `x86-propagate-copies` counts the uses of
a copied register through `a64-source-registers` before deciding a `mov` is
dead, and a use it cannot see is a `mov` it removes while something still needs
it. That path was not reached by this defect; the key costs nothing and closes
the same class.

## Why the tests did not catch it

Every ADR 0043 test drove the operation with parameters, because that is the
shape the emitter goldens needed — five distinct registers, so the byte runs
are stable. Literals are the shape a *caller* writes, and no test wrote one.

The regression test asserts the GMIR rather than the emitted bytes, for the
reason above: the byte path only fails under enough register pressure to reach
the conservative allocator, so a byte assertion would pass on some programs and
not others for reasons that have nothing to do with the defect.

## What would have found it earlier

Nothing in this repository. The check that found it was compiling a real
`.kotoba` program — `os/aiueos/native/dot-f32-probe.kotoba`, written to run the
operation under QEMU — which is the first thing outside the compiler's own
suite to use the operation at all.

That is the honest lesson and it is worth stating plainly: a green suite here
is encodings, and a table of hand-written key names is not an encoding. The
suite could not have failed on this, because nothing in it asked the question.

## Verification

`kbb -M:test`: 280 tests / 3483 assertions, 0 failures (was 279 / 3476).

Removing the three keys from `gmir-source-keys` again turns
`dot-f32-keeps-the-definitions-of-its-literal-operands` red by name, on
`:gmir/second-length` and `:gmir/count` — and *not* on `:gmir/base`,
`:gmir/length` or `:gmir/second-base`, which is the asymmetry the defect had.
