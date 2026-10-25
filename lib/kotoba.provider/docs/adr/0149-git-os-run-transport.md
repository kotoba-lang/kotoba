# ADR 0149: git os-run transport (JVM)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0148 landed `provider.git` id 22 with pure `validate-run` and
`echo-transport`. Production hosts need a real `git` binary without
ambient PATH or CWD.

## Decision

`provider.git-transport/os-run`:

| opt | rule |
|---|---|
| `:git-bin` | absolute executable path (required) |
| `:worktree` | absolute directory (required) |

Spawns `[git-bin & args]` with `ProcessBuilder.directory(worktree)`.
Subcommand allowlist stays in the provider.

cljs os-run remains a documented gap.

## Related

- ADR 0148 git kit contract
- ADR 0144 process os-spawn
