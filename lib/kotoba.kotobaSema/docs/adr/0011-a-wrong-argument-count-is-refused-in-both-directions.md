# ADR 0011: A wrong argument count is refused in both directions

## Status

Accepted (2026-09-02). Closes the third of the three truncations found on the
same day; the other two are the `let` body (`let-body-test`) and `if`
(`if-parts`, ADR 0007's note).

## The measurement

Taken at `fd68866`, before the change. Each row is what the compiler DID, not
what it was supposed to do.

| case | before | after |
|---|---|---|
| `(defn- two [a b] …)` called `(two 1 2 3)` | **admitted, answered 3** | refused `function call arity mismatch: two takes 2 arguments; got 3` (`:kotoba.error/call-arity`) |
| `(defn two [a b] …)` called `(two 1 2 3)` | **admitted, answered 3** | same |
| `(two 1 2 3 4 5)` | **admitted, answered 3** | refused, `got 5` |
| `(two 1)` | refused `function call arity mismatch` (`:subset-reject`) | refused `function call arity mismatch: two takes 2 arguments; got 1` (`:call-arity`) |
| multi-arity `(defn m ([a] …) ([a b] …))` called `(m 1 2 3)` | refused `no matching multi-arity clause` (`:subset-reject`) | same text, now `:call-arity` + ex-data `{:function m :expected #{1 2} :supplied 3}` |
| the same called `(m)` | refused, same text | same, `:supplied 0` |
| `defdesugar` template at the wrong count (either way) | refused `desugar template call arity does not match its parameters` | same text, now `:call-arity` + ex-data |
| `(string-concat "a")` / `(string-concat "a" "b" "c")` | refused `string operation arity mismatch` | unchanged |
| `(quot 1)` / `(quot 1 2 3)` | refused `invalid arithmetic arity` | unchanged |
| a closure called at the wrong arity, direct or via `invoke` | compiled; **trapped at runtime** with `division-by-zero` | unchanged |
| `if` with 4 or 2 forms | refused `if requires test, then, else; got N arguments` | unchanged |

One row was the defect. A caller who added an argument got a DIFFERENT ANSWER
rather than a refusal, and nothing in the output said a check had not run —
the under-arity direction was guarded, correctly, which is exactly what made
the check read as complete.

## Where it was

`elaborate-named-ability`'s call branch walked arguments with

    (map (fn [argument argument-type] …) args expected-arg-types)

and two-collection `map` stops at the SHORTER collection. A call carrying more
arguments than the callee has parameters came out of that branch SHORTER than
it went in. `validate-expr` then ran its own arity check — which is correct and
always was — against the already-shortened form, and passed it.

Third instance of one shape in one day: a pass rebuilds a form from a
destructuring that cannot express the surplus, and every checker downstream
measures the rebuilt form. `let` dropped every body form but the first; `if`
dropped everything past the third; this dropped every argument past the
callee's arity. In all three the refusal that would have caught it existed and
was reading a form that no longer contained the evidence.

## Decision

**The count is checked where the fact is known, and the walk cannot shorten a
form again.** `elaborate-named-ability` refuses on a mismatch and then walks
arguments BY INDEX (`map-indexed` with `(nth param-types index nil)`) rather
than by zipping two collections, so a future disagreement between `:params`
and `:param-types` cannot silently truncate.

**Both directions produce one sentence**, from one helper, `reject-call-arity!`,
shared with `validate-expr` — which keeps its check, because it sees calls
elaboration does not walk (a call nested in a vector literal, for one). The
sentence names the callee, the arity it takes and the count that was written,
because `arity mismatch` alone does not say which way it points, and the
direction is the whole content of the report when one direction used to be
answered. The code is `:kotoba.error/call-arity`; no existing code fitted —
`:slice-call-arity` is the slice-erasure pass's own version of this check and
would have been misleading.

**Two messages keep their exact text and gain ex-data instead.**
`no matching multi-arity clause` is compared with `=`, not a regex, in
`amu/test/nbb/project.cljs`; `desugar template call arity does not match its
parameters` is compared with `=` in this repo's `defdesugar-test`. Both now
carry `:function`, `:expected` (a set of admitted arities for the multi-arity
case) and `:supplied` in ex-data, and both now carry `:kotoba.error/call-arity`.
Widening either sentence is a coordinated change with its pinning suite, not a
local one.

## The control

Two programs were digested at `fd68866`, BEFORE the refusal existed, over the
two shapes the change touches — a multi-arity module and a module of lambdas,
`invoke` and closure dispatchers — and the digests are asserted in
`call-arity-test`:

    multi-arity     HIR 89ca1c75…ad26   KIR cf2a007f…a9ca   main = 42
    closure/invoke  HIR 5679558d…921e   KIR bd537741…bdcd   main = 14

They did not move — on BOTH runtimes. The digests are per runtime because the
digest is over a rendering and `pr-str` writes a bigint as `42` on the JVM and
`42n` on ClojureScript; both pairs were measured pre-fix, so neither runtime's
half is a place where nothing is checked. The full JVM suite (254 tests, 1222
assertions) and the nbb suite (95 tests, 256 assertions) are green with no
edits to any existing test or fixture: nothing in this repo was relying on the
hole.

Consumers were screened rather than proved. 5,803 `.kotoba` / `.cljk` files
under `orgs/kotoba-lang` were parsed with this repo's own reader and every
call to a same-file `defn` compared against that `defn`'s arities: **0
over-arity candidates**. The screen is approximate — it sees only same-file
definitions and handles typed and destructured parameter vectors crudely,
which is what its 1,058 spurious UNDER-arity hits are (that direction was
already refused before this change, so every one of them is a false positive).
A zero from an over-reporting screen is a reason to expect no breakage, not a
proof of it.

## What stays unrefused, and why

**A closure called at the wrong arity is still admitted by the compiler and
trapped by the machine.** A closure value's arity is not a static fact here:
`invoke` dispatches on a closure id at runtime, so the arity-N dispatcher is
built from the module's arity-N lambdas and ends in a fallback trap for an id
that is not one of them. A call at the wrong arity reaches a dispatcher that
holds no candidate for it and traps. No wrong count ANSWERS — which is the
property this ADR is about — but the trap is spelled `(quot 1 0)`, so the
message names the instrument (`division-by-zero`) and not the mistake. Pinned
as measured in `call-arity-test`; giving it its own trap is a lowering change,
in kir, not a frontend one.

A narrower static check is possible for the sub-case where the callee is a
lexical name bound to a literal `fn` in the same `let` — the arity IS known
there. Not taken: it would refuse one spelling of a defect that the other
spellings still reach at runtime, which is the kind of partial guard that made
this ADR necessary.

**Built-in operations keep their family-level messages.** They were already
refused in both directions before this change. `string operation arity
mismatch` names the FAMILY rather than the operation and gives neither count;
that is a smaller and separate defect (a refusal naming the wrong noun is still
a refusal), spread over roughly thirty reject sites with one message each.
Pinned in `call-arity-test` so a later widening of an operation table cannot
quietly reopen the direction this ADR closed.
