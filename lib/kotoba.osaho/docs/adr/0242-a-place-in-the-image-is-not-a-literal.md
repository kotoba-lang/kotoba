# ADR-0242: A place in the image is not a literal, and neither is a function name

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added `(kernel-scratch-region)` -- the base of the
writable area an image packager reserves in the image's own `.data` -- and
`(kernel-function-address f)` -- the address the layout pass gave `f`. This
oracle has to say what it does with both.

## Decision

**Both refuse, under one new keyword, `:image-address-unavailable`.** There is
no image here, no packager has reserved anything, and no layout pass has run.

**It is not `:rodata-address-unavailable`, and that is the decision.** ADR-0235
gave the three literal ADDRESS heads their own keyword rather than the
privileged family's, on the grounds that "a privileged operation names an
instruction this machine is not running; a literal address names a place in an
image that does not exist". The second half of that sentence covers these two
as well, so reusing the keyword is the obvious move. It is wrong for a reason
that is about the NAME rather than the category: a caller told
`rodata-address-unavailable` about `(kernel-scratch-region)` has been told that
read-only DATA is unavailable, which is the opposite of what was asked -- the
whole point of the region is that it is writable, and the whole point of a
function's address is that it is code. A refusal that sends a reader to look at
their literals is worse than a coarser one that names nothing.

**`kernel-function-address`'s argument is never evaluated.** It is a function
NAME, and every other argument here is an expression. Evaluating it would
report an unbound symbol for a program that is correct, and the report would
be about a local variable that does not exist rather than about the operation
that was written. The clause traps before touching `args`, which is what the
literal heads' clause does for the same structural reason -- and this is
asserted for a name no binding could resolve, so the test cannot pass by
accident.

**Both mark a module kernel-native.** Without it the constant oracle folds one,
the trap fires, and a program that compiles perfectly well fails to compile.
The observable consequence is that `lower` seals no `:oracle-value`, which is
what the suite asserts -- with a control module naming neither head that IS
folded, so the two nils are the flag and not the absence of an entry.

## A defect this ADR records because ADR-0235 recorded its twin

The control assertion -- a module naming neither head IS folded, so the two
nils above are the flag rather than the absence of an entry -- compared the
sealed oracle against the literal `7`. On the JVM an i64 is a `long` and that
is true; on ClojureScript it is a BigInt and `(= 7 (js/BigInt 7))` is false.
The JVM branch was green. Caught by running the nbb suite, which is exactly
how ADR-0235 found the same asymmetry in `bytes-literal-length`'s answer, one
layer away and in the opposite direction.

## Consequences

- `bytes-literal-length` remains the one head in this area with an answer, for
  ADR-0235's reason. Neither of these two has a comparable half: a region's
  LENGTH is a compile-time constant the source writes at the window it
  declares, and kotoba-sema refuses a window wider than the reservation, so
  there is nothing for this layer to answer.
- Three refusals now exist where there was one:
  `:kernel-privileged-unavailable` (an instruction this machine is not
  running), `:rodata-address-unavailable` (a literal the backend would have
  placed) and `:image-address-unavailable` (a place in the image's own
  layout). Each names a different thing a caller might have got wrong.
