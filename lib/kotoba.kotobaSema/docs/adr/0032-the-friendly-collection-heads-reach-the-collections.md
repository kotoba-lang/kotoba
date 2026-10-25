# 0032 — the friendly collection heads reach the collections

Status: accepted
Date: 2026-09-03

## The report

`count` was declared admitted by the language authority on three backends and
implemented on none of them, and `first`/`second`/`rest` refused every typed
collection with a message about `i64`.

Measured 2026-09-03 against this repository at `df383ba0` and amu `57ba0ee0`.
Each cell is one `(defn main [] <body>)`, analysed and then executed on the
KIR interpreter. The receivers are `[7 8 9]`, `(typed-list-new [:list :i64] 7
8 9)`, `#{:a :b}`, `(typed-map-new [:map :i64 :i64] 1 10 2 20)`, `{:a 1}` and
`"abc"`.

| head | vector | [:list T] | set | [:map K V] | keyword map | string |
|---|---|---|---|---|---|---|
| `count` | **no lowering** | no lowering | **no lowering** | **no lowering** | no lowering | no lowering |
| `first` | **expected i64** | expected i64 | **expected i64** | **expected i64** | expected i64 | expected i64 |
| `second` | **expected i64** | expected i64 | expected i64 | expected i64 | expected i64 | expected i64 |
| `rest` | **expected i64** | expected i64 | expected i64 | expected i64 | expected i64 | expected i64 |
| `nth` | ran | no lowering | no lowering | no lowering | no lowering | no lowering |
| `get` | expected map | expected map | expected map | ran | ran | expected map |
| `assoc` | expected map | expected map | expected map | ran | ran | expected map |
| `conj` / `disj` | receiver refusal | receiver refusal | ran | receiver refusal | receiver refusal | receiver refusal |
| `contains?` / `dissoc` | receiver refusal | receiver refusal | receiver refusal | ran | receiver refusal | receiver refusal |
| `empty?` | equality operands | equality operands | equality operands | equality operands | equality operands | equality operands |
| `last` / `seq` | no lowering | no lowering | no lowering | no lowering | no lowering | no lowering |
| `peek` / `pop` / `keys` / `vals` | no lowering | no lowering | no lowering | no lowering | no lowering | no lowering |

Bold marks what this change moves.

Two shapes of refusal appear, and they are the same gap:

* `operation has no admitted lowering` — the message for a head nothing
  rewrote. It at least names the operation.
* `expression type mismatch: expected i64, got vector-i64` — **worse**, because
  it reads as a defect in the caller's program. `first` desugars to
  `pair-first`, which is declared over the legacy i64 pair chain, so a reader
  was told their vector was the wrong type for an operation whose Clojure
  meaning it satisfies exactly.

## 1. What was dispatched, and what was not

`vector-count`, `vector-f64-count`, `hetero-vector-count`, `typed-set-count`,
`typed-map-count`, `vector-at`, `vector-f64-at`, `vector-drop` and
`vector-f64-drop` were all already there, already lowered on the three
backends, already returning the right types. Nothing was missing but the
dispatch — the same defect `contains?`, `dissoc`, `conj` and `disj` had
earlier the same day.

**Dispatched** (a typed operation exists and the authority claims the name):

| head | receiver | lowers to |
|---|---|---|
| `count` | `:vector-i64` | `vector-count` |
| `count` | `:vector-f64` | `vector-f64-count` |
| `count` | `[:vector [T …]]` | `hetero-vector-count` |
| `count` | `[:set T]` | `typed-set-count` |
| `count` | `[:map K V]` | `typed-map-count` |
| `first` (`pair-first`) | `:vector-i64` / `:vector-f64` | `vector-at` / `vector-f64-at` at 0 |
| `rest` (`pair-second`) | `:vector-i64` / `:vector-f64` | `vector-drop` / `vector-f64-drop` by 1 |
| `second` | a bounded vector | `first` of `rest`, unchanged |

**Refusal improved, no lowering invented**: `nth` on a receiver it does not
index now names `typed-set-nth` / `typed-map-entry-at` instead of saying the
operation has none.

**Not dispatched, authority corrected instead** (`lang/surface-status.edn` in
kotoba-lang):

* `peek` / `pop` — Clojure's `peek` and `pop` on a vector take from the END.
  `vector-drop` is a FRONT drop and there is no `vector-pop`, so `pop` cannot
  be lowered from anything that exists. The grammar's reading — "empty-safe
  pair-first" / "empty-safe pair-second" — describes a pair chain, which is
  not what a vector literal is any more, and giving a vector those semantics
  would answer a Clojure question wrongly while looking right. Implementing
  only `peek` would leave `(peek (pop v))` — the authority's own fixture —
  still refused while making the claim half true.
* `keys` / `vals` — there is no `typed-map-keys` or `typed-map-vals`. Building
  one is a new lowering, not a dispatch.
* `empty?` — desugars to `(= x 0)` before any type is known, so the head is
  gone by the time a receiver type exists. `(= (count c) 0)` is the spelling
  that works, and it works because of this change.
* `last` / `seq` — not declared by any authority. Correctly refused as unknown
  heads; nothing to correct.

`count` is now RESERVED. Measured before this change, `(defn count [a] :i64
a)` was **accepted**, and its calls would have been rewritten out from under
it silently. `peek`, `pop`, `keys`, `vals`, `seq` and `last` are deliberately
**not** reserved: taking a name away without implementing it is a regression,
and the test pins that direction too.

## 2. A rewrite alone was not enough

The first version of this change added only the desugar arms, and it made a
program worse:

    (+ (pair-first [1 4 2]) (reduce add 4 [1 2 3]))

went from `expression type mismatch: expected i64, got vector-i64` — pointing
at the author's own vector — to a refusal naming `__kotoba_reduce_v_1`, a
binding the author never wrote. The same program with `(vector-at [1 4 2] 0)`
spelled by hand compiled. Dumping both after the rewrite pass showed
**identical bodies** and different `:param-types` on the synthesized `reduce`
loop helper: `[:i64 :i64 :vector-i64]` for the hand-written one and
`[:i64 :i64 :i64]` for the rewritten one.

The cause is pass order. `infer-absent-parameter-types` runs BEFORE
`rewrite-record-projections`, and it reads a refused operand's required type
out of the refusal's ex-data rather than out of the prose. A head with only a
rewrite is still REFUSED during that earlier pass, and the
`:kotoba.error/expected :i64` of that refusal was attributed to an unrelated
synthesized parameter.

So `count`, `pair-first` and `pair-second` gained a **type signature** as well
as a lowering, in the same `case` where `nth` has had one all along — which is
why `nth` never poisoned anything. That is the load-bearing half of this
change, and the test pins it directly rather than pinning only the heads.

## 3. What is measured

* New namespace `kotoba.compiler.collection-heads-test`, on the pinned
  frontend: 9 tests, 56 assertions, **21 failures / 25 errors, exit 1** — 22 of
  the reported messages literally `operation has no admitted lowering` and 8
  `expected i64, got vector-i64`, and `(defn count ...)` refused nothing.
  After: 56 assertions, 0 failures, 0 errors, exit 0. Same counts under nbb.
* Full JVM suite after: 334 tests, 1537 assertions, 0 failures, 0 errors.
  Full nbb suite after: 179 tests, 606 assertions, 0 failures, 0 errors.
* **Byte identity.** Five programs that already compiled — set ops, typed-map
  ops, vector ops, the keyword map, and `first`/`rest` over an actual
  `(list 1 2 3)` — digested per runtime (`pr-str` writes a bigint as `42` on
  the JVM and `42n` under nbb) before and after: HIR and KIR digests and
  values identical on both. The pair accessors are the closure, lazy-cell,
  cursor and destructuring vocabulary of this whole desugarer, so every
  receiver that is not a vector passes through unchanged, and a test pins the
  lowered form of `(first (rest (list 1 2 3)))` in both directions.
* **End to end.** A program using `count` on four receivers plus `first` and
  `rest` on a vector, through `amu compile --target wasm32-browser
  --jvm-free` and then `runtime/browser-host.mjs`: refused `operation has no
  admitted lowering` (exit 65) with the pinned frontend on the classpath, and
  `main() = 17n` with this one.
* Positives are executed on the KIR interpreter, not merely admitted, and
  every refusal is pinned by its stable code rather than by the fact that
  something was refused, so a fixture failing for another reason cannot be
  counted as this arm discriminating.

## 4. One thing measured on the way that is not this change's

The f64 vector LITERAL `[1.0 2.0]` is admitted on the JVM and refused under
nbb with `expression type mismatch: expected i64, got f64`. Measured on the
PINNED frontend as well, so it predates this change. The test writes
`(vector-f64-new 1.0 2.0)` instead — a test that used the literal would report
this change as broken on one runtime.

## 5. Consequences for consumers

amu pins this repository by `:git/sha` in its own `deps.edn`. A west pin
advance does not move that pin, so **amu needs a `deps.edn` bump** before any
amu user sees these heads. `lang/guest-grammar.edn` is untouched here, so the
byte copies amu and this repository vendor, and the sha256 pinned in four
repositories, are unaffected.
