# ADR 0147: cljs/nbb OS spawn + scoped-fs root-mount transports

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0144 landed JVM `process-transport/os-spawn` and
`scoped-fs-transport/os-store`. W6 kbb ability gap Next listed **cljs/nbb
OS transports under the sync provider contract** as the remaining dual-
runtime hole (async Node child_process/fs vs sync `(fn [req] -> reply)`).

HTTP/LLM/storage already use `child_process.spawnSync` hops for the same
reason (ADR 0117–0119).

## Decision

| transport | cljs host mechanism | host-required config |
|---|---|---|
| `process-transport/os-spawn` | `child_process.spawnSync` (absolute bin, `shell:false`) | `:binaries` |
| `scoped-fs-transport/os-store` | Node `fs` + `path` sync; `realpathSync` under-root | `:roots` |

### Non-goals / fail-closed (unchanged from ADR 0144)

- **No ambient PATH** — binaries map only.
- **No ambient FS roots** — not CWD / `$HOME` / `/tmp` default.
- **No shell** — `shell: false` on spawnSync.
- Browser/workerd remain out of scope (Node/nbb ops host only).

### Bounds

- Process: `timeout` + `maxBuffer` (stdout/stderr truncated to max-stdout-bytes).
- FS: `scoped-fs/resolve-path` + realpath under-root after read/write parent prep.

### Test injects

- cljs `os-spawn` accepts optional `:spawn-sync` double.
- cljs `os-store` accepts optional `:fs` / `:path` modules.

## Consequences

- process + scoped-fs gaps become **dual-runtime OS transport landed**.
- SSH fleet control remains a separate host-forever decision (gap policy).
- nbb smoke exercises real echo + temp-dir write/read.

## Related

- ADR 0144 process/scoped-fs OS transports (JVM)
- ADR 0117 http cljs spawnSync hop
- `lang/w6-kbb-ability-gap.edn` `:process-cljs-os-spawn` / `:scoped-fs-cljs-os-mount`
