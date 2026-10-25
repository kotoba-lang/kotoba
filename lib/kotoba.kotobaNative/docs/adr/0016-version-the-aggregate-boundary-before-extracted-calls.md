# ADR 0016: Version the aggregate boundary before extracted calls

## Status

Accepted. Scalar-call hold superseded by ADR 0017; scalar variant hold
superseded by ADR 0023; flat record hold by ADR 0024; nested record hold by ADR
0031.

## Context

The extracted GMIR pipeline currently compiles one scalar-returning function.
It has no call operation and allocates only caller-clobbered scratch registers.
The allocated MC program also owns one frame prologue and lets every `return`
release that frame. Adding a direct call token alone would therefore be wrong:
the callee could destroy every live allocation and release the caller's spill
frame before control returns.

The established emitters already have a distinct record boundary. A record is
flattened or scalar-replaced while local, but crosses a function boundary as
one context-owned handle to
`pair(f0, pair(f1, ... pair(fN-1, 0)))`. The arena is bounded to 4,096 cells.
That representation is safe and executable, but allocation-heavy; it must not
be confused with Rust-like unboxed aggregate calling conventions.

## Decision

Publish `resources/aggregate-abi.edn` as the versioned portable boundary
contract and keep a CLJ/CLJS projection in `kotoba.native.aggregate-abi`, with
an exact drift test between them.

The contract records:

- the existing one-word pair-chain representation, declaration-order layout,
  zero terminator, context ownership, and arena bound;
- local record and variant SROA as separate from any external ABI;
- the five argument registers and one return register on each native target;
- that every register in the extracted allocator profile is call-clobbered;
- four prerequisites for admitting calls: per-function frames, preservation of
  live values, parallel argument assignment, and a single-word return register.

Extracted record and variant boundaries and call admission remain `:held`.
Supplying all four prerequisite names does not silently flip admission; the
versioned contract must change deliberately. Call-shaped KIR that reaches the
current producer fails with `:call-abi-not-admitted` rather than entering GMIR
or being reported as an unrelated unknown scalar operation.

The first future extracted aggregate crossing is limited to named, non-empty
records with unique `:i64`/`:bool` fields. Nested records, variants, identity-
bearing values, and borrowed raw memory are outside this predicate.

## Consequences

The compiler now has an executable boundary between local SROA and external
representation. Downstream verifier and Amu work can consume one EDN vocabulary
instead of inferring ABI facts from target emitter comments.

At the time of this decision no new call or aggregate path was claimed. ADR
0017 subsequently satisfied the four named prerequisites for scalar-only
direct calls and advanced the contract to v2. Existing record calls still
allocate pair cells and retain the 4,096-cell execution bound; extracted record
boundaries were later admitted by ADR 0024 and ADR 0031. ADR 0023 admits the
bounded scalar variant pair-handle boundary. None of these decisions makes the backend
Rust-speed, defines ownership/borrowing, or permits a Rust parity claim.
