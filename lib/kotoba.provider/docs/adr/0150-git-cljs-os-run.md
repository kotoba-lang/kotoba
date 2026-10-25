# ADR 0150: git cljs/nbb os-run transport

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0149 landed JVM `git-transport/os-run`. W6 gap Next asked for cljs/nbb
parity under the same sync provider contract (spawnSync + absolute bin).

## Decision

`provider.git-transport/os-run` on `:cljs`:

| opt | rule |
|---|---|
| `:git-bin` | absolute path (required) |
| `:worktree` | absolute dir used as `cwd` (required) |
| `:spawn-sync` | optional test inject |

Uses `child_process.spawnSync` with `shell: false` — never PATH, never
ambient CWD. Subcommand allowlist remains in `provider.git`.

## Consequences

- git kit is dual-runtime for production os-run.
- Tooling cutover can target nbb murakumo ops without JVM-only transport.

## Related

- ADR 0148/0149 git kit + JVM os-run
- ADR 0147 process cljs spawnSync
