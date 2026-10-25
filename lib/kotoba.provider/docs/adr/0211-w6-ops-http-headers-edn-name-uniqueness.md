# ADR 0211: T8.3 header name uniqueness scan on EDN multi-header fold

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0210 multi-header append + result EDN

## Context

ADR 0189 / 0210 host-sequenced header packing does **not** enforce name
uniqueness (true set storage is W4). Product EDN folds still benefit from a
deterministic reject when the same header name is appended twice.

## Decision

Extend `http-request-edn-v1.wasm`:

| Export | Behavior |
|--------|----------|
| `headers_edn_has_name` | substring scan for `:name "…"` marker |
| `headers_edn_append` | reject (empty string) when name already present |

Scan is case-sensitive and tied to this encoder's map shape — **not** a
general set type / recursive ADT.

`main` fingerprint → **27005851950**.

### Honesty

- Does **not** claim W4 set storage or Component twin
- Does **not** flip `:wasm-aot` to `:implemented`
- Prefix false-positives possible if values embed the marker string (host
  still validates header policy separately)

## Evidence

- KIR: append A then A → `""`; append A then B → two-element vector
- Package registry sha match; ops kit tests green

## Related

- T8.3; ADR 0189 uniqueness residual; ADR 0210
- Follow-up: true set uniqueness under W4; Component twin (Canonical lowering)
