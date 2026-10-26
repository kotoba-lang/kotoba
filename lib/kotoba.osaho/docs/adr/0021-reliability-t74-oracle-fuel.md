# ADR 0021: T7.4 deep loop — oracle fuel + loop-helper trampoline

- Status: Accepted
- Date: 2026-07-29
- WBS: T7.4 (with compiler dual-backend pilot)

## Context

1. `kotoba.kir/lower` constant-oracles pure i64 entries via `execute` with the
   historical runtime default of **512** fuel (T7.2). Helper-desugared
   `loop`/`recur` charges **1 unit per helper entry**, so a 10k-iteration pure
   loop failed the oracle and aborted compile.
2. Even with raised fuel, each self-call nested a JVM frame in the KIR
   interpreter, so ~1.5k depth hit host stack overflow (mapped to
   `:fuel-exhausted` / `:host-stack-exhausted`).

## Decision

1. Private `oracle-fuel` = **100_000** for `lower`'s constant oracle only.
2. **Trampoline** self-calls when the target is `__kotoba_loop_N` **and** it is
   the current call-stack tip (frontend-synthesized tail-recursive helpers).
   Fuel still charges 1 unit per entry; host stack does not grow.
3. Runtime `execute` default remains **512**; deep cases pass `{:fuel n}`.
4. Unbounded non-helper recursion still traps during lower (fail closed).

## Not claimed

- Zero-charge `recur` / machine TCO for arbitrary functions
- Trampoline for non-`__kotoba_loop_*` mutual recursion

## Consequences

- 10k pure loop dual-backend (KIR + wasm) is reachable with raised fuel.
- Infinite pure self-recursion still aborts compile via oracle fuel/stack trap.
