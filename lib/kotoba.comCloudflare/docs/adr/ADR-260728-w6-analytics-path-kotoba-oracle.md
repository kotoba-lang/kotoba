# ADR-260728: W6 cloudflare pure-request oracle — analytics query + REST paths

Status: accepted second cutover slice of `cloudflare-pure-request-v1`

## Decision

Port pure string cores:

### `kotoba/analytics_core.kotoba`

| function | notes |
|---|---|
| `daily-query` | exact GraphQL for httpRequests1dGroups |
| `path-query` | host? 0/1 selects $host declaration + filter |
| `path-query-declares-host?` / `path-query-filters-host?` | includes checks |

### `kotoba/workers_path_core.kotoba`

| function | notes |
|---|---|
| `zone-routes-path` / `custom-domains-path` / `scripts-path` | workers product paths |
| `list-zones-path` / `dns-records-path` | zones product paths |
| `pages-projects-path` | pages product path |

### Not ported

- `parse-daily-report` / `path-report-rows` / tallies (map reduce)
- `daily-report!` / `path-report!` / ISO clock helpers
- Full request `{:query :variables}` maps

## Evidence

- `test/cloudflare/analytics_kotoba_parity_test.cljk`
- `test/cloudflare/workers_path_kotoba_parity_test.cljk`

## Related

- com-cloudflare#1 stream_core
- `lang/w6-cloudflare-path-inventory.edn`
