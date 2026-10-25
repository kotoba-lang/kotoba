# ADR 0044: Scalar-replace bounded non-escaping vector literals

- Status: Accepted
- Date: 2026-08-09
- Extends: ADR 0046

## Context

Structured loops removed recursive helper frames, but an eight-item vector
literal still crossed the `kotoba:typed` boundary ten times per iteration:
builder creation, eight pushes, and sealing. A following `vector-at` crossed
the boundary again. Five samples measured 5,998.10 ns/iteration versus 4.03
for Rust even though the immutable vector never escaped its loop iteration.

Replacing the general externref ABI would affect exported values, capabilities,
and host validation. The first optimization therefore needs a proof that a
particular aggregate has no observable identity and cannot escape.

## Decision

Typed Wasm scalar-replaces an i64 vector literal when either it is consumed by
an immediate `vector-at`/`vector-count`, or it is let-bound and every lexically
unshadowed use is the vector operand of one of those operations.

The lowering:

1. evaluates all items left-to-right at the original construction point;
2. stores each admitted i64 in a Wasm local;
3. evaluates each read index exactly once;
4. traps for negative, past-end, and empty-vector reads;
5. selects the requested local with standard Wasm control flow; and
6. returns the literal count as an i64 constant only after item evaluation.

At most 32 items are scalar-replaced, bounding local declarations and selector
depth independently of the language's larger vector limit. A literal that
escapes, crosses a function boundary, is used by another vector operation, or
exceeds the local limit retains the bounded typed-host externref path.

Host-import analysis mirrors the same lexical proof. When no other typed value
requires the host, the module omits all `kotoba:typed` imports. The sealed KIR
and typed metadata retain the source vector descriptor; only its internal,
non-observable representation changes.

## Evidence

The backend suite checks immediate and let-bound reads/counts, mixed count/read
uses, first and last items, negative and past-end indices, empty-vector traps,
import elimination, and fallback for escaping and 33-item literals. The full
result is 107 tests / 491
assertions / 0 failures.

The frontend-generated benchmark artifact validates, is byte-identical from
JVM Clojure and nbb ClojureScript, contains no typed-host import, and executes
under both V8 and standalone Wasmtime with checksum `2847627` at 100,000
iterations. It is 652 bytes with SHA-256
`b3b00cce8c6fa1235f995c73f616b0c4c6fbe92e9f676baef3b1c32501ad718e`.

Five V8 samples after an equal 100,000-iteration warmup measured 15.36
ns/iteration, down from the materialized candidate's 5,998.10 ns. Rust measured
2.59 ns, so the remaining workload-local ratio is 5.94×. The fail-closed v2
qualification reports `candidateQualified: true`; publication readiness stays
false because this evidence comes from a dirty working tree at base commit
`b0c9837f`.

## Consequences

Non-escaping immutable vector literals no longer pay host allocation or
externref crossing costs. Standalone Wasmtime can execute those artifacts.

This does not establish persistent-vector parity. Escaping, wide,
mutation-derived, returned, and parameter vectors still require the host
representation. ADR 0045 reduces literal materialization to one checked bulk
copy through bounded scratch memory; broader region lifetimes and
function-boundary representations remain future work.
