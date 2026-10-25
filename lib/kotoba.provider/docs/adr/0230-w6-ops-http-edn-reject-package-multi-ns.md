# ADR 0230: T8.3 multi-ns project body for http-edn-reject-package Component

- Status: Accepted
- Date: 2026-08-01
- Depends: compiler ADR 0192 (`b94cad96`); kotoba-component peel monomorph
  forwards (`b11e945b`); ADR 0226–0228

## Context

Progress gm closed the multi-file Component CLI gate but honesty noted the
real HTTP reject kit was still a single admission skeleton. link-source
monomorph wraps root exports as pure forwards to private helpers, which
broke `:http-edn-reject-package` role classification until peel landed.

## Decision

1. Split reject-path EDN kit into multi-ns project under
   `resources/kotoba/lang/wasm-packages/src/http-edn-reject-project/`:
   - `kotoba.http.edn-headers` — empty / append / names-add
   - `kotoba.http.edn-request` — request
   - `kotoba.http.edn-result` — result ok/err
   - `kotoba.http.edn-reject-package` — root re-export surface
2. Re-ship **`http-edn-reject-package-component`** via
   `kotoba compile --target component --source-path <project-root>`.
3. kotoba-component peels one-level monomorph forwards for role classification
   and WAT emit (private helpers allowed).

Honesty:

- Bodies remain admission skeletons; Canonical WAT owns scans/uniqueness.
- Does **not** flip `:wasm-aot :implemented` (W4 recursive nested EDN open).

## Evidence

- kotoba-component ≥ `b11e945b` (57 tests / 635 assertions)
- Component sha `a11a96f6…`; wasmtime empty/append/prefix/names-add
- ops kit registry + sha tests

## Related

- T8.3; ADR 0192, 0221–0229
- Follow-up: W4 recursive nested EDN; only then `:wasm-aot :implemented`
