# kotoba-lang/test

[![CI](https://github.com/kotoba-lang/test/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/test/actions/workflows/ci.yml)

**Layer 4 (tooling) of the kotoba foundational stdlib** — property-based
testing AND example-based unit testing, in one dependency-free namespace.
Consumes the sibling [`kotoba-lang/spec`](https://github.com/kotoba-lang/spec)
for generators, so **a spec is also a test generator** — the proptest /
test.check / deno.test equivalent for kotoba. No third-party deps; every
namespace is `.cljc` (JVM / SCI / ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

This repo is also the documented successor for `clojure.test` named in
[`manifest/dependency-substitution.edn`](https://github.com/com-junkawasaki/root/blob/main/manifest/dependency-substitution.edn)
(com-junkawasaki/root), per
[`adr-2809061500-clojure-namespace-to-kotoba-stdlib`](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2809061500-clojure-namespace-to-kotoba-stdlib.edn) —
the `deftest`/`is`/`testing`/`are`/`run-tests` surface below is what that
namespace was required for by far more files than any other single
`clojure.*` require in that workspace, which is also why its own pass/fail
detection is verified against deliberately-planted failures on **both** JVM
and nbb before anything else depends on it (see Verify, and
`test/kotoba/lang/test/selftest_negative.cljk`) — a defective test framework
that silently reports green on a real failure would be worse than the
`clojure.test` dependency it replaces.

## Why

`clojure.test` covers example-based tests; kotoba also needs **property tests**
that hold for *all* inputs a spec can generate. `test` provides a deterministic
PRNG, a `gen` protocol a spec implements, and `quickcheck` / `for-all` that
shrink failing cases — pure functions, no host, runs on kotoba-WASM. This makes
`kotoba-lang/test` a consumer of `kotoba-lang/spec` (the M5 milestone for spec:
an external lib depends on it).

## Property-testing surface

`kotoba.lang.test`:

- `make-rng` — deterministic PRNG from a seed (LCG, pure)
- `IGenerator` protocol: `gen` → `[value rng']`
- primitive generators: `gen-int`, `gen-bool`, `gen-element`, `gen-string`
- `quickcheck` — run a property `n` times with seeded rng; returns
  `{:pass? bool :seed :runs :smallest :shrink-depth}` on failure
- `for-all` — declarative property over bound generators
- `shrink` — integer shrinking toward zero (the default shrink strategy)
- `are-eq?` / `throws?` — small assertion helpers (unrelated to the `are` /
  `thrown?` unit-testing macros below, despite the similar names — these
  predate them and are kept as-is)

## Unit-testing surface (`clojure.test` replacement)

Also in `kotoba.lang.test`, alongside the property-testing surface above
(purely additive — neither layer touches the other):

- **`deftest`** — `(deftest my-test body...)` defines a 0-arg test function
  and registers it (under the current namespace) in a global registry, so
  `run-tests` can find it. Also `def`s `my-test` to that function, so it's
  directly callable too.
- **`is`** — `(is expr)` / `(is expr msg)` asserts `expr` is truthy.
  - `(is (= expected actual))` is special-cased: reports `expected` and
    `actual` **separately** on failure — clojure.test's single most useful
    behavior, matched here. `(is (= a b c ...))` with more than two operands
    is **not** special-cased (documented limitation, not a silent
    approximation): it's just evaluated as a plain boolean expression.
  - `(is (thrown? ExClass body...))` is special-cased: passes iff `body`
    throws an instance of `ExClass`, fails if `body` returns normally,
    errors if it throws something else. `ExClass` must be a class token the
    *host actually running the test* can resolve as a catch-clause target —
    like clojure.test's `thrown?`, this is not portable across a single
    literal spanning JVM and cljs; wrap it in
    `#?(:clj SomeException :cljs js/Error)` at call sites that need to run
    on both (see the examples below and in
    `test/kotoba/lang/test/selftest_negative.cljk`).
  - An exception thrown by `expr` itself (in the generic, non-`thrown?`
    case) is caught and recorded as an **error**, distinct from a **fail**
    — and does not stop the rest of the enclosing `deftest` from running.
  - File/line is recorded best-effort (via `&form` metadata) and printed
    when available; a miss there never affects the pass/fail/error signal
    itself.
- **`testing`** — `(testing "some context" body...)` labels `is` failures
  inside `body` with `"some context"`. Nested `testing` blocks compose,
  innermost last, joined with `" > "`.
- **`are`** — `(are [x y] (= x y) 1 1 2 2)` runs `(is (= 1 1))` then
  `(is (= 2 2))`: binds each row of trailing values to `argv`'s symbols and
  asserts `expr`. This is a small `let`-based reimplementation with the
  same observable behavior as clojure.test's `are` — **not** a port of
  `clojure.template/do-template`, so no `clojure.template` dependency is
  introduced.
- **`run-tests`** — `(run-tests)` runs every registered test; `(run-tests
  'some.ns ...)` runs only the given namespaces' tests. Prints per-
  failure/-error detail as it goes, then a summary line, then returns
  `{:test :pass :fail :error :assertions :details}`. On nbb (`:cljs`),
  calls `(js/process.exit 1)` when `(+ fail error)` is positive, so a
  calling script observes failure (a suite that fails while exiting 0 is
  worse than one that never ran). On `:clj`, no process exit is performed —
  the returned map is the contract. See also `run-tests-report`, the same
  function with the exit side effect removed, for callers (like this
  library's own self-verification harness) that need to inspect a result
  map in-process without the process exiting out from under them.

```clojure
(require '[kotoba.lang.test :as t])

(t/deftest addition-works
  (t/is (= 4 (+ 2 2))))

(t/deftest string-building
  (t/testing "join then reverse"
    (t/is (= "cba" (apply str (reverse "abc"))))))

(t/deftest division-by-zero-throws
  (t/is (thrown? #?(:clj ArithmeticException :cljs js/Error)
                 (throw #?(:clj (ArithmeticException. "boom")
                           :cljs (js/Error. "boom"))))))

(t/are [x y] (= x y)
  1 1
  2 2
  (+ 1 2) 3)

(t/run-tests)
;; prints per-failure detail (if any) + "Ran 4 tests, 6 assertions, 0 failures, 0 errors."
;;=> {:test 4 :pass 6 :fail 0 :error 0 :assertions 6 :details []}
```

### Not clojure.test's full API

Documented omissions (never silently approximated under the real function
name):

- **`thrown-with-msg?`** is not implemented. Use `thrown?` and assert the
  message yourself inside a `catch` if you need that, or check
  `ex-message`/`.getMessage` after `throws?` (the older, unrelated
  assertion helper above) returns true.
- **`use-fixtures`** (setup/teardown, `:each`/`:once`) is not implemented.
  Write setup/teardown directly in each `deftest` body (or use `testing` +
  ordinary `let`/`try`/`finally`).
- **No `:test` var metadata.** Unlike `clojure.test/deftest`, this
  `deftest` does not attach `{:test fn}` metadata to the defined var —
  tooling that discovers tests via that convention (e.g.
  `cognitect.test-runner`, most IDE "run test at cursor" integrations)
  will not find tests defined with this library's `deftest`. Discovery is
  purely through this library's own registry and `run-tests`.
- **No `report` multimethod / custom reporters.** Output format is fixed
  (see `is`'s docstring and the worked example above); there is no
  extension point to plug in a different reporter, unlike clojure.test's
  `report` multimethod.
- **No test selection by var, only by namespace.** `run-tests` accepts
  namespace symbols, not individual test vars (clojure.test's `test-vars`
  equivalent is not implemented).
- **`(is (= a b c ...))` with more than two operands** falls back to a
  plain boolean check (see `is` above) rather than clojure.test's
  multi-operand expected/actual reporting.

### Self-verification

`clj-kondo` doesn't know these macros' shapes out of the box; this repo's
[`.clj-kondo/config.edn`](.clj-kondo/config.edn) maps them onto the
built-in `clojure.test` equivalents it does understand (`:lint-as`) plus an
`:unresolved-symbol` exclusion for `thrown?` specifically (clj-kondo's
non-flagging of `thrown?` inside `is` is wired to the literal var
`clojure.test/is`, not to `:lint-as` targets of it). Consumers adopting
this library should copy or merge these entries too.

`test/kotoba/lang/test/selftest_negative.cljk` and `selftest_positive.cljc`
are **not** part of the ordinary green suite — they use this library's own
`deftest` (not `clojure.test`'s), so `cognitect.test-runner` / `cljs.test`
scanning for `clojure.test`-metadata vars find nothing there and never
report against them. `selftest_run.cljc` runs both suites via
`run-tests-report` and **asserts** (not eyeballs) the exact counts planted:
7 tests / 3 pass / 3 fail / 2 error / 8 assertions for the deliberately-
mixed negative suite, and 6 tests / 13 pass / 0 fail / 0 error / 13
assertions for the all-passing positive suite — identical on JVM and nbb.

## `kotoba.test` — the drop-in for `clojure.test` call sites

`kotoba.test` (the facade) carries a **clojure.test-compatible surface** so
that migrating a call site is a pure namespace rewrite:

```clojure
(:require [clojure.test :refer [deftest is testing are use-fixtures]])
;; becomes
(:require [kotoba.test :refer [deftest is testing are use-fixtures]])
```

Covered: `deftest` `is` (incl. `(is (thrown? C ...))` and
`(is (thrown-with-msg? C re ...))`) `are` `testing` `use-fixtures` `async`
(cljs) `run-tests` `successful?` `report` (the host multimethod object, so
`(defmethod t/report [:cljs.test/default :end-run-tests] ...)` exit hooks
keep working).

These forward to the **host** runner (clojure.test on the JVM, cljs.test on
the kbb engine), deliberately **not** to `kotoba.lang.test`'s registry: the
repo's own runner (`kbb -M:test`, which substitutes cljs.test over every
`*_test` namespace) discovers tests by `:test` var metadata and exits on
the host's counters. A suite rewritten onto `kotoba.lang.test/deftest` ran
0 tests and exited 0 (kotoba-lang/dance, 2026-09-07). Forwarding makes the
rewrite count-preserving by construction, and `kotoba.test` becomes the one
place that names the host framework.

Not covered (a migrator must refuse, not rewrite): `assert-expr`,
`do-report`, `*report-counters*`, `*testing-vars*`, `*testing-contexts*`,
`test-var(s)`, `test-ns`, `run-all-tests`, `with-test`, `set-test`,
`compose-fixtures`, `join-fixtures`, `deftest-`, and auto-resolved keywords
through the alias (`::t/default`). `run-tests` is clojure.test's; the
registry runner is `run-registered-tests`.

A consumer declares the dependency in **`nbb.edn`** (the kbb engine reads
`:deps` there; `kbb -M:test` puts no git coordinate from `deps.edn` on the
classpath).

Self-verification (`kbb -M:compat-selftest`) asserts, in-process and through
the fleet runner, that the planted suite
`test/kotoba/test/compat_negative.cljk` yields exactly 5 tests / 2 pass /
4 fail / 1 error and that `kbb -M:compat-negative` **exits non-zero**; a
copy whose `deftest` drops the `:test` metadata fails 4 of its 7 checks
(0 tests, exit 0 — the silent-green case).

## Install

```clojure
io.github.kotoba-lang/test {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.test :as pt])

;; a property: for all ints, x+x == 2*x
(pt/quickcheck (fn [x] (= (* x 2) (+ x x))) #(pt/gen-int %) :seed 42 :runs 100)
;;=> {:pass? true :seed 42 :runs 100}

;; a failing property shrinks to the smallest counterexample
(pt/quickcheck (fn [x] (pos? x)) #(pt/gen-int % [-10 10]) :seed 1 :runs 100)
;;=> {:pass? false :smallest 0 ...}
```

## Verify

```sh
kbb -M:test                                          # JVM, property-testing suite
npx nbb@1.4.210 --classpath src:test run-tests.cljk       # nbb, same suite, other runtime

kbb -M:selftest                                       # JVM, deftest layer self-verification
npx nbb@1.4.210 --classpath src:test selftest.cljk        # nbb, same self-verification

kbb -M:compat-selftest                                # kotoba.test clojure.test-compatible surface
```

Both hosts run the **same** `.cljc` suites and agree exactly:
property-testing suite `9 tests, 139 assertions, 0 failures, 0 errors`;
deftest-layer selftest `SELFTEST OK` for both the deliberately-mixed
negative suite and the all-passing positive suite.
