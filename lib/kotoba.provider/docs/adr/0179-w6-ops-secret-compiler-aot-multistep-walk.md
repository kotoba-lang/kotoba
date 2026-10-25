# ADR 0179: T8.3 pure multi-step secret name walk (compose len+char)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0173 name-len; ADR 0176 char-class; ADR 0178 typed-string single-call

## Context

ADR 0176 left composition of length + char-class gates as host-side until a
**pure multi-step guest** was packaged. ADR 0178 landed typed-string
single-call (needs `kotoba:typed` host, not pure Component). A pure-i64
walk protocol that composes both halves remains useful for hosts that
only speak the direct wasm32 ABI.

## Decision

Export a pure begin/next/end protocol:

| export | meaning |
|---|---|
| `secret_name_begin(len)` | `-1` empty, `-2` >128, else `0` |
| `secret_name_next(state, c)` | pass-through error, else `-3` forbidden / `0` |
| `secret_name_end(state)` | final state (`0` ok) |

Host algorithm:

```
s = begin(byteLength(name))
if s < 0: fail
for c in name.bytes: s = next(s, c); if s < 0: fail
return end(s)
```

| artifact | role |
|---|---|
| `src/secret_name_walk.kotoba` | source |
| `secret-name-walk-v1.wasm` | pure wasm32-kotoba-v1 |
| `secret-name-walk-v1.component.wasm` | Component embed |

Registry `:secret-name-walk{,-component}`, `:builder :kotoba-compiler/v1`.

### Honesty

- Does not replace hand WAT one-shot or typed-string single-call (0178)
- Host still iterates bytes (no guest memory load)
- `:wasm-aot` stays `:partial` (no full request/result EDN codec)

## Non-claims

- Not pure memory-scan one-shot without host loop
- Not scoped-fs typed-string path
- Not full EDN codec AOT

## Evidence

- digest match; Node live walks empty/ok/long/forbidden
- provenance `:builder :kotoba-compiler/v1`

## Related

- T8.3; ADR 0173, 0176–0178
