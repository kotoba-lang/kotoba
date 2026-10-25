# ADR 0047: a codebook is not an argument

Status: accepted. Date: 2026-09-03.

## Context

ADR 0043 opened this repository's two gates for the fused dequantize-and-dot
family: the arity table, because four of the five arguments are
interchangeable i64 words here and a short call would silently take a length
as a base; and `kernel-native-operations`, because the family reads memory the
compile-time oracle has not been given and its shape is not
`base length index [value]`, so it does not arrive with the windowed table.

`kotoba.gmir` ADR 0027 declared four more members — IQ4_XS, IQ2_S, IQ3_XXS,
IQ3_S, 306 of the Qwen3.5 model's 866 tensors. **This repository rejects by
absence.** A program every other layer admits would have failed here with
`runtime KIR operation rejected`, and ADR 0043's own record of `kernel-xgetbv`
says how that is found: not by a suite, but by a `.kotoba` program.

## Decision

Four more rows in each of the two tables, and a test that counts them
together. Arity five, unchanged.

**The codebook is not among the arguments.** A code in these four formats is
an index into a table of 256, 512 or 1024 entries, and that table belongs to
the FORMAT: it is read-only data the compiler places beside the code, not a
region a caller passes in. So there is no third base whose provenance to walk
and no third length to bound, and the arity that would otherwise have to grow
does not.

## Consequences

- Seven formats, both gates, counted by one test. A row added to one table and
  not to the other is the failure it exists for, and the two failures are
  different: the arity table's absence produces `runtime KIR operation
  rejected` where an arity rejection was expected, and the operations set's
  absence lets the compile-time oracle try to fold a read of memory it was
  never given.
- Break/unbreak, 2026-09-03: removing the `iq4-xs` arity row turned three
  arity rejections into `runtime KIR operation rejected`; removing the
  `iq3-s` operations row failed the suppression test by name.
- Admitting an operation is not implementing it. `kotoba-native` has no arms
  for any of these four and refuses them by name (its ADR 0075).
- **This does not make the four reachable from Kotoba source.** The frontend
  allowlist is in `kotoba-sema`, whose vendored copy of the language
  authority's grammar is pinned by sha256 in four repositories at once; adding
  a head there is a coordinated wave and was measured in flight on 2026-09-03
  (the authority on `kotoba-lang/main` hashes `1dfb0bb5…` while `kotoba-sema`
  main pins `9f4a779c…`). Until that wave carries these four heads, no
  `.kotoba` program can call one and no execution can measure one.
