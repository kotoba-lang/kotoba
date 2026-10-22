# Repository catalog and workspace manifest

Start with the machine-readable [organization inventory](library-repository-inventory.json)
to find a repository's classification, owner, monorepo destination, source ID,
consumer-pin hold, GitHub metadata, canonical checkout and west registration.
Reading every repository again is unnecessary for these recorded facts.

## Current organization and local placement

The authenticated 2026-10-22 observation contains **2,669 repositories**:
2,630 public and 39 private. All 2,669 now have a valid Git checkout with the
matching GitHub remote identity at `<github>/kotoba-lang/<repo>`.
The operation cloned 42 missing repositories, recovered five canonical
checkouts and normalized eight verified old-name remote URLs.

The five original directories, file modes, hashes and broken Git metadata are
retained outside Git in the local placement evidence. Their original parent
and index could not be recovered, so their previous WIP is not described as
clean or discarded. Existing valid checkouts were not reset or bulk-pulled.
New clones have the complete commit graph with a `blob:none` filter and their
default-branch checkout; LFS objects and recursive submodules were not fetched.

GitHub reports 2,242 active and 427 archived repositories, including 23 upstream
forks. The classification table covers public repositories only:

| Recorded classification | Repositories |
|---|---:|
| Source integration or licensed-owner compatibility derivation recorded | 427 |
| Ownership review required | 773 |
| Adapter/protocol review required | 1,312 |
| Retained app, foundation, upstream-fork or owner boundary | 116 |
| License provenance hold | 2 |
| Public total | 2,630 |

The 239 dependency-pin holds are an overlapping flag, not another category.
An archive is an operation state; a classification is a placement decision or
triage record. Neither replaces the source, branch, WIP, license, consumer and
runtime evidence needed before further integration or retirement. Pending
drafts such as Kami PR #139 are not counted as merged source integration.
GitHub's primary-language field often does not recognize `.cljk`; it does not
measure Kotoba adoption or runtime qualification.

Private repository names and project details are omitted from the public
catalog. The full 2,669-row inventory is retained locally as
`repository-inventory.local-private.json` in the placement task workspace.
The public catalog exposes the private count only.

## Which catalog owns which facts?

| Resource | Purpose and authority |
|---|---|
| [Organization inventory](library-repository-inventory.json) | Repository classification, source-review snapshot, owner/destination, current GitHub metadata, local placement and manifest join. |
| [Repository migration decisions](../lib/repository-migrations.json) | Reviewed source defaults, branches, compatibility adaptations and retirement holds for imported libraries. |
| [Bundled source catalog](../lib/catalog.edn) | 25 dotted library IDs, 70 exact old-name aliases, source roots and namespace APIs. Repository identity and package identity are separate. |
| [Kotoba Registry](https://github.com/kotoba-lang/kotoba-registry/blob/main/index.json) | Installable skills and MCP definitions. It is an extension registry, not an all-repository inventory. |
| [west registration policy](https://github.com/com-junkawasaki/west-manifest/blob/main/manifest/repos.edn) | Canonical repository registrations, paths and policy. The independently owned manifest remains the writer authority. |
| [Generated west lock](https://github.com/com-junkawasaki/west-manifest/blob/main/manifest/west.yml) | Pinned checkout revisions. `fleet-db.edn`, its ledger and the signed `fleet-head.edn` record the corresponding authority state. |

The current inventory joins 2,625 organization repositories to the existing
west manifest; 44 have no current registration. Placement did not register
them, advance pins or modify a signed head. The manifest also covers other
organizations and contains historical registrations, so its raw project count
is not the current Kotoba organization count.

Catalog lookup does not grant package admission, capabilities, permission to
execute an app or approval to contact an external service. Amu and the other
execution foundations retain their separate repositories.

## Query without opening repositories

Run from this checkout, or invoke the script with an absolute path:

```sh
node scripts/repository-catalog.mjs summary
node scripts/repository-catalog.mjs show kotobase-engine-lsm
node scripts/repository-catalog.mjs list --classification ownership-review-required
node scripts/repository-catalog.mjs list --owner kotoba-lang/kotoba
node scripts/repository-catalog.mjs list --held
node scripts/repository-catalog.mjs list --unregistered
node scripts/repository-catalog.mjs list --fork
node scripts/repository-catalog.mjs check
```

Output is JSON and may be filtered with ordinary JSON tools. Queries perform
no network access, execution, registration or pin writes. An unknown repository
or option fails. A refresh should re-observe GitHub metadata and checkout
identity, join the existing manifest read-only, and preserve prior source
review evidence. Existing `default-commit`/`default-tree` fields bind the source
snapshot actually inspected; they are not a promise that a floating default
branch or a retained WIP checkout is at the latest revision.
