# ADR 0007: Barriers, the timestamp counter and the general atomic family

## Status

Accepted.

## Context

A NIC driver written in Kotoba needs three things this contract could not
express. It needs to say that a descriptor was written before a doorbell was
rung. It needs to read a clock fine enough to time a DMA completion. And it
needs read-modify-writes on words a device also touches -- a producer index it
advances by its own delta, an ownership word it swaps for its own value, a
doorbell it claims against its own comparand.

GMIR had one atomic operation, the try-lock pair, and its comparand and
replacement are fixed BY THE OPERATION (0 -> 1 to acquire, 1 -> 0 to release).
That is the right shape for a mutex and the wrong shape for a ring: the guest
never gets to supply the word.

## Decision

Two additions, on two different channels, because they are two different kinds
of thing.

**Barriers, the timestamp counter and `swapgs` join the closed x86 privileged
action family**: `:fence-load` (0), `:fence-store` (0), `:fence-full` (0),
`:rdtsc` (0), `:rdtscp` (0), `:swapgs` (0). They take no operands and touch no
guest-declared memory window, so they need no new instruction shape -- only an
entry in `x86-privileged-action-arities`, which `kotoba.mir` already reads.

That channel is admitted for the x86-64 target and no other, so these six are
x86-only by construction. For the control registers and port I/O already in
that family, x86-only is a statement about the machine. For the barriers it is
weaker and must be said plainly: **AArch64 has `dmb ishld` / `dmb ishst` /
`dmb ish`, and we are not emitting them here.** A portable barrier operator is
possible, but it would have to name the ordering it guarantees rather than the
instruction it emits, because `lfence` under x86-TSO and `dmb ishld` under a
weak model do not answer the same question. That is a separate decision with
its own operator family. `rdtsc` is the same case for a different reason:
AArch64's `mrs cntvct_el0` is a fixed-frequency system counter, not a core
cycle counter -- a different clock, not a translation.

**The general atomics get six new instructions**, sharing the store's shape:

    :gmir/kernel-atomic-add-u32   base length index stored     maximum -> dst
    :gmir/kernel-atomic-add-u64   base length index stored     maximum -> dst
    :gmir/kernel-xchg-u32         base length index stored     maximum -> dst
    :gmir/kernel-xchg-u64         base length index stored     maximum -> dst
    :gmir/kernel-cmpxchg-u32      base length index expected stored maximum -> dst
    :gmir/kernel-cmpxchg-u64      base length index expected stored maximum -> dst

`:gmir/stored` is the guest's operand in every case -- the addend, or the
replacement. `:gmir/expected` exists only on the two compare-exchanges and is
the comparand the lock pair deliberately withholds.

`:gmir/dst` is the word that was in memory BEFORE the operation, for all six.
A compare-exchange that returned only a success flag would force the caller to
re-read on failure, which is exactly the race the instruction exists to close.

`:gmir/maximum` is pinned to 4096 and nothing else, the way the lock pair's is,
so a second spelling has to be added deliberately rather than by widening a
set.

## Evidence

`kbb -M:test`: 16 tests, 171 assertions, 0 failures (measured on this
change).

Both new tests were shown to discriminate before landing:

- deleting the atomic ceiling check produced 24 failures, all at the ceiling
  assertion (4 rejected maxima x 6 operations) and nowhere else;
- deleting `:fence-load` from the arity table produced exactly one failure at
  the table assertion (`{:fence-load 0 ...}` vs. a map missing that key) and
  one error, `GMIR rejected: invalid-x86-privileged`, from the program that
  uses it.

## Does not decide

The lock pair stays exactly as it is. It is not re-expressed in terms of
`cmpxchg`: its whole value is that the retry stays inside one selection, and
AArch64 has an implementation of it that these six do not yet have.
