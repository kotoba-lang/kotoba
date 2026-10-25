# ADR-0001: Independent protocol projects under the shared protocol owner

Status: source placement accepted and qualified on merged main; three child
repositories archived with readbacks. Tracking:
[JUN-267](https://linear.app/kotobalabs/issue/JUN-267).

The existing `kotobase-protocol-core` owner co-locates three opt-in projects.
Root production `src`, `deps.edn` and `nbb.edn` stay byte-identical to
`4fdf95ad92d5d73d98e33954484ce4bdec6313d7`. The registry-only router still has
no built-in surface table and does not serve or advertise an absent handler.
Source lookup neither admits a runtime nor grants authority or deploys a route.

| Source ID | Preserved repository and coordinate aliases | Root source needed |
|---|---|---|
| `kotoba.kotobase.protocol.ipq` | `kotoba-lang/kotobase-protocol-ipq`, `io.github.kotoba-lang/kotobase-protocol-ipq` | yes |
| `kotoba.kotobase.protocol.query-surfaces` | `kotoba-lang/kotobase-query-surfaces`, `io.github.kotoba-lang/kotobase-query-surfaces` | yes |
| `kotoba.kotobase.protocol.lfs` | `kotoba-lang/kotobase-lfs`, `io.github.kotoba-lang/kotobase-lfs` | no |

Each project lives at `surfaces/<source-id>` with its own original LICENSE,
configuration, tests and release boundary. Public namespaces, protocols and
wire formats keep their identities. IPQ and query composition localize only
their protocol-core edge. LFS remains an object-provider protocol and does not
acquire a protocol-core dependency. The standard Kotoba library catalog is not
expanded. Exact source aliases are independent from package admission.

The old `kotobase-protocols` facade contains colliding copies of core namespaces
and its built-in surface table. It remains a separate compatibility project;
never combine its classpath with this root. The private deploy shells and
protocol handlers retain their visibility and ownership. Co-location here
does not copy them, change a service or make this root a deploy shell.

## Source and dependency compatibility

All37 original files and modes are bound to immutable defaults and recoverable
histories. Production source bytes are unchanged. The real EDN validator checks
every external dependency and alias, with one explicit compatibility exception:
LFS storage floor `84abcc4007fd5d547b15dc36844c6b7e5f42e7ff` advances to
`d4f0ac224af5309d326be0b59a2e74b6993d8e82`, an existing upstream-main fix.

The original floor cannot compile `validate-object-store!` in CLJS: `satisfies?`
needs a literal protocol at macroexpansion, whereas the old code passes an
`if` expression. JVM and SCI interpret it successfully and cannot expose the
failure. The upstream fix branches between two literal calls. The reviewed
transition also adds explicit range operations and distinguishes range grants;
LFS still consumes the same stat/grant interfaces, and the original presigned
fixture declares neither range capability. The full reachable-source diff is
hash-bound in the import manifest. The original configuration remains preserved;
all other dependency values and aliases are unchanged. The original239 consumer
holds and signed west locks do not change.

SCI profiles declare complete runtime graphs. Test hosts are explicit in
`maintenance/protocol-test-hosts.json`: three JVM projects; four SCI and compiled
Node projects. The IPQ Node filesystem CLI suite and the existing query composition
suite are not declared JVM tests. Node-only files added after the old extension
map get byte-identical `.cljs` views, rather than a fictitious portable target.
Seven portable owner/LFS suites select the immutable shared compiled Kotoba test
bridge, preserving their JVM/SCI APIs. A portable IPQ test helper uses the
declared host's exception class. No production handler is modified for tests.

## Branches, WIP and recovery

Three complete histories / 30 refs / two historical PR heads and all37 source
hashes restore and fsck independently. Original checkouts, branches, stashes
and worktree metadata remain in place. Three nonancestor commits have explicit,
hash-bound reviews: the full/unpacked-limit implementation and its four controls
have current production/test successors; archived reconciliation WIP's two files
are byte-identical to main and its untracked tree is empty; the merged document
PR has a nonancestor head whose complete Git tree is exactly the squash tree.
All original objects and stash parents remain recoverable; nothing is discarded
because a tip is nonancestor. Recovery controls reject modified refs, bundles,
archive claims, missing reviews, successor hashes and review diffs.

## Placement boundaries still open

Lake metadata/tabular access and deterministic pre-encryption block compression
retain separate contracts and consumers. The posting index uses its own format
and cost model. They are not moved into this protocol root. The client remains
the CACAO/Biscuit and CID transport owner. Its client-query acceptance harness
matches the recorded root migration bytes, but no applicable license was found
in either recorded source location, so its transfer/retirement remains held.
Private families, runtime foundations and Amu remain separate. These decisions
do not declare the remaining organization-wide ownership review complete.

## Verification and retirement

```sh
node scripts/check-protocol-sources.mjs
kbb --backend sci --config scripts/source-check.nbb.edn scripts/check-protocol-dependencies.cljk
node scripts/test-protocol-sources.mjs /absolute/github/workspaces/protocol-source-tests
node scripts/check-protocol-history.mjs /absolute/github/workspaces/protocol-restore
node scripts/test-protocol-history.mjs /absolute/github/workspaces/protocol-recovery-tests
python3 scripts/test-protocol-hosts.py /absolute/github/workspaces/protocol-hosts \
  --kotoba /absolute/kotoba --engine /absolute/org-babashka-nbb/cli.js
```

The host command isolates each project's resolved dependencies, requires actual
positive test counts and verifies all three origins through the public Kotoba
CLI. The compiled reporter's planted failure/error changes only a recorded
work copy and must return Node exit1. IPQ lint uses actual host source views;
zero errors are required and remaining warnings are reported. Runtime, native,
live-service, performance and deployment qualification remain separate.

Actions settings are unchanged. The new workflow uses this owner's already
enabled Actions; specified disabled repositories/workflows stay disabled.
No repository is archived or deleted by this source commit. Retirement requires
actual merged-main gates, public source origins, fresh remote/local WIP and
consumer-hold guards, and explicit GitHub archive readbacks.

## Merged-main and archive readback

[Source PR #3](https://github.com/kotoba-lang/kotobase-protocol-core/pull/3)
merged as `d63193cd8312899b06c5fc1912dcc80a3dffe52f` after PR CI passed.
[Actual main CI](https://github.com/kotoba-lang/kotobase-protocol-core/actions/runs/39685963917)
also passed every step, including source/dependency/full-history contracts,
all declared hosts, public CLI origins and the planted failure/error control.
The same merged-main host command completed locally: JVM88 tests/369 assertions,
SCI and compiled Node102 tests/444 assertions each, three public source origins.

Immediate guards verified all30 original refs, working trees, branches/stashes,
archive-WIP/squash source bindings and all239 protected consumer repositories.
The three child repositories were archived with identical IDs, default commits,
heads, tags and source timestamps. All original physical checkouts and histories
remain intact; no repository was deleted. The dated receipt binds the exact
main qualification and individual GitHub archive readbacks. Source-only aliases
do not redirect old Git coordinates to a new graph; consumers select an
immutable owner commit and the corresponding project's `:deps/root` to adopt it.
Amu, existing disabled Actions and all other stated ownership boundaries remain
unchanged. The wider organization review is still in progress.
