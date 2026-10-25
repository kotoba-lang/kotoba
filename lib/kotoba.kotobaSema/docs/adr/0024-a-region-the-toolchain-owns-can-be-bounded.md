# ADR-0024: A region the toolchain owns can be bounded, and a name is not an expression

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added two operations, and both need something at this
layer that the layers below cannot do: this is where a base is traced to a
root and where a source form is checked against the module it sits in.

## Decision

**`(kernel-scratch-region)` is a provenance root, beside `kernel-boot-info`.**
The rule it joins is that every base flows unmodified from a compile-time
literal, from `kernel-boot-info`, or from a parameter -- never from
arithmetic, a load or a call result. Arithmetic on the region is still
refused, exactly as it is on `kernel-boot-info`; a `kernel-subregion` of it is
admitted, exactly as one of `kernel-boot-info` is.

**And it is a STRONGER root than `kernel-boot-info`, which is what the bound
is for.** `kernel-boot-info` answers with a word the firmware or the loader
handed over: this pass has to trust its extent because nothing here knows it.
The scratch region is a span the toolchain's own packager reserved, so both
its base and its SIZE are facts the compiler holds -- and a fact the compiler
holds is a fact it can refuse to contradict. A window declared over the region
wider than `image-scratch-bytes` is rejected
(`:kotoba.error/kernel-scratch-window`), because no emitted bounds check
catches it: the emitted check compares an index against the length the SOURCE
declared, and here the source is the thing that is wrong.

A NON-LITERAL length over the region is refused for the same reason. An
expression cannot be compared against the ceiling, and admitting it leaves
exactly the hole the check exists to close.

**16384, and the number lives in exactly two places.** Here, and in
`kotoba.compiler.packaging.pe32plus`, which reserves the space; amu's suite
asserts they are equal, because a frontend admitting a wider window than the
packager reserves admits a write past the section. 16 KiB rather than one page
because `package-embedded-kernel` has reserved exactly that for a UEFI memory
map since it was written, and a memory map is the largest thing a boot path
puts in scratch. It is also the largest CHECKED-MEMORY tier (`-16k`), so the
only spelling that can exceed it is the 64k one -- which is what the refusal
is for, and what the suite pins.

**`(kernel-function-address f)` gets its own family, `image-symbol-operations`,
and its argument is never typed.** Its own family rather than a fifth
`rodata-literal-operations` entry: those check that a piece of source text
DECODES under an encoding, and this checks that a name IS A FUNCTION THIS
MODULE DEFINES. Nothing about a GUID's grammar bears on the second.

The interception in `infer-expression-type` is the part worth recording.
`infer-call-type` types every argument BEFORE it looks at the head, and a bare
symbol in argument position is a local reference everywhere else in this
grammar -- so without the interception a correct program is rejected as
"unbound symbol has no value type", naming the callee rather than the
operation. A local that shadows a function is refused explicitly for the same
reason: taking it as a name would silently address a function the author was
not talking about.

## A defect this stream found one line above its own

`traceable-base?` admits a compile-time literal as a root with `(integer?
expr)`. A `.kotoba` integer literal reaches this pass as a `long` on the JVM
and as a **BigInt** under ClojureScript, and `(integer? (js/BigInt 512))` is
false -- so a literal physical base was a provenance root on one runtime and
not on the other, and had been since the rule was written.

It surfaced because the window ceiling asks the same question about the same
kind of literal: four of this stream's POSITIVE cases were green on the JVM
and red under nbb, and the four are all the cases whose length is a literal.
`integer-literal?` is the portable test -- a BigInt equals `(js/BigInt x)` of
itself, a string does not, a symbol throws -- and both clauses now use it. The
cross-runtime assertion is in the suite as its own test, named for the clause
it is about rather than for this stream's operation.

## Consequences

- `kernel-jump-to` finally has a first argument. It has been admitted since
  the UEFI boundary landed and nothing in the language produced the address of
  a Kotoba function; the suite asserts the composition rather than only the
  head.
- Both are admitted TARGET-INDEPENDENTLY here, as `kernel-write-cr3` is. amu
  owns the gate, and it puts them in two different sets for two different
  reasons -- see amu's ADR.
- `kernel-function-address` joins `reserved-function-names`. A function with
  that name would shadow the head silently: the call would become an ordinary
  call with a symbol argument to a function whose parameter is declared i64.
