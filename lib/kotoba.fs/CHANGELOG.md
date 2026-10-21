# Changelog

## Unreleased

- Add a root-confined `IAsyncFilesystem` host capability using
  `CompletableFuture` on JVM and `fs.promises` on Node, with real round-trip and
  escape-refusal tests on both runtimes.

All notable changes to kotoba-lang/fs are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [Unreleased]

### Added

- `kotoba.lang.fs-host/host-filesystem` — an `IFilesystem` backed by the real
  filesystem on both runtimes (`java.nio`/`java.io` and `node:fs`), confined to
  a required `:root`, with a `:max-bytes` bound on reads and typed `ex-info`
  refusals (`:type` from `kotoba.lang.fs-host/error-types`). Separate namespace:
  requiring `kotoba.lang.fs` still pulls in no host filesystem, and a test
  enforces that.
- `kotoba.lang.fs-host/resolve-relative` and `under-root?` — the pure path
  policy, matching `provider.scoped-fs/resolve-path`'s refusal vocabulary.
- `package.json` with `test:cljs`, so the portable suite has a named entry
  point on nbb like the sibling repos.

## [0.1.0] - 2026-07-01

Initial public release. kotoba.lang.fs — path ops + IFilesystem protocol (host-injected) + mem mock.

### Added

- Initial library surface, tests, and CI.
