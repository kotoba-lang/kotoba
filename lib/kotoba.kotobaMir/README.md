# kotoba-mir

Kotoba target Machine IR: target-selected instructions with explicit virtual or
physical register state.

**Tier**: `T0`  **Role**: `contract`

## Owns

- MIR v1 target and instruction contracts plus the versioned MIR v2 phi and
  MIR v3 function/call extensions;
- GMIR-to-MIR target selection for the matching closed operation set;
- x86-64-only admission for privileged actions, with structural rejection on
  AArch64 before allocation;
- deterministic allocation onto the v1 scratch-register profiles, growing
  into the leaf and preserved tiers on demand, then spilling only the live
  values that still do not fit;
- deterministic v2 phi lowering with direct edge moves for acyclic multi-phi
  joins, one reusable temporary frame slot for cyclic parallel copies, and
  destination-slot coalescing in the general spill path;
- fail-closed validation of virtual and physical MIR.
- independent per-function frames and liveness-minimal preservation for
  straight-line scalar direct calls, including parallel assignment into five
  ABI registers; CFG/phi joins stay on the linear allocator, and calls that
  cannot complete that way retain deterministic all-vreg preservation;
- canonical ABI input markers plus parallel function-entry assignment: four
  simultaneously used scalar parameters stay in registers with a zero-slot
  frame on x86-64 and AArch64; a fifth live parameter is stored directly from
  its ABI input into one stable slot and loaded lazily, including direct
  restoration into the fifth outgoing call register;

## Does not own

- KIR or KIR-to-GMIR lowering;
- instruction encoding or branch-byte layout;
- ABI prologues, calls, artifact identity, or object formats.

## Dependency direction

```text
kotoba-mir -> kotoba-gmir
```

No target backend is imported by this contract.

## Test

```bash
kbb -M:test
```
