# ADR 0006: W6 cloud-deploy module multipart kotoba oracle

- Status: Accepted
- Date: 2026-07-28

## Context

com-cloudflare#7 landed pure ES-module multipart plans (`validate-module-name`,
`encode-multipart`, `workers-module-put-plan`). ADR 0004 covered service-worker
validators/paths; module surfaces needed the same oracle parity.

## Decision

Extend `kotoba/deploy_core.kotoba`:

| function | notes |
|---|---|
| `validate-module-name` | blank / length / NUL / `..` / absolute / charset |
| `multipart-part` / `multipart-close` / `encode-parts` / `encode-parts-close` | pure CRLF body (ABI ≤5) |
| `boundary-ok?` / `multipart-content-type` | boundary policy + Content-Type |
| `module-js-content-type` / `metadata-content-type` | part type constants |
| `modules-count-ok?` / `max-module-name` / `max-modules` | host-projected bounds |

### Not ported

- Full `workers-module-put-plan` (module map + JSON metadata assembly)
- `module-metadata` map + `put-worker-module!`

## Evidence

- `test/cloudflare/deploy_kotoba_parity_test.cljk`

## Related

- ADR 0005 module multipart plan
- ADR 0004 deploy oracle (validators/paths)
