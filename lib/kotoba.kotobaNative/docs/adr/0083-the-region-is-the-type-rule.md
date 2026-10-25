# 0083 — the region is the type rule

Status: accepted
Date: 2026-09-16
Base: `origin/main` `7da6018`

## Context

Superproject ADR-2609160044: the command binaries' SIGILL traps are the
runtime's bump arenas refusing a budget, and the arenas never reclaim. The
owner's decision is to remove that structurally.

## Decision

`(arena-scope body)` lowers on both ISAs to the host's ENTER (slot 224), the
body in value position, LEAVE (slot 232), and the body's register as the
value (`kotoba.native.machine-ir`; both legacy `emit-expr` paths mirror it
with the result register saved across the leave call). The pair is emitted
here and nowhere else — no KIR program names enter or leave — so the LIFO the
host relies on holds by construction, and the host still traps a leave at
depth 0.

The safety argument is not in this repository: kotoba-sema admits the head
only when the body is `:i64` / `:bool` / `:f64`, and kotoba-verifier
re-derives the same rule. A scalar cannot carry a handle out; every mutable
structure a body can reach holds numbers; tail appends write past outer
handles and leave their lengths alone. What this backend adds is that the
body is lowered in value position on purpose: a self-call inside the scope is
not a tail call, since the leave follows it.

## Consequences

- `kotoba.gmir/runtime-operation-arities` 966bb4c carries the two operations
  at arity 0, `kotoba.mir/runtime-context-offsets` b33e90d the two offsets.
- `kotoba.native.arena-scope-test` pins the lowering shape and the slot loads
  on both ISAs (`ldr x16, [x7, #224]` / `#232`; `call [r9+0xe0]` /
  `[r9+0xe8]`). Portable slice: 71 tests, 601 assertions, 0 failures.
- Execution is measured in amu's conformance, both ways: the same loop under
  a small pool completes with the scope and traps without it.
