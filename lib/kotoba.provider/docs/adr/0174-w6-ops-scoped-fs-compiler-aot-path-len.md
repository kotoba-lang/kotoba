# ADR 0174: T8.3 compiler-AOT scoped-fs path-length kit body slice

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0169 scoped-fs path policy; ADR 0173 secret name-len pattern

## Context

ADR 0173 shipped the pure **length half** of secret name policy via
kotoba-compiler. Scoped-fs still has only hand WAT for path policy
(`fs_path_ok` memory-scan: empty, max 1024, leading `/`/`~`, escape dots).

Full path-scan compiler re-emit needs string/memory surface (same blocker
as secret char-class). This ADR lands the pure length half only.

## Decision

### Length half (pure i64)

```
fs_path_len_ok(len) → i64
```

| code | condition |
|---|---|
| `-1` | len ≤ 0 |
| `-2` | len > 1024 |
| `0` | ok |

Matches scoped-fs-v1 `:limits {:path-bytes 1024 …}` and ADR 0169 length
rules. Leading-slash/`~`/dot-escape scan stays on hand WAT
`scoped-fs-path-v1`.

| artifact | role |
|---|---|
| `src/fs_path_len.kotoba` | source |
| `fs-path-len-v1.wasm` | kotoba-compiler wasm32 + provenance |
| `fs-path-len-v1.component.wasm` | Component embed |

Registry: `:fs-path-len{,-component}`, `:builder :kotoba-compiler/v1`,
`:class :ops`.

### Honesty

- `:wasm-aot` stays `:partial`
- Does not replace scoped-fs-path hand Component
- Host root-scoped store authority unchanged

## Non-claims

- Not full path escape/dot/slash scan AOT
- Not typed-string packaging
- Not OS store success proof

## Evidence

- digest match
- Node live: 0→-1; 1/1024→0; 1025→-2
- provenance `:builder :kotoba-compiler/v1`

## Related

- Reliability WBS T8.3
- ADR 0169, 0171–0173
