# ADR-0001 — The monitor's decisions live in Kotoba; the mechanism stays in aiueos

- Status: **accepted** — 2026-08-23
- Deciders: Jun Kawasaki
- Root authority: `com-junkawasaki/root` ADR-2608239100
- Related: aiueos ADR-0014 (self-owned VMM / hvt tender), aiueos ADR-0015
  (decision-free C mechanism boundary), root ADR-2607022400 (tender/guest
  vocabulary)

## Context

`aiueos.hvt` is a working monitor: KVM through `java.lang.foreign`, guest RAM,
a vcpu loop, a virtio-mmio device model, a virtqueue data path, and five
Kotoba guests compiled to bare-metal AArch64 ELF. Its guests are ours.

The question this repository answers is a different one: hosting an
environment we did not write. That question is asked of the workspace often
enough — "is there a VirtualBox on amu" — and the honest answer was no, with
the second half missing: what is missing is not a hypervisor. It is a
devicetree, a boot protocol, and a set of judgements about addresses.

## Decision

1. **A new repository, not a branch of aiueos.** aiueos is dependency-minimal
   by invariant and is the capability broker; a library of boot-protocol
   decisions with no I/O and no policy is a different product. The dependency
   runs one way: aiueos may consume this, never the reverse.

2. **Decisions in `.kotoba`, compiled by amu.** This is aiueos ADR-0015's
   split applied one layer out. The monitor's C-shaped work — ioctl, mmap,
   moving bytes, `KVM_RUN` — stays mechanism in `aiueos.hvt`. Which image is
   admissible, where the blob lands, what an address is, which PSCI call was
   made: those are decisions, and they compile.

3. **The artifact ships; the compiler does not.** `resources/vmm/oracle/*.kir.edn`
   is the runtime dependency (`kotoba.kir`), amu is test-only. A freshness
   gate refuses an artifact that no longer matches its source, because
   otherwise the `.kotoba` file becomes documentation while the host keeps
   executing the old decision.

4. **One implementation.** Host namespaces execute the KIR. They do not
   restate a rule "for the host side" — the mirror is the failure mode this
   split is supposed to remove, not introduce.

5. **Non-goals, unchanged from ADR-0014.** No type-1 hypervisor. No device
   zoo parity with QEMU. Not a second copy of `aiueos.virtio`.

## Milestones

- **M0 — landed 2026-08-23.** arm64 boot-protocol and VM-exit decision cores,
  64 assertions, both gates checked in the failing direction. No KVM.
- **M1.** A devicetree (FDT) core: header, string block, node layout,
  `/memory`, `/chosen` with `bootargs` and `linux,initrd-{start,end}`, and
  virtio-mmio nodes matching the address map already decided here.
- **M2.** `aiueos.hvt` calls these cores instead of its own constants, and a
  real arm64 Linux kernel boots far enough to print through the virtio
  console. Gate: a receipt carrying the guest's own `/proc/version`.
  Substrate: Lima vz nested virtualization to an aarch64 Linux `/dev/kvm`, as
  in ADR-0014 V0.
- **M3.** macOS/HVF, gated on the entitlement question ADR-0014 deferred.
- **M4.** x86_64: long mode entry, the Linux boot protocol's `boot_params`,
  and an e820 map.

M2 is the milestone that makes the claim true. Until it lands, this
repository decides correctly about a guest nobody has booted, and the README
says so.
