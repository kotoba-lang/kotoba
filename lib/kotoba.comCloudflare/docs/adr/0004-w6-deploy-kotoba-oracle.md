# ADR 0004: W6 cloud-deploy kotoba pure oracle

- Status: Accepted
- Date: 2026-07-28

## Context

com-cloudflare#5 landed pure `cloudflare.deploy` plans (validators, paths,
put/delete plans, wrangler argv) plus live PUT. W6 oracle parity still needed
so guest code can share the fail-closed name policy and path surface.

## Decision

Port scalar cores to `kotoba/deploy_core.kotoba`:

| function | notes |
|---|---|
| `validate-account-id` / `validate-script-name` / `validate-project-name` | string error tag or `""` (ok); charset without regex |
| `workers-script-path` / `pages-project-path` / `pages-deployments-path` | pure path assembly |
| `put-content-type` / `put-method` / `delete-method` | plan constants |
| `wrangler-pages-deploy-cmd` | space-joined argv |
| `directory-ok?` / `script-body-ok-size?` | host-projected bounds |

### Not ported

- Plan map assembly (`{:method :path :headers :body}`)
- `put-worker-script!` / `delete-worker-script!` (HTTP + secret kit)

## Evidence

- `test/cloudflare/deploy_kotoba_parity_test.cljk`

## Related

- ADR 0003 cloud-deploy first slice
- com-cloudflare#1–#5 pure-request / deploy slices
