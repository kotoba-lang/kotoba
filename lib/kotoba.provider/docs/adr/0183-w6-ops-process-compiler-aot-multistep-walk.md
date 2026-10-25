# ADR 0183: T8.3 pure multi-step process spawn walk

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0172 process-spawn-bounds; ADR 0179/0181 multi-step walk pattern

## Context

Process had single-shot `process_spawn_bounds_ok(argc, max_out, timeout)`
(ADR 0172) but not a host-walk over **argv lengths**. Kit limits include
`:arg-bytes 4096` which the one-shot does not enforce per argument.

## Decision

### Protocol

| export | meaning |
|---|---|
| `process_spawn_begin(argc)` | remaining count \| `-1` empty \| `-2` argc>32 |
| `process_spawn_arg(state, arg_len)` | remaining-1 \| `-5` extra arg \| `-6` arg_len∉[1,4096] |
| `process_spawn_end(state, max_out, timeout-ms)` | `0` \| sticky \| `-7` missing args \| `-3` max_out \| `-4` timeout |

| artifact | role |
|---|---|
| `src/process_spawn_walk.kotoba` | source |
| `process-spawn-walk-v1.wasm` | kotoba-compiler wasm32 |
| `process-spawn-walk-v1.component.wasm` | Component |

Single-shot 0172 retained for argc/max/timeout-only callers.

### Honesty

- Host walks argv lengths (not pure memory one-shot of argv strings)
- OS spawn remains host-injected
- `:wasm-aot` stays `:partial`

## Non-claims

- Not basename allowlist encoding
- Not full request/result EDN codec AOT
- Not live OS spawn success

## Evidence

- Node live: ok 0; empty -1; argc>32 -2; arg too long -6; missing -7; extra -5; bad max/timeout -3/-4
- digest match + Component

## Related

- Reliability WBS T8.3
- ADR 0168, 0172, 0179, 0181
