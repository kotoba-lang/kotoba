# ADR 0151: entropy kit contract + dual-runtime CSPRNG transport (id 23)

- Status: Accepted
- Date: 2026-07-28

## Context

W6 kbb gap `clock-and-random` is **partial**: clock kit (id 7) landed in
W5; CSPRNG for ids is still missing. Guests must not call ambient
`Math.random` / unseeded PRNGs.

## Decision

| piece | role |
|---|---|
| `provider.entropy` (id **23**) | typed draw of `n` bytes → lowercase hex |
| pure `validate-n` / `bytes->hex` | bounds + encoding |
| `mem-draw` | deterministic test double |
| `entropy-transport/os-draw` | JVM SecureRandom / cljs getRandomValues |

### Bounds

- `1 ≤ n ≤ 64` bytes per draw
- Result is hex string of length `2n` (typed `:string`)

### Non-goals

- No UUID formatting (caller composes)
- No reseeding API, no entropy pool status, no list of draws
- No Math.random fallback

## Consequences

- `clock-and-random` gap can flip to **landed** (clock + entropy).
- Hosts inject `os-draw` or test `mem-draw` the same way as other kits.

## Related

- clock kit id 7 / ADR 0029 / 0073
- `lang/w6-kbb-ability-gap.edn` `:clock-and-random`
