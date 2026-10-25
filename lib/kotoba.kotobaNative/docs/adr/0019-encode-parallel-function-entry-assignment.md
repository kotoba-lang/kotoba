# ADR 0019: Encode parallel function-entry assignment

## Status

Accepted. Its five-live-argument fallback measurements are superseded by ADR
0020; the four-register parallel-entry evidence remains current.

## Decision

Pin the MIR and codegen contracts that represent every physical function entry
as canonical ABI argument markers followed by a cycle-safe parallel move
schedule. Native emits argument markers as zero bytes and encodes the scheduled
moves in their given order.

The native integration gate compiles a four-parameter local call through KIR,
GMIR, MIR, MC, and final x86-64/AArch64 layout. Both callee and caller must have
zero spill slots and no spill instructions. A separate five-live-parameter
case must retain and encode the conservative frame-backed fallback.

The measured final module sizes for the representative four-parameter call are
66 bytes on x86-64 and 40 bytes on AArch64. The five-parameter fallback is 287
and 176 bytes respectively, with callee/caller slot counts `[9 6]`.

## Consequences

x86-64 preserves the fourth input from `rcx` before assigning the second input
to `rcx`; AArch64's first four ABI inputs need no entry moves. The backend does
not infer or repair unsafe move order. Aggregate arguments, external calls, and
Rust performance parity remain outside this decision.
