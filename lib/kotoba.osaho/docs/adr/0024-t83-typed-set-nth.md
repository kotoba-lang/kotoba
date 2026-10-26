# ADR 0024: T8.3 typed-set-nth for guest set fold / EDN encode

- Status: Accepted
- Date: 2026-08-01

## Decision

Add `(typed-set-nth type set index) → item` over the sorted item vector of a
typed set. Out-of-bounds traps `:set-index-out-of-bounds`. Enables guest loops
over set members for full headers EDN encode (provider residual after ADR 0231).

## Evidence

- `kir-typed-set-nth-test`: sorted nth + OOB trap
