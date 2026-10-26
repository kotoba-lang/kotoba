# ADR-0002: Co-locate capability source packages under their existing owner

Status: accepted for source placement; signed publication and runtime admission
remain separate. Tracking: [JUN-267](https://linear.app/kotobalabs/issue/JUN-267).

## Decision

61 authority packages share the catalog, ABI and definition codec owned by
`kotoba-lang/kotoba-core-contracts`. Keep this neutral authority repository
independent of the CLI, language and execution foundations, and place those
packages in `capabilities/kotoba.capability.*` within it. Each keeps its own
source/test/build files, LICENSE, dependencies, artifacts and release boundary.
The default authority project does not depend on its providers. The only new
shared dependency edge is each package's existing authority coordinate pointing
to the parent source with `:local/root "../.."`.

This supersedes the physical one-public-repository-per-capability rule.
`:capability/repository` remains the exact legacy discovery alias in existing
manifests and sealed envelopes. The existing contract and envelope validators,
effects, default policies, imports, ABI, signature floor, provider status and
actual provider implementation bytes retain their meanings. No authority or
capability is granted by this source move. Old GitHub/Radicle aliases and
historical pins are not silently rewritten to a new signed release.

The source catalog is metadata, not another package admission protocol. It
selects a checked subtree by an exact dotted source ID or old coordinate. Git
consumers can select that subtree with `:deps/root`; its authority dependency
then resolves to the same checkout. Namespaces retain their existing Lisp
spelling, including hyphens. Monorepo HEAD is source provenance rather than a
new DefCID, capability meaning or signed package identity.

## Identity and refusals

61 package IDs currently describe 60 distinct semantic definitions:
`calendar/read` and `contacts/read` share a definition CID under the owning
codec. A CID-only source lookup with multiple matches refuses and reports the
explicit package IDs. It never chooses the first folder. Existing runtime
admission is still required for every selected source.

Recomputing every definition found one pre-existing inconsistency:
`process/spawn` declared
`bafyreihqyss6vswxjwjrfeafcuuzphbtzzlyxzbssk3tmut5r3w5ldqlrb`, while the
canonical authority encoder yields
`bafyreiculfhdusriqd6p3ihdvhrkbydrgrj5jzu3sn7vstm5yt3jafwtqu`.
Only that literal is corrected in the source manifest and README, with an
exact reversible byte binding in the import record. The previous invalid CID
is not registered as an alias for the corrected definition. No policy, effect,
import, artifact or RID is changed. `can/frame`, `link/frame`, `net/datagram`
and `process/spawn` remain unregistered by the current authority, and
`process/spawn` also lacks an approved Radicle RID. Their rejection reasons are
explicitly checked; no RID or grant is fabricated. Publication stays open.

## Preservation and verification

`maintenance/capability-source-imports.json` binds 551 original files to exact
Git commits/trees, SHA-256 and modes. 539 are active imported files. Twelve
tracked historical `.cpcache` records are retained only in the complete Git
histories, avoiding stale machine-specific build paths in active packages.
Dependency declarations, test-only adjustments and the one CID correction have
separate output digests and reasons. All current LICENSE files remain present;
one inherited empty final line is removed without changing their wording.

All 331 local/remote/PR refs and complete histories are bundled in the
[dated receipt](../../maintenance/capability-consolidation/2026-10-22/receipt.json).
It preserves all 16 historical PRs with comments/reviews. Seven PR heads are not
Git ancestors after squash/rebase; their actual merge commits are ancestors,
and source/artifact bytes match current defaults after extension migration.
The MMIO branch's port/parity intent is already in default and its ten compiled
cases pass. Original checkouts, branches, stashes and WIP remain in place.

The new MMIO package advances only its direct I/O pin to the authority's
existing `72dde04` floor: its older direct pin hid the required `io/resource`
API. Every other external runtime dependency and host alias value is retained.
The MMIO test uses an explicit/installed Amu and the host temporary directory.
The LLM resolver-observation test omits a request encoder and asserts refusal
before transport, so the test cannot send its sample prompt externally.

Local verification covers every package's original JVM suites (140 tests /
347 assertions), MMIO compiled JavaScript parity, the authority's portable
conformance corpus (35 cases) and execution suite (5 tests / 113 assertions),
canonical CID recomputation/source-literal equality, and all 61 manifest
namespaces through the real public source CLI. Existing Wasm core artifacts
validate; both unbound HTTP/inference cores execute with `-3` and no imports.
This is not production signing, browser/app consent, full native runtime
qualification or service deployment.

```sh
node scripts/check-capability-sources.mjs
node scripts/test-capability-sources.mjs /absolute/github/workspaces/source-test
node scripts/test-capability-provenance.mjs /absolute/github/workspaces/provenance-test
node scripts/check-capability-history.mjs /absolute/github/workspaces/history-restore
node scripts/check-capability-artifacts.mjs
node scripts/capability-sources.mjs resolve kotoba.capability.http.fetch
node scripts/capability-sources.mjs resolve io.github.kotoba-lang/capability-http-fetch
node scripts/capability-sources.mjs classpath kotoba.capability.http.fetch
```

The current original 239 consumer-pin holds stay unchanged. All 61 source repositories are now archived after source main
`301f2310ca900f843bc801ead7f1500fe60ad64c`, test/import readback and
immediate ref/WIP checks. The receipt records each completed archive and its
source/ref readback; no repository was deleted in this batch. Existing Actions remain in
their prior states. Amu and other execution foundations remain separate.
