# 0033 — a map value is not an i64

Status: accepted
Date: 2026-09-03

Follows [0012](0012-a-map-key-is-not-a-keyword.md), which is the same defect
one layer over.

## The report

    (ns m.probe)
    (defn main [] :i64 (let [m {1 "a"}] (typed-map-count [:map :i64 :string] m)))

`amu check --jvm-free` → exit **65**, `:kotoba.error/subset-reject`,
`expression type mismatch: expected i64, got string` (amu `57ba0ee0`, sema
`df383ba0`). A generic type error on a program that reads correct.

0012 left the reason in the frontend, in `map-literal-key-types`:

> `:i64` is what the keyword-keyed literal has always meant by a value, so
> that is what the other key types mean by one too. A literal wanting any
> other value type is written with `typed-map-new`, which says both halves.

and in the authority, `lang/guest-grammar.edn`:

> always `:i64`. A literal has no annotation and inference runs after
> desugaring, so the value half cannot be read off the source.

That is true of an **arbitrary** value expression and false of a **literal**
one. `{1 "a"}` says its value type in the source as plainly as `{1 10}` does.

## What the measurement found

Both layers, measured 2026-09-03 with `sema/analyze` + `kir/execute`, one row
per value type. Every positive is run **to a value**, not merely admitted.

**Before**

| value type | bare literal `{1 <v>}` | `typed-map-new` | `get` | `assoc` | `dissoc` | `contains?` | `entry-at` |
|---|---|---|---|---|---|---|---|
| `:i64` | **admits** | admits | admits | admits | admits | admits | admits |
| `:string` | `expected i64, got string` | admits | admits | admits | admits | admits | admits |
| `:bool` | `…got bool` | admits | admits | admits | admits | admits | admits |
| `:keyword` | `…got keyword` | admits | admits | admits | admits | admits | admits |
| record | `…got [:record …]` | admits | admits | admits | admits | admits | admits |
| `[:map :i64 :i64]` | `…got [:map :i64 :i64]` | admits | admits | admits | admits | admits | admits |
| `[:vector [:i64 :i64]]` | `…got [:vector …]` | admits | admits | admits | admits | admits | admits |
| `[:set :i64]` | `…got [:set :i64]` | admits | admits | admits | admits | admits | admits |
| `:f64` / `:f32` | ABI refusal | **refused** | refused | refused | refused | refused | refused |

Every column but the first was already generic. **Only the literal was
pinned.**

**After**

| value type | bare literal `{1 <v>}` |
|---|---|
| `:i64` | admits, `[:map K :i64]` — byte-identical lowering |
| `:string` | **admits**, `[:map K :string]` |
| `:bool` | **admits**, `[:map K :bool]` |
| `:keyword` | **admits**, `[:map K :keyword]` |
| record / nested map / hetero vector / typed set | **admits**, from the constructor's declared type |
| `:f64` / `:f32` | refused **by name**, with the ABI reason |
| values that disagree | refused **by name**, both types and both entries |
| keyword-keyed, non-`:i64` value | refused **by name**, pointed at `typed-map-new` |

## Decision

`map-literal-item-type` reads the value type off the literal's own value
expressions, the way `closed-vector-literal-type` reads a vector's item types.

* **Spelled directly**: an integer, string, boolean or keyword literal.
* **Spelled by a constructor**: `typed-map-new`, `typed-set-new`, `record-new`
  and `hetero-vector-new` declare the type they build as their first argument,
  and that argument is in the source. All four are reserved names, so a user
  function cannot shadow one and make a literal read a descriptor off an
  unrelated call; the descriptor's own head is checked too, so a malformed
  first argument falls through to *unknown* rather than becoming a value type
  nothing validated.
* **Not spelled**: `:i64`, as before. A value whose type only inference can
  know contributes nothing here and is checked afterwards against the agreed
  type, exactly as it was checked against `:i64` before. A literal with no
  typed value at all lowers to the descriptor it always lowered to.

The `(assoc {} 1 "a")` retype site runs **after** desugaring, so it asks
inference for the value type as it already asked for the key.

## The keyword-keyed literal does not get this

0012's decision stands: a keyword-keyed literal stays the legacy untagged pair
map, byte for byte, because `map-get`, `map-assoc` and every `match` map
pattern are written against that form. That map's values are `:i64`, so the
value type is **not** inferred there. `{:a "x"}` was refused with
`expression type mismatch: expected i64, got string` — true, and it says
nothing about what to do instead. It is now:

    map literal with keyword keys carries i64 values; the value at key :a is
    :string. A keyword-keyed literal lowers to the legacy untagged pair map
    that `map-get`, `map-assoc` and every `match` map pattern are written
    against, so its value type is not inferred; write
    (typed-map-new [:map :keyword :string] ...) for a typed map with keyword
    keys

## The float verdict: a real obstacle, not the key's inherited

0012 refuses a floating **key** because a float has no identity to be a key
by. That argument does not reach a value, and this is measured rather than
assumed. `kotoba.kir.value/bounded-typed-value!` validates a `[:map K V]`
entry by entry and then sorts with `compare-typed-values` **on the key alone**,
and detects duplicates **on the key alone**:

    (bounded-typed-value! [:map :i64 :string]
                          [[:map :i64 :string] [[9 "a"] [2 "z"] [5 "m"]]])
    ;; => [[2 "z"] [5 "m"] [9 "a"]]   -- ordered by key; the values rode along

    (bounded-typed-value! [:map :i64 :i64] [[:map :i64 :i64] [[1 10] [1 99]]])
    ;; => throws "typed map contains a duplicate key" -- although the values differ

So a value needs neither a total order nor a decidable identity. The
value-side obstacle is a **different, real** one: `validate-value-type!` has no
floating encoding for the value slot and throws *direct floating map keys or
values are outside the structured scalar ABI*. It is owned by **kotoba-kir**,
not by this frontend, and lifting it is a change there.

The two refusals are therefore said as two messages. One message covering both
would tell the reader neither.

## Byte identity

Captured on `df383ba0` on **both** runtimes before the change and compared
after: i64-valued, string-keyed, keyword-keyed and all-unknown-value programs
lower to the same HIR and KIR, character for character. `pr-str` writes a
`.kotoba` integer as `42` on the JVM and `42n` under nbb, so the goldens are
normalized rather than literal.

## What the nbb runner caught that the JVM one could not

The first draft named the offending entry with `pr-str` for every key. Green on
the JVM; under nbb it printed

    map literal value at key #object[BigInt 1] is a floating point literal…

because a `.kotoba` integer literal is a JS bigint there. The **same refusal
said two different things on the two runtimes this file claims**. An integer
key now goes through `str`; a string key keeps `pr-str`, which is what puts the
quotes on.

## Evidence

* `test/kotoba/compiler/typed_map_value_types_test.cljk` — 18 tests, 40
  assertions. Against the pinned frontend: **6 failures, 22 errors, exit 1**.
  After: **0, 0, exit 0**. Registered in both of `run-tests.cljk`'s lists.
* Full suites: JVM 343 tests / 1521 assertions, nbb 188 tests / 590 assertions,
  0 failures either way.
* End to end: `amu compile --target wasm32-browser` on a string-valued map
  literal, instantiated through `amu runtime/browser-host.mjs`, `main() = 12`
  (`3 + 5 + 4`, three string lengths). The control — the same program against
  the pinned sema on the same classpath — exits 65.
* `lang/guest-grammar.edn` moves with this change; the authority's `always
  :i64` sentence would be false otherwise. The vendored copy here and the four
  pinned digests move in the same wave (see
  [0028](0028-the-grammar-copy-is-compared-to-the-frontend-that-owns-it.md)).

## Consequences

* amu does not get this until it advances its `kotoba-sema` pin, and that
  commit must resync its vendored `guest-grammar.edn` and both digest
  literals, and regenerate `deps-lock.edn`.
* `kotoba-lang`'s `lang/conformance/collections/map_literal_values.kotoba` is
  the conformance case; `main()` is 125 on both `:kir` and wasm32.
* Widening the value side further is a `kotoba-kir` change, not one here: the
  frontend's `validate-value-type!` mirrors the runtime's, and the runtime is
  where `[:map K :f64]` has no encoding.
