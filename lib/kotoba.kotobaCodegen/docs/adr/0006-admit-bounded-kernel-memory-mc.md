# ADR 0006: Admit bounded kernel-memory MC

## Decision

Allocated MC admits the five MIR kernel-memory operations with exact keysets:
u8/u32 load, u8/u32 store, and subregion derivation. The selected instruction
retains the base, logical length, index or subregion bounds, and the GMIR-owned
maximum. Target encoders own only the final checks, addressing, and bytes.

## Consequences

- Memory policy remains explicit from GMIR through selected MC.
- Extra ambient keys fail validation instead of reaching a target encoder.
- Legacy emitters are no longer required for this bounded memory family.
