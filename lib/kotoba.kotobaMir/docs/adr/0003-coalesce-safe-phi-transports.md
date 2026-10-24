# ADR 0003: Coalesce safe phi transports

## Status

Accepted. This refines ADR 0002 without changing GMIR or virtual MIR.

## Context

ADR 0002 established a correctness-first lowering: every phi owns a dedicated
frame slot, predecessor edges store into it, and the join loads it. That keeps
the allocator single-definition and provides a safe fallback, but it performs
three memory operations and reserves eight frame bytes for an ordinary
two-predecessor scalar phi even when physical registers are available.

Blindly replacing every group of phi transports with sequential moves is not
correct. A join with several phis is a parallel-copy problem: one move can
overwrite a register that a later move still needs. Correctness must not depend
on an unspecified instruction order.

## Decision

After successful no-spill allocation, MIR may coalesce a merge slot only when:

1. the slot has exactly one join load and at least two predecessor stores;
2. every predecessor edge containing that slot transports exactly one phi;
3. the replacement remains within physical MIR.

Each predecessor store becomes a physical `:mir/move` into the register chosen
for the join value. The join load is removed, self-moves are omitted, and the
remaining frame slots are compacted. If an edge transports two or more phis,
all of those transports remain frame-backed until MIR owns a deterministic
parallel-copy scheduler.

When general spilling is required, the phi's destination already owns an
ordinary spill slot. Predecessor edges store directly into that destination
slot and the dedicated merge slot and join copy are omitted. This is safe for
multi-phi joins because distinct SSA destinations own distinct spill slots.

`:mir/move` is a physical-only operation. Virtual MIR containing it fails
closed, and physical MIR still rejects phi.

## Consequences

The common single-phi value-position branch has zero phi frame bytes and no
phi memory traffic. Spill-heavy programs avoid duplicate merge/destination
slots. Multi-phi no-spill joins retain ADR 0002's bounded frame transport, so
the optimization can never weaken correctness.
