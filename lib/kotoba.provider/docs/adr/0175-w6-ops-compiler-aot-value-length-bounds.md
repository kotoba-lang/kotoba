# ADR 0175: T8.3 compiler-AOT secret/fs value-length bounds

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0173 name-len; ADR 0174 path-len

## Context

ADR 0173/0174 covered **name** and **path** length halves. Kit limits still
include **value** ceilings: secret `:secret-bytes 8192`, scoped-fs
`:value-bytes 65536`. Those were not yet compiler-emitted.

## Decision

| export | limit | packages |
|---|---|---|
| `secret_value_len_ok` | 8192 | `:secret-value-len{,-component}` |
| `fs_value_len_ok` | 65536 | `:fs-value-len{,-component}` |

Codes: negative → `-1`; over max → `-2`; else `0`.

### Honesty

- Pure `i64` direct ABI (ADR 0171 class)
- Does not flip `:wasm-aot` to `:implemented`
- Char/path escape scans remain hand WAT

## Evidence

digest match; Node live vectors; `:builder :kotoba-compiler/v1`

## Related

T8.3; ADR 0171–0174
