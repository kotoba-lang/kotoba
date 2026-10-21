# kotoba-lang/error — `kotoba.lang.error`

The host's ex-info exception class under a kotoba name, so that `.cljk`
sources stop spelling the JVM class name `clojure.lang.ExceptionInfo` to
catch, test for, or assert on an `ex-info`.

```clojure
(require '[kotoba.lang.error :as err])

(try (f) (catch err/ExceptionInfo e (ex-data e)))       ; was clojure.lang.ExceptionInfo
(is (thrown? err/ExceptionInfo (f)))
(is (thrown-with-msg? err/ExceptionInfo #"bad" (f)))
(err/ex-info? x)                                         ; was (instance? clojure.lang.ExceptionInfo x)
```

| var | what it is |
|---|---|
| `ExceptionInfo` | the host class itself — `clojure.lang.ExceptionInfo` on the JVM, `cljs.core/ExceptionInfo` on the kbb engine / ClojureScript |
| `ex-info?` | `(instance? ExceptionInfo x)` — true exactly for ex-info instances, on every host |

## Why a new repository

Measured 2026-09-25 over the checked-out `.cljk` sources of the workspace:
`clojure.lang.ExceptionInfo` is named in 1,579 files across 521 repositories
(`thrown?` 1,791 sites, `catch` 1,362, `thrown-with-msg?` 1,187, `instance?`
14, reader conditionals ~160) — 97 % of every `clojure.lang.*` name in the
fleet. None of the kotoba stdlib repositories (`text`, `edn`, `spec`, `coll`,
`test`, `io`, `fs`, `process`, `bytes`, `json`, `http`, `pprint`) is about
exceptions, and nothing in the symbol index defined an ex-info predicate or
class alias outside vendored ClojureScript. It is the target of
`scripts/migrate-clojure-lang-exceptioninfo-to-kotoba-error.cljk`
(com-junkawasaki/root).

## Boundary — where the var works and where it does not

- **kbb engine (SCI) and ClojureScript:** the class position of `catch`,
  `thrown?` and `thrown-with-msg?` is an evaluated expression, so
  `err/ExceptionInfo` works there and catches exactly what the old clause
  caught (tests below, both directions).
- **JVM Clojure:** the compiler resolves a catch class as a class literal at
  compile time. `(catch kotoba.lang.error/ExceptionInfo e ..)` is
  `Unable to resolve classname: kotoba.lang.error/ExceptionInfo` (measured,
  Clojure 1.12.1 / JDK 21). `.cljk` is loaded only by the kbb engine
  (ADR-2609111700), which is what this namespace serves; a JVM `.clj` /
  `.cljc` source keeps `clojure.lang.ExceptionInfo` (or a reader
  conditional) in catch position. `ex-info?` and `ExceptionInfo` as a VALUE
  work on the JVM too (the oracle below loads this namespace there).
- **Not `(some? (ex-data e))`.** That is a different question: on
  ClojureScript `(ex-info msg nil)` keeps nil data (the JVM stores `{}`), so
  it disagrees with the class test. The tests pin the disagreement.

Nearest repositories: `kotoba-lang/test` (`kotoba.test`, whose `is` forwards
`thrown?` to the host — this repo only supplies the class) and
`kotoba-lang/org-babashka-nbb` (`nbb.jvm`, the kbb engine's JVM-compatibility
scaffolding that maps the spelling `clojure.lang.ExceptionInfo` onto the same
class so un-migrated sources still run; this repo is what they migrate to).

## Verify

```sh
kbb -M:test
```

`test/kotoba/lang/error_test.cljk` compares `ex-info?` with
`(instance? clojure.lang.ExceptionInfo x)` over a corpus of ex-infos and
non-ex-info values, catches through `err/ExceptionInfo` in both directions
(an ex-info is caught, a host `Error` falls through to the next clause), and
runs `thrown?` / `thrown-with-msg?` on it. Two mutants fail it: `ex-info?` as
`(some? (ex-data x))` (3 failures) and `ExceptionInfo` bound to the host's
base `Error` class (9 failures). JVM oracle (Clojure 1.12.1, JDK 21, a
`.cljc` copy): `ex-info?` agrees with `instance?` on 10 / 10 values,
`ExceptionInfo` is identical to `clojure.lang.ExceptionInfo`, and the catch
refusal above is reproduced.

## License

Apache-2.0.
