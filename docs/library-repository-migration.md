# Standard-library repository consolidation

The 2026-10-21 owner decision extends the coll/spec/json pilot. Standard-library
source belongs in `kotoba-lang/kotoba`, under project IDs starting with `kotoba.`.
Amu and independent execution/authority owners retain their repositories.

The first extension adds `kotoba.set`, `kotoba.walk`, `kotoba.string`,
`kotoba.time`, `kotoba.bytes`, `kotoba.pprint`, and `kotoba.error`. Their complete
same-family definition closures are bundled: 114 additional source repositories,
175 origins and 780 imported files across all ten libraries. Source namespace
APIs remain unchanged; for example, the `kotoba.error` package exports the
existing `kotoba.lang.error` namespace. Package IDs do not rewrite namespaces.
The old repository coordinates remain exact catalog aliases.

The launcher, SCI configuration and portable library project consume bundled
support libraries through `:local/root`. Other consumers' immutable Git pins
remain unchanged. Each imported subtree retains licenses, tests, original
commit/tree and file digests, modes, and explicit local-change records. Existing
`.kotoba` implementations and oracle fixtures are retained. This is source
consolidation with portable compatibility coverage, not new native qualification
or a signed subtree release.

## Inventory and boundaries

[The org inventory](library-repository-inventory.json) records 2,792 repositories
observed on 2026-10-21, with 2,754 public repository names. Non-public details are
omitted. Its categories are triage, not semantic qualification or archive proof.

- Standard libraries with coordinated maintenance belong in the monorepo.
  Definition identity and package release identity remain independent of Git
  placement. A single function does not require a separate repository.
- Amu, kototama, aiueos, osaho, ABI, language/compiler contracts, neutral core
  contracts, security authorities and protocol owners retain their boundaries.
- Apps retain their product, release and deployment boundaries. The common
  browser execution/consent contract does not change.
- External API bindings and protocol adapters require the registry/adapter
  review tracked in JUN-69. A reverse-domain repository name alone does not
  justify moving it into the standard library.
- Other repositories require an ownership and dependency review before moving.
  Unreviewed is not obsolete, and inactivity is not archive evidence.

The next standard-library review covers text/test/EDN compatibility readers,
I/O/process adapters, async/scheduler/store, numeric and formatting helpers.
These have broader bootstrap, host-effect or state boundaries and need their
own source/consumer tests. `math` remains separate because its current source
tree has no LICENSE; no license is invented during import.

## Archive criteria

[The reviewed retirement inventory](../lib/repository-migrations.json) binds each
imported repository to its destination and reviewed default commit. Before
archiving, the operator verifies:

1. The destination is merged into main, its CI succeeds, and public import/CLI
   readback loads the bundled implementation with canonical IDs and aliases.
2. All current default `src/`, `test/`, and `kotoba/` files are integrated with
   byte/mode equivalence or an explained, hashed local adjustment. Importing an
   older pin without checking current source is insufficient.
3. Open issues/PRs, all remote branches, local branches, WIP and stashes are
   reviewed. Unknown ancestry, new source or novel work holds that repository.
4. Default/branch state and local WIP are rechecked immediately before the
   GitHub operation; any change holds the repository. The result is read back.

At review, `json` and `bytes` have unintegrated branches. Their source is
bundled, but their repositories remain writable. The untracked Finder metadata
in the `set-rename-keys` checkout is reviewed as non-source data and preserved
locally. The remaining 173 repositories are eligible only after the main
verification gate. The inventory is an eligibility record, not a claim that
the remote operation has already occurred. Actual archive/readback evidence is
recorded in [JUN-195](https://linear.app/com-junkawasaki/issue/JUN-195).

Archive is preferred over deletion: it preserves source history, tags, releases,
and immutable Git dependencies used by existing consumers. Repository pins and
signed package locks are not rewritten. Source authority for further bundled
development moves to the monorepo; the original repositories remain readable.
Local checkouts, branches, stashes, worktrees and west registrations are retained.
No fleet-wide `west update` or manifest regeneration is part of this migration.

## Verification

`node scripts/check-libraries.mjs` checks imported bytes, licenses, modes,
local changes, portable test inventory and reviewed default-source equivalence.
`node scripts/test-libraries.mjs` executes the portable suites with JVM bootstrap
blocked, including the 17,338-case bytes oracle. Public CLI tests exercise all
catalog aliases and actual calls through the seven additional package IDs,
asserting that each loaded source is inside its monorepo subtree.
