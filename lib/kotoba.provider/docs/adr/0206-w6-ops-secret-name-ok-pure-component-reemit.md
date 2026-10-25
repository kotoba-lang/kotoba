# ADR 0206: T8.3 pure Component re-emit of secret_name_ok + header-name misfit fix

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0178 typed-string secret_name_ok; kotoba-component#100
  (`:secret-name-ok-with-main`)

## Context

ADR 0178 shipped a typed-host wasm module for secret name policy. Before
kotoba-component#100, full `secret_name_ok.kotoba` sources could compile
`--target component` by **misfitting** `:http-header-name-ok-with-main`
(RFC 7230 tchar allowlist). That incorrectly accepted `*` (tchar) which
secret policy must reject.

## Decision

| source | module (typed) | Component (pure) | live `main()` |
|---|---|---|---|
| `secret_name_ok.kotoba` | `:secret-name-ok` | `:secret-name-ok-component` | **-130** |

Policy (Canonical WAT denylist):

- empty → `-1`; length >128 → `-2`
- forbidden code points → `-3`: NUL, TAB, LF, SPACE, `*`, `/`, `?`, `\`
- else `0`

Export names containing `secret` are excluded from header-name-ok tchar shape.

### Honesty

- Does **not** flip secret kit `:wasm-aot :implemented` (reply codec AOT open)
- Does **not** replace host secret fetch / kagi transport
- Fixes charset correctness for pure Component packaging of secret names

## Evidence

- digest match; wasmtime `main()` → `-130`; `ok*` → `-3`
- component suite: denylist star rejection
- ops-kit component twin registration

## Related

- T8.3 network/secret; ADR 0178; kotoba-component#100
