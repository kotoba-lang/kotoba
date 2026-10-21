# Changelog

All notable changes to kotoba-lang/fmt are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased]

### Added

- `pprint` / `pprint-str` — the `clojure.pprint`-shaped entry points for the
  existing `format-str` emit engine, aimed at human-facing value inspection
  rather than source-text canonicalization. Part of
  `adr-2809061500-clojure-namespace-to-kotoba-stdlib` (com-junkawasaki/root),
  which named `clojure.pprint` (lowest-usage of the eight target namespaces)
  as a gap this repository was judged close enough in spirit to fill. See
  README's "pprint / pprint-str" section for the exact covered subset and
  the deliberate omissions (no column-alignment, no custom dispatch/
  `print-method` extension, no `cl-format`, no `print-length`/`print-level`
  truncation).

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.fmt — deterministic EDN formatter (canonical whitespace/indentation).

### Added

- Initial library surface, tests, and CI.
