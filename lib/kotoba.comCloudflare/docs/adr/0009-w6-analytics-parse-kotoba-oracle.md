# ADR 0009: W6 analytics parse tally/sum kotoba oracle

- Status: Accepted
- Date: 2026-07-28

## Context

`analytics_core.kotoba` covers GraphQL query text. `parse-daily-report` /
`parse-path-report` tallies were left cljc as map-bound. Typed guest maps
(`typed-map-*`) are available on the wasm32 oracle path, so the reduce step
can be shared without full JSON response parsing in guest.

## Decision

Add `kotoba/analytics_parse_core.kotoba`:

| function | notes |
|---|---|
| `empty-string-tally` / `string-tally-add` / `string-tally-get` | by-path/device/country |
| `empty-i64-tally` / `i64-tally-add` / `i64-tally-get` | by-status |
| `sum2` / `sum3` / `sum4` | daily totals + path total |
| `report-ok?` | host-projected error flag |

Host still parses GraphQL JSON → row fields; guest owns pure tally/sum folds.

### Not ported

- JSON / GraphQL response walk
- day sort-by-date
- `daily-report!` / `path-report!` / ISO clocks

## Evidence

- `test/cloudflare/analytics_parse_kotoba_parity_test.cljk`

## Related

- com-cloudflare#2 analytics query text oracle
