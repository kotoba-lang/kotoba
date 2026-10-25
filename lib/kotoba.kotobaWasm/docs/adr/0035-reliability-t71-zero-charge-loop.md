# ADR 0035: T7.1 zero-charge fuel prologue for loop helpers

- Status: Accepted
- Date: 2026-07-29
- WBS: T7.1

## Decision

Wasm function bodies named `__kotoba_loop_N` omit the fuel charge prologue so
desugared `loop`/`recur` matches KIR zero-charge re-entry. Other functions
still charge 1 unit on entry.

## Evidence

- Dual-backend pilot `:loop-deep-kit` with low fuel envelope
