# ADR - Repository boundaries and extraction policy

- **Status**: Accepted
- **Date**: 2026-07-15
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

Keep `kotoba-lang/kotoba` as the apex repository for the Kotoba language. It
owns the language contract and the integration needed to evolve that contract:

- language profile, conformance, admission gates, and compiler implementation
- `kotoba` CLI and integration paths such as `kotoba -e` and `kotoba wasm`
- the reference compiler/runtime while those implementations are co-versioned
  with the language contract
- generic examples and fixtures that verify the substrate

The bootable aiueos product belongs to `kotoba-lang/aiueos`. Firmware, loader,
kernel, drivers, images, hardware evidence, browser-desktop integration, and OS
release policy must not remain owned by the language apex. The current
`os/aiueos` tree is a migration source only and remains temporarily so its
working CI is not destroyed before the destination commit is pinned and
verified. See `ADR-aiueos-boot-kernel-os-integration.md`.

Reusable libraries are independently versioned repositories in the
`kotoba-lang` organization, not permanent subtrees of a growing monorepo. A
west manifest composes their pinned revisions for development, integration,
and releases. West is the checkout/composition authority; it does not transfer
source ownership back to this repository or allow floating branch references
in release manifests.

Use the following extraction rules:

- `kotoba-lang/aiueos`: owns the complete OS product, including all content
  currently under `os/aiueos`. After the destination commit is pinned and
  content-verified, this repository retains only freestanding language/compiler
  contracts and cross-repository conformance fixtures.
- repo-per-library: a reusable library with a stable public contract and an
  independent release gate receives its own `kotoba-lang/<library>` repository.
  Consumers use published identities or west-pinned revisions, never an
  unversioned workspace-only path as a release dependency.

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
- Its CI can run without relying on unpinned workspace-only path dependencies.
- At least one external consumer or independent release cadence exists.
- The destination repository has a named owner and release gate.
- `kotoba-lang/kotoba` retains only a narrow compatibility fixture, adapter, or
  integration test for that surface.

## Migration order

1. Record ownership in docs and ADRs before moving files.
2. Copy `os/aiueos` and its boot/release CI to `kotoba-lang/aiueos`, preserve
   executable bits, and make the destination CI pass independently.
3. Pin the accepted aiueos destination commit in the organization west
   manifest. Run `scripts/finalize-aiueos-extraction.sh` against a checkout at
   that exact commit; only then remove the duplicate source tree and its CI job.
4. Retain in the language/compiler repositories the target triples, object
   format and relocation contracts, freestanding ABI, entry-shim contract, and
   positive/negative compiler fixtures. Do not retain a kernel or device model
   as a compiler fixture.
5. Mirror or subtree `crates/kotoba-lang` plus `docs/lang` into
   `kotoba-lang/kotoba-lang` only after an external language-profile consumer
   exists.
6. Keep `kotodama-host`, `kotodama-mcp`, `kotodama-cells`, `kotodama-py`,
   `kotodama-holochain`, and `inference` as the canonical homes for extracted
   kotodama surfaces.
7. Drain any remaining product/domain code by moving domain code to
   `etzhayyim/com-etzhayyim-*`, AT Protocol app code to
   `gftdcojp/app-aozora`, and operational code to `kotoba-lang/murakumo`.
8. Decide packaging for the public `kotoba` crate/CLI after the repository
   boundaries are clean; do not create a separate CLI repository unless release
   cadence proves it necessary.

## Consequences

- `kotoba-lang/kotoba-lang` is appropriate as a language-contract repository,
  but not yet as the source of truth while the compiler/runtime and conformance
  suite are still co-evolving in this workspace.
- `kotoba-kotodama` is no longer a deep implementation subtree in `kotoba`; its
  major surfaces are separate repositories with redirect READMEs left behind.
- The organization west workspace becomes the integration point. This
  repository remains authoritative only for language/compiler surfaces.
- During migration, `os/aiueos` remains duplicated solely to preserve a green
  source gate. Its presence does not imply continuing ownership.
