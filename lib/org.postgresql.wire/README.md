# org-postgresql-wire

[![CI](https://github.com/kotoba-lang/org-postgresql-wire/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-postgresql-wire/actions/workflows/ci.yml)

`postgresql.kotobase.net` — a real PostgreSQL frontend/backend wire
protocol (version 3.0) handshake + simple-query subprotocol, over a
small, real SQL subset, running against
[`kotobase`](https://github.com/kotoba-lang/kotobase)-backed data via
[`kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
(ADR-2607172300 in `com-junkawasaki/root` — the "biggest, riskiest lift"
of that ADR's batch, explicitly scoped by the owner to a real SQL subset
alongside the wire handshake, not a handshake-only stub).

> [!WARNING]
> **NO TLS. NO REAL AUTHENTICATION. NOT SAFE TO EXPOSE ON A NETWORK YOU
> DON'T FULLY TRUST.** A client's `SSLRequest` is answered with a plain
> `N` (deny) byte — there is no TLS negotiation implemented at all.
> Every `StartupMessage` is answered `AuthenticationOk` unconditionally
> — no password, no SCRAM, no certificate check, no per-user/per-database
> access control of any kind. This is an explicit, deliberate v0.1
> carve-out the ADR itself names ("skip real auth for v0.1... this is
> not meant to be internet-exposed as-is"), not an oversight. Treat this
> the same way you'd treat an unreviewed network daemon: fine for local
> experimentation, this repo's own tests, and its own demo — not fine
> for anything that needs to actually keep data confidential or a
> service actually available against an adversary.

## Two independently-useful layers

| Layer | Namespace | Status |
|---|---|---|
| **SQL core** — a hand-written parser, `kotobase-query`-Datalog translator, and executor for a small, real SQL subset | `kotobase.pg.sql` (`.cljc`) | Solid. 28 tests / 47 assertions, pure, JVM-testable, zero socket/wire concepts. |
| **Wire transport** — the Postgres v3.0 startup handshake + simple-query subprotocol over plain TCP | `kotobase.pg.wire` (`.cljs`-only) | Genuinely works, unit-tested AND cross-process-tested (see below) — no security review, no TLS, no real auth (see warning above). |

Same core/transport separation `kotobase.sftp.fs` /
`kotobase.sftp.transport.*` established in
[`kotoba-lang/org-ietf-sftp`](https://github.com/kotoba-lang/org-ietf-sftp):
`kotobase.pg.sql` has no idea a socket exists; `kotobase.pg.wire` has no
SQL grammar knowledge of its own, it only calls
`kotobase.pg.sql/execute`.

## `kotobase.pg.sql` — the v0.1 SQL subset (read this before extending)

**Exactly this shape is supported, and nothing more — a deliberate scope
boundary confirmed by the owner in ADR-2607172300, not laziness:**

```sql
SELECT <col1>, <col2>, ... FROM <collection> WHERE <col> = <literal>
```

- single table (`FROM` names exactly one `kotobase.store` collection)
- `WHERE` is optional; if present, exactly ONE `<col> = <literal>`
  equality predicate
- `<literal>` is a single-quoted string, an integer/decimal number,
  `TRUE`/`FALSE`, or `NULL`
- `SELECT` list is an explicit, non-empty column list

**Explicitly unsupported, and REJECTED WITH A CLEAR ERROR** (never
silently mis-executed) — parsing throws `ex-info` with
`:type :kotobase.pg.sql/unsupported-syntax` and a `:feature` key
(`:join`, `:aggregate-or-function`, `:subquery`, `:order-by`,
`:group-by`, `:limit`, `:select-star`, `:distinct`,
`:comparison-operator`, `:compound-where`) or
`:type :kotobase.pg.sql/syntax-error` for malformed input:

- joins (multiple `FROM` tables, any `JOIN` keyword)
- aggregates (`COUNT`/`SUM`/`AVG`/`MIN`/`MAX`/any function-call syntax
  in `SELECT`)
- subqueries (a nested `SELECT` anywhere)
- `ORDER BY` / `GROUP BY` / `LIMIT` / `OFFSET` / `DISTINCT`
- `SELECT *`
- any comparison operator other than `=`, or more than one `WHERE`
  predicate (`AND`/`OR`)

`ORDER BY`/`LIMIT` were considered "trivial to add" per the task scope,
but deliberately left out: `bridge/query` returns an unordered result
**set**, so `LIMIT` without `ORDER BY` would be meaningless, and adding
real `ORDER BY` support pulls in comparison/sort-key semantics that
aren't otherwise needed for this v0.1 subset — scope discipline over
convenience, matching the task's explicit warning against scope creep
away from the wire-protocol work.

### Doc → row mapping

Delegates entirely to
[`kotobase.query.bridge`](https://github.com/kotoba-lang/kotobase-query)'s
doc→datoms mapping: a `SELECT` column name is looked up as a top-level
document attribute (as a keyword — SQL column `role` reads doc attribute
`:role`). A row is produced only for entities that have a value for
EVERY selected column (and the `WHERE` column, if present) — an entity
missing one of those attributes simply drops out of the result, the
same behavior `arrangement.datalog`'s pattern matching already has for
an unbound clause (not a `NULL` cell — a richer query shape than this
v0.1 subset would be needed for real SQL `NULL`-on-missing-column
semantics).

### Worked example

```clojure
(require '[kotobase.local :as local]
         '[kotobase.store :as st]
         '[kotobase.pg.sql :as sql])

(def store (local/local-store))
(st/-put store "users" "u1" {:name "Alice" :role "admin" :age 41})
(st/-put store "users" "u2" {:name "Bob" :role "user" :age 27})
(st/-put store "users" "u3" {:name "Carol" :role "admin" :age 35})

(sql/execute store "SELECT name, role FROM users WHERE role = 'admin'" (constantly true))
;=> {:columns ["name" "role"] :rows [["Alice" "admin"] ["Carol" "admin"]]}
```

`visible?` (the final argument) is **required, not defaulted** — same
discipline `kotobase.query.bridge` itself enforces (ADR-2607050500, no
permissive default). `kotobase.pg.wire`'s `start-server!` takes its own
`:visible?` and threads it straight through; it does not invent one.

## `kotobase.pg.wire` — the wire transport

- **Startup**: reads the client's `StartupMessage`, answers `SSLRequest`
  with a plain deny byte `N` (no TLS — see warning), answers a real
  startup with `AuthenticationOk` + `ParameterStatus` × several +
  `BackendKeyData` + `ReadyForQuery`.
- **Simple query**: reads a `Query` (`'Q'` + SQL text) message, runs it
  through `kotobase.pg.sql`, responds `RowDescription` + `DataRow` × N +
  `CommandComplete` + `ReadyForQuery` on success, or `ErrorResponse` +
  `ReadyForQuery` if `kotobase.pg.sql/execute` throws — an out-of-scope
  or malformed query is a normal Postgres-shaped error to the client,
  never a silent mis-execution or a crashed connection.
- `Terminate` (`'X'`) closes the connection.
- Every OTHER frontend message (the extended query protocol —
  `Parse`/`Bind`/`Execute`/`Describe`/`Sync`/`Close` — and `CopyData`
  etc.) gets `ErrorResponse` ("unsupported message type") +
  `ReadyForQuery`, not a crash or silent hang.
- **Result shaping**: every column is reported as Postgres OID 25
  (`text`), text format — `kotobase.query.bridge` materializes
  schemaless documents, so there's no static column type to report.
  Values are rendered to their TEXT wire form: strings as-is, numbers
  via `str`, booleans as `t`/`f`, `nil` as SQL `NULL`.

Zero npm dependencies — plain `node:net` + `Buffer`, the same house
style `kotoba-lang/dtn` and `kotoba-lang/org-ietf-sftp` use for their own
real-TCP transports (ADR-2607161817, ADR-2607162135).

### What's actually verified (read this before trusting anything above)

| Claim | Verified how | Confidence |
|---|---|---|
| Message framing (startup packet, tagged messages, `SSLRequest`/`StartupMessage` classification) | Unit tests, `wire_test.cljs` — 19 tests covering every message builder/decoder round-trip, `NULL`-vs-empty-string distinction, mixed value-type `DataRow` encoding | High |
| `kotobase.pg.sql` parser: valid queries, and rejection of every named out-of-scope construct | Unit tests, `sql_test.cljc` — 28 tests / 47 assertions, including explicit rejection tests per out-of-scope `:feature` | High |
| `kotobase.pg.sql` → `kotobase-query` translation + real execution (joins/aggregates NOT exercised — out of v0.1 scope) | Unit tests against a real materialized `kotobase.local` store, including a numeric-literal `WHERE`, a `visible?` redaction test, and a column-missing-on-some-rows test | High |
| Full handshake (`SSLRequest` → deny → `StartupMessage` → `AuthenticationOk`/`ParameterStatus`/`BackendKeyData`/`ReadyForQuery`) + simple-query round trip, END TO END, ACROSS TWO REAL OS PROCESSES, OVER A REAL SOCKET | `test/kotobase/pg/wire_demo.cljk`, **16/16 checks passed** — this is the strongest evidence in this repo | High, for THIS repo's hand-rolled client talking to THIS repo's server |
| An out-of-scope query (`SELECT COUNT(*) FROM users`) producing a real `ErrorResponse` (not a mis-execution or dropped connection), AND the connection surviving to serve a further query afterward | Exercised live in `wire_demo.cljs` (checks 13–16) | High |
| Interop with a real `psql`, `libpq`, or any off-the-shelf Postgres client/driver | **Not tested. Not claimed.** | None |
| Resistance to a real adversary (malformed-input fuzzing, resource-exhaustion, protocol-downgrade) | **Not tested. Not claimed.** | None |
| Security review by anyone other than the implementing agent | **Has not happened.** | None |
| `ORDER BY` / `LIMIT` / joins / aggregates / subqueries / prepared statements / COPY | **Not implemented at all — see scope sections above.** Not "untested," genuinely absent. | N/A |

### Try it by hand

```bash
kbb --backend sci --classpath "src:test:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" \
  bin/pg_node.cljk listen --port 6543
# separate terminal / process -- no general-purpose CLI Postgres client
# ships here (see kotobase.pg.wire's own docstring: the client this repo
# provides is demo/test-only, in test/kotobase/pg/wire_demo.cljk); use
# that file as a worked example of driving it, or the REPL API directly.
```

The pre-seeded fixture store (`bin/pg_node.cljk`) has a `users`
collection with `name`/`role`/`dept-key`/`age` — try
`SELECT name, role FROM users WHERE role = 'admin'` against it.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority: `kotoba
wasm` > `clojurewasm` > `ClojureScript` > `nbb` > (jvm/bb)):

```bash
git clone https://github.com/kotoba-lang/kotobase-query .deps/kotobase-query
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
git clone https://github.com/kotoba-lang/arrangement .deps/arrangement
git clone https://github.com/kotoba-lang/prolly-tree .deps/prolly-tree
git clone https://github.com/kotoba-lang/io-ipld .deps/io-ipld
git clone https://github.com/kotoba-lang/io-multiformats .deps/io-multiformats
git clone https://github.com/kotoba-lang/org-ietf-cbor .deps/org-ietf-cbor
npm install

CP="src:test:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src"

# Pure .cljc SQL suite + .cljs-only wire-framing/message unit tests (fast, no sockets)
kbb --backend sci --classpath "$CP" bin/run_tests.cljk

# The real cross-process Postgres-wire demo (slower -- spawns a second OS process)
kbb --backend sci --classpath "$CP" test/kotobase/pg/wire_demo.cljk
```

Each `.deps/<name>` should be checked out at the SHA pinned in
`deps.edn` (`kotobase-query`, `kotobase`) or transitively in
`kotobase-query`'s/`arrangement`'s own `deps.edn` (the rest) — CI pins
every one, see `.github/workflows/ci.yml`.

The `:test` alias in `deps.edn` is the JVM **compat** suite for the pure
`.cljc` core (`kotobase.pg.sql`) only (`kbb -M:test`, via
`tools.deps` transitive git-dep resolution) — it never loads anything
under `src/kotobase/pg/wire.cljk` (`.cljs`-only, cannot run on the JVM
at all).

## Scope guards (read before extending)

- **The SQL subset is deliberately tiny — see the rejection list above.**
  Adding joins/aggregates/subqueries/`ORDER BY` is real, valuable future
  work, but is out of THIS repo's v0.1 boundary per ADR-2607172300; if
  you need one of those, that's a new, separately-scoped change, not a
  quiet extension.
- **The wire transport is not a security boundary today.** No TLS, no
  real auth (see the warning at the top) — do not expose this to an
  untrusted network.
- **`kotobase.pg.sql` has no socket/wire-protocol concepts** — keep it
  that way; it's the single swap-in point for any future transport.
- **Result values are always `text`-typed on the wire** (OID 25) — real
  Postgres `int4`/`bool`/etc. type-OID fidelity is not implemented; see
  "Result shaping" above.

## License

Apache-2.0
