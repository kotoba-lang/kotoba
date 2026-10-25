# ADR 0176: T8.3 compiler-AOT secret name char-class gate

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0163/0166 hand name-scan; ADR 0173 name-len; ADR 0175 value-len

## Context

Length halves for secret name/value and scoped-fs path/value are
compiler-AOT (ADR 0173–0175). Char-class / path-scan still lived only in
hand WAT memory-scan (`secret_name_ok(ptr,len)`). Full string-surface
compiler emit needs `kotoba:typed` host and does not Component-embed as a
pure module.

## Decision

### Pure per-code-point gate (host walks)

```
secret_name_char_ok(c) → i64
```

Matches hand WAT forbidden set (→ `-3`):

`0` NUL, `9` TAB, `10` LF, `32` space, `42` `*`, `47` `/`, `63` `?`, `92` `\`

Any other code point → `0`. Length rules stay on `secret_name_len_ok`
(ADR 0173). Host/tender iterates name bytes and ANDs/short-circuits.

| artifact | role |
|---|---|
| `src/secret_name_char.kotoba` | source |
| `secret-name-char-v1.wasm` | kotoba-compiler wasm32 + provenance |
| `secret-name-char-v1.component.wasm` | Component embed |

Registry: `:secret-name-char{,-component}`, `:builder :kotoba-compiler/v1`.

### Honesty

- Does **not** delete hand WAT ptr/len scan (still the packed one-shot export)
- `:wasm-aot` stays `:partial` (no full request/result EDN codec; no pure
  memory-load path without host walk)
- Composition of len + char gates is host-side until a pure multi-step
  guest is packaged

## Non-claims

- Not scoped-fs path state-machine (dot/slash) AOT
- Not typed-string single-call `secret_name_ok(:string)` packaging
- Not secret value transport

## Evidence

- digest match
- Node live: `A/a` → 0; forbidden set → -3
- provenance `:builder :kotoba-compiler/v1`

## Related

- Reliability WBS T8.3
- ADR 0163, 0166, 0173–0175
