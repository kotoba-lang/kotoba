# kotoba-ledger

A generic append-only **issue / proposal / review / run ledger**: pure JSONL
event construction + last-line-wins projections, plus two pluggable I/O
backends (file+git, kotobase). `.cljc` core, zero-dep aside from `cheshire`
for JSON.

Generalizes manimani's `ledger.cljc` (already pure and cross-platform: JSONL
encode/decode + `run-status`/`supervisor-snapshot` projections) to the
`issue`/`proposal`/`review`/`run` vocabulary shared with
[`kotoba-issue-clj`](https://github.com/kotoba-lang/kotoba-issue-clj) — same
field shapes by convention, no code dependency between the two packages.

```
src/kotoba/ledger/
  core.cljc      event construction (issue-event/proposal-event/review-event/run-step) + JSONL codec + projections
  file_git.cljc  JVM/babashka-only: append a JSONL line + git commit (one event = one commit)
  kotobase.cljc  transact! ledger events via a caller-supplied fn -- the "kotoba git" / CID-pinned path
```

## Why a separate library from kotoba-issue-clj

The gate (`kotoba-issue-clj`) is a state machine over live entities; the
ledger is an append-only *projection* of the same events for
supervisors/CLIs/UIs to read. Different consumers, different volatility — a
UI wants ledger projections without ever calling `merge!`. Per
`90-docs/adr/2606272330-cae-shared-libs-and-seeds.md`'s precedent, these stay
two purpose-typed packages rather than one grab-bag library.

## Design

- `core.cljc` never touches disk or network — `parse-line`/`parse-jsonl`/
  `->line` are lifted near-verbatim from manimani's `ledger.cljc` (already
  host-independent), and the projections (`latest-by-issue`,
  `pending-issue-ids`, `run-status`, `run-statuses`, `supervisor-snapshot`)
  are the same proven logic, renamed from manimani's item/decision/agent
  terms to issue/proposal/run.
- `file_git.cljc` (`#?(:clj ...)`) fills a real gap: manimani's babashka
  runner path appends decisions to `data/decisions.jsonl` but never commits
  them to git (only its TypeScript server path does, via `ledger.ts`). This
  namespace brings `append-and-commit!` — one decision, one commit — to the
  babashka/JVM path too, matching manimani's own stated design.
- `kotobase.cljc` stays dependency-injected rather than requiring a concrete
  kotobase-clj dependency: pass in your own `transact!`-shaped fn (the same
  pattern `cloud-itonami`'s `store/db-api` already uses) and events become
  content-addressed, CID-pinned commits instead of local JSONL lines.

## Quickstart

```clojure
(require '[kotoba.ledger.core :as ledger]
         '[kotoba.ledger.file-git :as file-git])

(def event (ledger/proposal-event {:ts (str (java.time.Instant/now))
                                    :issue-id "issue-1" :proposal-id "prop-1"
                                    :kind :gmail/draft :risk :external-send
                                    :status :proposed :rationale "draft a reply"}))

(file-git/append-and-commit! "." "data/decisions.jsonl" event
                              (str "record proposal " (:proposalId event)))

(ledger/supervisor-snapshot (file-git/read-events "data/decisions.jsonl"))
```

## Tests

```sh
kbb -M:test
```
