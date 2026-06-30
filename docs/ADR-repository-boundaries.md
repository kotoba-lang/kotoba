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
- `kami-engine`: owns reusable rendering, input, text, devtool, and UI engine
  crates. Keep only thin WIT/component fixtures and integration tests in
  `kotoba`.
- `kotoba-lang/kotodama-host`: owns the TypeScript host SDK, Rust config crate,
  desktop host scaffold, and KAMI host integration. The KAMI host may depend on
  sibling `kotoba-lang/kami-engine` crates as explicit path dependencies during
  local development.
- `kotoba-lang/kotodama-mcp`: owns MCP server packages and MCP facade code.
- `kotoba-lang/kotodama-cells`: owns cell manifests and generated cell package
  inventory.
- `kotoba-lang/kotodama-py`: owns the Python worker layer, SQLMesh models,
  primitives, and Python project-specific worker code.
- `kotoba-lang/kotodama-holochain`: owns the Holochain runtime and DNA/zome
  scaffolding.
- `kotoba-lang/murakumo`: owns hosting, placement, fleet, gateway, deployment,
  model operations, and operational workers. Generic language/runtime
  capability interfaces may remain in `kotoba`; operational implementations and
  deployment state move to `murakumo`.
- `etzhayyim/com-etzhayyim-*`: owns domain actors, cells, business logic, and
  non-substrate `.cljc` programs.
- `gftdcojp/app-aozora`: owns AT Protocol actors, PDS/AppView handlers, XRPC
  application surfaces, and app-specific browser flows.
- `crates/kotoba-kotodama`: remains a legacy redirect root inside this workspace.
  It must contain only redirect READMEs, narrow compatibility fixtures, and
  historical migration notes.

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
3. Keep `kotodama-host`, `kotodama-mcp`, `kotodama-cells`, `kotodama-py`,
   `kotodama-holochain`, and `inference` as the canonical homes for extracted
   kotodama surfaces.
4. Drain any remaining product/domain code by moving domain code to
   `etzhayyim/com-etzhayyim-*`, AT Protocol app code to
   `gftdcojp/app-aozora`, and operational code to `kotoba-lang/murakumo`.
5. Decide packaging for the public `kotoba` crate/CLI after the repository
   boundaries are clean; do not create a separate CLI repository unless release
   cadence proves it necessary.

## Consequences

- `kotoba-lang/kotoba-lang` is appropriate as a language-contract repository,
  but not yet as the source of truth while the compiler/runtime and conformance
  suite are still co-evolving in this workspace.
- `kotoba-kotodama` is no longer a deep implementation subtree in `kotoba`; its
  major surfaces are separate repositories with redirect READMEs left behind.
- The current repository remains the integration point until extracted surfaces
  have independent tests and consumers.
