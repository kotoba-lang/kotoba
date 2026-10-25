# ADR-0011: A label is not only a branch target

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added `:gmir/function-address`, whose answer is the
runtime address of a function in the same module. The backend reaches it with
`lea dst,[rip+disp32]`, and the displacement is a label position that does not
exist until the first layout pass has run.

## Decision

**`:function-address` joins `selected-keysets` with `:mir/dst` and
`:mir/function`.** It is neither of the two address shapes already here:
`:data-address` names a UTF-8 string the value runtime resolves against a
runtime base, `:rodata-address` names a literal pool entry the backend places,
and this one names a LABEL the module already has -- the same `:mir/function`
a `:call` carries as `:mir/callee`. The keysets are exact, so a
`:rodata-address` that grew a name and a `:function-address` that grew a
content string are both refused; both directions are asserted.

**`:x86-64/lea-rip-label` joins `relative-branch-sizes` and its three sibling
tables**, at width 7, PC bias 7, alignment 1 and the full signed 32-bit range.

It is not a branch, and it belongs here anyway. What this namespace owns is
not branching: it is *an instruction of fixed encoded width whose displacement
is a label position the first pass has not computed yet*, which is exactly what
taking the address of a function is. The alternative is the mechanism the
literal pool uses -- a backend-private token resolved in the backend's own
second pass -- and that one works because a pool entry's offset is computed by
the backend from the token stream. A function's offset is computed by
`label-offsets`, here, and a second resolver would have to be handed the label
table anyway.

**The operand is a register CODE, not a register keyword.** This namespace
names no target registers; the AArch64 branch operands above are codes for the
same reason. The bytes -- REX.W, the mod-00 rm-101 ModRM -- belong to the
backend that holds the register map. The operand check is one register in
0..15, and it is asserted in five directions (absent, two, a keyword, 16, -1).

## Consequences

- **The PC bias is 7 and the trap is 3.** The displacement field starts three
  bytes into the instruction and is measured from the END of it, so a table
  written from where the field sits rather than from where the instruction
  finishes is wrong by four in every program that uses this. Broken to 3, the
  layout suite goes red in both directions (forward and backward), which is
  what that pair of tests is for.
- An unknown label still fails closed through `resolve-tokens`' existing
  check, so a backend cannot emit a `lea` at a name the module does not
  declare. kotoba-gmir refuses that program two layers earlier, and this is
  the floor under it.
