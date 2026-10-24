# ADR-0001 — kotoba-ledger-clj architecture: a shared append-only ledger for cloud-itonami and manimani

- Status: Accepted
- Date: 2026-07-06
- Context tags: agent-loop, ledger, cloud-itonami, manimani, portable-cljc
- Builds on: `local-manimani/src/manimani/ledger.cljc`,
  `kotoba-lang/kotoba-issue-clj` (companion library, event vocabulary),
  `90-docs/adr/2606272330-cae-shared-libs-and-seeds.md` (split-by-responsibility precedent)

## Decision

Promote manimani's `ledger.cljc` — already a pure, host-independent JSONL
codec plus last-line-wins projection functions — into a standalone library,
renamed to the `issue`/`proposal`/`review`/`run` vocabulary shared with
`kotoba-issue-clj`, and add the I/O backends manimani's own babashka path was
missing.

## Why a separate library from kotoba-issue-clj

Per the CAE-libs precedent, purpose-typed libraries beat one grab-bag: the
gate is a state machine over live entities (single source of truth, one
writer per proposal); the ledger is a read-oriented, append-only projection
of the same events (many readers: CLIs, supervisors, UIs). They have
different consumers and different failure modes — a dashboard should be able
to read ledger projections without depending on gate semantics at all. The two
packages share field names/shapes by convention (both call a merged proposal
event's status `"merged"`, etc.) but neither requires the other's code.

## The gap this closes: babashka path never committed to git

manimani's own README states the ledger design as "1判断 = 1 git commit," but
investigation of the actual code found this true only for the TypeScript
server path (`server/src/ledger.ts`, which shells out to `git add`/`git
commit`). The babashka runner path (`src/manimani/runner.clj`) only
`spit`s the JSONL line — CI commits in a separate batch afterward, and the
Rust desktop/mobile paths use their own storage (kotoba-datomic CID transact /
companion-server sync) with no git commit at all. `kotoba.ledger.file-git`'s
`append-and-commit!` is a babashka/JVM-native git-commit-per-decision,
closing that gap for the path manimani's own docs already call canonical.

## Why `kotobase.cljc` is dependency-injected, not a kotobase-clj dependency

Keeping this library's own `deps.edn` free of a `kotobase-clj` dependency
avoids forcing every consumer (even ones with no kotobase deployment, e.g. a
throwaway CLI demo) to pull it in. `cloud-itonami` already has its own
kotobase client (`cloud_itonami.kotoba.cljc`/`net_kotobase.clj`); passing its
`transact!` in as a plain function satisfies `kotoba.ledger.kotobase/append!`
without this library needing to know kotobase-clj's actual API surface. This
mirrors `cloud_itonami.store/db-api`'s existing injection pattern.

## Module boundaries

```
core       event construction (issue-event/proposal-event/review-event/run-step)
           + JSONL parse-line/parse-jsonl/->line + projections (pure, no I/O)
file-git   #?(:clj ...) append-line!/commit!/append-and-commit! -- local JSONL + git
kotobase   append!/append-many! over a caller-supplied transact! fn -- CID-pinned path
```

## Mapping from manimani's `ledger.cljc`

| kotoba-ledger-clj | manimani `ledger.cljc` |
|---|---|
| `core/parse-line`/`parse-jsonl`/`->line` | same names, unchanged (already generic) |
| `core/issue-event` | (new — manimani's decision event conflated issue+proposal) |
| `core/proposal-event` | `decision`/`outcome` |
| `core/review-event` | (new — no distinct review event existed) |
| `core/run-step` | `agent-step` (`kind "agent"` -> `kind "run"`) |
| `core/latest-by-issue`/`pending-issue-ids` | `latest-by-item`/`pending-ids` (`itemId` -> `issueId`) |
| `core/run-events`/`run-status`/`run-statuses`/`supervisor-snapshot` | same names, same logic |
| `file-git/append-and-commit!` | (new — ports `server/src/ledger.ts`'s git-commit behavior to babashka/JVM) |
| `kotobase/append!` | (new — no kotobase-backed ledger path existed for manimani) |

## Consequences

- manimani's `agent.cljc`/`runner.clj` and `ledger.cljc` adopt this
  library's field names (`issueId` instead of `itemId`, `kind "run"` instead
  of `kind "agent"`) when they're refactored onto it (Phase C of the
  companion implementation plan) -- existing `data/decisions.jsonl` files
  predate this rename and are not migrated automatically; `run-status`/etc.
  reading an old-format file simply won't recognize its `itemId`/`kind
  "agent"` lines until re-emitted in the new shape.
- Scope explicitly excludes manimani's TypeScript/Rust ledger writers for the
  same reason as `kotoba-issue-clj`: `.cljc` cannot run there. Those can
  converge on the same JSON field names without adopting this library's code.
