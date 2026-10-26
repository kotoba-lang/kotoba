# ADR-0060 — The offline floor is a gate now, and it was always true by accident

Date: 2026-08-18

## Status

Accepted and executable. It closes the oldest open item in this series:
ADR-0041's decision 5, which said the offline floor "is a gate ... not a
sentence in a README" and then stayed a sentence for ten iterations of the loop
that wrote it.

## What was already true, and unasserted

`smoke-qemu-uefi.sh` attaches a NIC **only when `AIUEOS_TEST_NET=1`**. So every
existing gate has been booting the NIC-absent machine all along, and the kernel
already emits `AIUEOS_VIRTIO_NET_ABSENT` when it finds none.

Nothing asserted any of it. **A property that holds because of a default is one
flip of that default away from being untrue with every gate still green** — and
nobody would be looking, because the thing that would have noticed was the
sentence in the ADR.

## The gate

`smoke-qemu-offline-floor.cljs`, in the equivalence shape ADR-0019 used for USB
versus disk: run the same image both ways and require a stated relation, rather
than two independent green checks that can drift apart.

- both runs reach `AIUEOS_UEFI_SMOKE_OK`;
- the NIC-absent run emits `AIUEOS_VIRTIO_NET_ABSENT` — **it noticed**, rather
  than skipping the network silently, which is the failure this whole series
  keeps finding;
- every marker the NIC-absent run produces, except that one, also appears in the
  NIC-present run: **removing the NIC removed nothing else**;
- the extra markers in the NIC-present run are **exactly** the three network
  ones, named rather than derived, so widening that set is a decision.

Measured: **65 shared markers, 3 network-only, 1 absence marker.**

An evidence floor sits under all of it: fewer than 40 markers from the
NIC-absent run is a missing log or a boot that did not get far, not a clean
comparison of two nearly-empty sets.

## The build runs here, and it confirms ADR-0058 the hard way

This iteration built the real thing rather than reasoning about it:
`build-kotoba-native-kernel.sh` and `build-kotoba-native-boot.sh` against an
amu worktree pinned at `1de9dafe…`, then the UEFI smoke, all on this machine.

`KERNEL.ELF` came out **49,520 bytes with SHA-256
`9ae5180a92f0fffe9e153a1440f8eda507c0f0c4d35f16c633ac3a609e5bbbd7`** — byte for
byte the digest ADR-0040 recorded, from a tree that **includes ADR-0058's
`(:export [main])` edit to `native/kernel.kotoba`**.

ADR-0058 argued that edit was inert from in-memory compiler digests and said
plainly it was "not a QEMU boot, and does not claim to be". It is now both: the
production build produces the identical kernel, and that kernel boots to
`AIUEOS_UEFI_SMOKE_OK`. The claim that was an argument is a measurement.

## Executable evidence

- `AIUEOS_OFFLINE_FLOOR_OK shared=65 network-only=3`
- `AIUEOS_KOTOBA_NATIVE_KERNEL_OK` and `AIUEOS_KOTOBA_NATIVE_BOOT_OK` from the
  builds; `AIUEOS_UEFI_SMOKE_OK` with the NIC absent and with it present
- Full suite **629 tests, 9390 assertions, 19 failures** — the baseline
  nineteen. Lint unchanged.

**Three mutations, each failing its own branch**: expecting an absence marker
the kernel never emits fails the "did not say so" check; declaring two network
markers instead of three fails the extra-markers check with both sets printed;
raising the evidence floor to 400 fails with the count it actually saw. Each is
equivalent to the reality it stands for — a kernel that stopped emitting the
marker is indistinguishable, to this gate, from a gate expecting the wrong
name — and that equivalence is stated because the alternative, rebuilding a
deliberately broken kernel per mutation, is three more builds for the same
information.

## Remaining boundary

- **The gate is not wired into any runner.** `scripts/tasks.edn` does not call
  it and neither does anything else; it is a script that passes when run. The
  same criticism this series has made of eleven verifiers nobody invoked
  applies to it until that changes.
- **It proves the boot reaches its terminal state without a NIC**, not the rest
  of ADR-0041's floor: verifying its own enrolment, refusing unadmitted
  components, and appending to the audit chain with the uplink down are
  separate claims and are still unasserted.
- QEMU with OVMF on one host is not hardware. No physical machine has booted
  this image, with or without a NIC.
