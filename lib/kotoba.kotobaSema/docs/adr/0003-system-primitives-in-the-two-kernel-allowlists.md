# ADR 0003: Where the new kernel operations go, and why the choice matters

## Status

Accepted.

## Decision

Ten operations from kotoba-gmir ADR 0007 join the frontend's two kernel
allowlists, and **which list each joins is the decision**, not bookkeeping.

`kernel-memory-operations` gains the six general atomics:

    (kernel-atomic-add-u32 base length index delta)    -> the old word
    (kernel-xchg-u32       base length index new)      -> the old word
    (kernel-cmpxchg-u32    base length index want new) -> the old word

and the u64 spelling of each. They go here because they take a REGION, and
membership in this map is what subjects an operation's first argument to the
region-provenance rule: a base must name a region (a literal, `kernel-boot-info`,
a parameter, or a checked `kernel-subregion`) and never compute one. Putting
them in the privileged map would have exempted them from that rule silently,
which is why a test asserts the rule for all six rather than trusting the
placement.

`kernel-privileged-operations` gains the four barrier/clock/segment
operations: `kernel-fence-load`, `kernel-fence-store`, `kernel-fence-full`,
`kernel-rdtsc`, `kernel-rdtscp`, `kernel-swapgs`, all zero-arity. They go here
because none of them names a region -- there is no base, length or index to
bound, so the provenance rule has nothing to say about them.

## The lock note above them is not superseded

`kernel-memory-operations` carries a long note arguing that a try-lock, not a
general compare-exchange, is the right primitive. That note recorded a
measurement -- across the five aiueos value-runtime objects, all eleven call
sites were the same binary try-lock at offset zero -- and it was right about
the program it measured.

A NIC's descriptor ring is a different program, and it has exactly the uses
that measurement did not find: a producer index advanced by the guest's own
delta, an ownership word swapped for the guest's own value, a doorbell claimed
against the guest's own comparand. So the general form goes BESIDE the lock
rather than instead of it, and the two costs the note names are paid where it
said they would be -- in the backend, not here.

## Evidence

`kbb -M:test`: 105 tests, 380 assertions, 0 failures.

Two deliberate breaks:

- declaring `kernel-cmpxchg-u32` with arity 4 -> `kernel memory operation
  arity mismatch` on the five-argument call;
- moving all six atomics into `kernel-privileged-operations` -> the
  region-provenance test fails for all six, which is the exemption this
  placement exists to prevent.
