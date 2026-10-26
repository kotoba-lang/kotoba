# ADR-0018 — Nix-shaped properties, adopted; and the reproducible half of `:regulated`

- Status: accepted
- Date: 2026-08-03
- Related: ADR-0016 (content-addressed external TCB), ADR-0017 (release
  attestations), `docs/deployment-profiles.md` (`regulated`),
  `com-junkawasaki/root` ADR-2608012050

## Context

Two things were true at once and neither was written down anywhere a check
could reach.

**One.** This repository holds several properties nix is known for —
reproducible builds, a content-addressed dependency closure, digest-gated
admission, declarative deny-by-default configuration, atomic update with
rollback. It reached them from capability security and evidence gating rather
than from build purity, and the word "nix" appears nowhere in the tree.
ADR-2608012050 audited that overlap and described it as *independent arrival*.
That framing was accurate as history and wrong as policy: a property nobody has
named is a property nobody notices losing. The audit itself only happened
because someone asked.

**Two.** `docs/deployment-profiles.md` has required a "reproducible, signed,
independently verified release pipeline" for `:regulated` since it was written.
`aiueos.deployment-profile` checked the signed half. Nothing checked the
reproducible half, and
`kotoba.security.supply-chain/evaluate-reproducibility` — which exists in the
shared security package this repository already pins, and which is written to
judge exactly that — had **no caller anywhere**.

That is the third instance of the pattern ADR-0016 and ADR-0017 each removed
once: a control exists, its evaluator exists, and the evidence it consumes is a
placeholder. An evaluator with no caller is the degenerate case — the check
cannot even report a false.

## Decision

### 1. The properties are an adopted contract, checked like any other record

`qualification/build-identity.edn` names them. Each adopted property carries
its `:statement`, the `:mechanism` paths that implement it, the `:gate` paths
that enforce it, and any `:assurance-gaps`. `:non-goals` records what is
deliberately *not* taken — a store and derivation language, binary-cache
substitution, a module system for system configuration, a content-addressed
bare-metal object store, in-toto/DSSE envelopes — each with the reason, so
"we do not have that" reads as a decision and a future proposal argues against
something.

`aiueos.tcb/validate-build-identity` enforces the same rule `:tcb/external`
already lives under:

1. a property must name mechanisms, and every named path must exist;
2. a property must name a gate **or** an explicit assurance gap — neither is an
   error, because an unenforced property must not read as an established one;
3. every mechanism under `src/` must be in `:tcb/files`, so the implementation
   of a declared property cannot change without the inventory review;
4. a non-goal without a reason is an error.

The record itself is in `:tcb/files` (`:adopted-property-record`). Otherwise a
property quietly deleted from the list leaves no trace, since the checker only
inspects the shape of what it finds there — the same reason `src/aiueos/tcb.cljk`
is in the inventory it checks.

The sibling contract for the other half of this workspace's borrowed ideas —
Unison-shaped definition identity — is `kotoba-lang/kotoba-lang`'s
`lang/code-identity.edn`. This file is its supply-chain counterpart.

### 2. Reproducibility evidence is computed where it can be computed

`aiueos.reproducibility` supplies the evaluator's inputs. Two are **derived
from records already kept fail-closed**, not asserted:

- `:dependencies` come from the TCB inventory's git entries, and each one's
  `:dependency/exact-fetch` is `:passed` only when the running JVM is actually
  served by that commit's checkout (`<gitlibs>/libs/<group>/<artifact>/<sha>`).
  The commit is part of the path, so presence on the classpath *is* the
  evidence of an exact fetch.
- `:local-overrides?` is measured the same way. A `:local/root` override
  replaces a dependency's git checkout on the classpath, so a pinned git
  dependency the classpath cannot account for is the override. The check cannot
  be satisfied by a declaration, because the declaration is what it disbelieves.

`fresh-clone?`, `hermetic?`, and the two artifact digests are claims about a
build environment this namespace cannot inspect. They are **required from the
caller and never defaulted to true**, for the reason `aiueos.sbom/provenance`
requires `isolated-builder?`: a default would make every local build claim the
property the document exists to establish. A test asserts that omitting them
produces `:fresh-clone` and `:hermetic-build` violations rather than a pass.

### 3. `:regulated` now checks the reproducible half — and binds it

Three keys, supplied by `aiueos.reproducibility/profile-evidence` and merged
into the evidence by `aiueos.sbom/regulated-evidence`:

- `:reproducibility-qualified?` must be `true`;
- `:reproducibility-artifact-digest` must be a `sha256:` reference;
- it must **equal `:artifact-digest`**, the digest the SBOM and provenance
  attest. Without that binding, a qualified reproduction of *something* would
  satisfy a release of something else.

`kbb -M:reproduce <source-commit> <digest-1> <digest-2> [--fresh-clone]
[--hermetic]` judges a pair of builds and exits non-zero when they do not
qualify.

## Consequences

- The reproducible half of `:regulated` is enforced rather than documented. A
  release with no reproduction is refused by name, not skipped.
- `aiueos.reproducibility` is in `:tcb/files` as
  `:release-reproducibility-authority`: it produces production admission
  evidence, which is the inventory's stated scope.
- Twelve new tests. The qualified case, the shared evaluator's verdict on this
  tree, and six fail-closed cases: an unclaimed environment, two disagreeing
  digests, a single build, a classpath that is not the pinned commit, and a
  reproduction of a different artifact.
- Removing a mechanism from `:tcb/files`, deleting a property, or adding one
  with neither gate nor gap now fails `kbb -M:tcb-check`.
- `aiueos.reproducibility` is the first namespace under `src/` to import
  `kotoba.security.supply-chain`, so `security-adoption.edn` gains the control
  namespace and the entrypoint edge. The adoption gate refused the commit until
  it did (`:unregistered-security-importers`) — worth recording because it is
  the mechanism this whole line of work is about, catching its own author: a
  new edge into a security control cannot be added without the record of that
  edge moving in the same commit.

## Not done

- **The release-media second digest.** The guest fixtures are byte-compared by a
  gate that runs (`scripts/build-hvt-guest.cljk`). The release media are
  deterministic under `SOURCE_DATE_EPOCH`, but no job builds them twice, so the
  second digest exists only when a caller supplies it. Recorded as
  `:release-media-second-build-not-produced` on the `:reproducible-build`
  property rather than left unmarked.

  This is the same blocker ADR-0017 names and for the same reason: the only job
  that builds release media provisions no JDK, and `.github/workflows/` cannot
  be edited by a token without the `workflow` scope. The exact YAML is in
  ADR-0017. Once it lands, `-M:attest` and `-M:reproduce` both become reachable
  from the same job — the second invocation of the build script is the second
  digest.

- **The `java.base` floor.** `:minimum-version 25` and the runner's temurin 21
  still disagree, still recorded, still an owner decision. The gate added in
  ADR-0016 keeps the record honest either way.

- **In-toto/DSSE** and **git's SHA-1 content addresses** remain as ADR-0016 and
  ADR-0017 left them, now with their reasons in `:non-goals` and
  `:assurance-gaps` where a reader of the property record will find them.
