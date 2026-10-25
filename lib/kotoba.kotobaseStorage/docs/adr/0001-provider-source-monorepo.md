# ADR-0001: Co-locate independently selected storage provider sources

Status: source placement and merged-main local qualification accepted; seven
legacy provider repositories archived after preservation guards. Tracking: [JUN-267](https://linear.app/kotobalabs/issue/JUN-267).

Seven non-deployment adapter/decorator projects now share the existing
`kotoba-lang/kotobase-storage` source owner. Each remains an opt-in project with
its own dependencies, tests, build declarations, LICENSE and release boundary.
The root storage contract's production source and dependency graph are unchanged
from `111c7156cd4a38b544cb3946f70b8edcca466d77`. It never depends on its providers.

| Source ID | Legacy repository |
|---|---|
| `kotoba.kotobase.storage.git` | `kotoba-lang/kotobase-storage-git` |
| `kotoba.kotobase.storage.ipfs` | `kotoba-lang/kotobase-storage-ipfs` |
| `kotoba.kotobase.storage.kura` | `kotoba-lang/kotobase-storage-kura` |
| `kotoba.kotobase.storage.pack` | `kotoba-lang/kotobase-storage-pack` |
| `kotoba.kotobase.storage.postgres` | `kotoba-lang/kotobase-storage-postgres` |
| `kotoba.kotobase.storage.s3` | `kotoba-lang/kotobase-storage-s3` |
| `kotoba.kotobase.storage.sqlite` | `kotoba-lang/kotobase-storage-sqlite` |

The projects live under `providers/<source-id>`. Exact old repository and
`io.github.*` coordinates remain source lookup aliases. Existing public Lisp
namespaces, protocols, data CIDs and provider capability profiles retain their
identities. These source IDs are separate from the language's standard library
catalog and from signed package/runtime admission. No grant is created.

Only selected storage dependency edges point to local roots. Every other EDN
runtime/test dependency value and host alias is retained. The IPFS project now
declares `@noble/hashes` 2.0.1 explicitly, matching its existing pinned
`io-multiformats` project's own declaration. Its old hoisted 2.4.0 copy is retained
under `@noble/curves` with identical integrity; all other locked entries remain
identical. This repairs an undeclared dependency without changing provider code.

Co-location does not make the legacy mutable-ref compatibility providers the
canonical Kotobase database correctness path. Signed immutable CID commits,
rollback protection, independent agreement and host-selected transport keep
their existing roles. D1's compatibility deployment/rollback boundary stays
separate. The frozen `kotobase-peer` is not made a new owner of capabilities
already extracted from it. Public runtime/deployment shells and Amu remain
outside this source monorepo operation.

## Source and history evidence

`maintenance/storage-source-imports.json` binds all seven sources to immutable
commits/trees, SHA-256 and modes. 123 imported files are active; 17 tracked
compiler outputs from pack's history are kept only in complete Git histories.
Test-only host exception-class corrections are recorded separately. Every
production provider source file remains byte-identical to its reviewed default.

The dated recovery receipt contains seven complete bundles / 114 refs, all 11
historical PRs and explicit successor bindings for the three nonancestor IPFS
PR heads. Their real merge commits are default ancestors; historical production
source is unchanged apart from extension names and two docstring path literals.
Every bundle was independently restored/fsck checked and all 140 original file
hashes were verified. Pack's existing 17 generated-file deletions are preserved
as a compressed Git patch that was applied in a fresh restore and produced the
exact original status. Original checkouts and broken worktree metadata remain
in place; private metadata backups are outside the repository.

Kura's async source is reviewed and merged through
[#2](https://github.com/kotoba-lang/kotobase-storage-kura/pull/2), main
`63b34f26af1a7d6a9f9b2099f61af76aa65c7050`, including draft #1's history.
The runner now actually executes the async suite. A stale-read CAS loser and
ambiguous catalog failures cannot remove a winner's shared pack. Using the real
older rollback implementation is a negative control: it destroys the winner's
data and the new suite exits 1. The shared compiled test bridge is selected as a
test-only, zero-dependency subproject of Kotoba main `f0ecb24b722664b825ab89992e9cc98c37ecaaf0`.

## Verification status

Current local qualification includes 138 JVM tests / 516 assertions across
the owner and five JVM providers; Kura's actual compiled Node suite has 17 tests /
70 assertions and zero lint errors/warnings. SCI conformance covers the owner,
pack, S3 mock/object/signature/benchmark guards, and IPFS's injected Kubo/Helia
clients, local archive HTTP fixture and real loopback TCP peers. Helia is not
started as a live node, and no live Kubo/S3/Kura service is used.

The two actual Miniflare/R2 binding suites, compiled engine and Prolly reopen
fixtures, and advanced ETag/CAS/race gate also pass locally. Their runners reject
an unconditional R2 client and an off-by-one range conversion. The existing
`amu compile` commands incorrectly treated Shadow build IDs as Amu source paths;
the test commands now invoke the original pinned Shadow/CLJS build declarations
through byte-identical extension views. The inconsistent S3 npm lock now includes
Miniflare's exact undici 7.28.0 instead of the unrelated hoisted 7.29.0; every other
entry and all direct dependency values remain unchanged. Seven provider source
origins are checked in their declared JVM or public Kotoba CLI/SCI hosts; a source
CLI lookup by itself is not runtime proof. These gates were subsequently
reproduced on the source main identified below before retirement. Native/Wasm, live interoperability, production
shard durability, signed-order admission and deployment are separate claims.
Existing Actions remain disabled; no CI success is claimed.

```sh
node scripts/check-storage-sources.mjs
# Install each IPFS/S3 npm lock with --ignore-scripts first (include optional for IPFS).
python3 scripts/test-storage-hosts.py /absolute/github/workspaces/storage-tests \
  --kotoba /absolute/kotoba --engine /absolute/org-babashka-nbb/cli.js
node scripts/check-storage-history.mjs /absolute/github/workspaces/storage-restore
node scripts/storage-sources.mjs resolve kotoba.kotobase.storage.ipfs
node scripts/storage-sources.mjs resolve io.github.kotoba-lang/kotobase-storage-ipfs
node scripts/storage-sources.mjs classpath kotoba.kotobase.storage.s3
```

No repository is archived or deleted by this source commit. Retirement requires
merged-main verification, immediate source/ref/WIP rechecks, recovery proof and
an explicit archive readback in the receipt. The original 239 consumer-pin
holds and signed locks stay unchanged. Organization-wide review remains active.


## Completed archive readback

Source main `a831dda3f475fa944824ee703e69da077dc79a25` passed the reproduced
host gates above and the repaired S3 `npm test` entry. All seven provider repos
were then archived, with immediate GitHub readback proving ID, default, heads,
tags and source timestamps unchanged. All114 refs and140 original file hashes
restore/fsck again; the pack WIP patch still reproduces its exact original
status. The original239 consumer-pin holds were freshly read and unchanged.
The dated receipt records each before/after snapshot and qualification. Old Git
URLs remain available; no deletion occurred. Existing Actions remain disabled,
and the organization-wide review continues.
