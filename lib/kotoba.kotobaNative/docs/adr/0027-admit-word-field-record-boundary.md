# ADR 0027: Admit word-field record boundaries

Status: accepted

## Decision

Aggregate ABI v5 widens the portable record pair-chain boundary from only
`:i64`/`:bool` fields to every field type already represented by one native
word: scalar primitives, string/keyword/vector handles, and the closed
option/result/list/set/map/ref handle families.

The representation does not change. Fields remain declaration-ordered pair
cells terminated by zero, owned by the bounded host context arena. Nested
record and variant layouts remain outside this boundary.

## Consequences

- Checked records containing option/result or other one-word handles can cross
  native function parameters and results without legacy emission.
- No recursive layout or additional machine word is introduced.
- Aggregate ABI consumers must pin version 5 and the
  `:word-pair-chain-admitted` record claim.
