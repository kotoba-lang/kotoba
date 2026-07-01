# Rust Crate Migration

Status: legacy Rust workspace removed from `kotoba-lang/kotoba`.

The repository default is now CLJC/EDN-first:

- `kotoba-lang/kotoba-lang` owns the public CLI contract and language surface.
- `bin/kotoba-clj`, Homebrew, and npm launchers delegate to that CLJC authority.
- Default CI no longer installs Rust or runs Cargo gates.
- Historical Rust crates and server deployment assets are available only through
  git history.

## Rule For New Work

New protocol, CLI, database, deploy, git/rad, or language behavior must land
first as a CLJC/EDN contract. Native adapters can be added later only when they
host that contract and do not become the semantic authority.

## Follow-up Migration Targets

1. Move remaining historical ADR details into owner repos as CLJC contracts land.
2. Keep `kotoba-lang/kotoba` focused on launchers, packaging, docs, and SDK
   fixtures.
3. Avoid reintroducing Cargo or Rust CI into the default repository path.
