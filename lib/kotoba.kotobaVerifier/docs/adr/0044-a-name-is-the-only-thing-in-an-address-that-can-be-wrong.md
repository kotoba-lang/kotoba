# ADR-0044: A name is the only thing in a function address that can be wrong

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added `(kernel-scratch-region)` and
`(kernel-function-address f)`. This verifier re-derives every operation's
admission independently of the frontend, so both need rows -- and the two need
different KINDS of row, which is the decision here.

## Decision

**`kernel-scratch-region` joins the privileged head set and the arity table at
0.** The arity row is the whole of what this operation has: a one-argument
spelling would walk an operand nothing reads, so a program that thought it was
passing an offset would silently get the region's BASE and write at the wrong
place inside it. That is the same failure shape ADR-0025 recorded for a
five-operand `kernel-uefi-call4`.

**`kernel-function-address` gets its own clause, and what it verifies is the
NAME.** The argument is not walked -- it is a piece of the source text, not an
expression -- which is exactly why the membership check has to be here. With
the argument unwalked and the name unchecked, nothing in this file stands
between a misspelling and a backend `lea` at a label it would have to invent.
kotoba-gmir refuses the same program, and this file exists to not depend on
that.

Three refusals, not one: the arity (both directions), the shape
(`simple-symbol?`, so a string, an integer and a NAMESPACED symbol are all
refused), and the membership.

**Both join `kernel-native-operations` and the aiueos-target set.** The first
has to agree with `kotoba.kir/lower`'s own, for the reason ADR-0025 gives: when
the two disagree the failure surfaces in neither one's terms -- the compiler
seals no value, this side re-executes the entry, gets the oracle's refusal, and
reports an oracle mismatch it never had. The second is the target gate, and a
`.data` reservation and a function label are places in an image the toolchain
laid out, which only the aiueos native targets have.

## A positive control this suite needed

The privileged clause admits a head and the arity table answers for it, and
those are two edits. A head admitted with no row falls to `(get table op)` →
`nil`, which never equals `(count args)` -- so it is REFUSED, for the wrong
reason, and a suite that asserted only refusals would report the operation as
correctly rejected while it was in fact unusable. `the-arity-table-covers-every-
head-it-admits` asserts the positive direction for three heads including this
one; deleting the new arity row reddens it.

## Consequences

- `kernel-jump-to` can finally be given an address, and the suite asserts the
  composition rather than only the two heads. It has been verified here since
  the UEFI boundary landed with nothing in the language able to produce its
  first argument.
- The SIZE of the reservation is not verified here and cannot be. This layer
  sees a KIR module and no target layout; the ceiling on a window over the
  region is kotoba-sema's (ADR-0024), and the reservation itself is amu's
  packager.
