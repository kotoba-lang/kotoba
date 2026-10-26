# ADR-0269: Refusing to answer is not the same as having no firmware

- Status: accepted
- Date: 2026-09-03

## Context

kotoba-gmir ADR-0030 adds `kernel-uefi-alloc-region`, which calls the
firmware's `AllocatePages` and answers with the base of the pages it got --
or with **zero** when the firmware declines. This interpreter has no firmware.

## Decision

**It joins `kernel-uefi-operations` and traps with
`:kernel-privileged-unavailable`.**

It refuses for both of that family's reasons at once, which is why it belongs
inside the set rather than beside it. It runs the firmware's own code, exactly
as `kernel-uefi-call2/4/6` run whatever their slot names, and there is no
firmware here to run. And what it answers with is a physical page address:
any number invented for it here is a number the caller then declares a window
over and writes through.

**It does NOT answer zero, and that is the decision worth recording.** Zero is
available in a way no other refusal in this family's answer is: "this machine
has no firmware, so nothing was allocated" is arguable, and the operation's
own failure answer is exactly zero. Offering it would be wrong for a reason
that is easy to miss. Zero is not "no answer" here -- it is the answer for a
*failed allocation*, and a caller cannot tell the two apart. Folding it turns
a program's allocation into a compile-time null and every access through it
into a trap the source never wrote. A compile that stops is not the same
outcome as a program that ships and traps.

That distinction is the same one ADR-0235 drew in the opposite direction for
`bytes-literal-length`, which IS folded because its answer is a property of
the literal text rather than of a machine. The test is not "can a number be
produced" but "is the number produced the one the operation means".

**It marks a module kernel-native**, for the reason every refusing head does.
Every operand at a real call site is a literal or a parameter -- a slot
number, an allocate type, a memory type, a page count -- so the sealed
constant oracle sees an operation over constants with nothing to suggest an
effect. Without the mark it folds the call, the trap above fires, and a
perfectly valid program fails to compile.

## Consequences

- Nothing is added to `only-native-word-typed-features?`. The head takes and
  returns machine words and falls through that walk's `:else`, which admits
  any head not in `non-string-typed-ops`. The admission that matters is amu's
  target gate, and it is amu's because that is the layer that sees a target
  keyword next to a module.
- Nothing is added to `native-floating-point-operations` either, so
  `kotoba.verifier-kir-agreement-test` has nothing new to compare. That check
  is scoped to the float admission lists; the firmware boundary's agreement
  with the verifier is maintained by the verifier's own independent tables and
  is not machine-compared today.
