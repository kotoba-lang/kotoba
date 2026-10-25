# ADR 0027: A loop carries the type its accumulator has

## Status

Accepted (2026-09-03).

## The measurement

Taken at sema `c031dd34` with amu `a8e30d5b`, before the change. The program is
the shortest Clojure-shaped loop over a float that anyone would write:

```clojure
(ns probe.loopf64)
(defn main []
  (f64-to-i64-truncating
    (loop [i 0 acc (f64-from-bits 0)]
      (if (< i 3) (recur (+ i 1) (f64-add acc (f64-from-bits 4607182418800017408))) acc))))
```

| | before | after |
|---|---|---|
| `amu check --jvm-free` | **exit 65**, `:kotoba.error/subset-reject`, `expression type mismatch: expected f64, got i64`, span pointing at the `loop` | exit 0, `{:ok true …}` |
| `amu compile --target wasm32 --jvm-free` | not reached | exit 0, 455-byte module |
| the module run under `WebAssembly.instantiate` | not reached | `main() = 3n` |
| the helper's signature | `__kotoba_loop_1 [:i64 :f64] -> :i64` | `__kotoba_loop_1 [:i64 :f64] -> :f64` |

Read the "before" row twice. The refusal named `f64` — the accumulator's
PARAMETER type was already correct, because `resolve-loop-helper-param-types`
recovers it from the loop's inits. The compiler knew the accumulator was an
f64 and returned an i64 anyway.

## What was actually wrong

`loop`/`recur` desugars to a synthesized recursive helper function
(ADR-2607150000). The helper's parameters are the loop bindings followed by the
captured outer variables; `recur` becomes a self-call. The helper's `:result`
was written at desugar time, where no type information exists, as

```clojure
:result (or *loop-result-type* :i64)
```

with `*loop-result-type*` defaulting to `:i64` and bound by exactly two call
sites in the whole compiler — the T4.5 `map` and `filter` desugarings, to
`:vector-i64`. So a loop's result type was **a constant with two hard-coded
values**. It was not inferred, not checked, and not derived from the loop body.

Every loop over an `f64`, `f32`, `bool`, `string`, `keyword`, record,
`option-i64`, `result-i64`, `bytes` or `vector-f64` accumulator was refused. So
was every `bool`-returning loop, which is most of what a predicate loop is for.

The parameter side of the same helper had already been fixed — that is what
`resolve-loop-helper-param-types` is. The result side had not, and the two
lived nine lines apart.

## The decision

A loop leaves through its non-`recur` tail exits, so **the helper's result is
the type those exits agree on**. Three passes, all in
`kotoba.compiler.frontend`, all running immediately after
`resolve-loop-helper-param-types` and before anything reads a helper signature:

1. **`infer-loop-helper-results`.** For each loop-helper, replace every
   self-call with a marker symbol, walk the body's tail positions (`if`, `do`
   and `let` are tail-transparent; `let` is the only binding form that survives
   desugaring, so threading it is threading all of them), drop tail markers —
   a tail self-call is a `recur`, which leaves the iteration, not the loop —
   and type what remains in the helper's own parameter environment. Iterated to
   a fixed point across the function list, because a nested loop's helper is
   called from the enclosing loop's body and the inner result has to settle
   first.

   Accumulator binding types are unchanged: they still come from the init
   expressions, via the existing call-site fixpoint.

2. **`check-loop-recur-argument-types!`.** Each `recur` argument is checked
   against the type of the binding it rebinds.

3. The desugar's arity guard now does the arithmetic out loud (below).

`*loop-result-type*` now defaults to `nil`, meaning "read it from the exits".
The `map`/`filter` bindings are **kept**, and the measured reason is that they
became a redundancy check rather than the answer: inference derives
`:vector-i64` for both loops on its own (their accumulator is initialised to
`(vector-i64)` and their sole exit is that accumulator), and
`infer-loop-helper-results` now refuses a declared result its exits disagree
with. Removing the bindings would emit identical HIR; keeping them means the
two cannot drift apart silently, at the cost of two lines.

### What is refused, and in whose words

| code | message |
|---|---|
| `:kotoba.error/loop-exit-type` | `loop exits with two different value types: f64 from b and i64 from a` |
| `:kotoba.error/loop-recur-type` | ``recur argument 2 rebinds the loop binding `acc`, which is f64, with an expression of type i64`` |
| `:kotoba.error/loop-parameter-ceiling` | `loop bindings plus captured outer variables exceed this compiler's ABI-supported arity: 4 bindings plus 2 captured outer variables is 6, and the limit is 5; the captured variables are m, n` |
| `:kotoba.error/loop-result-type` | `a loop is lowered to a function and its exits have the type T, which cannot cross a function boundary in this profile` |

The recur message exists because `check-value-types!` would have caught the
same mismatch — as an argument-type error in a call to `__kotoba_loop_3`, a
function the author never wrote, at a parameter index they cannot map back to a
name.

The ceiling message exists for the same reason. `max-parameters` is 5, and a
loop-helper's parameters are the bindings PLUS every outer variable the body
mentions, so **the ceiling on loop bindings is 5 minus the number of captured
variables** — not a constant, and not anything written in the source.
Five bindings and nothing captured is admitted; four bindings and two captures
is refused, and the refusal names the two captures.

The fourth code is a guard, and this ADR does not claim it has fired. No source
was found that reaches it: every accumulator type measured below is one
`validate-value-type!` admits, and a closure accumulator is already an `i64`
handle by the time this pass runs. It is there so that a type which cannot
cross the boundary produces a named refusal rather than a silent `:i64` —
a silent fallback is the defect this ADR removes, and reintroducing it as the
error path would be the same mistake in a smaller font.

### What is not inferred, and is not a refusal either

A loop whose every tail is a `recur` has no exit to read a type from. Nothing
is inferred and nothing is refused: it keeps `:i64` and lowers exactly as it
did. Likewise, when typing a loop's exits throws for a reason of its own — a
body with an independent type error — the result is left alone so
`check-value-types!` reports that error in its own words rather than as an
unreadable consequence of this pass.

## Measured after

Accumulator types that work, each compiled and run through KIR:
`:i64`, `:f64`, `:f32`, `:bool`, `:string`, `:keyword`, `:vector-i64`,
`:vector-f64`, `[:record …]`, `:option-i64`, `:result-i64`; `:bytes` and a
closure handle type-check (`:bytes` has no KIR lowering for `bytes-empty`,
which is unrelated to loops). Three accumulators of three different types in
one loop — `[i 0 acc 0.0 nm "x"]` → `[:i64 :f64 :string]` — work.
`doseq` and `dotimes`, which are loops, are unchanged.

## Byte identity

The output for an unchanged program is unchanged. Six programs — a plain
integer loop, `map`, `filter`, a loop with a captured variable, a nested loop,
and a loop whose body touches a string but whose accumulator is an i64 —
were dumped as full `pr-str` HIR and KIR text before and after, on **both**
runtimes (digested separately: `pr-str` writes a Kotoba integer as `0` on the
JVM and `#object[BigInt 0]` on ClojureScript). All twelve pairs are
byte-identical.

That control caught a real regression in the first version of this change,
which carried its two extra facts — how many of the helper's parameters are
loop bindings, and whether the result was declared — **in the helper's own
function map**. Two extra keys pushed it past the eight-entry array-map
threshold, so it printed its keys in a different order, and every loop-using
module's HIR text moved without one value in it changing. The two facts now
travel in a side table (`*loop-helper-shapes*`, bound once per `analyze`
beside `*loop-counter*`) and the function map is left exactly as it was.
`loop-accumulator-type-test` pins the key order for that reason.

## Verification

| | before | after |
|---|---|---|
| `loop-accumulator-type-test`, JVM | exit 1 — 13 tests, 53 assertions, 8 failures, 26 errors | exit 0 — 13 tests, 53 assertions, 0 failures, 0 errors |
| `loop-accumulator-type-test`, nbb (in `run-tests.cljk`) | exit 1 — 108 tests, 309 assertions, 8 failures, 26 errors | exit 0 — 108 tests, 309 assertions, 0 failures, 0 errors |
| full `kbb -M:test` | — | exit 0 — 267 tests, 1275 assertions, 0 failures |

No existing fixture relied on the `:i64` default. The full suite was run with
the change applied and the new namespace not yet written: exit 0, 254 tests,
1222 assertions, 0 failures — the same 254 the pristine tree has. Adding the
new namespace takes it to 267 / 1275, still 0 failures.

End-to-end through the real CLI: `bin/amu` pins sema by `:git/sha`, so the
compiler was driven with this clone's `src` prepended to the classpath amu's
own launcher computes (`amu/src`, `amu/resources`, and the `deps-lock.edn`
closure), invoking `src/kotoba/compiler/nbb/wasm_cli.cljs` directly. The pinned
sema on the same classpath still refuses the probe with exit 65, which is the
control that says the prepend is what changed the answer.

## Related

- ADR-2607150000 — `loop`/`recur` as a synthesized recursive helper.
- ADR 0007 (four spellings for a literal), and the parameter-inference pass:
  an absent annotation means "no constraint", not `:i64`. This is the same
  decision applied to the one function the author does not write.
