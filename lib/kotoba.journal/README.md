# journal

[![CI](https://github.com/kotoba-lang/journal/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/journal/actions/workflows/ci.yml)

An **append-only EDN transaction journal** — the durable half of
[`langchain.db`](https://github.com/kotoba-lang/langchain)'s persistence port.
`create-conn` replays a journal to rebuild its in-memory index; every
subsequent `transact!` appends one line; restarting reads the same history
back.

```clojure
(require '[journal.core :as journal]
         '[journal.fs :as journal.fs]
         '[langchain.db :as db]
         '[langchain.persist :as persist])

(let [j (journal/journal (journal.fs/file-io "decisions.journal.edn"))]
  (db/create-conn schema (persist/scoped j :authn.decisions)))
;; => a Datomic-shaped conn whose history outlives the process
```

## Why

Several libraries here had each grown the same half-answer: emit Datomic
transaction data, then persist it by `pr-str`-ing one big map to a file and
rewriting that file on every write. Rewriting loses the property the datom
model is chosen for — you can no longer read what happened, only what is
currently true — and the rebuilt state was never actually queryable, because
nothing loaded it back into a database.

Splitting it in two fixes both ends: `langchain.db` is the index and the query
engine, this is the history. Neither knows about the other; `langchain.persist`
is the seam.

## Surface

`journal.core`:

- `journal` — build the host op map `{:append (fn [stream event]) :read (fn [stream since])}` over an injected sink
- `encode` / `decode` / `events` — the line codec and stream/`:tx` filtering, if you want the history without a database

`journal.fs` — sinks:

- `file-io` — appends to a path (JVM `java.io`, or ClojureScript on Node)
- `memory-io` — an atom, for tests and for hosts with no filesystem

A sink is just `{:read-text (fn []) :append-text! (fn [text])}`, so a host with
its own storage supplies one without this namespace being involved.

## Format

One EDN map per line, appended and never rewritten — the same shape as the
other append-only ledgers in this workspace, so `git log -p` on a journal reads
as a list of what happened rather than a diff of a rewritten blob.

```clojure
{:journal/stream :authn.decisions :tx 1 :tx-data [[:db/add 1 :authn.decision/decision :authenticated]]}
{:journal/stream :authn.decisions :tx 2 :tx-data [[:db/add 2 :authn.decision/decision :denied]]}
```

File order is transaction order — no sequence number is stamped, so an append
never has to read what is already there. `pr-str` escapes newlines inside
values, so a line break in the text is always a record boundary. Streams share
one sink: several connections can persist into the same file and each replays
only its own events.

## What append-only costs

A journal keeps every value it was ever given, including ones a later
transaction retracts — retraction removes a fact from the index, not from the
history. That is exactly what an audit ledger wants and exactly the wrong shape
for secrets. Do not journal a store whose delete has to actually erase;
[`authenticator`](https://github.com/kotoba-lang/authenticator)'s TOTP vault
stays a rewritten snapshot for this reason. `journal.langchain-test` pins the
behaviour down so nobody has to rediscover it.

## Design

Zero runtime dependencies; every namespace is `.cljc`. `journal.fs` is the only
host-specific code, behind reader conditionals for JVM and Node. `langchain` is
a **test** dependency only — `journal.langchain-test` proves the two shapes
still fit each other, and nothing in `src/` names it.

## Consumers

- [`authentication`](https://github.com/kotoba-lang/authentication) — authn decision ledger
- [`authorization`](https://github.com/kotoba-lang/authorization) — authz decision ledger

## Test

```bash
kbb -M:test          # CI: langchain from git
kbb -M:dev:test      # workspace: langchain from ../langchain
```
