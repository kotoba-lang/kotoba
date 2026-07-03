# Changelog

This log starts here — it doesn't attempt to reconstruct the full project
history (see `git log` for that). Entries going forward should summarize
user-visible or architecturally significant changes.

## Unreleased

- Added `clj-kondo` lint (Clojars-based, no system install) and fixed the
  handful of warnings it surfaced (unused requires/bindings/params in
  `kotoba.runtime`), so CI now runs both tests and lint.
- Documented every public function in `kotoba.runtime` (the WASM-compiling
  CLJ execution core) that previously had no docstring.
- `deps.edn` moved off `:local/root` monorepo-only paths for its base
  dependencies onto real git-SHA pins, so a fresh standalone clone builds
  without needing sibling checkouts (the old paths only resolved inside the
  west monorepo layout).
- Dropped the Charter Compliance Rider; the project is licensed as plain
  Apache-2.0.
- README refreshed to describe the current CLJC-based design and drop
  stale claims from the retired Rust-era implementation.

## Earlier

Not tracked in this file. See `git log` and `90-docs/adr/` (in the
`com-junkawasaki/root` superproject) for the historical record.
