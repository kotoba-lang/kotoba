# Organization-wide monorepo review

The owner goal covers every `kotoba-lang` repository that would benefit from
co-location. The completed 125-repository retirement is a milestone, not proof
that this wider goal is finished. JUN-269 tracks the continuing work; JUN-69
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

The current source catalog contains 21 dotted IDs and 58 exact aliases. Its
374 origins include 125 deleted repositories with recoverable histories and
239 repositories held for existing consumer pins. Those holds are unchanged.
The additional ten origins described below remain separately recorded for
main verification and archive readback.

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

## Remaining ownership decisions

The review found further one-definition families around LSP, lint, HTTP,
device, netcap, crypto and WIT. Their root READMEs and dependency declarations
show different roles: pure tooling/data, injected transport, capability
vocabulary and cryptographic/contract authority. Review each complete family
against its actual owner before choosing the destination; an independent owner
can itself contain its related definitions in one repository. Moving standard
source must not silently re-own a neutral contract or an enforcement boundary.

There are also product/engine/database families and adapter catalogs still in
ownership review. The remaining work includes their current implementations,
licenses, dependency closures, release/deployment ownership, branches and WIP;
recording their names is not completing that work. Missing `math`/`i64` license
provenance remains explicit. Amu and other execution foundations remain in
separate repositories. Existing consumer pins and signed locks are unchanged.

GitHub Actions previously disabled by the owner remain disabled. Local source
compatibility checks do not establish native/runtime qualification. No runtime
identity/state is restored and no daemon is restarted by this consolidation.
