# ADR-0016: Privileged operands borrow the preserved tier, and a literal is one instruction

- Status: accepted
- Date: 2026-09-02

## Context

Two things arrived from kotoba-gmir ADR-0011.

`:uefi-call6` has eight operands. The conservative expansion sliced privileged
argument registers out of `[r0 r1 r2 r3]` -- the scratch tier, four wide -- so
eight would have thrown out of `subvec` rather than allocating. That vector had
already been widened once, from two to four, when `:uefi-call2` arrived; the
second time is a reason to derive it rather than write it out again.

`:gmir/rodata-address` is a new value-producing instruction with no operands.

## Decision

**`privileged-argument-registers` is the scratch tier followed by the preserved
tier**, derived from the two vars rather than transcribed. Nine wide on x86-64,
twelve on AArch64, against a widest privileged arity of eight.

The order is the decision. The scratch tier comes first so an action narrow
enough to stay inside it -- every kernel port write, every `cpuid` -- still
costs no frame save; `mir/saved-registers` derives the frame's saves from the
emitted stream, so naming a preserved register is what makes the frame save it.
Reversing the halves would allocate just as correctly and would quietly add a
save/restore pair to every kernel that writes a port. The suite asserts the
absence of that pair for `:uefi-call2` rather than only asserting the vector.

The second half is safe for a firmware call for a reason that is about the
OTHER ABI: RBX, RBP, RDI, RSI and R12-R15 are callee-saved under Microsoft x64
as well as under the internal one, so an operand parked in one survives the
call it is an operand to. Operands in the scratch tier do not, which is why the
backend's `:uefi-call*` encoders save and reload RAX/RCX/RDX/R8/R9 around the
`call` themselves.

**`:mir/rodata-address` selects and expands like `:mir/data-address`** -- one
destination, no sources -- and joins the value-producing set so the
call-frame policy backs it. Two things it does NOT share with that operation:

- **It is x86-only, and this layer says so.** `lea dst,[rip+disp32]` has no
  AArch64 translation that the layout pass models today; `adrp`+`add` splits
  the address at a 4 KiB page boundary. Refusing at selection with
  `:rodata-address-target-mismatch` is the alternative to selecting an
  `:aarch64/` encoding that does not exist and failing later with
  `:unknown-encoding`, which reads as a compiler bug rather than as the missing
  feature it is. This is an admission of a gap, not a decision about AArch64.
- **Well-formedness is re-derived here**, through `gmir/rodata-content?`, for
  the reason the kernel-memory arities are re-derived: selection copies content
  through untouched, and a hand-built MIR program that never passed
  `gmir/validate!` would otherwise still get a pool entry and an address.

## Consequences

- Adding a privileged action wider than nine operands now fails an assertion
  rather than an index. That assertion compares against
  `gmir/x86-privileged-action-arities`, so it stays true as that table grows.
- `with-scratch-tier-only`, the macro tests use to exhaust the profile,
  redefines `preserved-registers` to empty -- so a test written under it can
  still only allocate four privileged operands. The wide-call tests force the
  conservative path a different way, with a non-prefix `:mir/argument`, and say
  so in a docstring.
