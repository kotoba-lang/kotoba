# org-opencypher-cypher

[![CI](https://github.com/kotoba-lang/org-opencypher-cypher/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-opencypher-cypher/actions/workflows/ci.yml)

**`cypher.kotobase.net` — an [openCypher](https://opencypher.org) v0.1 query
subset over [kotobase](https://github.com/kotoba-lang/kotobase), via the
shared [`kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
bridge** (ADR-2607172300 in `com-junkawasaki/root`).

`openCypher.org` is a real, citable, independently-specified open standard —
unlike a Datomic-shaped surface (see
[`datomic-client-shim`](https://github.com/kotoba-lang/datomic-client-shim)'s
README for why that sibling repo is deliberately *not*
reverse-domain-named), naming this repo `org-opencypher-cypher` does not
overclaim.

## Why HTTP, not Bolt

Neo4j's real Cypher wire protocol is **Bolt**: binary, stateful, session-based.
This repo does not implement Bolt. ADR-2607172300 explicitly chose the
**HTTP transaction-endpoint shape** (Neo4j's *HTTP Cypher API* —
`POST /db/data/transaction/commit`, plain JSON request/response) for v0.1:

- Bolt is a materially bigger lift (binary framing, session/transaction
  state machine) for no v0.1 capability gain.
- There is no Bolt precedent anywhere in this workspace.
- The HTTP shape fits the established `.cljc` **ring-shaped handler**
  pattern every other `kotobase-protocols`-style surface in this org uses
  (`{:method :path :headers :body}` → `{:status :headers :body}`) directly —
  no special transport split needed, `kotobase.protocols.cypher` is plain
  HTTP exactly like `kotobase.protocols.s3`/`ipfs-pinning`.

Bolt is left as an explicit possible future addition (ADR-2607172300,
Rejected section), not blocking this repo.

## Wire shape

`POST /db/data/transaction/commit`

Request body:

```json
{"statements": [
  {"statement": "MATCH (n:users) WHERE n.role = 'admin' RETURN n.name, n.role",
   "parameters": {}}
]}
```

Response body — **always HTTP 200** once the request itself is valid JSON
with a `statements` array (this matches the real HTTP Cypher API: per-query
errors are reported *inside* the body, not via HTTP status):

```json
{"results": [
  {"columns": ["n.name", "n.role"],
   "data": [
     {"row": ["Alice", "admin"], "meta": [null, null]},
     {"row": ["Carol", "admin"], "meta": [null, null]}
   ]}
 ],
 "errors": []}
```

Statements run **in order**; the first one that fails to parse or execute
**aborts the whole request** — `results` holds every statement that
succeeded before it, `errors` holds exactly one
`{"code": "...", "message": "..."}` entry, and statements after the
failing one never run. This mirrors the real HTTP Cypher API's auto-commit,
abort-on-first-error transaction semantics.

Malformed JSON, or JSON with no `statements` array, is a request-level
failure with **HTTP 400** (there is no statement to even attempt):

```json
{"results": [], "errors": [{"code": "Neo.ClientError.Request.InvalidFormat", "message": "malformed JSON body"}]}
```

`"code"` values (`Neo.ClientError.Statement.SyntaxError`,
`Neo.ClientError.Statement.SemanticError`,
`Neo.ClientError.Request.InvalidFormat`) are **modeled on**, not a
guaranteed-identical enumeration of, real Neo4j's `Neo.ClientError.*` code
namespace.

## v0.1 Cypher subset — hard scope boundary

```
MATCH (n:Label) [WHERE n.prop <op> <value> [AND n.prop2 <op> <value2> ...]]
                 ; <op> is one of  =  <  >  <=  >=  <>
  RETURN [DISTINCT] n.prop1 [, n.prop2 ...]
  [ORDER BY n.propA [ASC|DESC] [, ...]] [SKIP n] [LIMIT n]
```

- exactly one `MATCH`, one `RETURN`, at most one `WHERE`.
- every node pattern **must be labeled** — `(n:Label)`, never bare `(n)`.
- `WHERE` is a boolean expression: `=` `<` `>` `<=` `>=` `<>` combined with
  `AND`, `OR`, `NOT` and parentheses, at Cypher's precedence (OR looser than
  AND, AND looser than NOT) — no `IS NULL`/string functions/regex.
- `OR` branches may be conjunctions (`arrangement.datalog` takes `(and ...)`
  as a branch since kotoba-lang/arrangement#13), so a comparison, `IS NULL`, or
  a parenthesised group inside `OR` all work.
- **`NOT` negates the operator**, not the clause. Cypher is three-valued:
  `NOT n.age > 18` on a node with no `age` does not match, and operator
  negation keeps that while a datalog `not` would include those rows. `NOT`
  over `CONTAINS` has no negated form and is a named error.
- `IS NULL` / `IS NOT NULL` ask about **absence** — this store cannot hold the
  difference between missing and null, and neither does Cypher.
- `CONTAINS` maps onto the whitelisted `includes?`. No regex: a caller-supplied
  pattern is a ReDoS vector.
- **Multi-hop** patterns chain to any length; each hop gets its own foreign-key
  variable.
- `count(*)` / `count(n.prop)` group by the non-aggregate columns, and `AS`
  renames any output. **`count` counts nodes** — the entity variables enter
  `:find` when an aggregate is present, or datalog's set semantics would
  collapse four users holding two roles into 2. `=` puts the literal in
  the triple so the index can probe it; a comparison binds and then constrains
  via an `arrangement.datalog` predicate clause.
- `RETURN` projects one or more `var.prop` properties — never a bare node,
  never `*`, never `AS` aliasing, never an aggregate.
- `DISTINCT`, `ORDER BY` (per-item `ASC`/`DESC`), `SKIP` and `LIMIT` are
  supported, applied to result rows in Cypher's clause order — so `DISTINCT`
  collapses before `LIMIT` counts, which is the order that changes answers.
  `ORDER BY` may only name a property `RETURN` projects.
- values: string / number / boolean / `null` / `$parameter` literals only.
- **read-only**: `CREATE`/`MERGE`/`DELETE`/`SET`/`REMOVE`/`DETACH`/
  `FOREACH`/`CALL`/`UNWIND`/`LOAD CSV` are all **explicitly rejected** with
  a named error (`"CREATE is not supported -- ... v0.1 is a READ-ONLY query
  surface"`), never silently ignored or partially executed.
- **no** variable-length paths (`-[:REL*1..3]->`), **no** multi-hop chains
  (more than one relationship per pattern).

With no `ORDER BY`, rows are sorted by their stringified value for
deterministic output across runs — an implementation convenience, since the
bridge promises no order. `ORDER BY` is the contract.

### Label → collection mapping

A label is used **verbatim** as the `kotobase.store` collection name
materialized via `kotobase-query`'s `bridge/materialize` — `(n:users)`
queries the `"users"` collection exactly, no case-folding, no
pluralization, no other transform.

### Bonus (not required by v0.1, implemented anyway): relationship patterns

`(a:LabelA)-[:REL_TYPE]->(b:LabelB)` (single hop, **directed rightward
only** — no `<-`, no undirected `--`) is a real cross-collection **join**
through `kotobase-query`'s bridge, not a stub. There is no native
"relationship"/"edge" concept in kotobase's flat document model, so this
repo defines its own convention: `a`'s materialized document must carry an
attribute named `(keyword (clojure.string/lower-case "REL_TYPE"))` — the
relationship type, case-folded to lower, underscores **unchanged** (e.g.
`WORKS_AT` → `:works_at`) — whose **string** value equals `b`'s
`:kotobase/key`. This is exactly the foreign-key-attribute join pattern
`kotobase-query`'s own README worked example uses (`:dept-key` joining a
department's `:kotobase/key`), just with the attribute name derived
mechanically from the Cypher relationship type. See
`test/kotobase/protocols/cypher_test.cljk`'s
`end-to-end-relationship-join` for a worked fixture (`(u:users)-[:WORKS_AT]->(d:departments)`
against users carrying a `:works_at` attribute).

## `visible?` — required, injectable, never defaulted

`ctx` passed to `handle` **must** include `:visible?` — a predicate over
materialized datoms, `(fn [{:keys [s p o]}] boolean?)` — the same
discipline `kotobase-query`/`arrangement.datalog` enforce (ADR-2607050500,
"Query as first-class effect": no permissive default to silently fall back
on). `handle` throws immediately if `:visible?` is missing or not a
function — a ctx-construction bug, not a wire-protocol error. Pass
`(constantly true)` to see everything materialized; that is always the
caller's explicit choice, never this namespace's default.

```clojure
(require '[kotobase.local :as local]
         '[kotobase.store :as st]
         '[kotobase.protocols.cypher :as cypher]
         '[kotobase.protocols.json :as json])

(def store (local/local-store))
(st/-put store "users" "u1" {:name "Alice" :role "admin"})
(st/-put store "users" "u2" {:name "Bob" :role "user"})

(def ctx {:store store :visible? (constantly true) :now "2026-07-17T00:00:00Z"})

(cypher/handle ctx
  {:method :post :path "/db/data/transaction/commit"
   :body (json/encode
          {"statements" [{"statement" "MATCH (n:users) WHERE n.role = 'admin' RETURN n.name, n.role"}]})})
;; => {:status 200 :headers {"content-type" "application/json"}
;;     :body "{\"results\":[{\"columns\":[\"n.name\",\"n.role\"],\"data\":[{\"row\":[\"Alice\",\"admin\"],\"meta\":[null,null]}]}],\"errors\":[]}"}
```

## Audit choice

This is a **read-only** query surface — there is no mutated document to
log the way `kotobase.protocols.s3`/`ipfs-pinning` audit their writes. Per
ADR-2607050500's "query as first-class effect" framing, every processed
statement is still appended to the shared `:kotobase.protocols/audit`
stream regardless of outcome:

- success: `{:surface :cypher :op :query :statement <raw Cypher text> :row-count N :now ...}`
- failure: `{:surface :cypher :op :query-error :statement <raw Cypher text> :code ... :error ... :now ...}`

**Parameter values are never audited** — only the raw statement text (the
caller's own Cypher source, not materialized data) and a row count, to
avoid leaking materialized property values or parameter payloads into the
audit trail.

## Namespace

Single `.cljc` namespace, `kotobase.protocols.cypher`, matching the
established HTTP-handler pattern directly (`http.cljc`-shaped
request/response, `s3.cljc`/`ipfs_pinning.cljc`-shaped `(handle ctx req)`
convention) — no special transport split needed, this is plain HTTP.
Contains a hand-written tokenizer + recursive-descent parser for the v0.1
grammar (`parse`), an AST → `kotobase-query`-shaped Datalog translator
(`translate`), an executor (`execute`, delegates to
`kotobase.query.bridge/query`), and the HTTP handler (`handle`). No
third-party Cypher parser dependency — the v0.1 grammar is small enough
that a hand-rolled scanner + parser is the right-sized tool, per
ADR-2607172300.

## Dependencies

- [`kotoba-lang/kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
  — the ADR-2607172300 bridge: `kotobase.query.bridge/materialize` (IStore
  docs → an `arrangement`-backed Datalog database) + `q`/`query`
  (delegates to `arrangement.datalog/q`). This repo's parser/translator
  targets that bridge's `:find`/`:where` shape directly; it does not
  reimplement materialization or query evaluation.
- transitively (via `kotobase-query`): `kotoba-lang/kotobase`
  (`kotobase.store`/`kotobase.local`), `kotoba-lang/arrangement` (the
  4-covering index + `arrangement.datalog`), and *its* transitive
  `prolly-tree`/`io-ipld`/`io-multiformats`/`org-ietf-cbor` (required at
  namespace-load time by `arrangement.core`'s `commit!`/CID-snapshot
  machinery, unused by this chain but pulled in transitively — see
  `kotobase-query`'s own README for the full explanation).
- npm `@noble/hashes` — same transitive JS-runtime dep `kotobase-query`
  needs (`multiformats.core` under `:cljs`); mirrors `kotobase-query`'s
  `package.json` exactly.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority):

```bash
git clone https://github.com/kotoba-lang/kotobase-query .deps/kotobase-query
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
git clone https://github.com/kotoba-lang/arrangement .deps/arrangement
git clone https://github.com/kotoba-lang/prolly-tree .deps/prolly-tree
git clone https://github.com/kotoba-lang/io-ipld .deps/io-ipld
git clone https://github.com/kotoba-lang/io-multiformats .deps/io-multiformats
git clone https://github.com/kotoba-lang/org-ietf-cbor .deps/org-ietf-cbor
npm install
kbb --backend sci --classpath "src:test:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" bin/run_tests.cljk
```

Each `.deps/<name>` should be checked out at the SHA pinned in `deps.edn`
(`kotobase-query`) or transitively in `kotobase-query`'s / `arrangement`'s
own `deps.edn` (the rest) — CI pins every one of them, see
`.github/workflows/ci.yml`.

The `:test` alias in `deps.edn` is the JVM **compat** suite only (`clojure
-M:test`, via `tools.deps` transitive git-dep resolution — no manual
`.deps/` cloning needed for this path) — not the primary execution path.

## License

Apache-2.0
