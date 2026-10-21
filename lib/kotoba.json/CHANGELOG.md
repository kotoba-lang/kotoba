# Changelog

All notable changes to kotoba-lang/json are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased]

### Added

- `kotoba/json_scalar.kotoba` — the first `.kotoba` port in this repo.
  `json-string-field` reads the string value of a top-level object member
  inside a Kotoba guest, returning `[:option :string]` and requiring zero
  capabilities. This unblocks the limitation `amu/runtime/http-service.mjs`
  names in its header ("No structural JSON parsing *inside* the guest ...
  once `kotoba-lang/json` has a `.kotoba` port, use that"). It is one
  operation, not a port of `decode`. See ADR-2608292330.
- `scripts/kotoba_test.cljk` — runs `test/kotoba/*.kotoba-part` through amu's
  official `amu test` harness, so all 23 cases run on `:jvm-kir`, `:js` and
  `:wasm` (69 rows). Exits 2, not 1, when the suite could not be run.

### Known limitations (measured, not chosen)

- `\uXXXX`, `\b` and `\f` escapes are refused (return none) rather than
  decoded. `\u` needs a code-point → string constructor, which the compiler
  frontend does not have; `\b` and `\f` cannot be *written* in `.kotoba`
  source at all — the reader rejects a file containing those literals. None
  of the three is a safety constraint.
- Top-level string-valued members only. A full `decode` needs a recursive
  JSON value, which is qualified on three backends but not on native.
- Input size is bounded by compile-time `--fuel`, ~1 unit per input byte.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.json — pure encode/decode JSON.

### Added

- Initial library surface, tests, and CI.
