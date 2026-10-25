# ADR 0049: the list accessor, on two conditionally imported intrinsics

- Status: accepted
- Date: 2026-09-08

## Context

`typed-list-new` has been lowered here since the list descriptor landed, and
`vector-count` walks the list carrier. Nothing read an element back:
`typed-list-nth` fell through the typed-operation `cond` to its `:else` and was
refused `typed Wasm operation is not qualified`, exit 70 -- for the whole
module, whether the function was reached or not.

kotoba-sema has typed and rewritten it (`nth` on a `[:list T]`) since
2026-09-03; the KIR reference interpreter executes it. This backend and
kotoba-script were the two that did not.

## Decision

`typed-list-nth` lowers to a call on one of two intrinsics,
`kotoba:typed/list-nth-i64` and `kotoba:typed/list-nth-ref`, chosen by the WASM
type the item lowers to. This is exactly the shape `typed-set-nth` already has,
with two differences.

**The imports are CONDITIONAL.** `typed-set-nth`'s pair sits in the
unconditional import block, so every host that runs any typed module must
supply it. Adding two more names there would break each of those hosts at
instantiation, for modules that never index a list. `has-typed-list-nth?` is
`uses-operation?` over the module's bodies, and a module that does not index a
list imports neither name -- asserted, because the whole safety of the change
rests on it.

**An item type with no matching intrinsic is REFUSED, not mis-typed.** `:f64`,
`:f32` and `:bool` lower to f64/f32/i64 words, not to `externref`, so neither
intrinsic's result type matches. `typed-set-nth`'s `(if (= item-type :i64) …
ref)` would emit the ref call for all three. Measured 2026-09-08: doing that for
`[:list :f64]` produced a module the compiler accepted and V8 rejected --
`WebAssembly.compile(): type error in fallthru[0] (expected f64, got externref)`
-- a defect that survives the compiler and appears only at instantiation. The
dispatch is `:i64` → i64, `reference-type?` → ref, otherwise `throw` with the
item type named. `typed-set-nth` has the same hole; this ADR does not close it.

## Evidence

In `test/kotoba/wasm_test.cljk`:

- `canonical-lists-index-through-list-nth-intrinsics` reads the import's
  function index out of `wasm-tools print` and asserts which one the body
  `call`s. Both names are imported together, so their mere presence says
  nothing about the dispatch; a test that only looked for the name would pass
  with the arms swapped. Broken on purpose by swapping them: 6 assertions go
  red, including `wasm-tools validate`.
- `a-module-that-does-not-index-a-list-imports-neither-intrinsic` is the
  conditional-import claim. Broken on purpose by making the import
  unconditional: red.
- `an-item-type-with-no-matching-intrinsic-is-refused-not-mis-typed` covers
  `:f64`, `:f32` and `:bool`. Broken on purpose by deleting the `when-not`:
  red.

Executed, not only validated: the same module compiled through `amu` and run on
`amu`'s `runtime/browser-host.mjs` answers `"bb"` for
`(nth (typed-list-new [:list :string] "a" "bb" "ccc") 1)`, `30` for the i64
list, and traps `list index out of bounds` at index 3 and at -1.

## Consequences

- A host that wants to run a module which indexes a list must answer
  `list-nth-i64` and `list-nth-ref`. `amu`'s browser host does, as of the same
  day; any other host will fail at instantiation with the import named, which
  is the correct failure and not a silent one.
- `typed-set-nth` keeps both its unconditional import and its `:f64` / `:bool`
  hole. Fixing it is a separate change with a separate host-compatibility
  question, because its imports cannot be made conditional without changing
  what existing modules import.
