# 0012 — a map key is not a keyword

Status: accepted
Date: 2026-09-02

## The report

    (ns probe.mapi64)
    (defn main [] :i64 (let [m (assoc {} 1 10)] (get m 1 0)))

`amu check --jvm-free` → exit **65**, `:kotoba.error/subset-reject`,
`expression type mismatch: expected keyword, got i64` (amu a8e30d5b, sema
c031dd34). `kotoba-lang`'s `lang/conformance/stdlib/manifest.edn` records
`frequencies` and `get-in` under `:absent` for exactly this message.

## What the measurement found

`[:map K V]` was **already generic in K**. The refusal was in the friendly
surface on top of it, and one line of the table says what the defect really
was: `assoc` refuses a **keyword**-keyed typed map too. `get` had been
type-directed since the typed map landed; the write half had never been
written, for any key type.

Measured with `sema/analyze` over the two surfaces, one row per operation:

| key type | canonical `typed-map-*` | `{}` literal | `get` (2 & 3) | `assoc` | `contains?` | `dissoc` | `entry-at` |
|---|---|---|---|---|---|---|---|
| `:i64` | **all ops admit** | `map keys must be bounded keywords` | **admits** | `expected map, got [:map :i64 :i64]` | `operation has no admitted lowering` | `…no admitted lowering` | admits (JVM only — see below) |
| `:string` | all ops admit | same refusal | admits | `…got [:map :string :i64]` | no lowering | no lowering | admits |
| `:bool` | all ops admit | same refusal | admits | `…got [:map :bool :i64]` | no lowering | no lowering | admits |
| `:keyword` | all ops admit | **admits** (legacy `map-new`) | admits | `…got [:map :keyword :i64]` | no lowering | no lowering | admits |
| record | all ops admit, and RUN | no literal form | admits | refused | no lowering | no lowering | admits |
| `:f64` / `:f32` | refused | same refusal | refused | refused | no lowering | refused | refused |

After:

| key type | `{}` literal | `get` | `assoc` | `contains?` | `dissoc` | `entry-at` |
|---|---|---|---|---|---|---|
| `:i64` | **admits**, `[:map :i64 :i64]` | admits | **admits** | **admits** | **admits** | admits, **both runtimes** |
| `:string` | **admits**, `[:map :string :i64]` | admits | **admits** | **admits** | **admits** | admits |
| `:bool` | refused, named | admits | **admits** | **admits** | **admits** | admits |
| `:keyword` | admits (legacy `map-new`, byte-identical) | admits | **admits** | **admits** | **admits** | admits |
| record | no literal form | admits | **admits** | **admits** | **admits** | admits |
| `:f64` / `:f32` | refused, named, with the reason | refused | refused | refused | refused | refused |

## Decisions

**1. A map literal infers its key type and keeps `:i64` values.**
`:keyword` keeps the legacy untagged pair-map (`map-new`) byte for byte —
that is the representation `map-get`, `map-assoc` and every `match` map
pattern are written against. `:i64` and `:string` lower to
`(typed-map-new [:map K :i64] …)` instead.

The value type is `:i64` and is **not** inferred. A literal has no
annotation, so both halves would have to be read off the source, and the
values are arbitrary expressions whose types are not known until inference,
which runs after desugaring. `:i64` is what the keyword-keyed literal has
always meant by a value. `{"a" "b"}` is therefore still refused, and
`typed-map-new`, which says both halves, is the spelling for it. **This did
not fall out for free and is the largest thing left undone here.**

**2. `assoc` / `contains?` / `dissoc` select their primitive from the
receiver's type**, the way `get` already did, in `rewrite-record-projection`.
`contains?` and `dissoc` are new heads: the language authority
(`lang/guest-grammar.edn`) already declared them admitted, and nothing
implemented them. They are reserved as well as implemented — the rewrite
dispatches on the head before signatures are consulted, so a user
`(defn contains? …)` would have been shadowed silently.

**3. An EMPTY literal takes its key type from the first `assoc`.** `{}`
desugars to `(map-new)`, whose type is the legacy `:map` whatever the program
goes on to put in it, so `(assoc {} 1 10)` — the reported shape — has nowhere
else to get a key type. Only `:i64` and `:string` are retyped, so
`(assoc {} :a 1)` still lowers to the legacy map it always did.

Limit: the receiver must be the literal itself. `(let [m {}] (assoc m 1 10))`
is still refused, because `m`'s type is fixed at binding time and this is a
rewrite, not an inference pass.

## The order

`kotoba.kir.value/bounded-typed-value!` re-sorts every typed map it validates
by `compare-typed-values` on the KEY type, so the order `typed-map-entry-at`
walks is the language's, not the emitter's. It is total for every admitted key
type, and it was already implemented; this change measures and pins it:

- **`:i64` — signed numeric ascending.** `{3 30, -5 50, 0 0, 2 20}` walks
  `-5, 0, 2, 3`. A comparator reading two's-complement patterns as unsigned
  would put `-5` last.
- **`:string` — UTF-16 code-unit lexicographic.** `{"b", "a", "C", "ab"}`
  walks `"C", "a", "ab", "b"`. Upper case precedes lower case: this is not a
  locale collation and not case-insensitive. JVM `String.compareTo` and JS
  `<` agree on the ORDER (they disagree only on the magnitude of the returned
  integer, which nothing here reads).
- `:keyword` / `:symbol` — by printed text. `:bool` — `false` before `true`.
  Records and other structured keys — field by field, left to right.

The frontend emits literal entries already in that order, so the KIR is
reproducible without hashing identity, and the runtime order does not depend
on the order the literal was written in.

## What stays refused, and why

- **`:f64` / `:f32` as a KEY** — no portable key identity. NaN compares
  unequal to itself, and `+0.0` and `-0.0` are equal while differing in bits,
  so neither the total order the entry chain is kept in nor duplicate-key
  detection is decidable. Previously one message covered keys and values
  together; it is now two, because they are two different facts — a value
  needs no order and is refused on the structured scalar ABI alone.
- **A `:bool` literal key** — refused by name at the literal (`this literal
  has a key of kind: boolean`), and still admitted through `typed-map-new`.
  There is no identity problem; there is no useful two-entry literal either.
- **Mixed key kinds in one literal** (`{1 2 :a 3}`) — the kinds are named in
  sorted order so the message does not depend on host map iteration order.
- **`contains?` / `dissoc` on a typed SET** — deliberately out of scope. The
  refusal names the receiver's type and points at `typed-set-contains` /
  `typed-set-disj` rather than saying `operation has no admitted lowering`.
- **Records as keys are NOT refused.** The brief for this work assumed
  structural equality made them non-deterministic. It does not: the order is
  `compare-typed-values`'s, field by field, language-owned rather than
  host-owned, and a record-keyed map already ran end to end on the KIR
  interpreter before this change. Refusing them would have been a regression,
  so the measurement is recorded instead of the assumption.

## Two pre-existing `:cljs` defects this exposed

Both were measured at `origin/main` **before** any change here, and both make
integer keys unusable on one of the two runtimes.

1. **`annotate-doseq-collection-kinds` rebuilt map literals with `(into {} …)`.**
   `{}` is a PersistentArrayMap that promotes to a hashed map above EIGHT
   entries, and a `.kotoba` integer literal is a JS bigint, which
   ClojureScript cannot hash. So a nine-entry integer-keyed literal died in
   that walker — before desugaring could say anything about it — with
   `Cannot create property 'closure_uid_…' on bigint '0'`. It also discarded
   the comparator `kotoba-reader/reader-map` installs for exactly that reason.
   Fixed here, in this repository: rebuild from `(empty form)`.

2. **`kotoba.kir.value/compare-typed-values` used `clojure.core/compare` on an
   i64.** Fixed in `kotoba-lang/kotoba-kir` (ADR 0257, merged `ad6db332`, this
   repository's pin advanced to it). Worth recording where it did the damage:
   `amu compile --target wasm32` evaluates the oracle through `lower`, so a
   two-entry `[:map :i64 :i64]` exited **70** with `internal compiler error`,
   which reads as a missing wasm lowering. One entry compiled and two did not
   (a one-element sort never calls the comparator), and `:bool` / `:string` /
   `:keyword` keys compiled at every entry count — those two facts are what
   identify it as a comparator.

## What is pinned

`test/kotoba/compiler/typed_map_key_types_test.cljk`, in both lists of
`run-tests.cljk`. 21 tests / 50 assertions.

Before the change: **exit 1, 20 failures and 23 errors** on the JVM. The three
that passed are the ones that had to: the two byte-identity controls, and the
case asserting that the key types the canonical surface already admitted still
work. After: exit 0, 0 failures. Full suites — sema JVM 275/1272 green, sema
nbb 116/306 green.

The byte-identity control is the part that could regress silently: nothing
else in the file would notice if the keyword literal quietly started lowering
to a typed map, because every keyword case would still answer the same number.
It pins the normalized HIR and KIR of two keyword-keyed programs, captured
before the edit and identical on both runtimes (`pr-str` writes a bigint as
`42` on the JVM and `42n` under nbb, so the rendering is normalized rather
than `pr-str`'d).
