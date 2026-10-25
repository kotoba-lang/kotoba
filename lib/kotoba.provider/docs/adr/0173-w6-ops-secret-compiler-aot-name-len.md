# ADR 0173: T8.3 compiler-AOT secret name-length kit body slice

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0163/0166 secret name policy; ADR 0171–0172 numeric compiler-AOT pilots

## Context

ADR 0172 re-emitted process/entropy/git **numeric** pure bounds via
kotoba-compiler. Secret (and scoped-fs) remain hand WAT because the
dominant policy is a **memory-scan** over name/path bytes.

A full string-surface compiler emit (`secret_name_ok [name :string]`)
**does** compile on wasm32, but lowers to `kotoba:typed` externref host
imports — it is not a pure import-free module and `wasm-tools component
new` cannot embed it without a typed world. That path is deferred.

## Decision

### Length half only (pure i64)

Ship compiler-emitted pure:

```
secret_name_len_ok(len) → i64
```

Matching ADR 0163 length rules:

| code | condition |
|---|---|
| `-1` | len ≤ 0 |
| `-2` | len > 128 |
| `0` | ok |

Char-class scan (`/ \ * ?` whitespace NUL) stays on hand WAT
`secret-get-v1` until a pure memory/string free path exists.

| artifact | role |
|---|---|
| `src/secret_name_len.kotoba` | source |
| `secret-name-len-v1.wasm` | kotoba-compiler wasm32 + provenance |
| `secret-name-len-v1.component.wasm` | Component embed |

Registry: `:secret-name-len{,-component}`, `:builder :kotoba-compiler/v1`.

### Honesty

- `:wasm-aot` stays `:partial`
- Does **not** replace secret-get hand name-policy Component
- Host-injected secret fetch unchanged

## Non-claims

- Not full char-class scan compiler re-emit
- Not typed-string `kotoba:typed` packaging production claim
- Not scoped-fs path scan AOT
- Not secret value transport

## Evidence

- digest match
- Node live: len 0 → -1; 1..128 → 0; 129 → -2
- provenance `:builder :kotoba-compiler/v1`

## Related

- Reliability WBS T8.3
- ADR 0163, 0166, 0171, 0172
