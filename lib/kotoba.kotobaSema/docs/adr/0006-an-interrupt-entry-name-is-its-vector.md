# ADR 0006: An interrupt entry name is its vector, and its signature is fixed

## Status

Accepted.

## Decision

Two things enter this frontend.

**`kernel-isr-entry-address`, arity 1.** `(kernel-isr-entry-address vector)`
answers with the address of the toolchain-generated interrupt entry for that
vector -- the three offset fields of an IDT gate descriptor. It joins
`kernel-privileged-operations` and is therefore also a reserved function name.

**An interrupt entry is declared as `aiueos-isr-<vector>` and has one
signature:** four `:i64` parameters -- the vector, the error code, the
interrupted RIP and the interrupted RSP -- and an `:i64` result. A function
whose name starts with `aiueos-isr-` and does not obey this is refused, with a
distinct code for each of the two ways of not obeying it.

## Why the name carries the number

The toolchain-generated entry passes the vector to the body, so it has to know
its own vector. Either the number appears in the name, or a table maps a
mnemonic to it -- and that table would be a second place to keep in sync,
across three repositories, kept equal only by review. A decimal suffix is
derivable in both directions with no table at all.

`aiueos-isr-bp` is therefore **refused**, not ignored. It reads as an entry,
and there is no entry for it, so admitting it would produce a function that
looks installed and is not. So is `aiueos-isr-64`, which is above the
reservation the image packager makes, and `aiueos-isr-03`, which would be a
second spelling of vector 3.

## Why the signature refusal is here and not in the packager

The generated entry is a fixed byte sequence. It loads rdi, rsi, rdx and rcx
out of the frame the CPU built and calls. It cannot ask the body what it
wanted. A two-parameter body reads rdi and rsi and leaves the other two
registers holding a RIP and an RSP it never asked for; a five-parameter body
reads a fifth register that holds whatever the interrupted code left in r8.
Neither produces a diagnostic anywhere -- it is a wrong answer inside an
interrupt handler, which is the worst place in a kernel to have one.

The parameter TYPE matters for the same reason at one remove. Every one of the
four is a machine word lifted straight out of the frame. A `:string` parameter
would have the entry hand a raw frame word to code expecting a validated pair
handle.

The packager checks arity too, and that is not duplication: it checks the
arity of the exported symbol it is about to name, and this checks the shape of
the source before any byte exists. The packager cannot see a `:string`
parameter at all -- an artifact's export record carries an arity and an offset,
and no types.

## Vectors 0..63

The exceptions are 0..31; the rest is room for the remapped legacy PIC
(32..47) and a handful of message-signalled lines, which is what a NIC driver
needs. The limit is a RESERVATION in the image's text segment -- the packager
lays one fixed-size entry per vector -- so widening it costs bytes in every
kernel image that has any entry at all. It is a decision with an ADR rather
than a constant to nudge.

## Evidence

`kbb -M:test`: 141 tests, 781 assertions, 0 failures (after merging kotoba-lang/main).
`kbb --backend sci run-tests.cljk`: 58 tests, 172 assertions, 0 failures.

Two deliberate breaks, each producing the failure it names and no other:

| break | result |
|---|---|
| `kernel-isr-entry-address` removed from `kernel-privileged-operations` | 7 failures; the arity refusals become `operation has no admitted lowering`, which is what the call got before this row |
| the `validate-interrupt-entries!` pass removed from `analyze*` | the signature and name refusals stop happening; the malformed entries analyze |
