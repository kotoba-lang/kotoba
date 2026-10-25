# ADR 0005: W6 Workers ES-module multipart upload plan

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0003 landed service-worker format PUT. Modern Workers use ES modules
uploaded as `multipart/form-data` with a `metadata` JSON part
(`main_module`, bindings, compatibility_date) plus one part per module
file (Cloudflare multipart upload metadata docs).

## Decision

| builder | role |
|---|---|
| `module-metadata` | pure metadata map |
| `encode-multipart` | pure multipart body + boundary |
| `workers-module-put-plan` | pure PUT plan |
| `put-worker-module!` | JVM live via `client/rest!` |

### Non-goals

- Pages bulk asset tree upload over REST (still wrangler argv)
- Durable Objects / assets binding expansion beyond pass-through `:bindings`

## Consequences

- Gap action `cloud-deploy-module-multipart` → done.
- Service-worker and module formats coexist as separate pure plans.
