# ADR 0004: Preserve the call-live frame policy

## Status

Accepted.

## Decision

MC v3 preserves MIR's `:call-live` frame policy without backend inference. Its
spill loads, stores, parallel argument moves, direct call, and bounded frame
remain ordinary closed MC instructions and are independently revalidated by
the pinned MIR contract.

The existing `:all-vregs` policy remains valid for MIR's control-flow and
register-pressure fallback. MC does not rewrite one policy into the other.

## Consequences

Target encoders can distinguish a call-containing liveness frame from a
call-free allocator frame while retaining the exact same direct-call encoding
contract. This repository claims preservation and validation, not ownership of
the liveness analysis.
