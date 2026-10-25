# ADR 0007: W6 Pages bulk Direct Upload pure plans

- Status: Accepted
- Date: 2026-07-28

## Context

W6 cloud-deploy still listed **Pages bulk asset deploy over REST** as
optional (wrangler argv already available). Direct Upload is a three-step
host flow (upload JWT → missing blobs → deployment manifest).

## Decision

Pure builders in `cloudflare.deploy`:

| builder | role |
|---|---|
| `validate-asset-path` | fail-closed relative paths |
| `pages-asset-manifest` | path→sha256 from content map |
| `pages-missing-hashes` | set difference for skip-upload |
| `pages-assets-upload-payload` | blob upload body shape |
| `pages-deployment-manifest-plan` | multipart POST deployments |
| `pages-bulk-deploy-plan` | ordered multi-step pure plan |
| `get-pages-upload-token!` / `create-pages-deployment!` | JVM live helpers |

Host still injects JWT for the assets-upload step (`Authorization: Bearer
<jwt>`); API token is used for token mint + deployment create via secret kit.

### Non-goals

- Binary/non-UTF8 assets in pure plan (string bodies only)
- Full wrangler parity (functions, headers, redirects files)

## Consequences

- Gap action `cloud-deploy-pages-bulk` → **done**.
- W6 kbb optional polish list is empty; further work is product-driven.
