# SBOM and SLSA Provenance

Status: proposed baseline
Date: 2026-07-01

## Purpose

Kotoba's package model uses CIDs, repo RIDs, signed manifests, and deterministic
components. SBOM and SLSA/in-toto provenance make those claims consumable by
external security programs.

## Required Release Artifacts

Each release candidate should produce:

- SBOM for Rust crates;
- SBOM for Clojure/ClojureScript dependencies;
- SBOM for npm/web assets where present;
- list of Wasm components with source CID, manifest CID, component CID, and
  compiler version;
- SLSA/in-toto provenance for release build;
- signed release security note.

## SBOM Minimum Fields

| Field | Requirement |
|---|---|
| package name | canonical package or crate name |
| version | source version or commit |
| supplier | repo/org identity where known |
| dependency relation | direct/transitive/build/dev/runtime |
| digest | package digest or source tree CID |
| license | detected license |
| vulnerability status | linked VEX or triage state when available |

## Provenance Minimum Fields

- builder identity;
- source repository and commit;
- source tree CID where available;
- build command or workflow id;
- compiler/toolchain versions;
- dependency lock digests;
- produced artifact digests and component CIDs;
- signing identity;
- timestamp.

## SLSA Target

| Phase | Target |
|---|---|
| M0 | manual SBOM and release note |
| M1 | automated SBOM in CI |
| M2 | provenance statement attached to artifacts |
| M3 | signed provenance with isolated builder |
| M4 | policy rejects release without SBOM/provenance |

## Kotoba-Specific Requirements

- Wasm component CID must be in provenance.
- Package manifest CID and lockfile digest must be in provenance.
- Safe-build policy CID must be in provenance for executable components.
- Release note must list any unsigned/classical-only/PQC-incomplete artifacts.

