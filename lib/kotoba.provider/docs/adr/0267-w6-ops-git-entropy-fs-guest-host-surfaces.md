# ADR 0267: T8.3 git/entropy/scoped-fs guest host surfaces

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0266 process host_spawn; 0265 secret host_get; 0260 HTTP host_post

## Context

Process guest host surface landed as ADR 0266 (concurrent). Remaining ops kits
needed the same encode + typed-cap-call inject pattern.

## Decision

1. Ship guest packages:
   | Package | Cap wire | Export | main |
   |---------|----------|--------|------|
   | git-w4-host-edn | 22 | host_run_edn | -2509 |
   | entropy-w4-host-edn | 23 | host_draw_edn | -2510 |
   | scoped-fs-w4-host-edn | 19 | host_read_edn | -2511 |
2. edn-codec inject helpers (echo / primary-cap-id).
3. Completes ops-kit guest host surface plane (HTTP/secret/process/git/entropy/fs).
4. Does **not** flip `:wasm-aot :implemented`. Named catalog registration for
   wire ids 19–23 **landed** (kotoba-lang#358 + compiler#470 / ADR 0198).

## Evidence

- Package digests; pure main codes; optional inject tests

## Related

- T8.3; ADR 0260/0265/0266; kit ids 19–23
