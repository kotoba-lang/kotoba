# kotoba-lang/sparql

EDN-first SPARQL algebra: pattern-match/join/filter over
[`rdf.core`](https://github.com/kotoba-lang/rdf)-shaped quads.

A triple pattern is a 3-vector `[s p o]` where each position is either a
concrete RDF term (an `rdf.core` term map) or a logic variable (a symbol
whose name starts with `?`, e.g. `'?s`). The algebra is plain EDN, built
from these node shapes:

- `{:sparql/op :bgp :patterns [pattern ...]}` — basic graph pattern,
  patterns joined left-to-right on shared `?vars`
- `{:sparql/op :filter :pred (fn [bindings]) :pattern p}`
- `{:sparql/op :join :left p1 :right p2}`
- `{:sparql/op :union :left p1 :right p2}`
- `{:sparql/op :optional :left p1 :right p2}` — SPARQL `OPTIONAL`/LeftJoin
- `{:sparql/op :project :vars [...] :pattern p}`
- `{:sparql/op :distinct :pattern p}`
- `{:sparql/op :order-by :vars [...] :desc #{...} :pattern p}` — `:desc` is
  optional and names the subset of `:vars` to sort descending
- `{:sparql/op :group :by [?v ...] :aggregates [{:var ?c :fn :count :arg ?e}] :pattern p}`
  — `GROUP BY` + aggregates. `:fn` is `:count`/`:sum`/`:min`/`:max`/`:avg`,
  `:arg` a var or `:*` (COUNT(*)), optional `:distinct? true`. No `:by` means
  one group over everything, which exists even for an empty result (so
  `COUNT` answers 0 rather than no row); with `:by`, an empty result is zero
  groups. The numeric aggregates parse numbers out of string values — a datom
  plane that stringifies on write reports `30` as `"30"` — and skip what does
  not parse rather than throwing.
- `{:sparql/op :slice :offset n :limit n :pattern p}`

`select` and `ask` return solutions. `construct`, `describe` and
`describe-solutions` return an RDF **graph** — a SET of quad maps, because a
graph has no duplicates and no order and a seq would invite callers to depend
on both. A template triple with an unbound slot produces nothing (SPARQL 1.1
§16.2). `describe` returns the SUBJECT triples, not the Concise Bounded
Description the spec permits: CBD follows blank nodes and this library has no
blank-node syntax to follow. The spec leaves the shape implementation-defined
so a service can say which one it returns; this one says it.

```clojure
(require '[sparql.core :as sparql])

(def alice (assoc {} :rdf/type :iri :value "alice"))
;; ... or use rdf.core's iri/literal constructors directly

(sparql/select
 {:sparql/op :bgp :patterns [['?s role-pred (lit "admin")]
                             ['?s name-pred '?n]]}
 quads)
;;=> [{'?s alice-term '?n "Alice"-literal}]

(sparql/ask {:sparql/op :bgp :patterns [['?s role-pred (lit "admin")]]} quads)
;;=> true
```

## Not in this landing (explicit scope, matching `rdf`/`shacl`'s own
"full semantics left for a later processor layer" boundary)

- **No SPARQL text-syntax parser.** Callers build the algebra tree
  directly as EDN, the same philosophy `rdf`/`turtle`/`shacl` already
  commit to (no Turtle/N-Triples/N-Quads text parsing there either — a
  separate parser repo is the natural place for `SELECT ?s WHERE {...}`
  string syntax, if/when a caller needs it).
- **No aggregates** (`COUNT`/`SUM`/`GROUP BY`), **no property paths**
  (`pred+`/`pred*`), **no named-graph `GRAPH` clause**, **no `SERVICE`**
  federation. `:bgp`/`:filter`/`:join`/`:union`/`:optional`/`:project`/
  `:distinct`/`:order-by`/`:slice` only.
- **No storage of its own** — `select`/`ask` take a plain seq of
  `rdf.core`-shaped quads (or anything with `:subject`/`:predicate`/
  `:object` keys); wiring this against a real indexed store (e.g.
  `kotoba-lang/arrangement`) is a caller's job, not this repo's.
- **No dependency on `rdf.core`** — this repo pattern-matches against
  the `:subject`/`:predicate`/`:object` map shape structurally (duck
  typing), the same low-coupling choice `shacl` already makes against
  the same shape. A caller normally builds terms with `rdf.core`, but
  nothing here requires that specific library.

## Test

```bash
kbb -M:test
```
