# ADR 0279: HTTP header-state nominal-record migration

- Status: Accepted
- Date: 2026-08-04
- Depends: provider ADR 0223/0229/0233/0276–0278; compiler ADR 0208

## Context

The three largest remaining HTTP packages modeled header-name state, a header
EDN accumulator, and a foldable header bag with manual schemas and 52 explicit
raw record operations in total.

## Decision

1. Introduce domain-named `HeaderNameSet`, `HeaderEdnAccumulator`, `Header`,
   and `HeaderBag` records in their independently compiled packages.
2. Replace raw construction/projection with nominal constructors, keyword
   access, and record destructuring.
3. Preserve every export and all three `main = -9002` oracles.
4. Keep recursive W4 and Component AOT qualification unchanged.

## Evidence

- compiler merge: `3ebb7ffa0cfa91463fbe75d0f0bfc7e77d95d94c`
- header-name-set wasm/source/provenance:
  - `85dd13bda2c801753d88025dce913bac4a2d5c3e80acf4648130ea2a022200d2`
  - `0e96f1611671c8d67bc139ef385c5c675f9f832902d2dc9bed93ae03ad326528`
  - `aa50736073713fda8baf7b6ce9590f1f21643a045a222cc3458dc7bec12ad447`
- header fold wasm/source/provenance:
  - `83e436b0674ceec5a85cd0a771e42b52d5b4e2a2286d708deee723afdceb8e98`
  - `9c0898892aaeacfc61033fc58f39d177de065e9240ecf7e5f5adcc18364ba20d`
  - `f5fcb8357bd3b7d19b4a86df0011318ffc0efed4bc34e3a75bf8d41a4442d8bc`
- EDN set package wasm/source/provenance:
  - `366a0ee5e2a34150ddf213e1bf073ed60485ba95d5266f1881fa6f1517cae906`
  - `5411aeaf959ac84f68a4b45f5ec5dbbf40a4e3d88696d6da45339198ec19a4c9`
  - `cda4890cb0e37dd4bf876d48de93e7aa1ff325e1838838f6f7d6b895b3f5c6a3`
- Independent KIR oracles, registry/export/digest tests, and raw-surface
  absence tripwires cover each package.

## Consequences

The provider residual loses another 52 compiler-shaped sites. Short positional
constructors are retained where their arity is truthful; wider records keep
exact-map construction. This makes the source concise without hiding bounds.
