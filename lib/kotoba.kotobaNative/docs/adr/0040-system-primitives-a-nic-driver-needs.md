# ADR 0040: The x86-64 system primitives a NIC driver needs, and one AArch64 baseline

## Status

Accepted.

## Decision

Twelve operations reach machine code, in two groups with two different
answers about portability.

**Six general atomics, on BOTH ISAs.** `kernel-atomic-add-u32/u64`,
`kernel-xchg-u32/u64`, `kernel-cmpxchg-u32/u64`. The try-lock pair fixes both
its comparand and its replacement, which is what makes it a lock; these take
the word from the guest, which is what a descriptor ring needs -- a producer
index advanced by the guest's own delta, an ownership word swapped for its own
value, a doorbell claimed against its own comparand.

All six answer with the word memory held BEFORE the operation, which is what
the instruction leaves behind. For the 32-bit spellings that answer needs no
widening on either ISA: a write to a 32-bit register zeroes the upper half.

**Six x86 system operations, on x86-64 only.** `kernel-fence-load/store/full`,
`kernel-rdtsc`, `kernel-rdtscp`, `kernel-swapgs`. They ride the x86 privileged
channel, which `kotoba.mir` admits for one target, and they take no operands
and name no window.

## The AArch64 atomics cost an ISA baseline, and that is the decision

`a64-kernel-lock` is an LDAXR/STLXR pair, and its own comment says why: there
is no CAS below ARMv8.1-LSE. **That pair cannot be generalised here, and the
reason is register count rather than taste.** A general atomic needs the
address, the loaded word, the word to store and the store status live at once,
and this encoder has exactly two scratch registers (x16, x17) because every
other register may hold an allocated value. The lock manages with three only
because its replacement is an immediate it can build in `dst`.

LSE makes each of them one instruction with no loop, no status register and no
monitor to clear -- and therefore no third scratch register.

**Stated plainly: this raises the AArch64 baseline to ARMv8.1-A for a module
that uses these six operations.** FEAT_LSE is architecturally mandatory from
ARMv8.1 (2014) and present on every Apple Silicon part; nothing else in this
backend needs it, and a module that uses none of the six is unchanged. The
alternative is not "the same thing without LSE" -- it is a third scratch
register removed from the allocator's pool for every AArch64 program, to serve
six operations.

## The barriers are x86-only for a weaker reason than the control registers

`isa_parity_test`'s x86-only list is headed "every one names an x86 facility
with no AArch64 counterpart". That is true of `cr3` and port I/O. **It is not
true of the barriers**, and the entry says so rather than letting the heading
absorb them: AArch64 has `dmb ishld` / `dmb ishst` / `dmb ish`. What makes
these x86-only is the channel they ride, plus the fact that a portable barrier
would have to name the ORDERING it guarantees rather than the instruction it
emits -- `lfence` under x86-TSO and `dmb ishld` under a weak memory model do
not answer the same question. `rdtsc` is the same shape for a different
reason: `mrs cntvct_el0` is a fixed-frequency system counter, not a core cycle
counter -- a different clock, not a translation.

## Two things worth naming

The shared bounds preamble's tail check reads the operation's width instead of
the literal 4, on both ISAs. It is still 4 for every operation that had it.

`rdtscp` discards the processor id it writes to ECX. An operation answering
with two values would need a second spelling; the caller that wants the id can
have one when someone needs it.

## Evidence

`kbb -M:test`: 248 tests, 2844 assertions, 0 failures.

**Every byte string in the tests came from the system assembler, not from a
hand carry.** `clang -target x86_64-unknown-none` and `clang -target
aarch64-unknown-none -march=armv8.1-a`, bytes read out of the object file:

    lock xadd [r11],r10d  f0 45 0f c1 13    ldaddal w3,w17,[x16]  0xb8e30211
    lock xadd [r11],r10   f0 4d 0f c1 13    ldaddal x3,x17,[x16]  0xf8e30211
    lock cmpxchg [r11],r10d f0 45 0f b1 13  swpal   w3,w17,[x16]  0xb8e38211
    lock cmpxchg [r11],r10  f0 4d 0f b1 13  swpal   x3,x17,[x16]  0xf8e38211
    xchg [r11],r10d          45 87 13       casal   w17,w3,[x16]  0x88f1fe03
    xchg [r11],r10           4d 87 13       casal   x17,x3,[x16]  0xc8f1fe03
    lfence 0f ae e8   sfence 0f ae f8   mfence 0f ae f0
    rdtsc  0f 31      rdtscp 0f 01 f9   swapgs 0f 01 f8

`a64-kernel-lock`'s own comment records what the alternative costs: an earlier
hand-carried STLXR was written as 0x8910fe00, which decodes as nothing at all.

Four deliberate breaks, each producing the failure it names and no other:

| break | result |
|---|---|
| REX.W dropped from the eight-byte forms | 3 failures, all on the u64 byte goldens |
| `pop rax` moved before `mov r10d, eax` in the compare-exchange | the adjacency assertion, on both widths |
| bounds tail restored to the literal 4 | the eight-byte tail test |
| one AArch64 atomic removed from the encoder dispatch | `every-portable-operator-emits-on-both-isas` |

## Not done

Nothing here is executed. This repository does not run compiled programs, so a
green suite is encodings only -- and the assembler agreement above is what
stands in for execution.

## Addendum: a literal comparand was being deleted

Found after landing, by compiling a driver-shaped guest **from source** rather
than from a hand-written KIR program.

`gmir-source-keys` did not list `:gmir/expected`, so `dce-gmir` -- which drops
a `:gmir/constant` whose destination appears in no source position -- deleted
the definition of a **literal** comparand. `(kernel-cmpxchg-u32 base length
index 0 1)`, which is the shape a doorbell claim actually has, went on reading
a vreg nothing defined.

**Nothing upstream catches that.** GMIR's own `validate!` checks that an
operand IS a virtual register, not that anything defines it, and MIR's
`select-target` does not check definition order either. It surfaced as
`MIR rejected: use-before-definition` from the CONSERVATIVE allocator, which
only runs once the scanner has given up -- so the same program under less
register pressure reached an allocator with an undefined operand.

Three more field lists had the same omission and are fixed with it:
`a64-source-registers-mir` (feeds `a64-used-before-definition?`),
the alias-remap key list, and `a64-source-keys` (feeds AArch64 constant
rematerialisation).

**Why the existing tests did not see it:** every assertion in
`machine_ir_test` and in `isa_parity_test` passes the comparand as a
PARAMETER, and a parameter is never dead. The tests were written from the
instruction's shape rather than from a caller's, and a caller supplies
literals. `a-literal-comparand-survives-dead-constant-elimination` now covers
it, and deleting `:gmir/expected` again reproduces
`MIR rejected: use-before-definition` on exactly those cases.
