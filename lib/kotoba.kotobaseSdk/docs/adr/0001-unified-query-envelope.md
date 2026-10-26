# ADR-0001: Unified polyglot query envelope

- Status: Accepted and deployed
- Date: 2026-08-01

## Context

Kotobase already has independent query implementations for Datomic-shaped
Datalog, openCypher, SPARQL, GraphQL, and Gremlin. Their native transports and
result shapes differ. Reimplementing parsers or translating queries inside each
language SDK would multiply semantic drift and security review work.

## Decision

Expose one read-only XRPC procedure:

```text
ai.gftd.apps.kotobase.query.execute
```

Its JSON request carries a language discriminator, the native query document,
parameters, graph/database scope, and portable execution options. Its response
wraps the engine-native JSON value in common metadata. The OpenAPI document is
the language-neutral source of truth.

The server gateway is an adapter, not a query engine:

| Language | Existing implementation target |
|---|---|
| `datalog` | `datomic-client-shim` / `datomic.q` |
| `cypher` | `org-opencypher-cypher` |
| `gremlin` | `org-apache-tinkerpop-gremlin` traversal core |
| `graphql` | `org-graphql-http` |
| `sparql` | `org-w3-sparql-protocol` |

Gremlin uses JSON bytecode (`[["V"], ["hasLabel", "users"], ...]`) rather
than executing arbitrary Groovy strings. This preserves the current Gremlin
security boundary.

## Invariants

1. Query execution is read-only. Mutations remain on explicit, separately
   authorized write APIs.
2. Tenant/database scope is resolved and authorized by the edge; an SDK value
   never grants access by itself.
3. Unknown languages, unknown options, unavailable engines, and unsupported
   language features fail explicitly.
4. The gateway passes native query semantics through without cross-language
   rewriting.
5. Request IDs, error codes, retryability, basis/provenance CIDs, elapsed time,
   truncation, and warnings use the same envelope in every SDK.
6. A response body is size-limited at the edge. `limit` is a request ceiling,
   not permission to bypass server quotas.

## Server integration sequence

1. Add a Lexicon for `ai.gftd.apps.kotobase.query.execute` matching the OpenAPI
   schema.
2. Mount the procedure in the net-kotobase edge read allowlist.
3. Add adapters around each existing query implementation. Keep visibility and
   tenant predicates mandatory at the adapter boundary.
4. Add contract fixtures shared by the gateway and all SDKs.
5. Deploy capability discovery before enabling engines individually. An
   unavailable engine returns `engine_unavailable`, never an empty result.

## Consequences

Applications get one stable API and idiomatic helpers in every supported host
language. Native protocol compatibility endpoints may continue to exist for
specialized drivers. The common client surface intentionally exposes the
engine-native result under `data`; forcing GraphQL objects, SPARQL bindings,
Cypher rows, and Gremlin values into one fake table would lose information.

## Deployment record

The gateway was deployed on 2026-08-01 as Cloudflare Worker
`net-kotobase-query-gateway`, owning only the exact route
`kotobase.net/xrpc/ai.gftd.apps.kotobase.query.execute`. Initial production
version: `f84bad87-5aca-4505-90bf-d96947552a4c`.
Current verified version after 5xx sanitization:
`cc723493-15e0-4b24-83e5-179343fade65`.

Cypher, Gremlin, and SPARQL protocol hosts were live at deployment time.
Datalog dispatches through the existing tenant-scoped apex `datomic.q` route.
The GraphQL hostname was not yet resolvable, so GraphQL calls fail explicitly
with `engine_unavailable` until that independent surface is deployed.
