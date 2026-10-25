# ADR 0184: T8.3 pure multi-step git run walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0172 git-run-bounds; ADR 0183 process multi-step walk pattern

## Context

Git had single-shot `git_run_bounds_ok(argc, max_out, timeout)` (ADR 0172)
but not a host-walk over **arg lengths**. Kit limits include `:argv 64` and
`:arg-bytes 4096`. Process multi-step walk (ADR 0183) is the template.

## Decision

| export | meaning |
|---|---|
| `git_run_begin(argc)` | remaining \| `-1` empty \| `-2` argc>64 |
| `git_run_arg(state, arg_len)` | remaining-1 \| `-5` extra \| `-6` arg_len∉[1,4096] |
| `git_run_end(state, max_out, timeout-ms)` | `0` \| sticky \| `-7` missing \| `-3`/`-4` bounds |

Artifacts: `git-run-walk-v1.wasm` + Component; single-shot 0172 retained.

### Honesty

- Host walks arg lengths (not argv string memory one-shot)
- Git binary remains host-injected
- `:wasm-aot` stays `:partial`

## Non-claims

- Not subcommand allowlist encoding
- Not path-escape in walk (scoped-fs path policy owns paths)
- Not full EDN codec AOT

## Evidence

- Node live: ok/empty/argc/arg-long/missing/extra/max/timeout codes
- digest match + Component

## Related

- T8.3; ADR 0170, 0172, 0183
