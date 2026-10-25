# kotoba-lang/bmc

Portable `.cljc` core for a **Business Model Canvas (lean canvas) / Lean Loop
(build-measure-learn) engine**: datoms indexing + append-only event fold
(`bmc.canvas`), an append-only ledger (`bmc.ledger`), a gate evaluator that
turns collected metrics into hypothesis progression (`bmc.gate`), and a small
`:cljs`-only Node fs/env bridge (`bmc.io`) for hosts (like `nbb`) that have no
cross-repo `:deps` classpath mechanism. Every namespace is `.cljc` (JVM /
ClojureScript / nbb), with **zero third-party runtime deps**.

## Provenance

This library is a rescue of WIP that was found untracked in an abandoned git
worktree (branch `feat/bmc-kotoba-lang-extraction`, superproject commit
`255a382537e`, `com-junkawasaki/root`). It was salvaged to a pushed branch
per that superproject's `git-cleanup-conflict` retirement policy rather than
discarded, then reviewed and scaffolded here as its own west-managed project
per `90-docs/adr/2607209910-kotoba-lang-bmc-scaffold.edn` in that
superproject.

The four namespaces are a **zero-product-literal extraction** of the same
logic already running in production as `70-tools/bmc`'s `gftd.canvas` /
`gftd.gate` / `gftd.ledger` (ADR-2607021500 / ADR-2607021600 / ADR-2607022100
in `com-junkawasaki/root`) — every docstring says so explicitly. `70-tools/bmc`
binds that engine to concrete products (cloud-itonami, cloud-murakumo,
net-kotobase, etc.) and their literal file paths / gate-spec tables; this
library strips all of that out so the reusable core (index/fold/evaluate/
render, append-only ledger read+append, gate-spec evaluation) can be shared
by more than one product-bound CLI, instead of being re-implemented per
script. `70-tools/bmc`'s own README already anticipated this split ("将来分割:
… 再利用部品 = com-junkawasaki 子リポへ split し、各 product repo の CLI から
deps 参照する"). Nothing in `70-tools/bmc` has been rewired to depend on this
library yet — that consumption wiring is deliberately out of scope for this
scaffold and is a follow-up for whoever picks it up next.

## Known gap: no test coverage

**This code has zero tests.** It was rescued as-is from WIP and scaffolded
into its own repo unchanged; no tests have been written or fabricated as
part of that rescue. `deps.edn` has a `:test` alias wired for
`cognitect-labs/test-runner` (matching sibling `kotoba-lang` `.cljc`
libraries' convention) so adding tests later is a matter of dropping files
under `test/bmc/`, but nothing exists there yet. Treat this library as
unverified WIP, not a hardened dependency, until that gap is closed.

## Modules

```
src/bmc/canvas.cljk   # datoms index / event fold / md·text·EDN render (pure .cljc)
src/bmc/ledger.cljk   # append-only ledger — 1 EDN event per line (read/append)
src/bmc/gate.cljk     # gate evaluator: metrics -> hypothesis status proposals
src/bmc/io.cljk       # minimal :cljs (nbb) fs/env bridge; :clj call sites use
                      # java.io.File / core slurp / core spit directly
```

`bmc.canvas` and `bmc.ledger` take zero product literals: the base datoms
file, ledger events, and display labels are all supplied by the caller.
`bmc.gate` likewise takes the caller's own `gate-specs` table — this library
only implements the evaluator half, not any concrete product's gates.

## Test

```
kbb -M:test
```

(No test sources exist yet — see "Known gap" above.)
