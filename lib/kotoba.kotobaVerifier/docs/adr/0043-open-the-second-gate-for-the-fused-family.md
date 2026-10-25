# ADR 0043: open the second gate for the fused dequantize-and-dot family

Status: accepted. Date: 2026-09-02.

## Context

ADR 0023 recorded what happens when this repository does not know about an
operation the other six admit: the artifact is refused with "runtime KIR
operation rejected", and it was measured on the first real `.kotoba` program
that used `kernel-dot-f32`.

kotoba-gmir ADR 0023 adds three more.

## Decision

`kernel-dequant-dot-q8-0`, `-q4-k` and `-q6-k` at arity five in this file's
independently re-derived table, and in `kernel-native-operations`.

Both rows are needed and they say different things. The arity row admits the
call; the `kernel-native-operations` row suppresses the compile-time constant
oracle, because these operations read memory the oracle has not been given.
They do not arrive in that set with the windowed family's table — their
operands are two regions and a count rather than `base length index [value]` —
so they have to be named, once per format.

Arity is data rather than a shared constant, and it matters more here than for
the compare-exchanges beside it: four of the five arguments are
interchangeable i64 words at this layer, so a short call does not fail on a
type. It silently takes a length as a base and folds whatever is at that
address.

## Evidence

`test/kotoba/verifier_test.cljk`, three tests, each per format: admitted at
arity five with parameters and with literals; rejected at four, three and six
with the reason pinned; present in `kernel-native-operations` and absent from
`kernel-memory-operations`. Suite: 74 tests / 481 assertions.
