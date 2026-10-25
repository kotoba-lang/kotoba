# ADR 0022: Migrate bounded kernel memory

## Decision

Route bounded kernel u8/u32 loads and stores and kernel subregion derivation
through KIR to GMIR, target MIR, selected MC, final layout, and target bytes.
The GMIR instruction owns the admitted maximum. Encoders use private ABI scratch
registers and emit all trap branches as layout tokens.

For u32 access, first prove `index < length`, then prove
`length - index >= 4`. This avoids the overflow ambiguity of `index + 4`.

## Consequences

- Source operands evaluate exactly once and in source order.
- Null, maximum, range, and width checks share the final-layout trap target.
- These operations no longer enter a legacy expression emitter in production.
- Runtime handles, strings, capabilities, and non-scalar aggregates remain
  separate migration families.
