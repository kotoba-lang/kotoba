# Organization-wide monorepo review

The owner goal covers every `kotoba-lang` repository that would benefit from
co-location. The completed 125-repository retirement is a milestone, not proof
that this wider goal is finished. [JUN-267 in Kotoba Labs](https://linear.app/kotobalabs/issue/JUN-267)
tracks the continuing work; JUN-69
tracks the adapter/registry boundary.

## Current evidence, 2026-10-22 JST

GitHub lists 2,668 repositories: 2,630 public and 38 private, including the 239
archived dependency-pin holds. Every current default commit and Git tree was
read from GitHub. Current project metadata was read from matching local Git
objects for 2,564 repositories and through pinned GitHub objects for the other
104. The latter still need tree-level review when selecting source to move.
Private repository details stay outside this public inventory.

[The inventory](library-repository-inventory.json) binds public entries to those
commits and project-file digests. Its classifications remain triage unless a
placement decision is supported by implementation, dependency and ownership
review. A prefix, age, test result or absence of a deployment file alone does
not establish that a repository should be moved or retired.

The current source catalog contains 25 dotted IDs and 70 exact aliases. Its
405 licensed origins include 125 deleted repositories with recoverable histories and
239 repositories held for existing consumer pins. Those holds are unchanged.
The additional ten origins described below were subsequently merged in #667
and archived after main/CLI verification. Their local histories were restored
and checked with git fsck; no original checkout or WIP was discarded.

## Complete the already-selected source families

Ten unbundled definitions belonged to the existing process, test and string
packages. They have a single current remote branch, no tags/open issues/open
PRs/releases, clean local state and no stashes or additional worktrees. Their
local branches and remote-tracking tips are ancestors of the reviewed default.
Their source bytes, metadata, licenses and file modes are now preserved in the
existing package imports and repository-migration inventory:

| Destination | Added repositories |
|---|---|
| `kotoba.process` | `process-error-types`, `process-iprocess` |
| `kotoba.test` | `test-are`, `test-deftest`, `test-eq-form`, `test-is`, `test-is-build`, `test-testing`, `test-thrown-form` |
| `kotoba.string` | `string-byte-index-to-codepoint-index` |

The old `kotoba.process.iprocess/IProcess` stays a distinct protocol with its
own dispatch identity. It is not copied over `kotoba.process.process/Process`.
The split test macros retain their shared registry, dynamic context/report
bindings and exact public namespaces. The host-runner macros in `kotoba.test`
remain unchanged. The UTF-8 offset helper retains its refusal of offsets inside
a code point. Only inherited empty lines at EOF are removed, with original and adjusted
digests recorded explicitly; implementation forms remain unchanged.

Portable and JVM regression tests cover protocol dispatch, deliberately planted
failures/errors with context and source lines, macro registry discovery and
UTF-8 boundaries. The public `definitions.cljk` fixture exercises all ten
sources through canonical package IDs and declared old aliases, with source
paths asserted inside the monorepo.

## Independent owner family monorepos

Five existing owners now co-locate their own same-family definitions. Their
protocol/transport/capability/crypto authority remains in those repositories;
putting recovery bundles here does not select or re-own their implementations.

| Owner retained | Child repositories integrated and archived | Main PR |
|---|---:|---|
| `kotoba-lang/http` | 10 | [#11](https://github.com/kotoba-lang/http/pull/11) |
| `kotoba-lang/device` | 15 | [#1](https://github.com/kotoba-lang/device/pull/1) |
| `kotoba-lang/netcap` | 11 | [#1](https://github.com/kotoba-lang/netcap/pull/1) |
| `kotoba-lang/crypto` | 13 | [#1](https://github.com/kotoba-lang/crypto/pull/1) |
| `kotoba-lang/wit` | 12 | [#1](https://github.com/kotoba-lang/wit/pull/1) |

Production source bytes and namespace/protocol identities are unchanged.
Only imported internal Git edges were removed; other runtime dependency values
and test aliases were checked with the authoritative EDN reader. SCI manifests
now declare those same runtime dependencies. Test-only corrections select the
actual host exception class, explicitly inject a Node digest while preserving
the uninjected refusal, and close test-created TLS servers. They do not change
production defaults or grant policy.

After fresh main readback, portable checks passed 131 tests / 532 assertions
and JVM checks passed 146 tests / 565 assertions. The public source CLI loaded
all 62 imported namespaces from the five owner trees. Native qualification is
not claimed. Existing manually disabled workflows remain disabled.

All 61 child archives were rechecked immediately before the operation; source,
refs and local state were verified again. Their 396 reviewed Git refs, reachable
histories and the one historical PR are preserved in the
[dated receipt](../maintenance/family-consolidations/2026-10-22/receipt.json).
All bundles restored and passed fsck. No repositories were deleted in this
batch, and old URLs continue to support historical pins. The original 239
held repositories retained their exact IDs/defaults/refs/archive state.

Verify the recovery archive without any archived GitHub URL:

```sh
node scripts/check-family-consolidations.mjs
node scripts/check-family-consolidations.mjs /absolute/github/workspaces/family-restore
```

## Tooling source monorepo

LSP/lint tooling source is selected as four bundled packages, covering 31
licensed origins plus 12 compatibility modules derived from the licensed LSP
owner. All 43 histories/320 refs are preserved and restored/fsck checked.
All 43 were archived after main/tests/import/CLI verification; source/refs stayed
unchanged, and the dated tooling receipt retains complete before/after metadata. See
[the tooling review](library-tooling-consolidation.md) for provenance, the
reproduced UTF-8 framing bug and its shared repair. This selection does not
resolve unrelated license or ownership holds.

## Capability source owner monorepo

The existing neutral `kotoba-lang/kotoba-core-contracts` owner now co-locates
61 atomic packages in `capabilities/kotoba.capability.*`, following
[source PR #31](https://github.com/kotoba-lang/kotoba-core-contracts/pull/31).
The authority remains independent of the language CLI and execution foundations.
Each package retains its own source, tests, build artifacts, LICENSE and release
boundary. The root authority's production source and dependency closure are
unchanged. These 61 source IDs / 122 exact aliases are separate from the standard
library catalog's 25 IDs / 70 aliases; lookup grants no admission.

The owning definition codec recomputes all 61 manifests as 60 distinct CIDs.
`calendar/read` and `contacts/read` share a semantic CID, so CID-only source
selection refuses ambiguity. One existing `process/spawn` CID literal was
corrected with reversible byte provenance; its old invalid CID is not an alias.
Four definitions remain unregistered and rejected, including `process/spawn`
without an approved RID. No grant, signed release or RID was fabricated.

Merged source main `301f2310ca900f843bc801ead7f1500fe60ad64c` passed all 61 original JVM suites
(140 tests / 347 assertions), authority conformance (35 cases), execution
(5 tests / 113 assertions), canonical CID/source-literal agreement and the real
public source CLI's 61 namespaces with origins inside the owner subtrees.
Ten existing Wasm cores validate and both unbound HTTP/inference cores return
`-3` with no host imports. MMIO's direct I/O pin now matches the authority's
existing API floor; all other external dependency values remain unchanged.
The LLM resolver test refuses before transport and sends no prompt externally.
These are local source checks; existing Actions remain disabled, and native
runtime qualification, signing and production operation remain separate.

All 61 repositories were archived only after main verification and fresh remote
ref/local WIP checks. Their complete histories, 331 refs, all 16 historical PRs
and 551 original file hashes were restored/fsck checked. See the
[merged receipt](https://github.com/kotoba-lang/kotoba-core-contracts/blob/575dc9def2042ca4d7a67f944184ce517375f960/maintenance/capability-consolidation/2026-10-22/receipt.json) and
[receipt PR #32](https://github.com/kotoba-lang/kotoba-core-contracts/pull/32).
Two local Finder metadata files remain byte-identical in their original
checkouts with private local backups; private metadata is not published.
Legacy GitHub discovery URLs remain archived and readable, not deleted.
The original 239 dependency-pin holds and all original checkouts are retained.

## Storage provider source owner monorepo

Seven opt-in Git, IPFS, Kura, pack, PostgreSQL, S3/R2 and SQLite provider projects
now share the existing `kotoba-lang/kotobase-storage` owner under
`providers/kotoba.kotobase.storage.*`. The neutral root's production source and
dependency graph remain unchanged. Each provider keeps its dependencies, build
configuration, LICENSE and release boundary. The seven IDs / fourteen exact
repository and coordinate aliases are source-only; they do not expand the
standard library catalog or grant runtime admission. See
[source PR #4](https://github.com/kotoba-lang/kotobase-storage/pull/4).

Source main `a831dda3f475fa944824ee703e69da077dc79a25` passed 138 JVM tests / 516 assertions, fourteen
SCI fixture scripts, Kura compiled Node17 tests / 70 assertions with lint0/0,
the real local Miniflare R2 block/object suites, and compiled engine, Prolly and
advanced ETag/CAS/reopen fixtures. The public S3 npm test entry also passed.
All seven provider source origins were verified in their declared JVM or public
Kotoba CLI/SCI hosts. Unconditional CAS and off-by-one range oracles are rejected.
Existing invalid Amu build-ID test commands now use the original pinned
Shadow/CLJS declarations with byte-identical filename views. Native/Wasm, live
services/interoperability, production durability, signing and deployment remain
separate claims. Existing Actions stay disabled; local results are not CI success.

The seven sources were archived after main verification and immediate source,
refs and local WIP rechecks. Seven complete histories / 114 refs / 11 historical
PRs and all140 original file hashes restore/fsck successfully. Pack's existing17
generated-file deletions apply in an independent restore with the exact original
status. Original checkouts, stashes, branches and broken worktree metadata stay
in place. See the [merged receipt](https://github.com/kotoba-lang/kotobase-storage/blob/ce8640e24ee2b1b8a15129b7a71f020a22f979a8/maintenance/storage-consolidation/2026-10-22/receipt.json) and
[receipt PR #5](https://github.com/kotoba-lang/kotobase-storage/pull/5).
No repository was deleted in this wave; old Git dependency URLs remain readable.
The original239 dependency-pin holds remain unchanged.

D1 remains a compatibility deployment/rollback boundary. The frozen peer is not
made the owner of capabilities already extracted from it. Protocol/deployment
shells and Amu/execution foundations remain separate pending their own source,
ownership and compatibility reviews. Other Kotobase families and private sources
remain under review; private details are not included in this public inventory.

## Database engine source owner monorepo

Three opt-in legacy, LSM and Prolly engine projects now share the existing
`kotoba-lang/kotobase-engine-contract` owner under
`implementations/kotoba.kotobase.engine.*`. The neutral root production source,
dependency graph and qualification matrix are unchanged. Three source IDs and
six exact repository/coordinate aliases preserve public namespaces and logical
versus physical root semantics. Each project retains its license, dependencies,
build and release boundary. Source lookup grants no runtime admission and does
not expand the standard library catalog. See
[source PR #11](https://github.com/kotoba-lang/kotobase-engine-contract/pull/11).

Actual source main `87213760c7394271301423c08a4ec1106370527e` passed four independent JVM projects,
95 tests / 425 assertions; SCI and compiled Node each ran100 unit tests /
374 assertions, with three SCI and two compiled asynchronous provider fixtures.
All three declared lint profiles reported zero errors/warnings. The public
Kotoba CLI resolved all three source origins inside the owner; nine exact
ID/alias lookups and source-refusal cases passed. A planted compiled failure and
error returned exit1. Existing Actions remain disabled, so these are local
main results, not CI success or native/live/production-default qualification.

Three complete histories / 83 Git refs / 24 historical PR heads / 56 original
file hashes restore and fsck successfully, including an explicitly bound linked
LSM worktree HEAD. Five nonancestor commits have hash-bound branch review
dispositions. The unused peer async-get option and incompatible LSM format-v2
experiment remain fully recoverable; their APIs/formats are not claimed migrated
or admitted. Original checkouts, branches, stashes and the experimental linked
worktree remain in place. After main verification and immediate source/ref/WIP
rechecks, all three child URLs were archived, with identical defaults, heads,
tags and source timestamps. See the [merged receipt](https://github.com/kotoba-lang/kotobase-engine-contract/blob/ef214ec7a9801c8ad546ef641bd179f0abc26c22/maintenance/engine-consolidation/2026-10-22/receipt.json) and
[receipt PR #12](https://github.com/kotoba-lang/kotobase-engine-contract/pull/12).
No repository was deleted in this wave. The original239 dependency-pin holds
are unchanged. Physical tree mechanisms, storage owners/providers, the frozen
peer, Amu and other execution foundations remain independent. Other Kotobase
families and private sources still need their own review.

## Protocol source owner monorepo

Three opt-in LFS, IPQ and query-composition projects now share the existing
`kotoba-lang/kotobase-protocol-core` owner under
`surfaces/kotoba.kotobase.protocol.*`. Root production source and the default
dependency graph are unchanged, and the registry-only router does not auto-mount
or advertise an absent surface. Three source IDs and six exact repository and
coordinate aliases preserve public Lisp namespaces, protocol identities and
wire formats. LFS keeps its object-provider boundary and does not acquire a
protocol-core dependency. Source lookup remains `admission: not-granted`,
independent from standard library package admission. See
[source PR #3](https://github.com/kotoba-lang/kotobase-protocol-core/pull/3).

Only LFS's old storage floor advances to the existing upstream-main compiler fix
`d4f0ac224af5309d326be0b59a2e74b6993d8e82`. The original computed `satisfies?`
protocol passes JVM/SCI but fails real CLJS macroexpansion; the fix uses literal
protocols. The transition's reachable source is hash-bound and the original
configuration remains recoverable. Every other external EDN dependency and
alias is unchanged. Imported production handler bytes are unchanged.

Actual source main `d63193cd8312899b06c5fc1912dcc80a3dffe52f` passed [main CI](https://github.com/kotoba-lang/kotobase-protocol-core/actions/runs/39685963917), including
three JVM projects (88 tests / 369 assertions), four SCI and compiled Node projects
(102 tests / 444 assertions each), nine exact source lookups, and three actual
public Kotoba CLI origins, full recovery and negative controls. Local main gates
also completed. IPQ lint reports 0 errors / 11 retained warnings on byte-identical
host views. A planted failure/error produces 28 tests / 108 assertions and Node
exit 1. Node filesystem CLI and the existing query-composition tests are declared
CLJS suites rather than fictitious JVM coverage. Native, live service, signing,
runtime admission, production performance/default and deployment remain separate.

Three complete histories / 30 refs / two historical PR heads / 37 original hashes
restore and fsck. Archived reconciliation WIP and a squashed PR head have exact
main successors; original nonancestor objects and all stash parents remain in
the bundles. Original checkouts, branches, stashes and worktree metadata stay
in place. After main gates and fresh source/ref/WIP and original 239 consumer guards, all three
child URLs were archived with identical IDs/defaults/heads/tags/source timestamps.
See the [merged receipt](https://github.com/kotoba-lang/kotobase-protocol-core/blob/6e520f21ebfd62bd5c03b5ad3ccf9e8c04d32936/maintenance/protocol-consolidation/2026-10-22/receipt.json) and
[receipt PR #4](https://github.com/kotoba-lang/kotobase-protocol-core/pull/4).
No repository was deleted. Archived Git coordinates keep their original history;
they do not redirect consumers to a new dependency graph. Consumers select an
immutable owner commit and the project's `:deps/root` when adopting this source.
The original 239 consumer holds and signed west locks stay unchanged.

The colliding legacy facade, private protocol/deploy shells, lake metadata,
block codec, independent posting index, client transport, frozen peer and
Amu/execution foundations retain their boundaries. Client-query transfer is held
for missing license provenance. The original four protocol repos had Actions
enabled and their settings were not changed manually; specified disabled repos
and workflows stay disabled. Other org/private families remain under review.

## Remaining ownership decisions

Other product/engine/database families and adapter catalogs remain in ownership
review. Their implementations, licenses, dependency closures, releases,
deployment ownership, branches and WIP are part of the full goal. Recording
names is not completing that work. Math/i64 license provenance remains open.
Amu and other execution foundations remain separate. Existing signed locks
and the original 239 consumer-pin holds are unchanged. Private details stay
outside this public inventory.

GitHub Actions previously disabled by the owner remain disabled. No runtime
identity/state is restored and no daemon or production route is changed by
this source consolidation. The organization-wide goal remains active.
