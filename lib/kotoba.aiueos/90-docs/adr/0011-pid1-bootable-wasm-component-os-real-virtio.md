# ADR-0011 — Restore PID-1-bootable aiueos as a wasm-component OS, with real virtio MMIO/DMA/PCI/IRQ, in CLJC/kotoba-wasm

- Status: accepted, Phase-0 in progress
- Date: 2026-07-09

## Context

ADR-0008 (accepted, 2026-06-27) got aiueos booting as PID 1 inside a Linux-kernel
`initramfs`/QEMU VM: `bin/aiueos.rs` detected `argv[0] == "init"` +
`/etc/aiueos/boot.edn`, `aiueos image build` staged a `cpio` initramfs, `aiueos vm
boot` drove QEMU. `src/virtio.rs` (4533 lines) implemented the *safe* virtio guest
protocol: transport handshake, feature negotiation, split-queue layout,
descriptor-chain validation, a DMA/IOMMU accounting model, and full virtio-blk +
virtio-console request planners with emulated/file-backed backends.

Commit `961dee4302` ("Remove Rust runtime from aiueos authority (#14)") retired
all of it. README.md now states plainly: aiueos no longer owns a Rust runtime
crate; Chicory (pure-JVM Wasm) replaced it for decision *and* execution, **except**
"real hardware access (the device-access quartet's raw MMIO/DMA/PCI/IRQ handling,
the retired `virtio.rs` driver, and VM/initramfs provisioning stay genuinely out of
scope)." `launcher.cljc`'s `dispatch` lists `image`/`vm` among the "adapter-only
six ... not wired here ... native provisioning." `kotoba-core-contracts`
(`resources/kotoba/runtime/capability_contract.edn`) still declares capability IDs
215-218 (`pci/config`, `dma/map`, `irq/subscribe`, `mmio/map`) as host-import ABI
names with deterministic stub bindings — the names exist, nothing backs them.

Three facts, gathered by re-reading the retired Rust (recovered via GitHub API —
this repo is shallow-cloned, so `git log`/`git show` locally cannot reach it;
`gh api repos/kotoba-lang/aiueos/contents/src/virtio.rs?ref=<pre-retirement-sha>`
can) and the superproject's own prior art, change the shape of this decision:

1. **~85% of `virtio.rs` is pure, portable protocol logic, not hardware access.**
   Feature negotiation, `split_queue_layout`/descriptor-chain validation, the
   `Iommu`/`DmaAllocator` accounting model, and the virtio-blk/console request
   planners are all generic over trait interfaces (`MmioRegisterIo`,
   `PciConfigIo`, `Iommu`, `VirtioIrqController`) and tested against in-memory
   fakes. Only two functions ever touched a raw pointer — `VolatileMmio::new`
   (register read/write on an *already-mapped* region) and
   `PciBarMapping::new` (BAR pointer arithmetic) — and even those assumed the
   mapping was obtained elsewhere. **The real MMIO/DMA/PCI/IRQ hardware-access
   layer was never actually built**, in Rust or since; `lib.rs`'s own docstring
   named it deferred. This is greenfield work, not a port, but the protocol
   logic that will *drive* it is a near-complete, mechanical port target.
2. **`bin/aiueos.rs`'s PID-1 mode was a placeholder.** `cmd_init` loaded
   `boot.edn`, called `up`, then `std::thread::park()`ed forever — no zombie
   reaping, no signal handling, no `reboot(2)`/poweroff. `image build` shelled
   out to `find | cpio -o -H newc | gzip -1`; `vm boot` shelled out to
   `qemu-system-aarch64 -machine virt,accel=hvf` (macOS/HVF-only). Restoring
   this is mostly re-authoring straightforward CLI/process-orchestration code
   in CLJC, plus doing the PID-1 responsibilities properly this time.
3. **The superproject already settled the surrounding architecture, unimplemented.**
   `90-docs/adr/2607022400-kototama-unikernel-tender-runtime-vocabulary.md`
   (accepted 2026-07-02) surveyed Solo5/Nanos/Unikraft/Mewz/seL4 and decided:
   `kototama = tender` (Solo5-style — a thin, deliberately non-sandboxed native
   mediator; `hvt` hardware-virtualized or `spt` seccomp-sandboxed), `aiueos`'s
   wasm components = `guest`. It explicitly **rejected** Unikraft/Mewz
   ("bake the wasm engine into the kernel image" — expands the TCB with
   wasmtime/Chicory's own bugs) and explicitly named the existing
   `mmio/map`/`dma/map`/`irq/subscribe`/`pci/config` capability names as
   *already* Solo5-tender-shaped: the guest declares logical devices, the
   tender is the only thing that touches hardware. It also states plainly:
   *"現状のkototamaはまだhost OS上で直接動く前提のまま"* — kototama running
   as an actual Solo5 `hvt`/`spt` tender is unstarted follow-up. This ADR is
   that follow-up, scoped to what's achievable without a from-scratch
   bare-metal boot stub (see Phase 1 below for why that's separate).

`kotoba-lang/kotoba`'s `.kotoba` compiler (`src/kotoba/runtime.clj`'s
`builtin-fns`) has no AOT/native/freestanding output — `kotoba wasm emit` always
targets a `.wasm` module hosted by `kotoba.wasm-exec` (JVM-only, Chicory). There
is no third, non-JVM/non-browser host anywhere in the monorepo. `builtin-fns`
also currently has **no bitwise operators** (`bit-and`/`bit-or`/`bit-xor`/
`bit-shift-left`/`bit-shift-right`) even though an earlier Rust safe-language
design (`docs/ADR-safe-capability-language.md`) had already modeled them as
safe-to-expose numeric ops — this is a small, concrete gap, not a design
question, and it blocks authoring virtio's flag/mask-heavy protocol logic
directly in `.kotoba` today.

## Decision

### Phase 0 (this ADR, in progress): PID-1 under a Linux-kernel guest VM, with an experimental VFIO provider

Keep Linux as the boot kernel and virtqueue-owning driver stack for the *guest
VM as a whole* (matching ADR-0008 — this is not the bare-metal microkernel
replacement, see Phase 1), but give the **aiueos tender process itself** direct,
real, raw access to a virtio-pci device's registers/DMA/IRQs from ordinary Linux
userspace, via **VFIO** (`vfio-pci`): bind the target virtio-pci device to the
`vfio-pci` kernel driver, then from the tender process `mmap` its BAR (via
`/dev/vfio/<group>` + `VFIO_DEVICE_GET_REGION_INFO`), program DMA mappings via
`VFIO_IOMMU_MAP_DMA`, and receive interrupts via `VFIO_DEVICE_SET_IRQS` + an
eventfd. This is the same technique DPDK/SPDK/QEMU's own vfio-pci passthrough
use, is real (not simulated) raw MMIO/DMA/PCI/IRQ access, requires no kernel
module of our own, and — critically — is fully reachable from JVM Clojure via
`java.lang.foreign` (the FFM API: `open`/`ioctl`/`mmap`/`close` against
`/dev/vfio/*`), so it stays "clj on clj," not Rust/C.

Architecture, mapping directly onto ADR-2607022400's already-accepted
tender/guest split:

```
VM firmware -> Linux kernel -> initramfs -> /init = aiueos tender (JVM/kototama, PID 1)
                                               |
                                               | VFIO ioctls/mmap (java.lang.foreign)
                                               v
                                       virtio-pci device (real registers/queues/IRQs)
                                               ^
                                               | mmio/map, dma/map, irq/subscribe, pci/config
                                               | (capability-gated host-import calls)
                                               |
                                       aiueos.virtio guest component
                                       (.kotoba -> kotoba wasm emit -> Chicory-hosted;
                                        ported from virtio.rs's pure protocol logic)
```

- **Tender** (`aiueos.pid1` + a new `aiueos.vfio` namespace, JVM-only, `:clj`):
  owns the VFIO file descriptors and does the actual privileged syscalls. Also
  owns real PID-1 responsibilities the old placeholder never had: reap zombies
  (libc `waitpid(-1, WNOHANG)` loop via FFM), handle `SIGTERM`/`SIGINT`
  (`sun.misc.Signal`, no native code needed), and power off/reboot via the
  Linux `reboot(2)` syscall via FFM (`LINUX_REBOOT_CMD_POWER_OFF`/`_RESTART`)
  instead of parking forever.
- **Guest** (`aiueos.virtio.cljc`, portable): the ~85% pure/portable slice of
  the retired `virtio.rs` — feature negotiation, split-queue layout,
  descriptor-chain validation, the DMA/IOMMU accounting model, virtio-blk and
  virtio-console request planners + backends — ported near-verbatim to CLJC
  pure functions/data (the old code was already trait-abstracted over register
  I/O, so this maps directly onto host-import calls instead of in-process
  trait dispatch). Authored as `.kotoba` where the language subset allows
  (compiled via `kotoba wasm emit`, executed as a Chicory-hosted guest
  component, capability-gated exactly like every other aiueos component per
  ADR-0002/0004 — no new policy machinery), falling back to plain `.cljc`
  hosted directly by the tender for any piece the `.kotoba` subset can't yet
  express (see prerequisite below). virtio-gpu request planning did not exist
  even in the old Rust (only the `DeviceType::Gpu` enum case) and is greenfield
  in this port, same as the VFIO binding itself.
- Capability manifests define how hardware access will be gated
  everything else: a component needs `:aiueos/imports #{:mmio/map :dma/map
  :irq/subscribe :pci/config}` and `:aiueos/requires #{:iommu}` granted by
  policy before the tender may hand it a live VFIO-backed handle. In this
  implementation `aiueos.vfio` is a provider primitive only: `aiueos.execute`
  still binds IDs 215-218 to deterministic stubs and no production path passes
  a VFIO handle to a Wasm component. Wiring that boundary and testing
  revocation/teardown is required before claiming a component-visible backend.
- `aiueos.image` (cpio `newc` initramfs builder + `boot.edn` generation) and
  `aiueos.vm` (QEMU invocation: kernel/initramfs/cmdline, `--block`/`--console`/
  `--graphics virtio-gpu` device flags) replace `launcher.cljc`'s two
  "not-wired" `:image`/`:vm` dispatch cases — a straightforward re-authoring of
  `bin/aiueos.rs`'s shell-out logic in Clojure (`clojure.java.shell`/
  `ProcessBuilder`), not a research problem.

**Prerequisite, tracked but not blocking**: `.kotoba`'s `builtin-fns` has no
bitwise operators today. Adding `bit-and`/`bit-or`/`bit-xor`/
`bit-shift-left`/`bit-shift-right` to `kotoba-lang/kotoba`'s
`src/kotoba/runtime.clj` `builtin-fns` (+ the matching wasm opcode emission in
`wasm_exec.clj`) is a small, contained follow-up in that repo — flags/masks in
virtio's feature bitsets and descriptor/status bytes need it. Until landed,
`aiueos.virtio.cljc`'s bit-manipulating pieces run as plain CLJC in the tender
process rather than as a compiled `.kotoba` guest component; they migrate to
the guest side once the language gains the ops.

**Verification for Phase 0**: `kbb -M:test` covers the ported pure
protocol logic (mirrors the old Rust unit tests against in-memory fakes) without
needing real hardware. End-to-end VFIO+QEMU verification needs a Linux guest
with IOMMU enabled and a `vfio-pci`-bound virtio device — a `bb robot:*`-style
smoke task (successor to the old `kbb -M:robot:block-smoke`/`console-smoke`)
exercises this against local QEMU (already installed) but is a separate,
heavier verification step from the unit-tested pure logic and is called out
explicitly rather than silently assumed passing.

### Phase 1 (future, explicitly out of scope here): true bare-metal unikernel, no Linux kernel

ADR-2607022400 already named this direction (`hvt` = hardware-virtualized
tender, no guest OS underneath at all — the tender itself is the first code
the hypervisor runs) and already flagged it as unstarted. It requires a minimal
native boot stub (CPU mode setup, memory map, hypervisor-guest trap handling)
below anything a wasm runtime or JVM can execute — no `.kotoba`/kotoba-wasm
toolchain today emits a freestanding/AOT-native binary capable of being that
first-executed code (confirmed: no AOT/native-image/no_std/bootloader/multiboot
support anywhere in `kotoba-lang/kotoba`). Closing that gap means either
adopting upstream Solo5's own `hvt` tender (an existing, minimal, already-public
C boot substrate — arguably legitimate under kototama's own "tender is the one
deliberately non-sandboxed native layer" framing, not a new Rust/C driver we'd
maintain) or a from-scratch boot stub, and is a separate, multi-week
project-scale ADR of its own — not attempted in this pass.

## Consequences

- (+) Restores the capability the user asked for — aiueos boots as PID 1 on a
  real VM (QEMU, already installed locally) — with **real**, not simulated,
  raw virtio MMIO/DMA/PCI/IRQ access, in CLJC/kotoba-wasm rather than Rust.
- (+) Directly executes the specific unstarted follow-up ADR-2607022400 named
  ("kototama actually running as a tender"), scoped to what's reachable without
  a bare-metal boot stub, rather than inventing a new architecture.
- (+) `kotoba-core-contracts`' capability IDs 215-218 already supply the policy
  vocabulary needed to wire the VFIO provider later; they remain deterministic
  stubs at the component execution boundary in this phase.
- (+) ~85% of the retired `virtio.rs` protocol logic is a near-mechanical port,
  not new design, because it was already trait-abstracted over register I/O.
- (−) Real MMIO/DMA/PCI/IRQ access (the VFIO binding) is greenfield in every
  language, not a port — it never existed even in the Rust era. Treat it as
  new, unverified systems code until it's actually exercised against a
  VFIO-bound device.
- (−) `.kotoba`'s missing bitwise builtins mean part of the virtio guest logic
  starts life as plain `.cljc` in the tender (not sandboxed) until that
  language gap is closed in `kotoba-lang/kotoba`.
- (−) A true bare-metal (no-Linux) unikernel remains unimplemented; Phase 0
  still depends on Linux for boot, scheduling, and owning the PCI bus/IOMMU
  setup that VFIO rides on top of.

## References

- `90-docs/adr/0008-bootable-image-and-virtio-guest-drivers.md` (superseded in
  part by this ADR: image/QEMU planning and virtio protocol logic are restored;
  an end-to-end VFIO-backed component path is not yet implemented).
- `com-junkawasaki/90-docs/adr/2607022400-kototama-unikernel-tender-runtime-vocabulary.md`
  (tender/guest split this ADR implements against).
- `resources/kotoba/runtime/capability_contract.edn` (capability IDs 215-218).
- Retired sources (recovered via GitHub API from commit
  `79ad05e91038f4942d6f41244ba707898c2ba4aa`, the parent of the removal commit
  `961dee4302`): `src/virtio.rs`, `src/bin/aiueos.rs`, `src/host.rs`,
  `src/backing.rs`, `src/lib.rs`.
- VFIO: Linux kernel `Documentation/driver-api/vfio.rst`.
