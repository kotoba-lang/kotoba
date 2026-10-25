# ADR 0010: An abort propagates through calls, and an aborting operand is A-normalized

## Status

Accepted (slice 2, 2026-09-02). Contract: kotoba-lang `lang/abort-ability.edn`.
Supersedes two of the four restrictions ADR 0007 landed with; the other two
(the export boundary and the `:checked-lexical-facet-unwind` precondition)
stand.

## Decision

**Propagation is no longer strict.** A call to an aborting function, with no
try body between it and the function boundary, makes the CALLER aborting with
the same E. Slice 1 required the caller to throw the same type itself, which
made E a per-function local fact and made the middle of a call chain
unwritable: `parse` throws, `read` calls `parse`, and `read` had to write a
`throw` it did not mean in order to be allowed to call. Now `read` acquires
`:abort` and the `[:result T E]` interface without writing either.

E is therefore an interprocedural inference, computed to a fixed point
alongside result inference (propagation advances one call edge per round; the
call graph is finite). Everything that can abort one function must agree on
one E, and the three ways to disagree are refused by name:

    own throws disagree     function f throws two different error types: X and Y
    own throw vs a callee   function f throws X but calls aborting function `g`,
                            which aborts with Y
    two callees             function f calls aborting functions with two
                            different error types: X (`g`) and Y (`h`)

The second was found by the fixed point rather than by design: a function that
throws gets its E in round one, when nothing is known about its callees, so
the disagreement is only visible LATER. The pass deliberately does not
short-circuit on a function it has already given an E to. Measured 2026-09-02:
with the short-circuit in place that program was admitted here and refused
much later by elaboration, naming a scope rather than the two functions.

**An aborting operand or test is A-normalized rather than refused.** `(+ 1
(f x))`, `(if (f x) a b)` and `(g (f x) y)` are admitted by hoisting the
aborting sub-expression into a fresh `let` binding, which is the position
slice 1's elaboration already lowered -- one `result-match-of` whose err arm
re-raises. No new lowering was written.

The whole difficulty is EVALUATION ORDER. `(op a b)` evaluates `a` then `b`;
hoisting `b` alone would evaluate it first. So once any argument is hoisted,
every argument to its LEFT that is not trivially pure is hoisted too, in
order; arguments to its right stay where they are. Containment, not shape,
decides triviality, because a vector literal can hold a call (`(vector-at
[(g 1) 2] 0)` is admitted, measured 2026-09-02) while a TYPE, `[:result :i64
:string]`, cannot -- which is what keeps a type out of a `let` binding, where
it would not be a value.

`h` is pure in the test that pins this, so no assertion on a VALUE could catch
a reordering. The emitted shape is pinned instead.

A `throw` reached in an operand position makes the enclosing expression dead:
`(+ (h 1) (throw "s"))` becomes `(let [t (h 1)] (throw "s"))` -- `(h 1)` still
runs, the `+` does not, because it never would have.

The pass runs TWICE, with disjoint name prefixes. Own `throw`s are syntax and
must move BEFORE inference, because `require-expression-type!` refuses a
bottom-typed operand before the fixed point could report anything; which
functions abort is only known after that fixed point, so the calls move
after it.

**The precondition guard grew a second half.** A loop / doseq / dotimes body,
a lazy thunk and a fn literal each become a function of their own, and an
abort leaving one unwinds a context whose obligations nothing checks yet.
`throw` there is refused while it is still syntax. An aborting CALL cannot be:
which functions abort is not known then. Without a second guard, slice 2's
propagation would have admitted exactly what slice 1's guard was written to
stop -- so a synthesized function (no `:source-name`) that would acquire E
from a call is refused, citing the same precondition in the same words. The
words still say "slice 1" on purpose: they name the slice that recorded the
precondition, and the precondition has not moved.

## Consequences

The slice-1 refusal `call to aborting function ... must be inside try or in a
function that aborts with the same error type` is gone. The program it refused
now reaches the export boundary instead, and that is what the conformance
fixture pins -- reaching it THROUGH the propagation is what says the
propagation happened.

Two refusals in the elaboration are now backstops: they fire only where the
normalizer does not descend, a map or set literal holding an aborting call.
They are worded to say that rather than to name a rule this slice lifted.

What is still refused: the export boundary (the wire ABI does not carry
`[:result T E]` across one), the guarded lexical contexts above, and E
disagreement.
