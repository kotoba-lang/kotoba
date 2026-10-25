# kotoba-wasm

Amu's Wasm **綾** — checked KIR to core Wasm and Canonical ABI.

This is not a being. [`amu`](https://github.com/kotoba-lang/amu) weaves;
this repository is one pattern in that weave. It does not link at runtime
and does not execute. That is [`kototama`](https://github.com/kotoba-lang/kototama).
See root ADR-2608139980.

**Tier**: `T2`  **Role**: `backend` of amu

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `kotoba.wasm.core (KIR -> core wasm)`
- `kotoba.wasm.typed (typed lowering)`
- `kotoba.wasm.canonical-abi (Canonical ABI lowering)`

The Canonical ABI owner also normalizes Kotoba's public `:vector-i64` and
`:vector-f64` descriptors to the standard Component Model `list<s64>` and
`list<f64>` pointer/length layouts. Hosts and component producers consume
that single checked layout instead of reimplementing vector ABI rules.
Selected indirect list leaves use the shared `component-list-count` lowering,
which checks alignment, the descriptor item bound, unsigned byte-size/range
overflow, and the module's actual linear-memory size before exposing a count.
The matching `component-list-at-i64`/`component-list-at-f64` lowerings reuse
that exact validation, reject an unsigned out-of-range index, and only then
load one aligned scalar item from the borrowed Canonical buffer.
The `component-list-get-*` forms preserve those list checks but choose a
caller-supplied fallback for a negative or out-of-range index without
addressing memory.

Declared core-Wasm fuel is a positive exact i64 subset through `2^62 - 1` on
both JVM Clojure and ClojureScript/Node. The Node branch keeps policy values as
BigInt through validation and signed-LEB128 emission; it never narrows them
through JavaScript Number.
Frontend-generated `__kotoba_loop_N` helpers lower to standard structured Wasm
`block`/`loop`/`br` control flow for scalar KIR v3 and typed-scalar KIR v4.
Parameter replacements are evaluated before locals are updated, so source
`recur` remains simultaneous and deep loops do not grow the host call stack.
Only exact-arity tail self-calls are eligible. Ordinary recursion remains
fuel-charged.
Typed `u32` let-bound intermediates remain in i32 locals and nested i32
expressions, eliminating redundant wrap/extend traffic while preserving the
language-level i64 boundary.
Bounded non-escaping `vector-i64` literals used only by checked `vector-at`
reads and/or `vector-count` are scalar-replaced into Wasm locals. Count becomes
a constant only after every item expression has run in source order. Bounds traps
are preserved, and literals wider than 32 items or values that escape retain
the typed-host `externref` path. See ADR 0044. Materialized `vector-i64`
literals use a private bounded LIFO slice of a fixed two-page imported scratch
memory and one synchronous checked host copy, rather than one host call per
item. Nested or host-re-entrant construction receives a disjoint slice; the
memory and bump pointer are never exported. See ADR 0045.

## Does not own

- parse .kotoba source
- own language semantics
- link or execute

## Depends on

- `kotoba-lang/osaho` (formerly `kotoba-kir`)

## Test

```bash
kbb -M:test
```
