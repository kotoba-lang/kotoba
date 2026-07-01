# ADR: Kotoba package references, CID locks, and capability-safe dependencies

**Status**: accepted-contract / initial CLI enforcement landed
**Date**: 2026-06-30
**Related**: `ADR-kotoba-lang-profile.md`, `ADR-safe-capability-language.md`, `ADR-kotoba-rad-git-sovereign-repo.md`

## Context

`kotoba-lang/kotoba-lang` now owns the standalone language-level package
contract:

- `lang/package.edn`
- `examples/package-manifest.edn`
- `examples/kotoba.lock.edn`

This repository owns the implementation surfaces that must eventually consume
that contract: `kotoba wasm safe-build`, `kotoba-cli`, `kotoba-rad`,
`kotoba-git`, and the runtime/capability gate.

CID pinning gives byte integrity. It does not, by itself, say who was allowed to
publish a package name/version, whether a ref is still authorized, or whether a
dependency may request graph, model, filesystem, network, clock, random, or
secret capabilities.

The language contract also defines package boundary kinds. Optional integrations
must not be hidden behind a vague `core` split; they should be explicit adapter
packages or explicit build aliases. Data-shape dependencies should be schema
contract packages pinned by CID like code.

## Decision

Safe Kotoba dependency resolution must use the package contract from
`kotoba-lang/kotoba-lang`, not ad hoc name/version resolution.

A dependency is conforming for safe execution only when it is locked with:

- package name and package version;
- repository identity CID (`repo-rid`);
- package manifest CID;
- source tree CID;
- Git commit id when the package is mirrored through Git;
- publisher DID signatures;
- explicit capability grant set;
- locked transitive dependencies;
- optional reproducible component CID.

Name plus semver without repo RID, signature, and CID pins is non-conforming for
safe Kotoba execution.

Package kind is part of the dependency contract:

- `:library` for pure code/data APIs with no implicit host capability;
- `:adapter` for integrations that bind two or more libraries or contracts;
- `:schema-contract` for Lexicon, EDN IR, WIT, or similar data contracts;
- `:tool` for CLI/development tools;
- `:component` for executable or Wasm components.

For example, the slides family should be represented as responsibility-named
packages such as `kotoba-lang/slides`, `kotoba-lang/slides-office`, and
`kotoba-lang/slides-svgraph`, with `app.kotoba.slides.deck`,
`app.kotoba.office.graph`, `app.kotoba.officeStyle.styleIr`, and
`app.kotoba.svgraph.presentation` represented as locked schema-contract
surfaces where the dependency is only a data shape.

## Implementation Responsibilities

`kotoba-cli`:

- reject safe-build dependencies that are version-only, unsigned, not CID-pinned,
  or grant capabilities outside the caller policy;
- expose package-contract errors separately from compiler errors;
- eventually read `kotoba.lock.edn` as the supply-chain counterpart to
  safe-build policy EDN.
- preserve dependency `:dep/kind`, `:dep/provides`, and `:dep/consumes` metadata
  so adapter and schema-contract boundaries can be audited separately from
  runtime capability grants.

Initial landed slice: `kotoba wasm safe-build --package-lock <kotoba.lock.edn>`
parses the lockfile, requires repo RID / tree CID / manifest CID / signer DID,
and rejects dependency capability grants that exceed the caller policy before
compilation emits bytes.

`kotoba-git` / `kotoba-rad`:

- resolve repo RID and signed journal/tag records to Git commit and tree CID;
- verify that every reachable Git object has a `:git.object/cid` bridge;
- treat registry records as indexes, not roots of trust.

`kotoba-runtime` / host layers:

- bind only capabilities granted by both the safe-build policy and the package
  lock;
- keep dependency capabilities deny-by-default.

`kototama`:

- remains a host facade. It should consume already-verified host capability
  grants (`HostCaps`) derived from policy plus lockfile, not decide package
  authority itself.

## Safety Rule

The safe-build acceptance predicate becomes:

```text
source profile conforms
and dependencies are CID-locked
and package authority is signed by current repo/registry authority
and schema contracts used as dependency boundaries are CID-locked
and requested dependency capabilities are a subset of package manifest requests
and granted dependency capabilities are a subset of caller policy
and optional integrations are selected as explicit adapter packages or aliases
and emitted wasm import surface is a subset of the final grant set
```

## Maturity

- `M0`: this implementation ADR.
- `M1`: consume the package contract shape in implementation tests.
- `M2`: positive fixtures for package manifest and lockfile.
- `M3`: negative fixtures for missing CID, bad signature, bad repo RID, and
  excessive capability grant.
- `M4`: `kotoba-cli` package-contract runner.
- `M5`: `kotoba wasm safe-build` enforces package locks.
- `M6`: signing, revocation, and package compatibility policy wired to
  `kotoba-rad`.
