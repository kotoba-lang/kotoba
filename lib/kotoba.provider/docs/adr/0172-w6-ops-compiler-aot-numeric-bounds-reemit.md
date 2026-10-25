# ADR 0172: T8.3 compiler-AOT re-emit of process/entropy/git pure bounds

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0171 http bounds compiler-AOT pilot; ADR 0167–0170 hand pure policy Components

## Context

ADR 0171 landed the first **compiler-emitted** ops kit body
(`http_post_bounds_ok`). Remaining pure policy modules for process, entropy,
and git were still **hand-written WAT** (ADR 0167–0170). Secret name policy
and scoped-fs path policy scan guest memory and stay hand-WAT until a string
kit surface is available for compiler AOT.

## Decision

Re-emit the three **numeric** pure bounds checkers via `kotoba-compiler`
wasm32 from `.kotoba` sources (entryless `(:export […])`), plus Component
embed via `wasm-tools component new`. Hand WAT modules remain as historical
reference digests; new packages use distinct names with
`:builder :kotoba-compiler/v1`.

| source | export | package names |
|---|---|---|
| `process_spawn_bounds.kotoba` | `process_spawn_bounds_ok(argc,max-out,timeout)` | `:process-spawn-bounds{,-component}` |
| `entropy_draw_bounds.kotoba` | `entropy_draw_ok(n)` | `:entropy-draw-bounds{,-component}` |
| `git_run_bounds.kotoba` | `git_run_bounds_ok(argc,max-out,timeout)` | `:git-run-bounds{,-component}` |

Error codes match the hand WAT pilots (process/git: -1 empty argc, -2 argc
over limit, -3 max-out, -4 timeout; entropy: -1 out of [1,64]).

### Honesty

- Does **not** flip any kit `:wasm-aot` to `:implemented` — full request/result
  EDN codec AOT remains open
- Does **not** replace host OS spawn / CSPRNG / git binary
- Does **not** re-emit secret `secret_name_ok` or scoped-fs `fs_path_ok`
  (memory-scan policies; follow-up when string kit AOT is ready)

## Non-claims

- Not multi-file kit project mode with capability grants
- Not live host success proof for process/entropy/git
- Not retirement of hand WAT digests (kept for continuity)

## Evidence

- digest match for each module + Component
- Node/WebAssembly live vectors for ok and each error code
- provenance `:builder :kotoba-compiler/v1`
- kit notes + readiness evidence list ADR 0172

## Related

- Reliability WBS T8.3
- ADR 0167–0171
- Frontier ADR-2607299400 Progress residual “re-emit pure policies via compiler”
