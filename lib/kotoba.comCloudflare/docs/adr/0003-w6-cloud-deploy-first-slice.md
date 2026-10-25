# ADR 0003: W6 cloud-deploy first slice (pure plans + PUT worker)

- Status: Accepted
- Date: 2026-07-28

## Context

W6 kbb ability gap lists **cloud-deploy** (Workers/Pages deploy verbs under
grant) as low / missing. com-cloudflare already has pure request builders
for analytics/stream and secret-kit token resolution; deploy still required
ambient wrangler/ops knowledge.

## Decision

Add `cloudflare.deploy`:

| surface | role |
|---|---|
| pure validators + path builders | fail-closed names |
| `workers-script-put-plan` / delete-plan | pure REST plans |
| `wrangler-pages-deploy-argv` | process-kit argv (no PATH) |
| `put-worker-script!` / `delete-worker-script!` | JVM live via `client/rest!` |

Extend `client/rest!` + `jvm-http-fn` with `:put` and non-JSON content-type.

### Non-goals

- Module-format multipart Worker upload
- Pages asset bulk upload over REST (use wrangler argv or later slice)
- provider.cloud-deploy capability id (compose client + secret + process)

## Consequences

- Gap `:cloud-deploy` → **pure-plan first slice**.
- Ops hosts inject token via secret kit and optional process-kit for wrangler.
