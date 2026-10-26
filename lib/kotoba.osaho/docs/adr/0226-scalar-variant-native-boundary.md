# ADR 0226: Admit the closed scalar-variant native boundary

## Status

Accepted

## Decision

Native typed-feature admission accepts a variant at a function boundary only
when its descriptor has a qualified name, one through 32 uniquely named cases,
and every case payload is exactly `:i64` or `:bool`.

The public host value remains the canonical KIR value
`[type case-keyword payload]`. The native runtime representation is not a
second value model: downstream owns a context-local pair handle containing the
zero-based declaration ordinal and one scalar payload word.

## Evidence

- the KIR oracle echoes both the minimum signed i64 payload and a false boolean
  through a typed variant parameter and result;
- admission accepts that same exported function;
- unqualified, empty, duplicate, nested-record, string-payload, and 33-case
  descriptors are rejected;
- changing the case limit from 32 to 33 makes the 33-case negative fail.

## Consequences

- Amu may route this exact descriptor family to independently validating
  native/verifier/tender/loader consumers;
- local expression variants may retain richer representations, but those do
  not become public ABI by implication;
- wider payloads, nesting, and more than 32 cases remain design work rather
  than silently admitted values.
