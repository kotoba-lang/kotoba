# ADR 0045: Materialize i64 vector literals through bounded scratch memory

- Status: Accepted
- Date: 2026-08-09
- Extends: ADR 0044

## Context

ADR 0044 removes allocation entirely when a bounded vector literal provably
cannot escape and is used only by `vector-at`/`vector-count`. A literal that is returned,
used by another vector operation, or wider than the scalar-replacement limit
must still become an immutable typed-host value. The previous builder ABI made
that path cross the host boundary once for builder creation, once per item,
and once for sealing. It was bounded and validated, but dominated collection
throughput.

A shared scratch area can reduce that to one host call, but a fixed offset is
not safe: evaluation of an item may call the host, and that callback may
re-enter another exported Kotoba function. The nested construction would then
overwrite the outer vector before its host copy.

## Decision

When typed lowering must materialize a `vector-i64` literal, the module imports:

- `kotoba:typed/scratch`, a WebAssembly memory with minimum and maximum exactly
  two pages (128 KiB); and
- `kotoba:typed/vector-from-memory-i64(i32 descriptor, i32 offset, i32 count)
  -> externref`.

The two pages hold at most 16,384 i64 items, matching the typed-host vector
item ceiling. The memory is created afresh for each host instance and is never
exported by the guest module. The host allocates it only for modules that
import the bulk function and scratch memory as a required pair; ordinary typed
modules retain zero scratch pages.

Code generation owns a private mutable i32 bump global. A construction:

1. reads the current bump and computes `end = offset + count * 8`;
2. traps on unsigned wraparound or if `end` exceeds 131,072 bytes;
3. advances the bump before evaluating any item;
4. evaluates every item exactly once, left to right, and stores it little
   endian in the reserved aligned slice;
5. calls the host bulk constructor once; and
6. restores the prior bump after normal synchronous completion.

This is a bounded LIFO reservation, not an allocator exposed to source code.
Nested and host-re-entrant constructions observe the advanced bump and receive
disjoint slices. If item evaluation or the host call traps, the instance may
retain an advanced bump, but it cannot access beyond the fixed memory and
future construction fails closed when capacity is exhausted.

The host independently validates the descriptor, integral non-negative aligned
offset, integral count, 16,384-item limit, safe end computation, and actual
memory length. It synchronously reads signed little-endian i64 values, copies
them into a newly frozen admitted value, and retains no view of scratch memory.

The ordinary typed builder ABI remains available for non-literal aggregate
operations. Component artifacts that cannot depend on the browser typed host
continue to reject this materialized externref path rather than silently
changing their ABI.

## Evidence

The backend suite emits and validates escaping and 33-item literals, requires
the exact fixed memory import, the private bump global, unsigned wrap/capacity
checks, LIFO global updates, and the final `i64.store offset=256`. The complete
suite passes 107 tests / 491 assertions / 0 failures.

The browser-host integration module constructs a vector through the bulk
import, verifies the copied value through a result checksum, rejects unaligned
and oversized requests, rejects either half of an unpaired bulk ABI, confirms
that scratch is imported but no memory is exported, proves non-bulk typed
modules allocate zero scratch pages, and pins the profile to two pages and
16,384 items.

Compiler qualification compiles scalar, scalar-replaced vector, and forced-
materialization vector fixtures through both JVM Clojure and nbb. It requires
byte identity, `wasm-tools` validation, and checksum `7560` for both vector
forms at 256 iterations. The candidate result remains separate from publication
readiness.

In the compiler's v7 five-sample matrix, a source vector-returning function
boundary every 512th iteration forces materialization without relying on
`vector-count`, which ADR 0044 now scalar-replaces. At 100,000 measured
iterations after an equal warmup, V8 measured 967.69 ns/iteration, down from
the pre-bulk candidate's 5,998.10 ns (6.20× faster) and the pinned materialized
row's 7,777.99 ns (8.04× faster). Primitive Clojure measured 244.19 ns,
advanced ClojureScript 22.83 ns, and Rust 2.62 ns; the remaining V8/Rust ratio
is 369.00×. Native is explicitly unsupported for this row because it does not
admit `vector-i64` function parameters/results. The LIFO-hardened Wasm artifact
is 2,282 bytes with SHA-256
`9fe581a86a959375d3e82b95338ec1bf0b04c44bede840be8805251c262c828d`.
These are workload-local working-tree results, not Rust parity or
publication evidence.

## Consequences

Literal materialization now performs one host call and one bounded linear
memory copy instead of one host call per item. Scratch memory is fixed-size,
per-instance, inaccessible as a source capability, and safe against nested or
re-entrant construction.

This does not eliminate materialization, host allocation, or copying. It does
not yet cover mutation-derived vectors, general builders, parameters/returns
with an internal region representation, or an embedded Wasmtime typed host.
Those are subsequent representation and execution-host increments, not reasons
to weaken this bound.
