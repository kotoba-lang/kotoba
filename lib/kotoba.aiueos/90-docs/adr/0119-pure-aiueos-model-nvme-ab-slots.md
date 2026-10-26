# ADR-0119: Pure AIUEOS streams model updates into guarded NVMe A/B slots

Date: 2026-08-29
Status: accepted; UEFI/NVMe adapter implemented and QEMU-qualified, K16 write unverified

## Context

ADR-0117 loaded a split 10.9 GiB model into one contiguous allocation. That is
not a practical 16 GiB K16 update path. ADR-0118 selected immutable Kotobase
CID blocks and an IPNS head, but deliberately left the physical writer red.
An update must not overwrite the model the node can still boot, and the loader
must never interpret any convenient internal disk as its cache.

The K16 firmware already exposes NVMe namespaces through UEFI. Using that
mechanism before `ExitBootServices` keeps this slice pure AIUEOS: no Ubuntu,
Linux filesystem, init system or userspace downloader is introduced. It does
not claim a native post-handoff NVMe driver.

## Decision

1. AIUEOS writes only a non-removable, writable, logical UEFI Block I/O handle
   whose device path contains an NVMe namespace and whose first block is a
   valid `AIUEOS-MODEL-AB1` anchor. It does not format or discover a target by
   free space, position, size or disk model.
2. The partition has two selectors, two slot headers and two aligned equal-size
   data slots. Data is streamed into the inactive slot in bounded memory.
3. Activation order is data write, flush, full SHA-256 readback, slot-header
   write/readback, then alternate-selector write/readback. The old selector,
   header and data remain intact until the final selector is durable.
4. Boot selects the highest valid selector whose generation, slot, byte count
   and SHA-256 exactly match a valid slot header. A torn or corrupt newest
   selector falls back to the prior generation. Partial data has no selector
   and is not bootable.
5. Normal bytes will come from the admitted Kotobase/IPFS HTTPS channel. For
   this first physical qualification, the same exact three-file FAT32 bundle
   may be fetched directly by exact HTTPS byte ranges and streamed from
   removable USB. USB is a source, never the cache target. If no anchored
   model partition exists, the combined qualification records a deferred
   import and continues the direct-HTTPS test without an internal-disk write.

## Evidence and limits

`model_slots.c` passes a host state-machine gate that forces interruption at
selector commit and corruption of the newest selector. The QEMU gate boots the
real UEFI application against a QEMU NVMe namespace, imports generation 1 to
A, generation 2 to B without changing A, and refuses a corrupt generation 3
while generation 2 remains active.

The same QEMU gate also boots with no admitted target and proves the physical
qualification takes the explicit deferred branch before continuing, with no
Block I/O write target selected.

The ranged downloader is separately tested with a resumable prefix and exact
206 responses. It writes three FAT32-safe files directly and verifies the
reconstructed whole-artifact SHA-256; it never requires a 10.9 GiB staging
file that FAT32 cannot represent.

This is physical-adapter-shaped evidence, not a completed K16 disk write. The
K16 still needs a deliberately provisioned model partition, a physical boot,
and saved receipt. The existing RTL8125/TLS direct-HTTPS profile also remains
transport-only until certificate-chain and hostname admission are completed.
No Qwen runtime or generation speed follows from storing the artifact.
