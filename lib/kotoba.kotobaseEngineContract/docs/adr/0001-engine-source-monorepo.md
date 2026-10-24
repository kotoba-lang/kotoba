# ADR-0001: Independent database engine sources under the neutral contract owner

Status: source placement accepted and qualified on merged main; three source
repositories archived with readbacks. Tracking:
[JUN-267](https://linear.app/kotobalabs/issue/JUN-267).

The existing `kotobase-engine-contract` owner now co-locates three opt-in source
projects. Its production `src`, `deps.edn` and `nbb.edn` remain byte-identical to
`53d10eea8a09ba7d9f466f9f57cbc21e8314df45`; the neutral default graph never
depends on implementations, providers, a deployment, or Amu.

| Source ID | Preserved repository/coordinate aliases |
|---|---|
| `kotoba.kotobase.engine.legacy` | `kotoba-lang/kotobase-engine`, `io.github.kotoba-lang/kotobase-engine` |
| `kotoba.kotobase.engine.lsm` | `kotoba-lang/kotobase-engine-lsm`, `io.github.kotoba-lang/kotobase-engine-lsm` |
| `kotoba.kotobase.engine.prolly` | `kotoba-lang/kotobase-engine-prolly`, `io.github.kotoba-lang/kotobase-engine-prolly` |

Each project lives in `implementations/<source-id>` with its original LICENSE,
NOTICE, dependencies, build configuration, tests and release boundary. Discovery
is exact and source-only; it grants no runtime admission, changes no standard
library catalog, and renames no public Lisp namespace or logical/physical CID.
The generated npm ISC label in the legacy project is corrected to match its
existing Apache-2.0 LICENSE/NOTICE, without changing dependency values.

Only the selected engine-contract edge becomes `{:local/root "../.."}`. A real
EDN reader verifies all other dependency values and aliases against the original
hash-bound configurations. Each explicit SCI profile receives that same complete
runtime graph. The original239 consumer-pin holds and signed locks stay unchanged.
The physical tree mechanisms (`arrangement`, `prolly-tree`, `merkle-lsm`), storage
contracts/providers, frozen peer and Amu/execution foundations retain ownership.
Physical roots, logical transaction/checkpoint roots and production qualification
remain distinct. Co-location does not select a production default or close the
qualification matrix's performance, live-transport or durability gates.

## Branch and history review

Three complete histories / 83 Git refs / 24 historical PR heads and56 original
file hashes are preserved and independently restored/fsck checked. One additional
linked-worktree HEAD alias is explicitly bound in the bundle; the existing LSM
worktree and every original branch/stash/working tree remain in place. Private
worktree metadata backups remain outside the public repository. The recovery
receipt and source manifest bind every nonancestor ref to an explicit review.

The merged fold/view and physical-maintenance branches have real merged-PR
ancestry and hash-bound production successors. The closed admin/tuple cleanup
branch has its accepted behavior in the later merged API and its regressions;
its complete original source remains recoverable.

Two unaccepted experiments remain history, without a qualified implementation
claim. `cf62e124` adds only an `:async-get-fn` option that the pinned peer
`e98d0864` does not consume in `fold-serialized-if-needed!`; that wrapper passes
nil at the underlying async-get slot. Keeping the option would not implement
its claimed optimization. The closed LSM `7d4a4371` branch uses a different
plaintext format-v2/request-index layout and inline-compaction API. Current v3
requires sealed metadata, keyed lookup, canonical logical roots and the shared
`IMaintenance` CAS contract. Reintroducing that experiment would restore a
conflicting format and omit those controls. Its branch, tests, documentation
and existing worktree are preserved; its format/APIs are not claimed migrated.
Cold fold/view performance remains a separate peer follow-up.

## Host verification

`maintenance/engine-test-hosts.json` declares the actual suites. The six legacy
Promise suites are CLJS-only; its original synchronous facade suites remain on
the JVM. Root and legacy tests contain the same `kotobase.engine.merge-test`
namespace, so each project always runs in a separate process/classpath. No test
classpath merges implementation suites or supplies one as the neutral oracle.

The portable contract tests now use explicit host exception classes, equivalent
test-only SHA-256/clocks, an explicit-epoch forged fixture that does not compute
`inc(nil)`, and division for an unchanged9/2 bound that compiled CLJS cannot read
as a JVM Ratio constant. The compiled host selects the shared immutable Kotoba
test macro/report bridge; JVM and SCI retain their original APIs. The Prolly
async fixture now declares its required capability protocol, and the LRU test
uses the appropriate SCI/compiled var operation while restoring its old value.
Production implementation bytes are unchanged. The original metadata suite is
included in the public contract runner, which checks actual completion/counts.

Local qualification measured JVM95 tests/425 assertions, portable contract
SCI57/228 and compiled Node57/228, legacy Promise SCI43/146 and compiled Node43/146,
plus real compiled LSM/Prolly cold-write/CAS/crash/reopen/corruption fixtures.
Actual source views for the three declared lint profiles have zero errors and
warnings. A planted failure and error produce59 tests,1 failure,1 error and Node
exit1; the overlay changes only a recorded work copy. These are local source
and host checks. Existing Actions remain disabled; no CI, native/Wasm, live
service, production workload/default, signed-admission or deployment claim is made.

```sh
npm ci --ignore-scripts
node scripts/check-engine-sources.mjs
kbb --backend sci scripts/check-engine-dependencies.cljk
node scripts/check-engine-history.mjs /absolute/github/workspaces/engine-restore
node scripts/test-engine-history.mjs /absolute/github/workspaces/engine-negative
node scripts/engine-sources.mjs resolve kotoba.kotobase.engine.prolly
python3 scripts/test-engine-hosts.py /absolute/github/workspaces/engine-tests \
  --kotoba /absolute/kotoba --engine /absolute/org-babashka-nbb/cli.js
```

No repository is archived/deleted by this source commit. Retirement requires
actual merged-main gates, public CLI/source origins, immediate remote/local
rechecks and explicit archive readbacks. Complete source/history retention does
not turn a rejected historical experiment into an admitted implementation.

## Merged-main and archive readback

[Source PR #11](https://github.com/kotoba-lang/kotobase-engine-contract/pull/11)
merged as `87213760c7394271301423c08a4ec1106370527e`. The published combined
host command completed successfully on that exact main: four JVM projects with
95 tests / 425 assertions, SCI and compiled Node each100 tests / 374 assertions,
three SCI and two compiled asynchronous fixtures, and all three declared lint
profiles with zero errors/warnings. All three public Kotoba CLI origins resolve
inside this owner; exact source IDs/aliases remain source-only.

Immediate remote/local guards verified the original checkouts, linked LSM
worktree, branches, stashes, all83 refs and all239 protected consumer-pin
repositories. The three child repositories were then archived, with their IDs,
defaults, heads, tags and source timestamps unchanged. No repository was deleted.
The dated receipt binds the actual main verification and each GitHub readback;
complete bundle restore/fsck and the recovery refusal controls pass after archive.
All four repositories' Actions remain disabled, and the source main has zero
Actions runs. Local qualification is recorded separately from CI. The full-org
review continues; Amu and other execution foundations remain independent.
