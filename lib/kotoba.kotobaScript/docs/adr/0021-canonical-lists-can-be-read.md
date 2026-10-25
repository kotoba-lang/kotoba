# ADR 0021: a canonical list can be read, not only built and counted

- Status: accepted
- Date: 2026-09-08

## Context

This backend has had `typed-list-new` and `vector-count` on a `[:list T]` since
the list descriptor landed. It has never had an accessor. `typed-list-nth`
reached `infer-type` as an unknown head and `emit-expr` as an unrecognised one,
and the compile failed `unsupported KIR node` (single file) /
`unsupported KIR operation` (project route), exit 70.

kotoba-sema has typed `typed-list-nth` since 2026-09-03 and rewrites `nth` on a
`[:list T]` to it (sema ADR 0034), so the head arrives from ordinary guest
source. The KIR reference interpreter already executed it. Only the two
backends were missing.

Measured 2026-09-08 at amu `9092ee34`:

```
$ amu check r4.kotoba                            # exit 0
$ amu compile r4.kotoba --target web  --output x.mjs
exit 70  :message "unsupported KIR node"
$ amu compile r4.kotoba --target wasm32 --output x.wasm
exit 70  :message "typed Wasm operation is not qualified"
```

The refusal is the whole module's, not the function's: a two-function
reproduction whose `main` returns `7` and never calls the indexing function was
refused on both targets.

The consequence was recorded in `kotoba-lang/kotoba-lang`'s `lang/compat.edn`
as the reason three `clojure.string` names were absent: a `[:list :string]`
could be built and counted and nothing could be read back out of it, so a
function returning one would hand the caller a value with no accessor. Every
`typed-map-keys` / `typed-map-vals` projection is such a value.

## Decision

`typed-list-nth` is inferred and emitted here.

- Inference mirrors `typed-list-new`'s: arity 3, a `[:list item-type]`
  descriptor, the carrier at that type, an `:i64` index; the result type is the
  item type.
- Emission is `typedListNth(t, v, index)`, a new prelude helper that asserts the
  carrier, asserts the index is an i64, and **traps** out of range with
  `list-index-out-of-range` rather than answering `undefined`. That is what sema
  promises for it -- *"typed-list-nth traps on an index out of range, as vector
  nth without a default does"* -- and it is the same shape `vectorAt` already
  has (`vector-index-out-of-range`).

## Evidence

`canonical-lists-read-an-element-back-and-trap-out-of-range` in
`test/kotoba/script_test.cljk` emits a module, imports it into node as restricted
ESM, and reads elements back at both ends and the middle, on an i64 list and a
string list; then asserts both ends of the range trap with that exact message,
and that a carrier holding the wrong item type is still refused on the way in.
The negative half checks the index type, the descriptor kind and the arity.

Broken on purpose once, to see it discriminate: deleting the range check from
`typedListNth` turns the test red on the out-of-range branch (`process.exit(5)`
-- the index no longer produces `list-index-out-of-range`) and green again when
restored. Deleting the emit arm entirely puts the whole-module refusal back:
`amu compile --target web` returns exit 70 `unsupported KIR operation` while
`--target wasm32` stays 0.

End to end, through the real project route with the compiled artifact RUN:
`(str/join "," (typed-list-new [:list :string] "a" "bb" "ccc"))` is `"a,bb,ccc"`.

## Consequences

- A `[:list T]` is now a usable value on this backend, so `typed-map-keys` and
  `typed-map-vals` projections are usable too.
- `kotoba-lang`'s `clojure.string` compat module gains `join`, whose second
  argument is a `[:list :string]`. That moves the module's floor: an amu whose
  kotoba-script pin predates this refuses the whole module. Loudly, at compile
  time, never with a different answer.
- `typed-set-nth` is still absent here. It lowers on wasm32 and not on this
  backend; that is a separate gap and is not addressed by this ADR.
