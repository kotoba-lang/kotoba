# ADR 0046: Lower frontend loop helpers to structured Wasm control flow

- Status: Accepted
- Date: 2026-08-09
- Extends: ADR 0035

## Context

ADR 0035 made `__kotoba_loop_N` re-entry zero-charge, matching the KIR fuel
model, but the backend still emitted every `recur` as an ordinary Wasm call.
Long admitted loops therefore consumed the host's native call stack even
though they consumed no Kotoba fuel. The compiler runtime comparison exposed
the consequence: one million scalar iterations raised V8 `RangeError: Maximum
call stack size exceeded`.

Increasing the host stack, enabling an experimental tail-call proposal, or
replenishing fuel would change deployment assumptions rather than fix the
lowering.

## Decision

An unqualified function named `__kotoba_loop_N` is emitted as an outer result
`block` containing an empty-result Wasm `loop`. A tail self-call:

1. evaluates every replacement argument while all old parameter locals remain
   intact;
2. writes the new values to parameter locals in reverse stack order; and
3. branches to the loop header.

Eligibility additionally requires every self-call to supply exactly the
helper's parameter count. Malformed arity and unknown self-call contexts retain
ordinary call lowering, so the optimization cannot silently preserve stale
parameter locals or branch through an untracked label.

A terminal expression branches to the outer result block. Nested source `if`
labels are included in the branch depth. Both KIR v3 scalar lowering and KIR v4
typed scalar lowering use the same structure. Ordinary recursion remains an
ordinary charged call.

Typed reference-result helpers retain the previous call lowering until result
assertion can be placed inside every terminal branch; silently bypassing that
assertion is forbidden.

## Evidence

The backend suite emits, validates, prints, and executes scalar and typed loop
helpers for 100,000 iterations under Wasmtime, returning 4,200,000. A sibling
ordinary recursive countdown at depth 600 still traps at the fixed fuel
boundary. An intentionally non-tail helper-shaped self-call falls back to valid
ordinary call lowering. Typed and untyped 100,001-iteration swap loops return
21, proving replacement expressions observe the old locals and are committed
simultaneously. A wrong-arity helper is refused by structured lowering and
remains invalid at Wasm validation rather than changing meaning.
Typed `u32` let-bound intermediates use i32 locals and nested i32 expressions,
avoiding repeated i64 wrap/extend pairs while preserving i64 at the language
boundary. The full repository result is 103 tests / 453 assertions / 0
failures.

The compiler frontend-to-KIR path was tested through a tools.deps alias whose
resolved classpath was required to contain this checkout. JVM Clojure and nbb
ClojureScript emitted byte-identical Wasm for the scalar and vector artifacts.
The scalar artifact is 731 bytes (`b828c616…`), and the vector artifact is
2,056 bytes (`5f1aa6e8…`); both passed `wasm-tools validate`. The scalar module
returned integer-mix checksum `3882214040` at ten million iterations, and the
vector module returned checksum `7560` at 256 iterations through the
production-compatible typed browser host.

In the compiler's standard five-sample matrix, scalar multiplication,
balanced branch, and data-dependent integer-mix used ten million measured
iterations after a one-million-iteration warmup. V8 measured 0.68, 1.06, and
3.05 ns/iteration; Rust measured 2.25, 5.35, and 3.90 ns/iteration, producing
workload-local V8/Rust ratios of 0.30×, 0.20×, and 0.78×. Against the recursive
pinned backend's 5,000-iteration medians, the candidate speedups were
approximately 18.4×, 15.0×, and 8.0×.

Before ADR 0044 scalar replacement, the vector allocation-and-scan workload
used 100,000 measured iterations after
an equal warmup. V8 required 5,998.10 ns/iteration while Rust required 4.03,
a 1,489.75× ratio. Structured control flow and i32-local lowering therefore
establish scalar workload-local parity, but do not optimize typed-host
`externref` allocation or persistent vector construction. ADR 0044 subsequently
optimizes the proven non-escaping literal case while retaining this row as the
materialized-path baseline. General Rust parity is not claimed.

The report records base commit `b0c9837f`, `dirty: true`, and
`classpathVerified: true`. It therefore proves the working-tree candidate, not
the published base commit.

## Consequences

Deep source `loop` no longer relies on host stack size for supported scalar
helpers. Fuel semantics, function signatures, exports, KIR, and the standard
Wasm instruction set remain unchanged. The compiler repository must advance
its git pin before this behavior becomes its default nbb/JVM backend.
