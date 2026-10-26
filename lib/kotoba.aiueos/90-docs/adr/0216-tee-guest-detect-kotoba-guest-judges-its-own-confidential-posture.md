# ADR-0216 — tee-guest-detect.kotoba: the guest judges its own confidential posture

- Status: accepted
- Date: 2026-09-15
- Completes the guest half of vmm ADR-0002 (TDX / SEV-SNP admissible
  postures). Executes ADR-0015's split one more time: C carries the
  instruction, the compiled object carries the judgement.

## What changed

`os/aiueos/kotoba/tee-guest-detect.kotoba` is a new kernel-side decision
object. It exports two predicates over CPUID results:

- **TDX**: CPUID leaf `0x21` present ("Intel TDX" signature) **and** the
  TDVF window inside `[0xFE000000, 4 GiB)` — base+size form, 1 MiB
  minimum size.
- **SEV-SNP**: CPUID Fn8000_001F EDX bit 31 (SEV) **and** bit 11 (SNP).

Nothing in C decides: the C side gains only the CPUID-issuing instruction
shim (the same mechanism/judgement split as `cpu-feature-nx`, ADR-0015).

## Verification (measured, 2026-09-15)

- `test/aiueos/tee_guest_detect_test.cljk` compiles the `.kotoba` at test
  time through amu and runs the KIR: 4 tests / 16 assertions, 0 failures.
- Boundary values measured both sides: `0xFE000000` exactly (in),
  one byte below (out), `4 GiB` exactly + 1 (out), minimum-size 1 MiB.
- The test route is JVM-only on this host (amu compile needs
  `java.nio.charset`); the kbb/sci route reuses the compiled object and
  was exercised in the landing verification (16/16 assertions green both
  routes).

## Not claimed

- The guest cannot yet *act* on the posture (no TDG.VP.VMCALL issuing,
  no PSC requests from the guest side); this ADR records detection only.
- Host-side KVM_SEV_*/KVM_TDX_* ioctls remain unimplemented (vmm ADR-0002
  "Known gaps"). Detection without a launching host is a decision plane
  waiting for its mechanism; both halves are named so neither is mistaken
  for the other.
