# aiueos extraction contract

This document is the source-side gate for moving `os/aiueos` from
`kotoba-lang/kotoba` to `kotoba-lang/aiueos`.

## Destination acceptance

The duplicate may be removed only when all of the following are true:

1. The aiueos destination commit is immutable and recorded as a full 40-digit
   object ID in the organization west manifest.
2. A checkout at that exact commit contains the complete migrated source tree.
3. File paths, bytes, and executable bits match this repository's
   `os/aiueos` tree. Intentional destination-only changes happen in a later
   commit, after extraction is complete.
4. aiueos independently passes the direct UEFI, journal recovery, corrupt
   kernel rejection, GPT release image, and VT-d/interrupt-remapping gates.
5. The destination CI, ADR, and release receipt no longer invoke files from a
   sibling `kotoba` checkout.

`scripts/finalize-aiueos-extraction.sh` enforces items 1–3 before producing the
source-side deletion. Items 4–5 require review of the pinned destination CI.

## Contracts that remain outside the OS repository

The language/compiler side retains only reusable freestanding contracts:

- target profiles `x86_64-aiueos-kernel`, `aarch64-aiueos-kernel`, and
  `x86_64-aiueos-uefi`;
- ELF64 and PE32+/COFF section, relocation, symbol, entry-point, and image
  layout emission;
- the no-libc/no-JVM/no-host-syscall freestanding runtime rule;
- calling convention, stack alignment, TLS/per-CPU, trap/context, and linker
  boundary ABIs;
- compiler-generated reset/entry shims and native-substrate link contracts;
- positive fixtures that link and execute a minimal emitted artifact, plus
  negative fixtures that reject hosted imports, writable executable sections,
  invalid relocations, and undeclared authority.

Bootloaders, kernel code, ACPI/APIC/PCI/IOMMU logic, device drivers, disk
formats, browser desktop transport, QEMU machine configuration, and bootable
images belong exclusively to aiueos after extraction.

## Source-side completion

After the verifier succeeds, the extraction commit removes:

- `os/aiueos`;
- the `aiueos-uefi` job from `.github/workflows/ci.yml`.

It updates links to the pinned aiueos source and leaves this contract plus the
language/compiler conformance fixtures. The deletion commit must not be merged
before its pinned aiueos commit is reachable from the west manifest.
