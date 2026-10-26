# ADR 0023: T7.1 zero-charge loop-helper trampoline re-entry

- Status: Accepted
- Date: 2026-07-29
- WBS: T7.1

## Decision

On KIR, self-tail trampoline re-entries of `__kotoba_loop_N` **do not charge
fuel**. The first entry of the helper still charges 1 unit (T7.2).

Non-helper recursion continues to charge every entry (fail closed).

Hosts must wall-clock-bound adversarial `(loop [] (recur))` infinite loops.

## Evidence

- `kir-zero-charge-loop-test` — 10k iters with fuel 16
