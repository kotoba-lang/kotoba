# ADR 0087: Recursive and generic aggregates are one-word handles

## Status

Accepted.

## Context

Aggregate ABI v7 carried a record as a declaration-order pair chain and a
variant as `pair(ordinal, payload)`, but spelled the admissible payload set as
scalars plus an inline record. A type can only name itself through
`[:ref q]`, and a node's children are a heterogeneous vector, so every
recursive ADT (trees, cons lists) and every variant carrying a string, an
option or another variant was refused, although each of those members is
already exactly one native word.

## Decision

Advance `aggregate-abi.edn` to version 8.

- A variant payload, record field or heterogeneous-vector position is
  admissible when it is one word: a scalar, a pair-backed string/option/
  result, a qualified `[:ref q]`, or a record / variant / heterogeneous
  vector whose own members obey the same rule (`:boundary/payload-types`
  gains `:handle`).
- `[:vector [T ...]]` (1..32 positions) lowers to the same pair chain a
  record uses; `hetero-vector-at` / `-assoc` take a literal, in-range index;
  `hetero-vector-count` is the declared width.
- A variant with any non-`:i64`/`:bool` payload selects the boxed
  normalization, never the two-register local SROA path.
- Structural equality over handles (`hetero-vector-equal`, `record-equal`)
  stays refused: comparing handles compares cells, not values.
- Exported functions keep the host-validated boundary set; the widening is
  for internal calls only.

## Evidence

`recursive-adt-test` compiles a recursive tree module and the hand-written
pair program it should equal, and asserts identical machine code on x86-64
and AArch64. Executed end to end through amu (`compile` → `extract-native`
→ `tools/kexe_loader.c`) on both ISAs: tree sum 42, persistent update 10,
guest structural equality 1/0, cons list via a record 15, generic
`[:option [:ref ...]]` / `[:result [:ref ...] :string]` 63.

## Held boundary

Runtime ADT values remain bounded by the shared typed-value budget
(osaho `adt-node-limit` 64, `adt-depth-limit` 12), which the reference
interpreter re-checks at every constructor and which the Web and Wasm
runtimes share. A native arena could hold more, but lifting that budget is a
language-wide change, not an ABI one.
