# Rust Crate Migration

Status: legacy Rust workspace removed from `kotoba-lang/kotoba`.

The repository default is now CLJC/EDN-first:

- `kotoba-lang/kotoba-lang` owns the public CLI contract and language surface.
- `bin/kotoba-clj` and Homebrew launchers delegate to that CLJC authority.
- Launcher source plans are passed as data and reflected into delegated argv,
  including explicit `.cljc` reader targets.
- Selfhost data that used to live under Rust crates now belongs to
  `kotoba-lang/kotoba-selfhost-contracts` under
  `resources/kotoba/selfhost/*.edn` and is loaded, listed, and checked by the
  CLJ launcher as data.
- Default CI no longer installs Rust or runs Cargo gates.
- Historical Rust crates and server deployment assets are available only through
  git history.

## Rule For New Work

New protocol, CLI, database, deploy, git/rad, or language behavior must land
first as a CLJC/EDN contract. Native adapters can be added later only when they
host that contract and do not become the semantic authority.

Analyzer classification tables, evidence contract values, and shell capability
catalogs should be EDN resources first. Do not reintroduce Rust source or Cargo
build steps to own these values.

Current selfhost resources are owned by `kotoba-lang/kotoba-selfhost-contracts`:

- `safe_analyzer_facts.edn`
- `aiueos_provider_catalog.edn`
- `shell_evidence_profile.edn`
- contract seeds for plugin, runtime, SDK, release, release target, signing,
  submission, app components, native host, compatibility, updater, updater
  channel, updater UI, and updater lifecycle.

Current launcher checks:

```sh
bin/kotoba-clj selfhost list --json
bin/kotoba-clj selfhost check --json
```

## Remaining After Current Wasm ABI Work

The current CLJC-owned Wasm slice covers deterministic MVP emission,
pointer+length provider imports, buffer writeback, memory growth, checked bump
allocation, integer result records, explicit `i64` `main` results, `^:i64`
params/locals for direct calls, an `i64 -> i64` host ABI signature, and an
`i32 -> i32` indirect-call table slice. The launcher also has a real
native-host process runner for mobile and desktop targets, plus a macOS
clipboard provider backed by `pbcopy` and `pbpaste`. Shell adapter authority has
now moved to `kotoba-lang/shell`; `kotoba-lang/kotoba` no longer exposes a shell
shim and keeps only the language/runtime conformance consumer surface. The
remaining migration is narrower and should stay out of Rust in this repository:

- allocator behavior beyond the current checked bump allocator;
- additional target-specific native shell providers behind the external host
  runner.

## Follow-up Migration Targets

1. Move remaining historical ADR details into owner repos as CLJC contracts land.
2. Keep `kotoba-lang/kotoba` focused on launchers, packaging, docs, and SDK
   fixtures.
3. Avoid reintroducing Cargo or Rust CI into the default repository path.
