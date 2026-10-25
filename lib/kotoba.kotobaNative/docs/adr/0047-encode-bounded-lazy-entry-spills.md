# ADR 0047: Encode bounded lazy function-entry spills

## Status

Accepted. This supersedes ADR 0019 only for five-live-argument behavior.

## Decision

Pin MIR `534caf12` and codegen `4d960da4`. Native preserves MIR's entry order:
canonical ABI argument markers, direct stores for inputs beyond the four-register
allocator profile, then the cycle-safe register copy schedule. Argument markers
remain zero-byte metadata; spill stores and lazy loads use the existing bounded
frame encodings.

For a five-argument local call, both the callee and caller own exactly one frame
slot. The callee loads the fifth input only when its expression consumes it.
The caller finishes register copies and then loads that backed input directly
into the fifth outgoing ABI register before the call.

## Evidence

The KIR-to-final-layout integration test compiles the same five-argument module
for both targets. Each function contains exactly one spill store and one spill
load. Policies are `[:allocator :call-live]`, and frame slots are `[1 1]`.

Final module size falls from 287 to 115 bytes on x86-64 and from 176 to 72 bytes
on AArch64. Four-argument modules remain 66 and 40 bytes respectively.

## Consequences

One excess entry value no longer materializes every SSA definition. The
all-vreg allocator remains the fail-closed fallback for unsupported control
flow or later pressure. These representative size reductions do not establish
whole-language Rust performance parity.
