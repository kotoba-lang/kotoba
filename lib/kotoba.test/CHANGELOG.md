# Changelog

All notable changes to kotoba-lang/test are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [0.3.0] - 2026-09-23

### Added

- `kotoba.test`: a clojure.test-compatible surface — `deftest` `is`
  (`thrown?` / `thrown-with-msg?`) `are` `testing` `use-fixtures` `async`
  `run-tests` `successful?` `report` — forwarding to the host runner so a
  `clojure.test` → `kotoba.test` rewrite is discovered and counted by the
  repo's existing runner (`kbb -M:test`). Self-verified by
  `kbb -M:compat-selftest` (planted failures must make the runner exit
  non-zero with exact counts).
- `nbb.edn` (the kbb engine reads `:deps` there), so `kbb -M:test` runs
  this repo's suites.

### Changed

- `kotoba.test/run-tests` is now clojure.test's `run-tests`. The registry
  runner it used to re-export (0 callers in the workspace) is
  `kotoba.test/run-registered-tests`.

## [0.2.0] - 2026-09-06

Added a `deftest`/`is`/`testing`/`are`/`run-tests` unit-testing layer
alongside the existing property-testing layer (purely additive), making
this repo the documented `clojure.test` successor named in
`manifest/dependency-substitution.edn` (com-junkawasaki/root), per
`adr-2809061500-clojure-namespace-to-kotoba-stdlib`.

### Added

- `deftest` / `is` / `testing` / `are` / `run-tests` / `run-tests-report`
  in `kotoba.lang.test`. `is` special-cases `(= expected actual)` (reports
  both separately on failure) and `(thrown? ExClass body)` (pass/fail/error
  three-way). `are` is a small `let`-based reimplementation, not a port of
  `clojure.template/do-template`.
- `test/kotoba/lang/test/selftest_negative.cljk`,
  `selftest_positive.cljc`, `selftest_run.cljc`, and the nbb entry
  `selftest.cljk` / JVM alias `:selftest`: a self-verification harness that
  asserts (not eyeballs) the exact test/pass/fail/error counts for a
  deliberately-mixed suite and an all-passing suite, on both JVM and nbb.
- `.clj-kondo/config.edn`: `:lint-as` mappings onto the `clojure.test`
  equivalents clj-kondo already understands, plus an `:unresolved-symbol`
  exclusion for `thrown?`.

### Not implemented (documented, not silently approximated)

- `thrown-with-msg?`, `use-fixtures`, `:test` var metadata, the `report`
  multimethod / custom reporters, test selection by var (only by
  namespace), and expected/actual splitting for `(is (= a b c ...))` with
  more than two operands. See README.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.test — property testing (PRNG, generators, quickcheck, shrinking).

### Added

- Initial library surface, tests, and CI.
