# ADR 0047: A structural position is converted to a host index before use

- Status: Accepted
- Date: 2026-08-30

## Context

`hetero-vector-at` and `hetero-vector-assoc` carry a STRUCTURAL position:
which member of a heterogeneous value is being read or replaced. KIR carries
that position as an ordinary i64 literal, and an i64 literal is a `Long` on
the JVM and a JavaScript `BigInt` under cljs/nbb (`kotoba.kir.cljs-i64`).

This backend used the literal directly as a host `nth` index in three places
-- `kotoba.wasm.core`'s `hetero-vector-at` and `hetero-vector-assoc` cases,
and `kotoba.wasm.typed/infer-type`'s `hetero-vector-at` case -- to select the
member type. On the JVM that is a no-op. On cljs `nth` refuses a BigInt with
`Index argument to nth must be a number`, a host-level error with no ex-data,
which the compiler CLI can only report as `:kotoba/internal-error`.

The KIR reference interpreter already performs this conversion for the same
two operations (`kotoba.kir`, `host-index`). The Wasm backend did not.

## Decision

`kotoba.wasm.typed` gains two exported functions:

- `host-index` converts a structural position to a host integer, and refuses
  anything that is not a non-negative integer literal with
  `{:phase :wasm-typed-lowering}` rather than letting a host-level `nth` error
  escape as an internal compiler error.
- `hetero-item-type` selects the member type at a structural position and
  refuses a position outside the value's arity with the same phase.

Both `hetero-vector-at` and `hetero-vector-assoc` use them, in `core` for the
member type and the emitted operand, and in `typed/infer-type` for the result
type. No construct is newly admitted: this is the lowering for a construct the
frontend already admitted and the JVM already lowered.

## Evidence boundary

### What was measured

Before the change, on nbb, the amu CLI answered exit 70 and
`:kotoba/internal-error` for `orgs/kotoba-lang/org-iso-h264/src/h264/expgolomb.kotoba`
and for an eight-line reduction of it. The underlying throw, obtained by
calling `kotoba.wasm.core/emit` directly, was `Index argument to nth must be a
number` with `ex-data` `nil`. The same KIR emitted bytes on the JVM without
complaint.

After the change, for `test/nbb/fixtures/hetero-vector-position.kotoba` in the
compiler repository, JVM and nbb emit BYTE-IDENTICAL `wasm32-browser-kotoba-v1`
modules: SHA-256 `748ad1c19831da8b12989396fbcd48d2c4fd74c76056fb3b8b53eceb4d52ec93`
on both. The nbb-emitted module, instantiated through the compiler's
`runtime/browser-host.mjs` and called by export NAME, returns `main` 327,
`head` 3, `tail` 2.5, `swapped-tail` 9.25 -- the same four values the KIR
reference interpreter `kotoba.kir/execute` returns for the same inputs.

This repository's suite is 119 tests / 525 assertions / 0 failures.

### What was NOT done, and why

This repository has no cljs test runner, so the assertions added here cannot
see the defect: on the JVM the conversion they exercise is a no-op cast, and
the pre-change code passed the identical positions. That is exactly why the
defect survived here. The falsifying regression test is in the compiler
repository's `test/nbb` suite, which runs on the second runtime.

No attempt was made to find other operations whose KIR operand is used as a
host index. `record-get`/`record-assoc` compute their position from a keyword
by `keep-indexed` and so are host numbers already; the dynamic-index operations
(`vector-at`, `typed-set-nth`, `typed-map-entry-at`) emit their index as an
expression rather than consuming it here. Positions elsewhere in the emitter
were not audited.

### Limits of this evidence

The behavioural comparison is over four exported functions of one fixture at
one set of inputs, through one host (`browser-host.mjs`) at one target. It is
not a claim about `wasm32-wasi`, about other typed operations, or about the
h264 module's semantics -- only that module's compilation was measured, not
its execution.
