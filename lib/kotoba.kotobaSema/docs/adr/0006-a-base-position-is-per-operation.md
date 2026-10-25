# ADR 0006 — A base position is per-operation, not "argument 0"

Status: accepted (2026-09-02)

## Context

`kernel-memory-operations` is the arity table for the checked-memory surface,
and it does more than arities: `kernel-memory-op?` reads it, so an operation
added there inherits the region-provenance analysis without a line being
written for it. That is the whole reason ADR 0005 widened the table rather than
adding a family beside it.

The inheritance had one thing hard-coded. `kernel-base-uses` walked a kernel
call as

```clojure
(base! (first args) env)
```

which is right for every operation the table has held so far, because every one
of them takes `base length index …`.

kotoba-gmir ADR 0010 adds `kernel-dot-f32`, which takes
`a-base a-length b-base b-length count`. Two regions.

## The defect this closes before it exists

Adding `kernel-dot-f32 5` to the table and stopping there would have admitted
the operation, typed it, reserved its name, and analysed **the first base
only**. The second base — a pointer the C kernel hands in, exactly as
unverifiable as the first — would have flowed past `traceable-base?` entirely.

`(kernel-dot-f32 a 8 (+ b 1) 8 n)` would have compiled.

That is the hole the provenance rule exists to close, reopened for one
operation, and it fails *by compiling* — the quietest possible way for a
pointer check to stop working.

## Decision

`kernel-base-positions` names the base argument positions per operation, with
`[0]` as the default, and `kernel-base-uses` reads it:

```clojure
(def kernel-base-positions '{kernel-dot-f32 [0 2]})
```

Three things about this shape.

**A separate table, not a widening of the arity map.** Arity and base positions
are different facts. Folding them together would make all forty-odd existing
entries restate a fact they share, and the shared default is what makes a new
single-region operation cost nothing.

**Positions, not a reshaped operation.** The alternative was to put both bases
first — `(kernel-dot-f32 a-base b-base a-length b-length count)` — so the
scanner could keep reading a prefix. An operation's argument order should read
the way a caller thinks (a region, then that region's length), not the way a
scanner finds convenient. The scanner is the thing that should bend.

**A short argument list is left alone.** An arity mismatch is `validate-expr`'s
rejection to make; reporting a missing argument as an untraceable base would
name the wrong defect.

## The operation itself

`kernel-dot-f32 5`, typed `:i64` in and `:i64` out like everything else in the
table. The word it answers with *is* an i64 — the binary32 pattern of the sum,
sign-extended from bit 31, which is the canonical f32 word, so
`(f32-from-bits (kernel-dot-f32 …))` is total. It is no more `:f32`-typed than
`kernel-load-u32` is; the float reading of the word is what `f32-from-bits` is
for.

## Verification

`kbb -M:test`: 133 tests / 746 assertions, 0 failures (was 125 / 721).

The fix was shown to discriminate. Reverting `kernel-base-uses` to
`(base! (first args) env)` turns six assertions red across four tests, and
every one of them names the second base:

- `a-computed-base-is-refused-in-either-position` — "second base", and the
  laundered-load row
- `both-bases-are-tainted-as-regions` — "both bases taint their parameters" and
  "both are reported as unverifiable ABI boundaries"
- `literal-bases-are-reported-from-both-positions`
- `a-base-passed-into-a-callee-second-region-is-checked-at-the-caller`

`a-checked-narrowing-is-admitted-in-either-position` is the control: without it
the negative rows would pass for an implementation that refused *everything* in
position 2.
