# ADR 0144: process OS spawn + scoped-fs root-mount transports

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0143 landed contract-first slices for `provider.process` (id 20) and
`provider.scoped-fs` (id 19) with pure policy and mem/echo doubles. W6 kbb
ability gap Next asked for production OS spawn and root-mount transports
without ambient authority.

## Decision

| transport | injects as | host-required config |
|---|---|---|
| `provider.process-transport/os-spawn` | `:spawn` | `:binaries` `{basename abs-path}` |
| `provider.scoped-fs-transport/os-store` | `:store` | `:roots` `{kw abs-dir}` |

### Non-goals / fail-closed rules

- **No ambient PATH** — binaries map is mandatory; no default search.
- **No ambient FS roots** — not CWD, not `$HOME`, not `/tmp` default.
- Symlink escape under roots: reject via canonical path `under-root?`.
- `:cljs` OS transports are an explicit gap (sync contract vs async host APIs).

### Bounds

- Process: timeout destroyForcibly; stdout/stderr capped at max-stdout-bytes.
- FS: reuse `scoped-fs/resolve-path` + `max-value-bytes` on read.

## Consequences

- kbb gaps stay **contract-first + OS transport available**; full nbb cutover
  still needs cljs transports and secret-custody wiring.
- SSH fleet remains optionally host-forever (gap policy unchanged).

## Related

- ADR 0143 process + scoped-fs contract first slice
- storage-transport no ambient filesystem (ADR 0049 / 0071)
