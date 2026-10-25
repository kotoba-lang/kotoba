# ADR 0143: process + scoped-fs kit contract first slice

- Status: Accepted
- Date: 2026-07-28

## Context

W6 kbb ability gap list (`lang/w6-kbb-ability-gap.edn`) marks **process** and
**scoped-filesystem** as high-priority missing kits that keep ops shells on
nbb/bb. Guest product cutovers use provider kits; kbb needs grant-scoped
spawn and root-scoped file IO without ambient Node/JVM authority.

## Decision

Land contract-first slices:

| kit | capability id | surface |
|---|---|---|
| `provider.scoped-fs` | 19 | read/write under allowlisted roots; pure `resolve-path` |
| `provider.process` | 20 | spawn request with argv/timeout bounds + command allowlist |

Both require host-injected transports/stores. **No ambient filesystem and no
ambient process spawn** in the provider itself.

### Pure policy

- `scoped-fs/resolve-path` — reject `..`, `.`, absolute, `~`, `\`, NUL, empty
- `process/validate-spawn` — argv length/bytes, basename-only command, allowlist

### Test doubles

- `scoped-fs/mem-store` — in-memory `{root {path value}}`
- `process/echo-transport` — exit 0, stdout = joined argv rest

## Consequences

- kbb ability gaps move from `:missing` to **contract first slice** (not full
  production OS transport).
- Production scoped mounts and real OS spawn remain later transports.
- SSH fleet may still stay host-mechanism forever (gap list policy).

## Related

- provider.storage ambient-filesystem false (ADR 0049)
- W6 `docs/w6-kbb-ability-gap.md`
