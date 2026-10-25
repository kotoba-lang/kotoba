# ADR-0032 — Only a tail record is a result

- Status: accepted
- Date: 2026-08-11
- Amends: ADR-0002 (scalar record native boundary)

## Context

`validate-record-reference-results!` was introduced with the scalar record
boundary. A function whose declared result is `[:ref :a]` returns its record
boxed into the pair chain a caller walks, and `[:ref :a]` carries no field list,
so the construction's own name is the only local evidence that the chain has
the promised arity. Checking that is right.

What it checked was not. It walked the **entire body** with `tree-seq` and
required every record type descriptor anywhere inside it to name the declared
result:

```clojure
type (filter aggregate-abi/scalar-record-type? (tree-seq coll? seq body))
```

So a function that builds one record on the way to returning another — the
ordinary shape — was rejected as a boundary violation. The intermediate never
reaches a caller: a binding's value flattens into slots (ADR-0002) and an
operand is consumed in place. Neither is boundary evidence.

The test suite had already written the intended rule down twice. The negative
test is named `a-tail-record-new-must-name-the-declared-result`, and the comment
above it states the positions outright: *"tail position through `if` (both
branches), `let` (the body, never a binding's value) and `do` (the last
subexpression) — the same positions `emit-expr` hands its own `:tail?` down
to."* Nothing asserted the converse, so the gap between the stated rule and the
implemented one went unmeasured.

### What it cost

Measured 2026-08-11 against kotoba-lang/murakumo's 33 shipped
`kotoba/*_core.kotoba` modules, on compiler `fe0d675` and this repository's
`8b1e22c`:

- **27 of 33** on `aarch64-macos`. Six failed, every one on
  `:record-boundary/:result-schema-mismatch`, none on anything else.
- `infer_credits_core`, `infer_plan_core`, `infer_rebalance_core`,
  `infer_schedule_core`, `reconcile_plan_core`, `task_plan_core`.
- Both the JVM compiler and the JDK-free `bin/kotoba` driver failed
  identically, so this was never a driver drift.

`task_plan_core/assign-task-step-2` is the representative case: it returns
`[:ref :task/assign2]` and builds a `:task/score` to pick with.

**This is a regression against a published figure.** compiler ADR-0221 recorded
33/33 on both ISAs, and it is correct as of its own measurement — it pinned
kotoba-native `f35a8ee`, which **predates** `d7de271`, the commit that added
this validation. The check has never been narrowed since. So 33/33 stopped
being true when `d7de271` landed, and nothing re-measured.

## Decision

Validate the record types a body can actually **return**, not the ones it
mentions. `tail-constructed-record-types` follows tail position through `let`
(the body), `do` (the last subexpression) and `if` (both branches), and reports
the type of a tail `record-new`. Everything else contributes nothing.

This only ever widens admission: the tail set is a subset of the old
whole-body set, so no program that was admitted before is rejected now.

`a-non-tail-record-of-another-schema-is-a-local-not-a-boundary` states the
converse of the existing negative test on both ISAs, so the two rules are now
pinned against each other rather than one being inferred from the other's
absence.

## Consequences

murakumo returns to 33/33 on both native ISAs, and the figure is again
reproducible from pins rather than from a closure that predates the check.

A tail `record-get` that projects a nested record field is still not validated
against the declared result — it was not validated before either, since the
whole-body scan compared the projection's *subject* type, not the field's. That
is a separate gap and is left named rather than silently folded into this one.
