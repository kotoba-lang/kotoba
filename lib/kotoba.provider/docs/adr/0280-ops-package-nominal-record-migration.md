# ADR 0280: process, git, and HTTP append nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0224/0238–0241/0276–0279; compiler ADR 0208

## Context

The next three largest raw-record users each contained 14 explicit operations:
process and git request accumulators, plus the earlier HTTP header EDN append
package.

## Decision

1. Introduce `ProcessRequest`, `GitRequest`, and `HeaderEdnAccumulator` as
   domain-named nominal records.
2. Use truthful three-argument positional constructors, keyword access, and
   record destructuring instead of manual schemas and raw ABI primitives.
3. Preserve every export and the `-2309`, `-2311`, and `-9002` main oracles.
4. Leave OS authority, recursive W4 data, and Component AOT claims unchanged.

## Evidence

- compiler merge: `3ebb7ffa0cfa91463fbe75d0f0bfc7e77d95d94c`
- process wasm/source/provenance:
  - `92c971e5d6b59d51c448091d45bf925ee0a87ea7808e9fa78cc697846c7d5917`
  - `114742d54764f311b4293a52e497890e874bbfd6ac5e08f2b140a127fd834588`
  - `a6861a8f91cb1020693501bfb8a970d8bbccb9938b8a685247dac3aa71c46fad`
- HTTP append wasm/source/provenance:
  - `5bf99a51ee63e6922c5c40dac91500fb54569f542469643ff51a09f38b63c494`
  - `afa5b66d7529ae6f432e639d6863f28cfb617e87a70b195b6a8f4de6b772a891`
  - `e6b693a3dccf8596e8e0458f99af48b0cdc096c112b292344845ca53db42c2c2`
- git wasm/source/provenance:
  - `b0c8e8581f2d82b9f87beb0781708e6304f3bb91741eff70568f4e4104ef4445`
  - `f0d799d383b4b2942920b2590ba2e5a413d0c8b8dfd010a3b49cf19304e4b928`
  - `934ba530da094790a2591f76cc85ba4caef0acbb1a9138dc22d76bb6a6c22c86`
- Independent KIR oracles and registry/source tripwires cover all three.

## Consequences

This removes another 42 raw record sites. The source exposes the accumulator's
meaning directly, and the small-record constructor syntax remains both concise
and honest about the callable ABI.
