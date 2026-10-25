# ADR 0196: T8.3 pure memory-scan HTTP header set packing

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0189 typed set packing walk; ADR 0195 pure header pair scan

## Context

Typed host-sequenced set packing (0189) and pure single-pair scan (0195)
exist. A pure **one-shot set packing** scan over N pairs in linear memory
completes pure-path parity without `kotoba:typed` (Component-packable).

## Decision

```
http_headers_set_scan(n, table_ptr) → i32
```

Table layout: `n` records of 4×i32 LE at `table_ptr`:

```
name_ptr | name_len | value_ptr | value_len
```

Pointers are absolute offsets into exported `memory`.

| code | meaning |
|---|---|
| `-4` | n∉[0,32] |
| `-1/-2/-3` | name empty / >128 / non-tchar |
| `-5/-6` | value >8192 / NUL\|CR\|LF |
| `0` | ok (n=0 allowed) |

| artifact | role |
|---|---|
| `src/http_headers_set_scan.wat` | hand source |
| `http-headers-set-scan-v1.wasm` | core |
| `http-headers-set-scan-v1.component.wasm` | Component embed |

Registry `:http-headers-set-scan` + component; builder `:hand-wat/v1`.

### Honesty

- Does **not** check name uniqueness (needs set storage / W4)
- Does **not** unlock typed Component world (compiler ADR 0076 4a)
- Does **not** flip `:wasm-aot` to `:implemented`

## Non-claims

- Not typed-string retirement
- Not full EDN codec / live network

## Evidence

- Node live: empty set ok, one ok pair, bad name, bad value, bad n
- digest match module + Component

## Related

- T8.3; ADR 0189, 0194–0195; pure set packing residual
