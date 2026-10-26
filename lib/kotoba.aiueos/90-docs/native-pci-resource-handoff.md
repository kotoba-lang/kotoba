# Native PCI resource handoff candidate

Status: local ARM/QEMU candidate, not merged or native x86/controller adopted.
JUN-31 owns this dependency
before whole-kernel/live, release media and desktop/input acceptance.

The retired `kernel-firmware-mmio` prototype used a firmware memory type as
device authority. UEFI specifies that EfiMemoryMappedIO is for firmware
runtime access; OS MMIO information comes from ACPI. Its observed range/null
checks did not prove OS ownership. The prototype was removed before public
compiler adoption. Private metadata copying and stack protection remain
separate valid mechanisms.

Use the PCI I/O protocol's GetBarAttributes resource descriptors as the
device-specific input, with GetLocation for identity. This remains a closed
x86 OS policy, not an app capability or permission to access arbitrary PCI
devices. Runtime-firmware ranges remain protected. Source references:
[UEFI memory usage after ExitBootServices](https://github.com/UEFI/UEFI-Specification-Release/blob/main/source/07_Services_Boot_Services.rst),
[UEFI PCI resource protocol](https://uefi.org/specs/UEFI/2.10/14_Protocols_PCI_Bus_Support.html),
[EDK2 protocol layout](https://github.com/tianocore/edk2/blob/master/MdePkg/Include/Protocol/PciIo.h).

## Producer and schema

The native Kotoba EFI packager needs a versioned extension, rather than a
reinterpretation of boot-info v5. The implemented candidate v6 keeps the160-byte prefix
and16KiB map, assigning the reserved144/152 fields to catalog pointer/bytes.
All constructor, packager, kernel and observer checks must move together.
The published full31 compiler remains v5 until a successor is admitted.

Before the final GetMemoryMap/ExitBootServices pair, the loader enumerates
PCI I/O handles, obtains location and BAR0..5 descriptors, and records exact
memory resources. Free every returned pool, including rejected descriptors;
close protocol accesses before the final memory map. No firmware call occurs
after ExitBootServices. No BAR probing write or device reset is necessary.

The bounded candidate catalog has a32-byte header and at most128 records of
64 bytes. Each record carries physical base/bytes, segment, bus, device,
function, BAR and vendor/device identity. Only the declared single-segment
x86 profile is initially in scope. Handle/resource overflow, malformed
descriptors, unsupported address translation and incomplete enumeration
must refuse instead of silently truncating the handoff.

Validation must retain exact descriptor bounds without rounding a resource
outward. Exclude firmware-runtime overlaps. A decoded BAR, a memory-type
classification, a caller-selected integer and a writable public boot record
do not independently establish a grant. The platform policy and ownership
decision require their own acceptance evidence.

## Consumer and private layout

Before main, copy and validate the bounded catalog into private image
storage. Do not reuse the non-live low20KiB context reservation for the live
queue/arena. The PCI candidate now has a larger, versioned private layout and stack
floor. Live records still need a separate reconciled layout.

The candidate constructor is
`kernel-pci-mmio(bus, device, function, base, bytes)` for segment0.
It checks identity, extent and ownership against that private handoff.
Positive bounded bytes with base0 represent absent hardware and return0;
all memory consumers retain non-null guards. Invalid lengths, nonzero
ungranted addresses, stale/mismatched resources and forged public metadata
must fail closed. The static region extent is the exact bytes operand.

Kernel, RTL8125 and debug-link callers must carry their actual PCI identity.
The candidate primitive is implemented in the Amu kernel worktree; it is
absent from the admitted public full31 compiler. Do not substitute reserved memory, the retired constructor or a
literal physical parent to make the graph compile.

## Acceptance order

1. Rebuild the complete compiler and native EFI collector from pinned Kotoba
   source; retain all18 core modules and whole source graphs.
2. Observe a real PCI BAR resource and its identity in QEMU, checking the
   collector against independent firmware/device observations. Empty,
   unsupported and over-limit cases need explicit controls.
3. Execute a bounded positive access and refusal controls for missing or
   mismatched identity, bounds, runtime overlap and public-record forgery.
   Restore modified guest device state. A synthetic resource cannot qualify
   an actual platform.
4. Rebuild and execute the complete15-module kernel, then the27-module live
   root with its queue/capability/domain ABI. Record admission, artifacts and
   runtime separately. No source trimming or hosted fallback.
5. Adopt successor ARM root/public x86/compiler/controller pins only with
   complete native x86 and two-role controller evidence; then proceed to
   native media and QEMU desktop/input. Physical RTL8125 qualification is
   separate from a QEMU display-device resource test.


## 2026-10-24 local candidate evidence

Amu collector commit70fcdf32b is source-bound to full37 ARM fixed point
b482a0738a1c17e6..., all24 runtime cases. Native F1/F2 reproduce both v6
EFI/payload candidates; v5 packaging/corruption regressions pass. QEMU
collects3 PCI memory BARs whose BDF/BAR/vendor-device/base/bytes exactly
match independent QMP observations.

The subsequent private consumer candidate is source-bound to full37 ARM
fixed pointdffb92704da855ac..., all24 runtime cases and region/helper/window/
width/lock/ISR packaging regressions. v6 uses128KiB image-owned RW storage,
with a64KiB private floor and the copied PCI catalog at context20480. v5
project context retains its20KiB floor. Single-source image/object ABI stays
separate. A PCI-dependent image refuses packaging without explicit v6.

QEMU's real VGA BAR is checked by BDF/extent, then read, written, verified
and restored; result42 and exact fuel999999. This fixture has one source
fuel-charge site; bounded inline primitives do not add source charges.
Public pointer/bytes forged to a RAM catalog cannot replace the private
snapshot. Bad BDF, outside BAR, zero/oversized bytes and RAM requests hit
the exact constructor UD2. A deliberately corrupted EFI collector record
pointing into RAM reaches the trusted bootstrap's refusal, distinct from
constructor, fuel or memory guards. This corruption is only a negative
input and does not qualify a platform resource. The observer's valid-image
negative control must refuse. Physical NIC and full ownership-policy
qualification, empty/limit firmware execution and successor adoption remain
open.

The full15 kernel now compiles and reproduces its ELF through the engineering
native region-graph solver, then packages through the native PCI v6 EFI
route. All functions and immutable owner dependencies are retained. See
[DMA contracts](native-dma-region-contracts.md) for the corrected2048-byte
RX buffer bounds and independently observed QEMU snapshot controls.
The full27 live root still needs queue/capability/domain and entry ABI work.
Native x86/controller adoption remains required before media/desktop acceptance.


Latest baseline: main0486b715e/PR1535 is integrated. Fresh ARM full37
F1=F2 is0066017a8330d960..., with all24 runtime and native fixture
regressions. All13 prior QEMU artifact/observer identities match the new
producer outputs exactly; latest compiler/source binding is recorded in
Amu's aiueos-pci-current-main-20261024 evidence. Those older whole-graph
refusals and six lock corruptions remain immutable historical receipts;
the newer DMA engineering candidate is recorded separately.
