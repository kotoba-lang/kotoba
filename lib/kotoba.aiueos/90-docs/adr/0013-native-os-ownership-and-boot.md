# ADR-0013 — aiueos boot, kernel, image, and OS integration

- **Status**: Accepted; ownership migrated; C-free hard flip in progress
- **Date**: 2026-07-15 (gap ledger updated 2026-08-11)
- **Owner**: `kotoba-lang/aiueos`
- **Language dependency**: `kotoba-lang/compiler` (code generation and
  freestanding ABI)
- **Imported from**: `kotoba-lang/kotoba` commit
  `bfcf31458ecc51d8a3e7f5896a32e719885f984b`
- **Related implementation**: `kotoba-lang/aiueos#29`, the reviewed replacement
  for PR #25; compiler PRs #42–#46; aiueos PRs #93–#95

## Context

aiueos currently names both a capability-secure component contract and an
intended machine OS. These are different maturity surfaces. PR #29 restores a
Linux-hosted initramfs/PID-1/QEMU path, portable virtio-blk/console logic, and
an experimental JVM FFM/VFIO provider. It is not a bare-metal kernel: Linux
still owns firmware handoff, PCI/IOMMU, interrupts, paging, scheduling, and
virtual memory. The VFIO provider is also not yet wired into aiueos's Wasm
host-import quartet; those imports remain deterministic stubs.

## Decision

### Ownership

`kotoba-lang/aiueos` owns the composition of the bootable product:

- boot profiles and release graph;
- firmware-to-kernel, kernel, syscall, and driver ABIs;
- ISO/raw-disk/initramfs composition;
- QEMU and real-machine evidence;
- aiueos, Kotoba, kototama, browser, and kotobase integration.

`kotoba-lang/compiler` owns genuinely freestanding targets:

- `x86_64-aiueos-kernel`, and `aarch64-aiueos-kernel-v1` (added 2026-07-17,
  compiler `e5e278a`: a bare-metal AArch64 kernel target — `.kotoba` →
  freestanding AArch64 ELF; first consumer is the ADR-0014 hvt-tender guest);
- `x86_64-aiueos-uefi`;
- PE/COFF and ELF emission;
- relocation, sections, entry point, stack, TLS, and no-host-runtime contracts.

`kotoba-lang/aiueos` also remains the authority for manifests, policy,
admission, audit/run receipts, component boot graphs, portable virtio protocol
logic, and hosted development profiles. Native and hosted profiles are two
evidence surfaces of one OS authority.

`kotoba-lang/kotoba` is the language apex. It may retain compiler integration
fixtures proving that freestanding Kotoba artifacts link and boot, but it does
not own the OS implementation or release graph. The dependency direction is:

```text
kotoba semantics -> compiler/runtime/freestanding ABI -> aiueos -> boot images
```

Libraries and products are separately versioned repositories in the
`kotoba-lang` organization. A west manifest pins and composes them; source is
not consolidated into `kotoba` as a product monorepo.

### Profiles

`hosted-linux` is Phase 0:

```text
firmware -> Linux -> initramfs -> JVM/aiueos PID 1
                              -> Chicory/Kotoba components
                              -> optional Linux VFIO provider
```

`bare-metal` is Phases 1–6:

```text
UEFI or BIOS/GRUB
  -> aiueos loader and native kernel
  -> ACPI/SMP/paging/APIC/IOMMU
  -> scheduler/virtual memory/syscalls
  -> PCI/MMIO/DMA/IRQ drivers
  -> kototama/Kotoba components
  -> browser shell + kotobase persistence
```

No hosted result satisfies a bare-metal release gate.

### C-free hard-flip release rule

The production `bare-metal` profile does not compile, link, load, or execute C.
It also does not depend on libc, a CRT, a JVM, Linux, a hosted supervisor, or a
prebuilt foreign object. Assembly encoded by the compiler is permitted only as
part of a named freestanding ABI; an independently assembled object is not.

Earlier native C/assembly work remains valuable as executable specification and
hardware-conformance evidence, but it is a reference profile, not cumulative
evidence that the C-free kernel already implements the same mechanism. A
mechanism moves to the production column only when all of these are true:

1. its executable implementation is Kotoba source or compiler-owned target
   emission;
2. its artifact receipt has empty `c_sources`, `foreign_objects`, `imports`, and
   `dynamic_dependencies`;
3. positive and fail-closed QEMU gates exercise the production boot chain; and
4. the compiler and aiueos merge commits are exact-pinned by west.

The current production chain is:

```text
OVMF/UEFI
  -> compiler-emitted PE32+ BOOTX64.EFI
  -> compiler-emitted ELF64 ET_EXEC aiueos kernel
  -> Kotoba main (ring 0)
```

The UEFI loader validates bounded `PT_LOAD` segments and entry containment,
allocates and copies the kernel, obtains the final memory map, retries
`ExitBootServices` with its current map key, and calls the kernel through the
versioned boot-info ABI. The compiler-generated kernel entry preserves the
SysV `rdi` boot-info pointer in its freestanding context. Kotoba obtains it with
the kernel-only `kernel-boot-info` intrinsic and validates:

- magic `AIUEBOOT` and ABI version 1;
- non-null memory-map pointer and nonzero byte length;
- descriptor size of at least 40 bytes; and
- nonzero UEFI descriptor version.

The kernel also reads CR3 and emits its QEMU success marker with privileged
port I/O. The resulting receipts contain no C sources, foreign objects, imports,
or dynamic dependencies. This proves firmware-to-Kotoba control transfer and a
usable final firmware memory-map view. It does not yet prove that the C-free
kernel allocates a physical page or owns its page tables.

### Required artifacts

| Artifact | Purpose |
|---|---|
| `BOOTX64.EFI` | primary UEFI loader |
| BIOS stage-1 sector | legacy boot test fixture |
| GRUB/Multiboot2 configuration | compatibility boot path |
| PE/COFF loader | UEFI-loadable compiler output |
| bootable ISO | VM/distribution image |
| GPT raw disk image | USB/QEMU/real-machine boot |
| kernel image | native aiueos kernel |
| `newc` initramfs/cpio | early components and recovery |

Each artifact is reproducible, hashed, signed, and accompanied by a build
receipt. A file-shaped placeholder does not count; successful QEMU boot is the
minimum evidence.

### Kernel scope

The native kernel must implement:

- firmware memory-map ingestion;
- ACPI RSDP/XSDT/MADT and CPU discovery;
- SMP application-processor startup;
- page tables, W^X, isolation, and guard pages;
- physical/virtual memory allocators;
- APIC, timer, exceptions, and interrupt dispatch;
- preemptive scheduler and address spaces;
- capability-handle tables;
- syscall entry/exit, validation, and copy-in/copy-out;
- PCI enumeration and BAR validation;
- MMIO, DMA, IOMMU, and IRQ providers;
- serial console, panic/crash receipt, and deterministic QEMU shutdown.

The first syscall ABI is capability-handle based. POSIX is an optional service,
not the kernel authority.

### Compiler and native-substrate rule

Policy, service, driver-protocol, and application code expressible in Kotoba is
compiled by `kotoba-lang/compiler`. The reference profile historically allowed
a small assembly/native substrate for reset entry, CPU mode transition,
page-table activation, interrupt stubs, and context switch. The production
hard-flip profile instead requires those instruction sequences to be emitted by
the compiler from a named target ABI, with no separately assembled or C object.

Every exception requires a named ABI, QEMU positive/negative tests, a compiler
migration issue, and no ambient authority above the capability boundary.
Hosted KEXE targets are not kernel targets. A target is freestanding only when
it has no supervisor, libc, JVM, or host syscall dependency.

The first native compiler boundary is `x86_64-aiueos-kernel-v1`. The compiler
emits an ELF64 little-endian `ET_REL`/`EM_X86_64` object and exports the SysV
function `uint64_t kotoba_aiueos_probe(void)`. The initial object is deliberately
closed: `.text`, `.data`, one `.rela.text` `R_X86_64_PC32` relocation to `.data`,
and the ELF string/symbol tables are the only sections; undefined symbols,
program headers, dynamic linkage, interpreters, and host imports are rejected
before link. The kernel calls the emitted function and requires result `42` as
boot evidence. This is the first Kotoba-generated vertical slice, not evidence
that the remaining C and assembly substrate has been replaced.

The next boundary exports
`uint64_t kotoba_aiueos_journal_plan(valid0, sequence0, valid1, sequence1)`.
Kotoba now owns selection of the latest valid journal commit, the monotonically
next sequence, and the alternate slot that preserves the rollback record. The
native substrate still owns record validation and bounded virtio-blk I/O; it
rejects an inconsistent Kotoba plan before replay or mutation. Multi-boot QEMU
tests cover initial append, committed redo, corrupt-latest fallback, and
rollback preservation.

The bounded-memory boundary is `kernel-load-u8(base, length, index)`. It is
available only to the aiueos kernel target and traps before access when the
base is null, length exceeds one disk sector (512 bytes), or the unsigned index
is outside that length. The first consumer is Kotoba FNV-1a, replacing the C
checksum loop for superblock, journal header/payload, transaction, and mutable
object validation. Firmware and device I/O remain outside this pure bounded
function.

Journal-record and object-transaction validation are also Kotoba-owned. Their
little-endian `u32` reader is expressed from four bounded byte loads, avoiding
unaligned native loads and hidden packed-structure authority. C retains the
physical record address and exact size but no longer decides journal magic,
version/state, transaction target/length, or checksum validity.

Superblock and mutable-object validation are Kotoba-owned as well. Superblock
object bounds are checked before deriving the bounded payload view. Mutable
objects are compared byte-for-byte with the committed transaction after magic,
version, sequence, length, and checksum agreement. The remaining C storage
boundary is queue/DMA I/O plus serialization of a newly committed record.

Write-side serialization is Kotoba-owned through
`kernel-store-u8(base,length,index,value)`, which applies the same null,
512-byte, and unsigned-index bounds as checked loads before mutation. Journal
metadata/payload/checksums and mutable-object materialization are emitted by
Kotoba builders. The native storage boundary is now sector clearing and
virtio-blk queue/DMA submission/readback.

PCI/virtio validation is entering the same boundary. Kotoba validates parsed
vendor capability shape, BAR extent power-of-two requirements, and rng/blk
MSI-X table/PBA containment. Native C retains config-space and MMIO access but
cannot map a derived capability region unless the Kotoba planner admits it.

Syscall pointer admission follows the same split. A Kotoba half-open range
planner validates non-empty bootstrap and user windows without overflow before
the native syscall dispatcher accepts a buffer. CPL3 enters through
STAR/LSTAR/FMASK-configured `SYSCALL`, switches to an allocator-owned per-task
kernel stack, validates canonical lower-half return RIP/RSP, and returns through
sanitized `SYSRETQ`; `int 0x80` remains DPL0-only for bootstrap tests. Kotoba then copies at most
256 bytes into kernel-owned storage using trapping bounded loads/stores and
produces the payload hash receipt. Native code still owns trap entry,
capability lookup, buffer lifetime, and page-fault recovery.

Capability identity is no longer a single hard-coded equality. Native storage
holds bounded slots, while a Kotoba planner derives the canonical handle from
slot, generation, type, active state, rights, owner domain, and the caller's
requested rights/domain. Revocation clears active state and increments
generation before reissue; CPL0 and CPL3 gates require foreign-owner plus
stale/type/rights failures without changing the copied payload.

### Driver, UI, and persistence split

```text
portable virtio planner
  -> admitted driver service
  -> kernel queue/MMIO/DMA/IRQ provider
  -> device
```

VFIO remains a hosted conformance provider. Bare metal owns PCI, IOMMU, and
interrupt setup.

`kotoba-lang/browser` supplies shell/window/workspace state, input vocabulary,
and retained draw operations. The native release additionally requires
framebuffer/virtio-gpu scanout, compositor, virtio-input/USB HID, keyboard/IME,
accessibility, and clipboard/file-picker permission brokers.

The first native output transport slice is intentionally narrower. The kernel
renders and hashes the actual OVMF GOP aperture, then emits a versioned surface
descriptor containing an opaque kernel handle, generation, pixel metadata, and
full-surface damage. Pixels cross the boundary only through a generation-checked,
rectangle-bounded copy into caller-owned memory; the physical address remains
hidden. A modern
`virtio-vga` controlq `GET_DISPLAY_INFO` request must complete with a bounded,
enabled scanout whose dimensions match that GOP surface. Together with the
existing desktop input envelope this establishes the browser desktop transport
ABI and real no-Linux QEMU device evidence. It does not yet create virtio-gpu
2D resources, attach backing, transfer/flush frames, run a compositor, or boot
the browser runtime.

`kotobase` is the datom persistence plane, not a block driver:

```text
virtio-blk/NVMe -> block service -> filesystem/object store
                -> kotobase IStore -> browser/profile/system datoms
```

### C-free status and remaining gap ledger

The following table is the baseline production maturity ledger. “Reference
exists” means the older native substrate demonstrates a design or QEMU
interaction but still must be re-expressed in Kotoba/compiler output. Its
Phase-2 cell is superseded by ADR-0039: the 2026-08-12 six-page path has an
activated W^X/guard map, a Kotoba-built vector-14 IDT, and independent CPU
fault receipts for guard write, RX write, and NX execute.

| Phase | C-free status | Remaining exit gate |
|---|---|---|
| 1 — compiler and UEFI boot | **Working:** direct ELF64 `ET_EXEC` kernel packaging; compiler-emitted PE32+ loader; bounded segment/entry admission; final UEFI memory-map boot-info; `ExitBootServices`; ring-0 Kotoba; CR3 and port-I/O evidence; reproducible no-foreign-code receipts | kernel/loader signature verification; Secure Boot key lifecycle; serial/panic receipt owned by the C-free kernel |
| 2 — CPU and memory | **Bounded five-page C-free paging slice working (2026-08-11):** the compiler-owned handoff keeps the final UEFI map in a bounded inline 16 KiB region; Kotoba derives it and walks variable-size descriptors under a 410-descriptor ceiling. It admits a contiguous five-page Conventional extent and derives five distinct zeroed 4,096-byte authorities from the named identity window. Page one stores a boot-lifetime five-slot bitmap, the next three own PML4/PDPT/PD, and page five proves release and reuse. Kotoba populates and validates all 512 2 MiB PDEs for a first-GiB identity map before loading the PML4 into CR3, reading CR3 back, executing `invlpg`, and continuing under the replacement tables. The positive path rejects duplicate claim and double-free before `MPRC`; real x86-64 KVM/OVMF gives `MPRC`/33. Mutations independently reject wrong ownership (`M`/45), a non-present PML4 link (`M`/47), and retaining the firmware CR3 (`M`/49); exhaustion (`M`/39) and overlap (`M`/41) remain separate. The compiler chain seals finite fuel 8192 and the verifier requires emitted CR3-read, CR3-write, and `invlpg` encodings. | general map-indexed ownership bitmap/free list and zones; dynamic mapping/unmapping; W^X/guard pages (the bootstrap identity map is currently RW+executable); full exception stubs and double-fault IST; ACPI validation; Local APIC/x2APIC and IOAPIC; timer/IRQ dispatch; AP trampoline, SMP startup, per-CPU GDT/TSS/stacks/state |
| 3 — kernel execution | Compiler has a freestanding context ABI. Reference implementations exist for preemption, CPL3, syscall/copy, address spaces, capability generations, IPC, and service lifecycle | Kotoba context switch; preemptive per-CPU scheduler; process/address-space isolation; ring 3; syscall entry/exit; bounded copy-in/out with fault recovery; capability handle table; arbitrary process/service creation; persistent service supervisor |
| 4 — hardware backend | Reference QEMU evidence exists for PCI discovery, BAR admission, virtio-blk MSI-X, VT-d translation/interrupt remapping, journaled storage, and initial virtio-gpu transport | Kotoba PCI config access and enumeration; validated BAR/MMIO provider; DMA allocator; VT-d/IOMMU per-device domains; MSI/MSI-X routing; production virtqueues; virtio-blk/net/gpu/input; NVMe and USB HID; real-machine evidence |
| 5 — boot and release | C-free UEFI artifacts and receipts exist. **Working (2026-07-16):** deterministic GPT raw disk and El Torito EFI (no-emulation) bootable ISO from one stdlib-only builder; both media carry the same `BOOTX64.EFI`/`KERNEL.ELF`, are structurally verified (GPT CRCs, FAT chains, volume descriptors, catalog checksum) with byte-for-byte artifact comparison, share one SHA-256 receipt, and each must pass the complete OVMF QEMU evidence gate; the verifier fail-closed rejects a one-byte kernel mutation inside the ISO and the recovery partition. The GPT disk carries a second independent FAT16 recovery ESP (byte-identical to the ISO boot image); QEMU gates prove the UEFI boot manager falls back to it and passes the full evidence gate when the primary loader fails `LoadImage`, and that the reference loader, after rejecting a corrupted primary kernel by its compiled-in SHA-256, admits the identical kernel from the recovery volume under the same digest requirement (explicit `AIUEOS_LOADER_RECOVERY_OK` marker, fail-closed when no volume passes). The protective MBR carries the legacy-BIOS stage-1 fixture: a 62-byte documented real-mode stub that prints `AIUEOS_BIOS_STUB uefi-required` and exits deterministically under SeaBIOS (halts without the test device), gated in the release smoke — BIOS remains a refused, not supported, boot path. `apply-update` implements the update flow: the new pair goes to the primary ESP only, the recovery partition must remain byte-identical, and an update receipt records previous/updated/recovery digests; QEMU gates prove the updated image boots the new version and that a corrupted update rolls back to the preserved previous version (versions distinguished by the self-test marker) — executable update and rollback receipts. Release-receipt signing is verifiable: a stdlib-only RSA-2048 PKCS#1 v1.5 SHA-256 verifier (public-key operation only, RSA-2048 enforced, fixed-work comparison) is CI-gated with an ephemeral key including tamper rejection; the production signing key stays offline. The kernel owns a durable crash receipt: a bounded record in a dedicated virtio-blk sector (magic, version, pending/consumed state, reason, journal sequence, Kotoba FNV checksum) with readback on write and consumption; a compile-gated synthetic panic persists it and terminates deterministically, and the next boot must consume and report it while still passing the complete evidence gate, both gated in the journal-recovery smoke. Fault-context capture works: the unexpected-exception dispatcher (a stray pre-probe `ud2` no longer masquerades as the success path) writes the same record over a try-lock, polled-completion transport with no interrupt dependence, skipping rather than corrupting a busy queue; a synthetic-fault QEMU gate proves the write and the next-boot consumption with the fault reason. A deterministic `newc` initramfs with early-component/recovery materials rides every medium as `INITRD.IMG`: loader volume admission requires its compiled-in SHA-256 alongside the kernel's, boot-info ABI v2 hands base/size to the kernel, and a bounded kernel parser (per-entry magic, hex fields, alignment, extents, entry cap, trailer) is QEMU-gated positively and with a corrupted-archive loader rejection. The recovery payload is admissible, not just carried: the kernel extracts the recovery ELF and signature into bounded buffers and admits them through the same Kotoba SHA-256 + RSA-2048 public-key policy as catalog applications, with a wrong-signature negative gate that the loader digest deliberately admits so the kernel policy layer must reject. Object-store restore works: an application failing digest/signature admission is rewritten from the initramfs recovery materials — only when the carried ELF hashes to the catalog's digest and its signature verifies under the same RSA policy — with per-sector write/readback and re-admission, QEMU-gated for payload and signature corruption while catalog corruption stays fail-closed. A Multiboot (v1) boot path works: a 32-bit trampoline (identity-map first GiB, PAE/LME/paging, long-mode far-jump) enables SSE (so -O2-vectorized byte loops do not #UD into a triple fault), hands a bounded Multiboot memory-map walk, firmware-independent ACPI discovery (signature + 20-byte checksum RSDP scan of the BIOS window with no UEFI config table, then a full table walk: the kernel ACPI parser now handles the ACPI 1.0 RSDT with 32-bit pointers alongside the 2.0 XSDT, sharing the MADT walk, CPU enumeration, and >=2-CPU/IOAPIC invariant), interrupt bring-up (minimal IDT plus the shared apic.c Local APIC periodic timer, waiting on a real vector-32 tick over a 4 GiB identity map that reaches the LAPIC MMIO), and the compiler-emitted Kotoba probe object to a 64-bit landing, gated through QEMU's own built-in Multiboot loader (no GRUB), with the linked x86_64 image wrapped verbatim in a 32-bit ELF container. The same kernel also carries a Multiboot2 header: grub-mkrescue builds a GRUB rescue ISO whose grub.cfg loads it with `multiboot2`, and an OVMF QEMU gate boots OVMF -> GRUB -> the kernel (32-bit entry, MB2 magic, MB2 memory-map tag walk, ACPI from an MB2 ACPI tag, Local APIC timer, a GRUB-provided linear framebuffer with a test-pattern readback, Kotoba probe) end to end at and beyond MB1-parity evidence | compiler-owned relocation/section coverage sufficient for the full kernel; recovery selection re-expressed in the compiler-emitted C-free loader; standing up the rest of the evidence gate (kernel-owned paging, virtio) on the Multiboot/GRUB path; production release-key ceremony and boot-receipt identity binding |
| 6 — OS and desktop | Capability/component contracts, browser desktop vocabulary, kototama/kotobase designs, and reference storage/GPU slices exist | native Kotoba component runtime; kototama integration; filesystem/object store and journal transaction plane; kotobase Datalog `IStore` persistence; compositor and virtio-gpu resources/scanout; browser shell as desktop UI; keyboard/IME/pointer/accessibility; permission broker; session restore |

Hosted named partial (ADR-0079, 2026-08-22): a JVM compositor process owns
`window-session-state` surfaces and QEMU lists `virtio-gpu-pci` under
`-display none`. Guest 2D create/flush on KERNEL.ELF is ADR-0084
(`kbb -M:compositor gpu`). Hosted WM (two stacked DADS-decorated
surfaces, z-order input) is ADR-0085 (`kbb -M:compositor wm`) and
still does **not** close this Phase 6 row: no IME, no native Kotoba
compositor, no guest-side WM. P5 real machine is UNVERIFIED. Remaining
still includes native Kotoba component runtime, IME/a11y, CertVerify,
CACAO write, permission broker, and physical boot.

Implementation order is dependency-driven:

```text
physical allocator -> dynamic paging -> exceptions/ACPI/APIC/SMP
  -> scheduler/address spaces/ring 3/syscalls/capabilities
  -> PCI/MMIO/DMA/IOMMU/MSI-X/virtio
  -> object store/kotobase + component services
  -> virtio-gpu/input + browser desktop
  -> signed ISO/GPT/recovery release and real-machine qualification
```

The immediate next gate starts where the activated first-GiB identity map stops:
replace the five-slot proof with a general map-indexed allocator and introduce
dynamic mapping/unmapping with explicit supervisor/RW/NX policy, W^X rejection,
guard pages, and deterministic failure paths in QEMU without adding a foreign
object.

Contract M6 does not imply kernel/hardware M6. Every subsystem records maturity
separately.

## Security invariants

- Firmware tables, descriptors, disk/package data, and binaries are hostile.
- DMA is disabled until IOMMU isolation, except in a named QEMU-only profile.
- Components receive revocable bounded handles, never physical addresses.
- Executable mappings are not writable after admission.
- Loader, kernel, policy, components, and filesystem identities are bound into
  one boot receipt.
- Secure Boot is not claimed until PE/COFF signing and key lifecycle are tested
  on real firmware.

## Consequences

- aiueos PR #29 is supported but classified as Linux-hosted Phase 0.
- The bootable product has one integration owner.
- The compiler must gain freestanding targets before claiming a Kotoba-compiled
  kernel.
- Native bootstrap code is constrained and auditable rather than hidden.
- Parity with macOS, Windows, or Linux is not claimed until Phase 6 passes on a
  real-machine class as well as QEMU.

## Reference native-substrate implementation record

This section records the older C/assembly-backed path. It is retained as a
porting specification and regression oracle. Unless a feature also appears as
working in the C-free ledger above, it is not part of the production hard-flip
kernel.

The Phase 1 vertical slice lives in `os/aiueos`. It builds a real PE32+ EFI
application and a separate static ELF64 kernel with a freestanding toolchain.
The loader reads the kernel from the ESP, validates bounded load segments and
its executable entry, captures the UEFI memory map, exits boot services, and
hands a versioned boot-info structure to the kernel. The kernel validates that
handoff, emits `AIUEOS_KERNEL_OK`, and uses a test-only I/O device for
deterministic shutdown. The assembly entry replaces the firmware stack with a
private 64 KiB stack, while the kernel initializes COM1 and emits independent
serial evidence. The guest contains no Linux, libc, JVM, initramfs, or hosted
supervisor.

This evidence proves firmware entry, PE/COFF packaging, a separate kernel
image, memory-map handoff, post-boot-services kernel execution, an owned kernel
stack, and COM1 output. It does not yet prove signature verification or any
complete Phase 2 kernel mechanism. The first Phase 2 slice replaces the
firmware GDT/IDT and proves exception dispatch by executing `ud2` and observing
the kernel's vector 6 handler; other exception stubs, paging, ACPI, APIC, and
SMP remain. The next slice installs a kernel-owned four-level bootstrap map,
sets CR0.WP and EFER.NXE, and separates text (RX), rodata (R+NX), and mutable
state (RW+NX). Vector 14 recovery verifies both a forbidden text write and a
forbidden instruction fetch from rodata, including the x86 error-code bits,
before the vector 6 regression probe runs.

The loader passes only the ACPI 2.0 RSDP selected by its UEFI GUID. The kernel
validates legacy and extended RSDP checksums, then applies bounded signature,
length, checksum, and subtable-walk checks to XSDT and MADT. The two-vCPU QEMU
gate requires at least two enabled Local APIC/x2APIC processor records. This is
discovery evidence, not SMP startup evidence.

The BSP Local APIC slice maps the xAPIC MMIO window cache-disabled, enables the
spurious vector, and programs a periodic timer on vector 32. The QEMU gate must
wake from `sti; hlt`, enter the kernel interrupt stub, issue EOI, and continue.
It does not yet route external interrupts or start application processors.

The external-interrupt slice retains the MADT IOAPIC and IRQ0 source override,
maps IOAPIC MMIO UC/NX, masks both legacy PICs, and routes the PIT through GSI
to vector 33. The smoke gate must wake through that external IRQ and issue a
Local APIC EOI. MSI/MSI-X routing remains separate.

The first C-free physical allocator consumes the variable-stride UEFI memory
map and admits only a contiguous five-page Conventional Memory extent above
the kernel image and below the current 1 GiB bootstrap identity limit. All
five page authorities are distinct and zeroed. Page one stores a bounded
five-slot ownership bitmap across allocator operations; pages two through four
hold PML4, PDPT, and PD; page five is released and reused. The three table pages
form a validated first-GiB identity map using 512 2 MiB leaves. The kernel loads
the PML4 into CR3, reads it back, invalidates one mapped address, and continues
execution under the replacement map.
The executable success path rejects both a duplicate claim and a double-free;
a QEMU mutation that reverses the free-state predicate must fail before the
`P` and `R` markers. Here "persistent" means boot-lifetime state, not durable
state across restart. A general map-indexed bitmap/free list, zones, allocation
above the bootstrap map, dynamic mapping, W^X, and guard pages remain. The
bootstrap identity leaves are RW and executable; table activation is therefore
not evidence of final page-permission policy.

The Phase 4 discovery slice performs a bounded PCI configuration mechanism #1
scan and requires a QEMU virtio function with vendor ID `0x1af4`. It does not
yet admit BARs, map device MMIO, allocate DMA, route MSI/MSI-X, or operate a
virtqueue.

The first storage slice uses a separately attached writable virtio-blk fixture,
isolated from the ESP and release disk. Sector 0 is an `aiuefs-v1` object-store
superblock: header size, object count, offset, length, and checksum are bounded
within one sector before an object is admitted. Sectors 1 and 2 are bounded
journal slots. Before mutation, the kernel validates both slots' magic, version,
nonzero sequence, committed state, payload bounds, and independent header and
payload checksums. Each payload describes one bounded sector-3 object mutation,
including target, version, length, checksum, and 16 object bytes. It selects the
highest valid sequence and replays that committed mutation idempotently before
appending its successor to the alternate slot. The successor journal record is
written and read back before the mutable object is written and read back, so a
reset between those operations is recovered as redo rather than an unjournaled
mutation. CI creates matching journal/object sequences 1 and 2, corrupts the
latest slot, then requires fallback to sequence 1, redo, and reconstruction of
sequence 2. This closes a one-commit rollback window and connects the journal
to a writable object, but is not yet an unbounded multi-record journal, object
allocator, filesystem, or kotobase IStore.

The block request queue is assigned MSI-X table entry 1 and architectural
vector 35 before `DRIVER_OK`. The kernel bounds the advertised vector count,
table and PBA byte ranges against probed BAR extents, maps only those validated
MMIO ranges, and rejects a queue vector assignment that the device does not
retain. Every sector operation waits in `sti; hlt` and is accepted only when
both a vector-35 IRQ and the matching used-ring element are observed. This is
real QEMU device-interrupt evidence; it is not a synthetic smoke event.
With VT-d active, the MSI-X entry uses remappable format rather than the
compatibility APIC address. The kernel requires `ECAP.IR`, installs a 256-entry
IR table through IRTA, and programs IRTE 1 with fixed physical delivery,
vector 35, and full requester-ID source validation for the discovered blk BDF.
It retains translation enable while issuing SIRTP/IRE and requires
`GSTS.IRTPS`, `GSTS.IRES`, and `GSTS.TES` before accepting completion. QEMU CI
enables `intel-iommu,intremap=on` explicitly; absence of the advertised
capability or failure to retain either enable state is fail-closed.

## Initial non-goals

The native service runtime owns eight descriptors, registers two stable service IDs, and requires their
generation and heartbeat state to survive timer-driven preemption and address-
space switches. A compiler-emitted Kotoba lifecycle planner emits spawn,
restart, and terminate actions and advances generation before the scheduler
allocates, replaces, or releases a generic descriptor-driven task context. A
bounded mailbox carries a scalar envelope across the two CR3 roots only after
the existing Kotoba capability planner admits the sender owner domain; the
foreign-domain negative path is required boot evidence. Once both services are
live, a compiler-emitted Kotoba serializer places their IDs, generations, and
restart counts into the existing journal-first object transaction. Recovery
replays that registry before the next append, feeds its validated lifecycle
states back into Kotoba-planned terminate/spawn, waits for restored heartbeats,
and only then admits user processes. The smoke verifies both a torn
materialization and latest-slot corruption against exact on-disk bytes.

- full POSIX/Linux ABI compatibility;
- every x86 chipset or GPU;
- BIOS as the primary production path;
- Windows/macOS binary compatibility;
- safety certification or hard real-time guarantees.
