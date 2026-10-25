# 0031 — a declared type of the wrong shape

Status: accepted
Date: 2026-09-03

## The report

`amu check --jvm-free`, amu `6c245f69` (which pins this repository at
`1a073853` and kotoba-kir at `b2e5d9c4`), one `(defn main [] …)` per file:

| probe | body | before |
|---|---|---|
| p1 | `(typed-map-count [:map :i64 :i64] {3 30 1 10 2 20})` | exit 0 |
| p2 | `(let [m {3 30 1 10 2 20}] (typed-map-count [:map :i64 :i64] m))` | exit 0 |
| p5 | `(let [m {3 30 1 10}] (typed-map-contains [:map :i64 :i64] m 3))` | exit 0 |
| **p6** | `(let [m {3 30 1 10}] (option-value-of :i64 (typed-map-get :i64 m 3) 0))` | **exit 70, internal compiler error** |
| **p7** | same, inline literal | **exit 70, internal compiler error** |
| **p4** | `(let [m {:a 1 :b 2}] (typed-map-count [:map :keyword :i64] m))` | exit 65, `expression type mismatch: expected [:map :keyword :i64], got map` |
| **p8** | `(let [m {:a 1 :b 2}] (typed-map-contains [:map :keyword :i64] m :a))` | exit 65, same message |

The whole diagnostic for p6/p7 was

    {:code :kotoba/internal-error :severity :error :source "p6.kotoba"}

— no operation, no span, no cause.

## 1. What actually crashed

**Not `typed-map-get`.** `typed-map-get` refuses a non-map type correctly:
`(typed-map-get :i64 m 3)` alone exits 65 with `typed map operation requires
[:map key-type value-type]`. What crashed is `option-value-of`, whose lowering
read `(second (first args))` off the declared type with no shape check, and
`(second :i64)` is a host error — `:i64 is not ISeqable` under nbb,
`Don't know how to create ISeq from: clojure.lang.Keyword` on the JVM.

The probe was malformed: `typed-map-get` takes the MAP type and
`option-value-of` takes the OPTION type, and `:i64` was handed to both. The
well-formed program

    (let [m {3 30 1 10 2 20}]
      (option-value-of [:option :i64] (typed-map-get [:map :i64 :i64] m 3) 0))

compiled before this change and compiles now, `--target wasm32-browser`,
byte-identical (`e2a9ea1b…`), and returns **30** through
`runtime/browser-host.mjs`.

### The shape, not the instance

Sweeping every head that takes a declared type (115 of them, arities 1–5,
six wrong shapes) found **76 programs that raised a raw host error** under
nbb and **36** on the JVM. Three families:

- **six lowering branches destructured the type unguarded** —
  `option-some-of`, `option-value-of`, `result-ok-of`, `result-err-of`,
  `result-value-of`, `result-error-of`. The `result-err-of` / `result-error-of`
  message went on to print ClojureScript's Keyword CONSTRUCTOR SOURCE into
  the compiler's own error.
- **three read a record's field list the same way** — `record`, `record-new`,
  `record-assoc`, via `(nth type 2 nil)`, which throws on a keyword even with
  a default.
- **`validate-value-type!` HASHED the type** to answer `(contains? value-types
  type)`. `value-types` is a set of keywords, so the test can only ever
  succeed for one — but ClojureScript hashes the argument to answer it, and a
  `.kotoba` integer literal is a JS bigint, which cannot carry the property
  the hasher writes. `(typed-set-count 3 0)` died with `Cannot create property
  'closure_uid_…' on bigint '3'` instead of reaching the `:else` arm four
  lines down that says exactly what is wrong with it. That accounts for the
  42-program gap between the two runtimes, and it is the third instance of
  the `:cljs` bigint defect ADR 0012 recorded two of.

Each site is guarded the way the typed-set and typed-map branches next to it
already were: `(when (generic-option-type? …) …)`, `(when
(parametric-result-type? …) …)`, `(when (record-type? …) …)`, `(and (keyword?
type) (contains? value-types type))`. A well-formed program takes the same
branch it always took, so the guards are byte-neutral. After: the sweep finds
**zero** raw host errors and **zero** internal failures, on both runtimes.

## 2. An internal error now says where

`internal-failure!` re-raises a host error that escaped a pass, naming what it
escaped from. It is installed at the three per-expression chokepoints —
`desugar-expr` (lowering), `validate-expr` (admission), `infer-expression-type`
(inference). The innermost frame wraps first, so the operation reported is the
one that broke; outer frames see `:phase` and rethrow untouched.

`:phase :internal` is kept, so **the exit code stays 70**. A compiler that
broke is not a caller who typed something wrong, and collapsing the two would
be the defect in the other direction. What changes is that 70 now says where.

**The CLI redaction is kept, and the operation travels in the code.** amu
replaces the MESSAGE of an internal error with the fixed words `internal
compiler error` on purpose — a host error's message can carry a filesystem
path — and `kotoba.compiler.diagnostic/from-error` copies only `:code`,
`:severity`, `:source` and `:span` into the envelope. So the operation is put
into the one field that survives:

    :code :kotoba.error.internal-operation/option-value-of

Match the NAMESPACE to recognise the class; read the NAME for the operation.
Measured through the CLI on p6 before the item-1 guards landed:

    {... :diagnostic {:code :kotoba.error.internal-operation/option-value-of,
                      :span {:line 2 :column 36 …}}, :message "internal compiler error"}

against `{:code :kotoba/internal-error :severity :error}` before.

Only a head in `reserved-function-names` — the compiler's own closed
vocabulary, a name a program is forbidden to define — is spelled into the
code. Nothing user-chosen can ride out through it; any other head falls back
to `:kotoba.error/internal-operation-failure` and stays in `ex-data` only.

**Host stack exhaustion is exempt.** `analyze` already owns it one frame
further out (`kir/host-stack-exhausted?` → `:kotoba.error/host-nesting-exhausted`,
naming the source depth limit the program was inside of). Wrapping it here hid
the RangeError from that predicate and demoted an actionable refusal into an
internal failure: `host-nesting-test` went red under nbb the moment the guard
landed without the exemption, reporting
`:kotoba.error.internal-operation/=` for 64 `case` arms. Caught by the suite,
recorded here.

## 3. The asymmetry is a decision, and now says so

An `:i64`-keyed literal types as `[:map :i64 :i64]` and a keyword-keyed one
types as the legacy `map`. **The refusal is right.** ADR 0012 decision 1: a
keyword-keyed literal keeps the legacy untagged pair-map byte for byte,
because that is the representation `map-get`, `map-assoc` and every `match`
map pattern are written against; `:i64` and `:string` are the ones that were
RETYPED. Decision 3: `{}` is legacy for the same reason — it has no key type
of its own. `lang/guest-grammar.edn` `:map-literal` says `pair cons-list of
pairs` and does not distinguish key types, so the decision lives in ADR 0012
and nowhere else.

What was wrong is that `expression type mismatch: expected [:map :keyword
:i64], got map` reads as a defect in a program that is written correctly for
the representation it actually has. The refusal now names the decision:

    this value is the legacy pair-map, whose type is `map` and not
    [:map :keyword :i64]. A map literal keeps the legacy representation when
    its keys are keywords and when it is empty; only :i64 and :string literals
    are retyped. Read and write it through get / assoc / contains? / dissoc,
    or build the typed map with (typed-map-new [:map :keyword :i64] ...)

The sentence is about the VALUE, not about the literal that produced it,
because `{}` reaches this refusal too and has no keyword keys to name. The
first wording said "a map literal with i64 keys keeps the legacy pair-map
representation" for `(let [m {}] (typed-map-count [:map :i64 :i64] m))`,
which is false of that program in two ways at once.

The code (`:kotoba.error/subset-reject`) and the ex-data
(`:kotoba.error/expected` / `:kotoba.error/actual`) are unchanged —
`infer-absent-parameter-types` reads the types from there rather than parsing
the message.

**Byte identity holds.** `typed-map-key-types-test`'s two byte-identity
controls (normalized HIR and KIR of two keyword-keyed programs) pass
unchanged, and a keyword-keyed program compiled with the pinned sema and with
this one produces the same `.wasm`: `5425eaca8fa79e0e…`, returning 4.

## What is pinned

`test/kotoba/compiler/malformed_type_argument_test.cljk`, in both lists of
`run-tests.cljk`. 13 tests / 49 assertions.

Before (the three tests that call `internal-failure!` cannot exist before it
does, so they are excluded from the before-run): JVM **exit 1, 10 tests / 38
assertions, 21 failures**; nbb **10 tests / 38 assertions, 25 failures**.
After: **exit 0, 13 tests / 49 assertions, 0 failures** on both.

Full suites after: JVM **318 tests / 1452 assertions, 0 failures, exit 0**;
nbb **163 tests / 522 assertions, 0 failures, exit 0**.

The last test is the evidence floor. `scanned` must reach 2000 or the sweep
fails: a sweep that measured nothing would otherwise report the same clean
answer as a sweep that measured everything.

## What this does not do

The `internal-failure!` wrapper is installed on the three per-expression
passes. Anything that throws OUTSIDE them — the reader, the namespace and
schema walks in `analyze*`, the record/multimethod/defdesugar expanders —
still reaches `kotoba.sema/analyze` bare, and the CLI will still say
`internal compiler error` with `:kotoba/internal-error` for it. The sweep
above cannot see those, because it can only reach them through a declared
type argument, and every one of those now refuses first.
