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
