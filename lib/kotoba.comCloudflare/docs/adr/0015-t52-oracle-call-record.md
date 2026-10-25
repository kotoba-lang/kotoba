# ADR 0015: T5.2 oracle call-record host bridge (murakumo pattern port)

- Status: accepted
- Date: 2026-07-31
- Depends: ADR-0012 product-shell oracle authority; ADR-0014 cljs dual-source; murakumo#155+#261–#276
- WBS: T5.2 product host bridge — **com-cloudflare** pattern port

## Decision

Port murakumo's T5.2 structural host-map bridge into `cloudflare.kotoba.oracle`:

| API | Role |
|-----|------|
| `project-field` | kinded map field → guest ABI (`:string`/`:i64`/`:bool`/options/`:raw`) |
| `map->args` | ordered field-specs → positional arg vector |
| `call-record` | host map + specs → `call` |

All product-shell hosts with **non-empty** guest args now use `o-record` /
`oracle/call-record` instead of hand-built arity vectors:

`client`, `workers`, `zones`, `logpush`, `stream`, `deploy` (+ pages-bulk),
`pages`, `analytics`.

Zero-arg tokens stay `oracle/call []`. Host pure mirrors under `try-oracle`
remain (T6.4 mirror-delete is a separate track for this repo).

## Non-claims

- Guest export signatures unchanged.
- Native guest `[:record …]` parameter wire not claimed (exports stay scalar).
- Does not flip production AOT / signed-wasm readiness (T8.3).

## Evidence

- `oracle-call-record-test` + host/parity suites green
