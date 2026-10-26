# ADR 0020: T3.3 — fuel traps cite function + call-stack

- Status: Accepted
- Date: 2026-07-28
- WBS: T3.3

## Decision

On function entry charge, `:fuel-exhausted` traps include:

- `:function` — current function name
- `:call-stack` — last ≤8 names
- `:hint` — short human note

Does not yet map to source form spans (frontend metadata not on KIR ops).

## Evidence

- `kotoba.kir-trap-source-test`
