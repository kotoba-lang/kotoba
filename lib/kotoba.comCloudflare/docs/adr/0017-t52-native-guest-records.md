# ADR 0017: T5.2 native guest records for multi-arg pure (com-cloudflare)

- Status: accepted
- Date: 2026-08-01
- Depends: T5.2 call-record host bridge (ADR 0015), T6.4 mirror-delete (ADR 0016)
- WBS: T5.2 residual multi-arg pure → single guest records

## Decision

Port murakumo-style **native guest records** into com-cloudflare product shells:

1. Add `cloudflare.kotoba.oracle/record` (schema + host-map → wire record).
2. Fold multi-arg pure exports into single-record inputs:

| Core | Exports | Schema |
|------|---------|--------|
| `client` | `query-pair`, `with-query`, `rest-url` | `:client/kv`, `:client/path-qs` |
| `deploy` | path builders, multipart, wrangler cmd | `:deploy/account-name`, `multipart-part`, `parts`, `parts-close`, `wrangler` |
| `zones_path` | `query-pair`, `with-query`, `dns-records-path-with-name`, `hostname-matches?` | `:zones/*` |
| `pages_bulk` | `pages-upload-token-path`, `ends-with?`, `hash-known?`, `missing-hash?` | `:pages/*` |
| `stream` | `validate-flags`, `destination-url`, paths, summary | `:stream/*` |
| `logpush_path` | `job-path` | `:logpush/zone-job` |

Host call sites use `oracle/record` + `[[:in :raw]]`.

3. Bump test compiler pin to murakumo-compatible
   `98b56bdb` and kotoba-kir `767f2f2` (record-get sugar + profile 5).

## Non-claims

- analytics_parse map tallies / sumN multi-arg remain (map-typed residual)
- T8.3 nested EDN / W4 still open on provider kits

## Evidence

- KIR regenerated for all 9 product-shell cores
- `kbb -M:test` 94 tests / 519 assertions green
