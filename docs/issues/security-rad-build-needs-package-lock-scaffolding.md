# Security: `rad build`/`rad export` need package-lock scaffolding after F-001

Architecture review finding: `F-001` (follow-up)
Severity: Medium
Owner: rad/tooling implementation

## Problem

`kotoba wasm emit` and `kotoba wasm run` now require `--package-lock <path>`
unconditionally (this session's F-001 fix: the package-admission gate always
runs, closing the gap where it was optional for `emit` and entirely absent for
`run`). `kotoba.rad-adapter`'s `build` step re-dispatches `["wasm" "emit" src
"--output" out]` in-process without a `--package-lock`, and `kotoba.rad-adapter`'s
`new` step does not scaffold any package-lock file for a freshly created
project. As a direct result, `rad build` (and anything downstream of it, e.g.
`rad export`) now fails every time with `:wasm/package-rejected` /
`:package/missing-lock-option`.

## Risk

Not a new safe-execution gap by itself (the opposite: it is safe-execution
correctly refusing to run rad-built cells with no admitted package input) —
but it currently makes the `rad` project lifecycle (`new` -> `build` -> `test`
-> `export`) entirely non-functional, which will push users toward finding
some other way to skip admission if this isn't fixed promptly.

## Required work

- `rad new` should scaffold a minimal, self-consistent package-lock (and
  matching manifest/trust, if the admission gate needs them) for a freshly
  created project — most likely a zero-dependency lock, since a fresh
  scaffold has no external package deps yet.
- `rad build` (`kotoba.rad-adapter`) should pass `--package-lock` (pointing at
  the scaffolded lock, or a project-configured one) when it re-dispatches
  `["wasm" "emit" ...]`.
- Add regression coverage: `rad_adapter_test.clj`'s
  `launcher-executes-rad-lifecycle-end-to-end` currently fails at the build
  step (`NoSuchFileException` on the never-produced `.wasm` output) — this
  should go back to green once the scaffolding lands.

## Acceptance criteria

- `rad new` produces a project whose `rad build`/`rad test`/`rad export`
  complete successfully without the caller manually authoring a lock file.
- `launcher-executes-rad-lifecycle-end-to-end` passes again.
- No regression to the F-001 package-admission gate itself (this must not be
  solved by weakening `wasm emit`/`wasm run`'s mandatory lock requirement).

## References

- `kotoba-lang/security/docs/architecture-review-2026-07-01.md` finding `F-001`
- `docs/issues/security-package-verification-admission-gate.md`
- `src/kotoba/rad_adapter.cljc` (`build` step)
- `test/kotoba/rad_adapter_test.clj` (`launcher-executes-rad-lifecycle-end-to-end`)
