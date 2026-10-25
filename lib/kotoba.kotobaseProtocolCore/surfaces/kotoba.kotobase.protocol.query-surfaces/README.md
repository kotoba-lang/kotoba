# kotobase-query-surfaces

**The four query-protocol surfaces — SPARQL 1.1, openCypher, Gremlin and GraphQL —
composed onto one router ctx, as a library.** `kotobase.query.surfaces`.

Each surface lives in its own repository and is a consumer of the shared query
bridge (`ayatori.query`): [`org-w3-sparql-protocol`](https://github.com/kotoba-lang/org-w3-sparql-protocol),
[`org-opencypher-cypher`](https://github.com/kotoba-lang/org-opencypher-cypher),
[`org-apache-tinkerpop-gremlin`](https://github.com/kotoba-lang/org-apache-tinkerpop-gremlin),
[`org-graphql-http`](https://github.com/kotoba-lang/org-graphql-http). This repository is
where they meet: a deployment hands `enrich` the hydrated state of a request's store
and gets back a ctx that `kotobase.protocols.router` can serve — `:surfaces`
(host label → handler), `:path-surfaces` (protocol path → surface), the GraphQL
schema and resolvers, the `:visible?` predicate and, for read-only surfaces, the
query memo.

Extracted on 2026-09-17 from the private deployment shell
`cloud-kotoba/control-plane/protocols-worker` (superproject ADR-2609171500: every
kotobase capability is an OSS library; `graph.kotoba.cloud` (private) and
`yataverse.com` (public) are two deployments of the same libraries). Nothing here
knows about Cloudflare, R2 or tenants.

## Use

```clojure
(require '[kotobase.query.surfaces :as surfaces]
         '[kotobase.protocols.router :as router])

;; per request: state is what the request's store was hydrated from
(let [ctx (surfaces/enrich {:store store} state (surfaces/surface-of path))]
  (router/handle ctx req))
```

- `surfaces/capabilities` — the machine-readable compatibility contract a
  deployment serves at `/capabilities` (conservative by design; a feature and
  its claim are reviewed in the same change).
- `surfaces/visible-everything` — the explicit *deployment* decision that the
  store handed to a request is already the isolation boundary. Every handler
  requires a `:visible?` predicate and refuses to run without one; there is no
  permissive default (ADR-2607050500).
- `surfaces/rdf4j-default-path?` — RDF4J compatibility names only
  `/repositories/default`.

## Test

First-class runtime is `kbb` (nbb/cljs). In the west workspace every dependency is a
sibling checkout under `orgs/kotoba-lang/`, so the test command lists their `src`
dirs (the exact list is the first comment line of `bin/run_tests.cljk`):

```sh
kbb --backend sci --classpath "src:test:../text/src:…" bin/run_tests.cljk
# Ran 5 tests containing 21 assertions. 0 failures, 0 errors.  (2026-09-17)
```

## License

Apache-2.0 (the kotobase family convention).
