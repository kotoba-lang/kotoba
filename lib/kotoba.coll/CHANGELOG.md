# Changelog

All notable changes to kotoba-lang/coll are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased]

### Added (2026-09-24, ADR-2609241200 count-gated codemod waves)

- `union`, `intersection`, `difference`, `map-invert` under clojure.set's own
  names, transcribed from ClojureScript's clojure/set.cljs (what `clojure.set`
  is on the kbb engine): same value, collection type, order and nil handling.
  `set-union`/`set-intersection`/`set-difference` keep their own (different)
  meaning. Oracle: `test/kotoba/lang/coll_clojure_oracle_test.cljk`.

### Fixed

- `walk` (and so `prewalk`/`postwalk`/`*-replace`/`keywordize-keys`/
  `stringify-keys`) rebuilds a map entry as a real map entry, not a 2-vector:
  `(map-entry? x)` inside the walk function is now true, as under clojure.walk.

`clojure.set`/`clojure.walk` gap-fill, per
adr-2809061500-clojure-namespace-to-kotoba-stdlib (com-junkawasaki/root).

### Added

- `clojure.set` coverage: `subset?`, `superset?`, `select`, `project`,
  `rename-keys`, `rename`, `index`, `join` (2-arg natural join and 3-arg
  explicit-key-mapping join).
- `clojure.walk` coverage: genuinely unbounded `walk`, `prewalk`,
  `postwalk`, `prewalk-replace`, `postwalk-replace` — new, separate
  functions alongside the existing (unchanged) `bounded-prewalk`/
  `bounded-postwalk`, not a widening of them. See README's "Tree
  walking" section for why the two pairs are permanent and parallel,
  not one superseding the other.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.coll — portable collection helpers (map-vals, deep-merge, index-by, assoc-some).

### Added

- Initial library surface, tests, and CI.
