# org-apache-tinkerpop-gremlin

[![CI](https://github.com/kotoba-lang/org-apache-tinkerpop-gremlin/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-apache-tinkerpop-gremlin/actions/workflows/ci.yml)

**`gremlin.kotobase.net` — a v0.1 [Apache TinkerPop](https://tinkerpop.apache.org)
Gremlin traversal subset over [kotobase](https://github.com/kotoba-lang/kotobase),
via the shared [`kotobase-query`](https://github.com/kotoba-lang/kotobase-query)
bridge** (ADR-2607172300 in `com-junkawasaki/root`, ADR-2607172500 scoping
this repo).

Apache TinkerPop is the real, citable open-source project (Apache Software
Foundation) that defines Gremlin — naming this repo
`org-apache-tinkerpop-gremlin` names the owning project precisely, the same
full-name-when-recognizable convention `org-vrmc-vrm`/`org-bluesky-atproto`
already use in this org (ADR-2607172500).

## Two namespaces, pure `.cljc` core + `.cljs`-only transport

| Namespace | Kind | Responsibility |
|---|---|---|
| `kotobase.gremlin.traversal` | pure `.cljc`, zero I/O | bytecode-shaped Gremlin traversal subset -> `kotobase.query.bridge` Datalog query -> results |
| `kotobase.gremlin.wire` | `.cljs`-only (real sockets) | GraphSON (JSON) `RequestMessage`/`ResponseMessage` envelope + a hand-rolled RFC 6455 WebSocket transport |

Same separation-of-concerns discipline `org-ietf-sftp` and
`org-postgresql-wire` use between core query-translation logic and
transport, and the same `.cljc`-core / `.cljs`-only-transport split
`kotoba-lang/nostr`'s `nostr.relay` / `nostr.relay.transport` established.

## Scope guard #1 — bytecode-shaped input, NOT raw Gremlin script strings

This repo does **not** parse Groovy-shaped Gremlin script text
(`g.V().hasLabel('users').values('name')` as a source string). It accepts a
small EDN vector-of-steps "bytecode" instead — structurally close to how
real TinkerPop Bytecode is shaped (a flat list of `[step-name & args]`
instructions), just simplified to plain EDN/JSON instead of TinkerPop's
GraphSON-typed Bytecode object graph:

```clojure
[[:V] [:hasLabel "users"] [:has "role" "admin"] [:values "name"]]
```

is the bytecode-shaped equivalent of
`g.V().hasLabel('users').has('role', 'admin').values('name')`. Avoiding a
Groovy-subset parser on top of everything else this repo already does
(translation + a real WebSocket transport) is a deliberate, honest v0.1
scope reduction (ADR-2607172500) — not a silent omission.

## Scope guard #2 — v0.1 traversal-step subset

| Step | Bytecode shape | Meaning |
|---|---|---|
| `g.V()` | `[:V]` | scan a materialized vertex collection — MUST be the first step |
| `.hasLabel(label)` | `[:hasLabel label]` | filter: current vertex's materialized collection name equals `label` |
| `.has(prop, value)` | `[:has prop value]` | equality filter on `prop` |
| `.out(edgeLabel)` | `[:out edgeLabel]` | outgoing edge traversal — see "Edge convention" below |
| `.in(edgeLabel)` | `[:in edgeLabel]` | incoming edge traversal (exact reverse of `.out`) |
| `.values(prop)` | `[:values prop]` | projection — the pivot: traversal steps before it, result steps after |
| `.dedup()` | `[:dedup]` | accepted, **no-op** — the bridge's Datalog `q` already has set semantics, so results arrive distinct |
| `.order()` | `[:order]` | natural ascending (bare only — no `.by()` modulators) |
| `.limit(n)` | `[:limit n]` | bound the answer to `n` rows |
| `.count()` | `[:count]` | reduce to a count — MUST be last, nothing may follow it |

`.dedup()`, `.order()`, `.limit(n)` and `.count()` operate on the **projected
results**, not on the traversal, and are applied in the order written — so
`.limit(2).count()` is 2 and `.count()` alone is the full size. Pushing them
into the Datalog `:where` would require the bridge to have a notion of order
and of a row window, which it does not.

**Explicitly OUT OF SCOPE for v0.1** (ADR-2607172500 — rejected with a clear
error, never silently ignored or partially executed):

- full Gremlin script `eval` (Groovy-shaped arbitrary expressions)
- `.repeat()` / variable-length paths
- lambda/closure-shaped traversal steps
- mutation steps (`addV`/`addE`/`drop`/`property` writes)
- transactions
- GraphBinary serialization (GraphSON — JSON — only, see below)
- multi-key `.values(k1, k2, ...)` fan-out (real Gremlin's flat multi-key
  stream semantics; v0.1 supports exactly one property per `.values()` call)
- `.hasLabel`/`.has` OR-semantics (`.hasLabel(l1, l2)`)

## Edge convention — this repo's own, documented mapping

kotobase's flat document model (`kotobase.store`: get/put/list per
collection, nothing else) has no first-class "edge" concept — same starting
point `org-opencypher-cypher`'s Cypher relationship-pattern bonus scope
documents for itself. This repo's own convention: a vertex represents an
outgoing edge labeled `edgeLabel` by carrying an attribute named
`(keyword edgeLabel)` whose value equals the **target** vertex's
`:kotobase/key` string (kotobase-query's own materialized-key convention).
Example — `.out("worksAt")` from a `users` vertex to a `departments`
vertex requires the `users` document to look like:

```clojure
{:name "Alice" :role "admin" :worksAt "d1"}   ; "d1" == the target dept's key
```

`.in("worksAt")` is the exact reverse traversal (find every vertex whose
`:worksAt` equals the CURRENT vertex's key) — a Datalog join run in the
opposite direction over the same stored attribute, not a separately
maintained "incoming edge" index.

## Vertex collections must be declared explicitly

Unlike Cypher (where both ends of a relationship pattern are labeled,
`(a:LabelA)-[:REL]->(b:LabelB)`, so the collections to materialize are
mechanically derivable), a Gremlin `.out()`/`.in()` step never names the
target vertex's label. `kotobase.gremlin.traversal/execute` therefore
requires the CALLER to declare, up front, every `kotobase.store` collection
to materialize as vertices — `ctx`'s `:vertex-colls` key, a seq of
collection identifiers passed straight through to
`kotobase.query.bridge/materialize`'s own `coll-keys` argument. This is
this repo's own v0.1 convention (see the ns docstring's "Vertex collections
MUST be declared explicitly" section) — the deploy shell / test fixtures
that own the graph schema are expected to supply the full vertex-collection
set, the same "deploy shell provides the schema" discipline ADR-2607172500
uses for `org-graphql-http`'s SDL.

## Scope guard #3 — GraphSON JSON, an honest v0.1 approximation of the wire

Real TinkerPop GraphSON `RequestMessage`/`ResponseMessage` wraps every typed
value (including the traversal itself, `g:Bytecode`) in GraphSON's typed
`{"@type": "...", "@value": ...}` envelope form, and additionally supports
an `"op": "eval"` mode for raw Gremlin script strings over Java's Groovy
runtime. **This repo does NOT implement GraphSON's typed `@type`/`@value`
wrapper format, and does not support `"op": "eval"` at all** — stated
plainly rather than silently claimed. What IS implemented, and real:

Request (one JSON object per WebSocket text frame):

```json
{"requestId": "<any string, echoed back verbatim>",
 "op": "bytecode",
 "processor": "traversal",
 "args": {"gremlin": [["V"], ["hasLabel", "users"], ["values", "name"]]}}
```

`args.gremlin` is a plain JSON array-of-arrays — this repo's own EDN
bytecode encoded straight to JSON, NOT real GraphSON-typed Bytecode.

Response:

```json
{"requestId": "<echoed requestId>",
 "status": {"code": 200, "message": "", "attributes": {}},
 "result": {"data": [...], "meta": {}}}
```

`status.code` is modeled on (not a guaranteed-identical enumeration of)
real TinkerPop Gremlin Server codes: `200` SUCCESS, `597`
translation/execution failure (out-of-scope step, malformed bytecode —
modeled on TinkerPop's `SCRIPT_EVALUATION_EXCEPTION`), `598` malformed
request (bad JSON, missing fields, `op` != `"bytecode"` — modeled on
TinkerPop's `MALFORMED_REQUEST`).

## WebSocket transport — reused/adapted from `kotoba-lang/nostr`, not re-derived

Real Gremlin Server protocol is WebSocket-based. Per ADR-2607172500's
explicit instruction, `kotobase.gremlin.wire`'s RFC 6455 handshake (SHA-1
accept-key via `node:crypto`) and frame codec (masking/unmasking, extended
length encoding, over raw `node:net`) is **adapted directly from
`kotoba-lang/nostr`'s `nostr.relay.transport`** — that repo already proved
this exact transport pattern works end-to-end (real cross-connection
fan-out test, 2/2 scenarios). What differs is only the payload semantics
inside each text frame (Gremlin `RequestMessage`/`ResponseMessage` instead
of Nostr's `EVENT`/`REQ`/`OK`/`EOSE`) — zero `ws` npm dependency, `.cljs`-
only, same as every transport in this consolidation series.

## `visible?` — required, injectable, never defaulted

`kotobase.gremlin.traversal/execute`'s `ctx` MUST include `:visible?`, a
predicate over materialized datoms (`(fn [{:keys [s p o]}] boolean?)`) —
the same discipline `kotobase.query.bridge`/`arrangement.datalog`/
`kotobase.protocols.cypher` enforce (ADR-2607050500, "Query as first-class
effect"). It throws immediately if missing — no silent
`(constantly true)` fallback. `kotobase.gremlin.wire/start-server!`
requires the same key in its own `opts` and threads it straight through.

## Result semantics — deduplicated set, not a Gremlin bag

Real Gremlin traversals have *bag* (multiset) semantics. This repo's
`execute` delegates straight to `kotobase.query.bridge/q`
(`arrangement.datalog` underneath), which returns a mathematical SET of
result tuples — duplicates are deduplicated, not a bug. Results are sorted
by stringified value for deterministic output (implementation convenience,
not a `.order()` guarantee — v0.1 has no `.order()` step).

## Develop / test

First-class runtime is nbb/cljs (repo-wide runtime priority: kotoba wasm >
clojurewasm > cljs > nbb > jvm/bb). Clone every transitive dep listed in
`deps.edn`'s comment into `.deps/<name>` at the pinned SHA:

```bash
kbb --backend sci --classpath "src:test:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" \
  bin/run_tests.cljk
# real cross-process WebSocket/GraphSON demo (spawns a second nbb OS process):
kbb --backend sci --classpath "src:test:.deps/kotobase-query/src:.deps/kotobase/src:.deps/arrangement/src:.deps/prolly-tree/src:.deps/io-ipld/src:.deps/io-multiformats/src:.deps/org-ietf-cbor/src" \
  test/kotobase/gremlin/wire_test.cljk
```

`deps.edn`'s `:test` alias is the JVM `:clj` COMPAT suite only (pure
`.cljc` — `kotobase.gremlin.wire` is `.cljs`-only and never loaded there):

```bash
kbb -M:test
```

## References

- ADR-2607172500 (`com-junkawasaki/root`) — the ADR that scoped this repo
- ADR-2607172300 — the four-surface `kotobase-query` precedent this ADR
  extends, and the source of the required, non-defaulted `visible?`
  discipline
- [`kotoba-lang/kotobase-query`](https://github.com/kotoba-lang/kotobase-query) —
  the materialize/query bridge this repo translates onto
- [`kotoba-lang/org-opencypher-cypher`](https://github.com/kotoba-lang/org-opencypher-cypher) —
  the sibling translator this repo's join convention and translate/execute
  split are modeled on
- [`kotoba-lang/nostr`](https://github.com/kotoba-lang/nostr)'s
  `nostr.relay.transport` — the WebSocket transport precedent this repo
  reuses/adapts
