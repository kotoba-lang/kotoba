# ADR-0050: The operand this file cannot see

- Status: accepted
- Date: 2026-09-03

## Context

kotoba-gmir ADR-0030 adds `kernel-uefi-alloc-region`, six operands, which
calls `AllocatePages` and answers with the base of the pages rather than with
a status. This verifier re-derives what native admits independently of the
frontend, and rejects by ABSENCE: a head with no row falls to the terminal
`:else`.

## Decision

**Four rows, in the four places this file already keeps for a firmware head**:
the privileged membership set, the arity table beside it, the kernel-native
set that stops the oracle folding it, and the aiueos-target list.

**The arity is the row worth reading twice, and this operation's arity has the
worst consequence in the table.** Every other entry here is wrong in a way
that can be pictured: a two-argument `kernel-in-u8` consumes something else as
the port, a one-argument `kernel-xsetbv` writes EDX:EAX into whatever XCR the
register happened to name. This one is wrong in a way that cannot be seen from
here at all, because **the operand that matters is the one that is not
there**. The out-pointer `AllocatePages` writes through belongs to the emitted
frame (kotoba-native ADR-0080), so a miscounted operand list does not fail to
compile and does not fault. It shifts every argument by one, hands
`AllocatePages` a page count that was meant to be a memory type -- and
kotoba-sema has already certified a window over the pages on the strength of
the count it read.

**The positive case is asserted first.** This file's failure mode is silence:
`kernel-xgetbv` was landed in four repositories and not this one, fell to the
`:else`, and was found by the first `.kotoba` program that called it. And
ADR-0011's own experience is sharper -- deleting the wide-call arity rows left
the suite green, because `(get table op)` returning nil is rejected for a
different reason. A test that only checks refusals cannot tell "refused for
the right reason" from "refused because nothing is here".

## Consequences

- The suite's three reds are all shown: dropping the membership row (3
  failures, including the positive case), dropping the arity row (1 failure --
  the positive case, and only that), and dropping the kernel-native row (1).
- `kotoba.verifier-kir-agreement-test` compares the two repositories' native
  FLOAT admission lists, so nothing here joins it. The firmware boundary's
  agreement with kotoba-kir is maintained by these independent tables and is
  not machine-compared today.
- Pins advance with the wave: kotoba-kir to d8b0e679, kotoba-gmir to
  d4e040b2, kotoba-native to adeb1b0f. The last one matters beyond this
  repository -- amu resolves one kotoba-native across its own pin and this
  one, so leaving this behind is how a compile route ends up without the
  encoder its verifier just admitted.
