# ADR-0002 — TDX and SEV-SNP as admissible guest postures, judged in Kotoba

- Status: **accepted** — 2026-09-15
- Deciders: Jun Kawasaki
- Root authority: `com-junkawasaki/root` (provisioning owned the TEE ask:
  "vmm, tdx, sev-snp guest os それぞれ対応する様に設計・実装")
- Related: ADR-0001 (decisions in Kotoba, mechanism in aiueos), aiueos
  ADR-0015 (decision-free C boundary)

## Context

ADR-0001 answered "can we host an environment we did not write?" for a plain
AArch64 guest. Confidential guests repeat that question under a harder
constraint: the host must be able to *assert* that a guest image and its
launch configuration are admissible for a confidential-VM technology, and
the guest must be able to *assert* which technology it is running under.
Neither side of that assertion existed anywhere in the workspace: `git grep`
for tdx/sev-snp/cvm across vmm and aiueos returned zero hits, the boot path
was plain q35 + OVMF, and the KVM ioctl surface in `aiueos.hvt` carries only
the basic aarch64 API.

## Decision

1. **The launch admission and runtime judgements are decisions, compiled.**
   `kotoba/tee_core.kotoba` (→ `resources/vmm/oracle/tee_core.kir.edn`)
   decides, per technology:
   - TDX: capability agreement (`KVM_TDX_CAPABILITIES` shape), a verified
     TDVF image, virtualization of the CPUID leaf-0x21 signature and the
     indirect-adapter bit, and post-boot translation of TDG.VP.VMCALL exit
     reasons (map-gpa / io / get-quote / setup-event-notify) into actions.
   - SEV-SNP: capability agreement, an AmdSev OVMF image, CPUID
     Fn8000_001F SEV+SNP bits, the `SNP_LAUNCH_START` policy layout from AMD
     56860 Rev. 1.59 (reserved bit 17 must be one; bits 63:26 must be zero),
     named rejection of every PSC error
     code, and guest-request size floor (400 bytes).
   The numbers pinned in tests are hand-computed from the Intel TDX module
   spec, AMD 56860 and AMD 24593, with rejection-reason literals pinned
   verbatim.

2. **The mechanism boundary is unchanged.** `src/vmm/tee.cljk` normalises
   KIR values and calls the oracle; it does not contain judgements. The
   KVM_SEV_*/KVM_TDX_* ioctl surface, RMP management, and attestation
   verification (TDREPORT / SNP attestation report) remain *unimplemented*
   in `aiueos.hvt` — macOS hosts cannot measure them, and this ADR does not
   claim TEE protection. The claim boundary is recorded in the vmm README
   and aiueos `docs/deployment-profiles.md`.

3. **The guest asserts its own posture, structurally.**
   `os/aiueos/kotoba/tee-guest-detect.kotoba` decides: TDX = CPUID leaf
   0x21 present *and* the TDVF window inside [0xFE000000, 4 GiB); SNP =
   Fn8000_001F EDX bit 31 (SEV) *and* bit 11 (SNP). C carries the
   instruction, the compiled object carries the judgement — the same split
   as `cpu-feature-nx` (aiueos ADR-0015), measured by a parity test that
   compiles the `.kotoba` at test time and runs the KIR.

## Verification

- vmm JVM suite: 24 tests / 116 assertions, 0 failures (includes
  `vmm.tee-test`: launch admissions, both technologies, PSC codes,
  policy-mask boundaries, guest-request floors).
- kbb/sci route: launch + all 5 named rejections + psc + psc-unknown green.
- aiueos parity test: 4 tests / 16 assertions, 0 failures (boundary values
  at 0xFE000000 exact, 4 GiB exact, one-past-ceiling included).
- Two measured KIR-interpreter quirks were worked around (not papered
  over): tail-comparison `:bool` fns trap on cljs only; `bit-not` on
  negative i64 intermediates miscalculates on cljs only. Both sites carry
  comments recording the measurement; the workarounds are `:i64`-typed
  helpers and a bit-not-free identity.

## Known gaps (not claimed as done)

- `aiueos.hvt` has no KVM_SEV_*/KVM_TDX_* ioctls: launching a real
  confidential VM on a KVM host is mechanism work, still to do.
- Attestation verification (host-side quote validation) is absent.
- Pre-existing red, unrelated to this change: `aiueos/uefi/{integrity,
  memory}.kotoba` reachability failures exist at HEAD.
