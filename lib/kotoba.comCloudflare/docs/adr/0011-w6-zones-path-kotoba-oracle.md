# ADR 0011: W6 zones query + hostname-match kotoba oracle

- Status: Accepted
- Date: 2026-07-28

## Context

`kotoba/workers_path_core.kotoba` (com-cloudflare#2) already oracles base REST
path strings for workers / zones / pages (`/zones`, `/dns_records`,
`/workers/routes`, `/workers/domains`, `/pages/projects`).

Zones read surfaces still had pure leftovers not covered by those bases:

1. `list-zones` passes `"/zones?per_page=50"` (query, not bare path)
2. `dns-records` optional `:name` filter becomes `?name=…` via `client/rest!`
3. Hostname discovery filters (`zone-by-name`, custom-domains, pages domains)
   are pure string equality over host results

## Decision

Port pure query construction + match to `kotoba/zones_path_core.kotoba`:

| function | notes |
|---|---|
| `list-zones-request-path` | exact `"/zones?per_page=50"` used by cljc |
| `dns-records-path` / `dns-name-query-pair` / `dns-records-path-with-name` | path + optional name query |
| `query-pair` / `with-query` | same shape as client_core |
| `hostname-matches?` | 1/0 string=? for discovery filters |

### Not ported

- `client/rest!` / HTTP / token getenv
- JSON parse of zone/DNS result maps
- List filter folds over zone vectors (host maps stay cljc)

## Evidence

- `test/cloudflare/zones_path_kotoba_parity_test.cljk`

## Related

- `docs/adr/ADR-260728-w6-analytics-path-kotoba-oracle.md` (workers_path_core)
- `docs/adr/0010-w6-client-kotoba-oracle.md` (query-pair / with-query)
