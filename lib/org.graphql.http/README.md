# org-graphql-http

[![CI](https://github.com/kotoba-lang/org-graphql-http/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-graphql-http/actions/workflows/ci.yml)

**`graphql.kotobase.net` — a [GraphQL over HTTP](https://graphql.github.io/graphql-over-http/)
query surface over [kotobase](https://github.com/kotoba-lang/kotobase)**, wiring
the pure [`kotoba-lang/graphql`](https://github.com/kotoba-lang/graphql)
(`graphql-clj` — SDL parsing, query parsing, structural validation, a
field-resolution executor over host-injected resolvers) engine to the shared
[`kotobase-query`](https://github.com/kotoba-lang/kotobase-query) bridge
(ADR-2607172300 in `com-junkawasaki/root`), per ADR-2607172500.

## Naming — why not just `graphql`

`kotoba-lang/graphql` already exists as the reusable SDL/query-parsing/
execution *engine* — same relationship `kotoba-lang/sparql` has to
`org-w3-sparql-protocol`. GraphQL's actual transport spec is "GraphQL over
HTTP" (graphql.github.io/graphql-over-http/, maintained by the GraphQL
Foundation), so `org-graphql-http` names the spec this repo implements (the
HTTP binding), not the query language `kotoba-lang/graphql` already owns.

## Scope: this repo is the HTTP transport + resolver wiring, not a GraphQL engine

`kotoba-lang/graphql` does ALL of the actual GraphQL work: SDL → schema EDN
(`graphql.sdl`), query string → selection AST (`graphql.query`), schema
structural validation (`graphql.validate`), and pure field-resolution
execution over host-injected resolvers (`graphql.execute` + `graphql.ports`).
This repo does not reimplement any of that. `kotobase.protocols.graphql`'s
job is:

1. decode the request body per the GraphQL-over-HTTP `POST` shape,
2. reject what's explicitly out of v0.1 scope (mutations/subscriptions,
   `$variable` references — see below),
3. run `graphql.query/parse-query` plus a small query-level field-existence
   check against the schema (the one thing `graphql.validate` doesn't do —
   it validates the *schema's* own structural well-formedness, not a
   particular *request's* selections against it),
4. run `graphql.execute/execute-query` with resolvers that call into
   `kotobase.query.bridge` (materialize + `arrangement.datalog` query),
   threading the REQUIRED `visible?` redaction predicate through every
   resolver,
5. shape the result as `{"data": ..., "errors": [...]}` per the spec.

## v0.1 scope — query-only (ADR-2607172500)

No mutations, no subscriptions — matches every sibling query surface in this
project (SPARQL protocol, Datomic shim, PostgreSQL's SELECT-only subset,
Cypher's MATCH-only subset). `mutation { ... }` / `subscription { ... }`
operations are explicitly rejected with a named error, never silently
executed as if they were queries.

**No `$variable` substitution.** `graphql.query/parse-query`'s own README
states variable binding is unsupported (`$var` tokens are not bound to a
request's `"variables"` payload) — rather than silently mis-tokenize a
`$name` reference as an enum-shaped string literal, this repo detects
`$name` tokens up front and rejects the request with a clear error. Use
inline literal argument values instead (`user(id: "u1")`, not
`user(id: $id)`).

**No schema-from-`IStore`-collections auto-derivation.** The ADR explicitly
rejects this as v0.1 scope creep — a real, separable feature a future ADR
could add. Schema (a `graphql.model` EDN map, typically built via
`graphql.sdl/parse-schema`) and the field-resolver registry are supplied by
the deploy shell / test fixtures via `ctx`, not invented by this repo.

## Wire shape: `POST /graphql`

Request body:

```json
{"query": "{ user(id: \"u1\") { name department { name budget } } }"}
```

Response body:

```json
{"data": {"user": {"name": "Alice",
                    "department": {"name": "Engineering", "budget": 900000}}}}
```

Per the GraphQL over HTTP spec's request-error vs. execution-error split:

- malformed JSON, missing/non-string `"query"`, a mutation/subscription
  operation, a `$variable` reference, or a query that fails the
  field-existence check — **request errors**: no execution attempted,
  **HTTP 400**, body is `{"errors": [...]}` with **no** `"data"` key.
- a resolver throwing mid-execution — an **execution error**: **HTTP 200**
  (execution began, per spec), body is `{"data": null, "errors": [...]}`.
  `graphql.execute` is a pure, single-pass, whole-query executor with no
  per-field error tracking (its own docstring: resolvers are "assumed
  pure"), so v0.1 cannot offer partial `data` alongside `errors` the way a
  full GraphQL server can — a thrown resolver error aborts the whole
  request's data, the same way `org-opencypher-cypher` aborts its whole
  transaction on the first failing statement instead of fabricating a
  partial result.
- otherwise: **HTTP 200**, `{"data": {...}}` (no `"errors"` key when there
  are none).

## `visible?` — required, injectable, never defaulted

`ctx` passed to `handle` **must** include `:visible?` — a predicate over
materialized datoms, `(fn [{:keys [s p o]}] boolean?)` — the same discipline
`kotobase-query`/`arrangement.datalog` enforce (ADR-2607050500, "Query as
first-class effect": no permissive default to silently fall back on).
`handle` throws immediately if `:visible?` (or `:schema`) is missing — a
ctx-construction bug, not a wire-protocol error. Resolvers registered via
`kotobase.protocols.graphql/resolver` receive `ctx` as `{:store IStore
:visible? (fn [datom] boolean?)}` and must themselves thread `visible?` on to
`kotobase.query.bridge/query` — there is no silent `(constantly true)`
fallback baked into this namespace.

## Worked example

```clojure
(require '[graphql.sdl :as sdl]
         '[kotobase.local :as local]
         '[kotobase.store :as st]
         '[kotobase.query.bridge :as bridge]
         '[kotobase.protocols.graphql :as gql]
         '[kotobase.protocols.json :as json])

(def schema
  (sdl/parse-schema
   "type Query { user(id: ID!): User users: [User] }
    type User  { id: ID! name: String department: Department }
    type Department { id: ID! name: String budget: Int }"))

(def store (local/local-store))
(st/-put store "users" "u1" {:name "Alice" :dept-key "d1"})
(st/-put store "departments" "d1" {:name "Engineering" :budget 900000})

(defn user-resolver [_parent args {:keys [store visible?]}]
  (let [id (str (get args "id"))
        rows (bridge/query store ["users"]
                           '{:find [?name] :in [?id]
                             :where [[?u :kotobase/key ?id] [?u :name ?name]]}
                           visible? [id])]
    (when-let [[name] (first rows)] {:id id :name name})))

;; a real cross-collection JOIN (both collections materialized together
;; and joined in one :where, not two lookups glued together in app code)
(defn department-resolver [parent _args {:keys [store visible?]}]
  (let [rows (bridge/query store ["users" "departments"]
                           '{:find [?dk ?dname ?dbudget] :in [?uid]
                             :where [[?u :kotobase/key ?uid]
                                     [?u :dept-key ?dk]
                                     [?d :kotobase/key ?dk]
                                     [?d :name ?dname]
                                     [?d :budget ?dbudget]]}
                           visible? [(:id parent)])]
    (when-let [[dk name budget] (first rows)] {:id dk :name name :budget budget})))

(def ctx {:store store :visible? (constantly true) :schema schema
          :resolvers {["Query" "user"] user-resolver
                      ["User" "department"] department-resolver}})

(gql/handle ctx
  {:method :post :path "/graphql"
   :body (json/encode {"query" "{ user(id: \"u1\") { name department { name budget } } }"})})
;; => {:status 200 :headers {"content-type" "application/json"}
;;     :body "{\"data\":{\"user\":{\"name\":\"Alice\",\"department\":{\"name\":\"Engineering\",\"budget\":900000}}}}"}
```

## Audit choice

Same read-only-surface audit discipline as `org-opencypher-cypher`
(ADR-2607050500's "query as first-class effect"): every request that
actually reaches execution is appended to the shared
`:kotobase.protocols/audit` stream — `{:surface :graphql :op :query :query
<raw query text> :now ...}` on success, `{:surface :graphql :op :query-error
:query <raw query text> :error ... :now ...}` when a resolver throws.
Request-level errors (malformed JSON, invalid query, mutation attempt, etc.)
never reach execution and are **not** audited. Resolved data is never
audited, only the caller's own raw query text (no `$variable` values exist
to leak in v0.1, since those are rejected outright).

## Namespace

Single `.cljc` namespace, `kotobase.protocols.graphql`, matching the
established HTTP-handler pattern this org's other `kotobase.protocols.*`
surfaces use (`http.cljc`-shaped request/response, `s3.cljc`/
`ipfs_pinning.cljc`/`cypher.cljc`-shaped `(handle ctx req)` convention).
Contains the resolver-registry builder (`resolver`), the request-error
guards (mutation/subscription rejection, `$variable` rejection), the
query-level field-existence validator (`validate-selections` — the one gap
`graphql.validate` deliberately leaves to the host), and the HTTP handler
(`handle`).

## Dependencies

- [`kotoba-lang/graphql`](https://github.com/kotoba-lang/graphql) — the
  GraphQL SDL/query-parsing/validation/execution engine. Zero third-party
  runtime deps, `.cljc`.
- [`kotoba-lang/kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
  — the ADR-2607172300 bridge: `kotobase.query.bridge/materialize` (IStore
  docs → an `arrangement`-backed Datalog database) + `q`/`query`
  (delegates to `arrangement.datalog/q`). Resolvers in this repo target
  that bridge's `:find`/`:where`/`:in` shape directly; they do not
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
git clone https://github.com/kotoba-lang/graphql .deps/graphql
git clone https://github.com/kotoba-lang/kotobase-query .deps/kotobase-query
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase
git clone https://github.com/kotoba-lang/arrangement .deps/arrangement
git clone https://github.com/kotoba-lang/prolly-tree .deps/prolly-tree
git clone https://github.com/kotoba-lang/io-ipld .deps/io-ipld
git clone https://github.com/kotoba-lang/io-multiformats .deps/io-multiformats
git clone https://github.com/kotoba-lang/org-ietf-cbor .deps/org-ietf-cbor
npm install
kbb --backend sci --classpath "src:test:.deps/graphql/src:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" bin/run_tests.cljk
```

Each `.deps/<name>` should be checked out at the SHA pinned in `deps.edn`
(`graphql`, `kotobase-query`) or transitively in `kotobase-query`'s /
`arrangement`'s own `deps.edn` (the rest) — CI pins every one of them, see
`.github/workflows/ci.yml`.

The `:test` alias in `deps.edn` is the JVM **compat** suite only (`clojure
-M:test`, via `tools.deps` transitive git-dep resolution — no manual
`.deps/` cloning needed for this path) — not the primary execution path.

## License

Apache-2.0
