# ADR 0025: Extract the x86 privileged operation family

Status: accepted

## Decision

The 19 x86-64 kernel operations for boot context, CR2/CR3, TLB invalidation,
interrupt state, halt/pause, port I/O, MSRs, and CPUID lower to the closed
`:gmir/x86-privileged` action family. MIR admits this family only for x86-64;
AArch64 rejects it during target selection because its system-register and
device-I/O model is not an equivalent spelling of these operations.

The allocated MC instruction retains the action and zero to two physical
arguments. The x86 encoder owns fixed-register moves and preserves every
non-destination allocator register. CPUID additionally preserves `rbx` as
required by the host ABI.

## Consequences

- Production x86 compilation no longer routes privileged operations through
  the legacy expression emitter.
- The operation names, arities, target restriction, MC keyset, and exact ISA
  opcode families are independently validated.
- Privileged instructions are byte-verified but are not executed in the
  unprivileged loader test process.
- A future AArch64 privileged surface requires its own semantic operations;
  this decision does not invent false one-to-one translations.
