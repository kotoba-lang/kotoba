# ADR - Repository boundaries and extraction policy

- **Status**: Accepted
- **Date**: 2026-06-30
- **Related**: `ADR-kotoba-lang-profile.md`, `ADR-kotoba-wasm.md`, `ADR-kotodama-cljc-num-torch-inference.md`

## Context

`kotoba-lang/kotoba` has grown from the core database and compiler substrate
into a staging area for language experiments, migration code, host SDKs,
inference work, UI/runtime experiments, and deployment operations.

That is useful while the system is still being consolidated, but it makes
ownership unclear. A repository should be split only when its public API,
release cadence, CI, and consumers can stand on their own. Splitting too early
would create path-dependency churn without a stable contract.

## Decision

Keep `kotoba-lang/kotoba` as the canonical substrate repository for now. It owns
the language/runtime/database foundation:

- language profile, conformance, admission gates, and compiler implementation
- `kotoba` CLI and integration paths such as `kotoba -e` and `kotoba wasm`
- reusable database, storage, crypto, auth, Datalog, lattice, mesh, and Wasm
  runtime crates
- generic examples and fixtures that verify the substrate

Use the following extraction rules:

- `kotoba-lang/kotoba-lang`: reserve this repo for the language contract once a
  second compiler/runtime, external package, or independent conformance suite
  needs it outside this workspace. The extractable surface is
  `crates/kotoba-lang`, `docs/lang`, language profile resources, conformance
  fixtures, and versioning/gate docs. It must not absorb storage, hosting,
  product UI, or domain actors.
- `kotoba` crate / CLI: keep it in `kotoba-lang/kotoba`. The CLI is an
  integration binary over several workspace crates, so a separate repository
  would add release overhead without a cleaner boundary. Publishing a crate or
  package named `kotoba` is a packaging decision, not a repository split.
- `kami-engine`: split to its own repository when the engine is reusable without
  the Kotoba database/language workspace. Candidate extractable code includes
  the `kotoba-kotodama` Kami host, Kami SDK/rendering/devtool/golden-test
  pieces, generated app templates, and UI verification assets. Keep only thin
  WIT/component fixtures and integration tests in `kotoba`.
- `kotoba-lang/murakumo`: owns hosting, placement, fleet, gateway, deployment,
  model operations, and operational workers. Generic language/runtime
  capability interfaces may remain in `kotoba`; operational implementations and
  deployment state move to `murakumo`.
- `etzhayyim/com-etzhayyim-*`: owns domain actors, cells, business logic, and
  non-substrate `.cljc` programs.
- `gftdcojp/app-aozora`: owns AT Protocol actors, PDS/AppView handlers, XRPC
  application surfaces, and app-specific browser flows.
- `crates/kotoba-kotodama`: remains migration-only inside this workspace until
  its reusable substrate is extracted and its domain/product/ops code has moved
  to the owners above.

## Split criteria

Before extracting code to another repository, all of these must be true:

- The extracted unit has a stable public contract and versioning policy.
- Its CI can run without relying on workspace-only path dependencies.
- At least one external consumer or independent release cadence exists.
- The destination repository has a named owner and release gate.
- `kotoba-lang/kotoba` retains only a narrow compatibility fixture, adapter, or
  integration test for that surface.

## Migration order

1. Record ownership in docs and ADRs before moving files.
2. Mirror or subtree `crates/kotoba-lang` plus `docs/lang` into
   `kotoba-lang/kotoba-lang` only after an external language-profile consumer
   exists.
3. Extract `kami-engine` once its host/runtime SDK can build and test without
   `kotoba-kotodama` path dependencies.
4. Drain `crates/kotoba-kotodama` by moving domain code to
   `etzhayyim/com-etzhayyim-*`, AT Protocol app code to
   `gftdcojp/app-aozora`, and operational code to `kotoba-lang/murakumo`.
5. Decide packaging for the public `kotoba` crate/CLI after the repository
   boundaries are clean; do not create a separate CLI repository unless release
   cadence proves it necessary.

## Consequences

- `kotoba-lang/kotoba-lang` is appropriate as a language-contract repository,
  but not yet as the source of truth while the compiler/runtime and conformance
  suite are still co-evolving in this workspace.
- `kami-engine` is the strongest candidate for a future separate repository,
  because its UI/runtime engine boundary can be independent from the Kotoba
  database and compiler.
- The current repository remains the integration point until extracted surfaces
  have independent tests and consumers.
