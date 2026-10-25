# ADR 0010: W6 cloudflare.client constants + URL/auth kotoba oracle

- Status: Accepted
- Date: 2026-07-28

## Context

Product surfaces (workers/zones/analytics/deploy) already have path and plan
oracles. `cloudflare.client` still owns the shared API base, GraphQL endpoint,
named secret identity, and REST URL assembly used by every `rest!`/`graphql!`
call.

## Decision

Port pure scalars to `kotoba/client_core.kotoba`:

| function | notes |
|---|---|
| `api-base` / `graphql-endpoint` | v4 endpoints |
| `api-token-secret-name` / `api-token-env-name` | secret-custody ids |
| `rest-url` / `query-pair` / `with-query` | URL construction |
| `bearer-auth` | Authorization header value |
| `transport-ok?` / `prefer-explicit-token?` / `secret-name-matches?` | host-projected policy |

### Not ported

- `jvm-http-fn` / `rest!` / `graphql!`
- JSON encode/decode
- `System.getenv`

## Evidence

- `test/cloudflare/client_kotoba_parity_test.cljk`
