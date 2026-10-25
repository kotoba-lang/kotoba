# ADR 0007: An abort is a tracked control effect, and it lowers to a result

## Status

Accepted (slice 1, 2026-09-02). Contract: kotoba-lang `lang/abort-ability.edn`.

## Decision

`throw` and `try`/`catch` enter this frontend, as the typed abort ability the
authority's `:explicit-errors` entry always said was admissible: an abort
whose effect appears in the inferred row. Three things make it tracked.

1. **`(throw e)` types as bottom** and puts `:abort` on the row of the
   function it escapes from. The function's error type E is the type of
   `e`; every throw in one function must agree on E, refused otherwise with
   both types named.
2. **`(try body (catch [E] binder handler))` removes `:abort`** from what
   `body` contributed. E is the explicit annotation or the one type the
   body can abort with -- its own throws, and the error types of the
   aborting functions it calls with no try between.
3. **Elaboration, after result inference and before any pass that writes
   HIR**, lowers an aborting function to return `[:result T E]`, a throw to
   `result-err-of`, a let whose binding value aborts to a re-raising
   `result-match-of`, and a try to one `result-match-of` over its body. No
   backend sees either head, and nothing unwinds: this is the result
   elaboration this frontend already knew how to lower.

The row member is the bare keyword `:abort`. It does not carry E -- E is
part of the elaborated interface, and a caller that needs it reads the
callee's `:result`. kotoba-hir `ac8e705` admits exactly that keyword.

## What slice 1 refuses, and why each is a refusal rather than a gap

- **A throw inside a loop/doseq/dotimes body, a lazy thunk or a fn literal;
  a throw or try in a function whose row carries a dataspace facet
  operation.** Precondition `:checked-lexical-facet-unwind` is not met: an
  abort leaving such a scope would skip an obligation (`facet-leave!`) and
  the language has no checked unwind that runs it. The refusal cites the
  precondition by name. Measured with the loop guard removed: the program
  was ADMITTED -- the loop helper became an aborting function and the
  caller's try caught it -- which is exactly the silent widening the
  precondition exists to stop.
- **An aborting function at an export boundary.** Its interface is
  `[:result T E]`, which the wire ABI does not carry across an export yet.
  Note that when nothing narrows the export list (no `(:export ...)`, no
  `defn-`), every function is exported, so a bare aborting helper is refused
  too; the fixtures use `defn-`.
- **A call to an aborting function from a scope that neither catches it nor
  aborts with the same E.** A function becomes aborting only through its
  own throws; calls never put `:abort` on a row. This is the strict reading
  of the contract's item 3(b), chosen because it keeps E per function a
  local fact.
- **A throw or aborting call anywhere but tail position or a let binding
  value.** Operand position would need ANF conversion; slice 1 does not do
  it, and says so.

## Why the byte-identity control is in the tests

Every pass this change touches (`if` typing, `let` lowering, effect
inference, the export check, `substitute-constants`, `form-free-symbols`)
also runs on programs that have no throw. A module with neither head takes
literally the path it took before: `infer-abort-error-types` returns
`(infer-absent-results functions)` unchanged and `elaborate-aborts` returns
its input. `abort_ability_test.clj` pins the HIR and KIR SHA-256 of a
program exercising those passes, taken on `c14ca39e` before this change.

## A bug this ADR records because its shape will recur

The elaboration walks sub-forms inside a `binding` of `*abort-error-types*`.
Written with `map`, the walk was a lazy seq realized after the binding had
unwound, where the table read as empty -- so the second of two tries in one
function reported `try body cannot abort` for a callee that plainly did.
Every sub-walk is `mapv`. Anything that reads a dynamic var inside a walk
must force the walk inside the binding.

## Suite

Post-merge: see the PR. Before: 153 tests / 807 assertions; this adds 20
tests / 49 assertions (kotoba-sema) and the hir suite grows by one test.
