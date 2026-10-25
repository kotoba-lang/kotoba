# ADR 0228: T8.3 multi-file project Component CLI first slice (honesty)

- Status: Accepted
- Date: 2026-08-01
- Depends: compiler ADR 0192 (`b94cad96`); kit-readiness residual text

## Context

T8.3 residual listed multi-file project kit body next to W4. Compiler#465
lands `--target component --source-path` (link → compile-component). Ops
packages remain single-file admission skeletons until a kit is intentionally
split.

## Decision

1. Record compiler ADR 0192 as closing the **CLI gate** for multi-file
   Component projects.
2. Refresh kit-readiness / http-v1 residual text: multi-file CLI first slice
   landed; residual is **W4 recursive nested EDN ADT** (and optional split of
   real kit bodies onto multi-ns projects).
3. Does **not** flip `:wasm-aot :implemented`.

## Evidence

- compiler ≥ `b94cad96` (776 tests / 6254 assertions)
- No new wasm package digests in this commit (docs-only honesty)

## Related

- T8.3; ADR 0227; compiler ADR 0192
- Follow-up: W4 recursive nested EDN; only then wasm-aot :implemented
