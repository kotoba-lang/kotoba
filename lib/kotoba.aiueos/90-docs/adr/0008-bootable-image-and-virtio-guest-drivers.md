# ADR-0008 — Bootable aiueos image path and virtio guest drivers

- Status: accepted, Phase-0 image path implemented
- Date: 2026-06-27

## Context

`aiueos vm up` originally used a Linux distribution VM as a convenient wrapper:
boot Ubuntu, mount this checkout, then run `cargo run -- aiueos up ...`. That is
useful for development, but it is not aiueos behaving as the guest OS.

The next practical boot target is:

```text
VM firmware
  -> Linux kernel
     -> initramfs
        -> /init = aiueos
           -> aiueos broker/runtime
              -> Wasm components
```

This still uses the Linux kernel as the booting kernel and virtio driver provider,
but it removes the distribution rootfs/userspace. aiueos is PID 1.

## Decision

Add two CLI surfaces:

- `aiueos image build <system>.edn --aiueos-bin <linux-bin>` builds a `newc`
  initramfs (`.cpio.gz`) containing `/init`, `/etc/aiueos/boot.edn`, and the
  system graph directory.
- `aiueos vm boot <system>.edn --kernel Image --aiueos-bin <linux-bin>` builds
  that initramfs when needed and boots it with QEMU using `rdinit=/init`.
- `aiueos vm boot ... --graphics virtio-gpu [--display cocoa]` exposes a
  virtio-gpu device in the QEMU boot plan. This is a device exposure path for the
  boot image, not an aiueos-native virtqueue driver yet.
- `aiueos vm boot ... --block block.raw` exposes a raw file as
  `virtio-blk-pci` in the QEMU boot plan, matching the file-backed block backend
  used by the safe virtio-blk provider core.
- `aiueos vm boot ... --console virtio-console [--console-socket path]` exposes
  a `virtio-serial-pci` device and named `virtconsole` socket while preserving
  the PL011 boot console for deterministic early logs.
- `kbb -M:robot:block-smoke` builds the robot initramfs, creates a default raw block
  image when absent, boots with `--block`, waits for PID 1 idle, and stops QEMU.
- `kbb -M:robot:console-smoke` boots the same image with the additional
  `virtio-console` device and stops QEMU after PID 1 idle.

The `/init` process is the aiueos binary itself. When `argv[0]` is `init` and
`/etc/aiueos/boot.edn` exists, the CLI enters PID-1 mode and calls the same
`up` path as the host CLI.

## Virtio guest driver stance

Phase-0 now implements the safe virtio core logic in `src/virtio.rs`: transport
status handshake, feature negotiation, queue-size validation, feature-aware
descriptor-chain validation, split-queue memory layout calculation, and
available/used ring slot accounting. It also defines the virtio-mmio register
I/O boundary, a bounded volatile MMIO accessor for already-mapped device
windows, and safe MMIO transport adapter for header validation, feature
selection, queue address programming, queue notification, and interrupt status
decode/ack.
Descriptor buffers and queue memory are checked against a directional DMA map
before programming the device. The core also includes a virtio-blk request
planner: read/write requests are encoded as three-descriptor chains with
directional DMA validation and status decoding. The virtio-blk service core now
submits read/write request heads through the available ring, tracks pending
descriptor heads, and completes used-ring entries after decoding the device
status byte. The component-facing provider adapter materializes requests through
a backend boundary, submits only after backend success, notifies the queue, and
polls decoded completions. A synchronous emulated block backend exercises the
same provider/backend contract against real guest-memory bytes and sector
storage for read/write E2E coverage; a file-backed backend presents a regular
host file as a sector-addressed block device for host/VM smoke paths. Virtio PCI
vendor capabilities are modeled and resolved into common/notify/ISR/device
regions with notify offset validation; PCI config-space capability lists are
walked and parsed into that model. Kernel-provided BAR mappings are checked
against those regions before volatile MMIO slices are produced. It also defines
the allocator-facing DMA allocation shape and IOMMU programming boundary,
validates those DMA windows, and rolls mappings back if programming fails. A
checked IOMMU backend enforces aperture bounds, overlap rejection, active
mapping introspection, and exact unmap matching. A deterministic DMA aperture
allocator can allocate and program split-queue backing memory through that
boundary. IRQ lines can be subscribed through an interrupt-controller boundary;
a checked IRQ backend rejects duplicate lines and delivers only subscribed
interrupt sources into provider event sinks. Pending virtio interrupt status can
be taken and acknowledged before delivery.

The virtio-console core now plans one-descriptor receive/transmit buffers,
validates their DMA direction (`console/read` as device-write RX,
`console/write` as device-read TX), submits descriptor heads through an
available ring, tracks pending completions from the used ring, and has an
emulated backend that moves bytes between guest memory and deterministic
input/output queues. It does not yet include host-specific hardware IOMMU/IRQ
adapters or VM MMIO-backed block/console-device backends.

For the bootable image path:

- `virtio-console` is exposed as an additional `virtio-serial-pci`/`virtconsole`
  device on request. The Linux PL011 path (`console=ttyAMA0`) remains the boot
  console; the safe aiueos-native console provider core is implemented, while
  the VM MMIO/PCI adapter that binds the live virtqueue is still a later step.
- `virtio-blk` is not required for the first image because the system graph is
  embedded in initramfs.
- `virtio-net` is intentionally absent from the first image; network authority
  must enter through an explicit aiueos capability/provider, not ambient guest
  networking.
- `virtio-gpu` can be requested in the QEMU plan with `--graphics virtio-gpu`;
  Linux owns the early scanout until aiueos has a native virtio-gpu provider.

The aiueos-native driver design remains capability-shaped:

| guest device | aiueos capability/provider |
|---|---|
| virtio-console | `console/read`, `console/write`, later mapped into `log/write` and audit streaming |
| virtio-blk | `block/read`, `block/write`, mounted only for components with storage caps |
| virtio-net | `net/fetch` / packet-level provider, denied by default |
| virtio-gpu | `framebuffer/present`, later backed by native scanout |

Each provider must be broker-mediated, audited, and target-aware like the current
host ABI. No device is ambient just because the VM exposes it.

The shared native-driver path is:

```text
MMIO/PCI adapter -> virtio status/features handshake -> virtqueue validation
  -> capability provider (`block/read`, `framebuffer/present`, `input/event`, ...)
```

The safe queue, MMIO transport, IRQ status/ack and delivery boundary, DMA
validation, IOMMU programming boundary, checked IOMMU/IRQ backends, virtio-blk
provider core, and emulated/file-backed read/write block backends are
implemented today, including the small volatile MMIO register accessor boundary,
PCI config-space traversal, and PCI capability region resolver. The remaining
kernel-facing work is host-specific hardware IOMMU/IRQ adapters and a VM
MMIO-backed block-device backend.

## Consequences

- Ubuntu rootfs is no longer required for the boot image path.
- The image can boot with only a kernel, initramfs, and embedded aiueos system.
- This is still not the final aiueos microkernel: Linux currently supplies early
  boot, scheduling, memory management, and low-level virtio register/IRQ handling.
- A future aiueos microkernel can replace the Linux kernel without changing the
  system graph or component capability contract.
