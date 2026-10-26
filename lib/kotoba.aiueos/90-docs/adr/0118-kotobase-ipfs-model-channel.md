# ADR-0118: Kotobase/IPFS is the model source; USB is boot and recovery

Date: 2026-08-29
Status: accepted; decision plane implemented, physical adapters unverified

## Context

ADR-0117 proved that an exact Qwen3.8 artifact can cross the UEFI/kernel
boundary as three verified FAT32 files. That is a useful offline recovery
gate, but it is the wrong normal distribution path: models change frequently,
copying ten gigabytes onto every boot USB couples the OS release to one weight
revision, and an interrupted copy leaves no atomic current/previous choice.

Kotobase owns durable content-addressed storage. Murakumo owns compute,
scanning, promotion and inference; its repository/search rows are projections,
not the byte authority. AIUEOS owns local admission and activation.

## Decision

1. An AIUEOS channel revision is a canonical JSON raw-CID manifest plus raw
   CIDv1/sha2-256 blocks of at most 95 MiB. It may link the corresponding
   DAG-CBOR model-registry revision. Kotobase/IPFS is the canonical read
   authority.
2. A dedicated Ed25519 IPNS name is the mutable `latest` channel. AIUEOS
   accepts its record only after signature and validity verification, requires
   a monotonic sequence, refuses same-sequence/different-CID equivocation, and
   requires every new manifest to link the locally committed previous CID.
3. The device downloads only missing block CIDs into the inactive NVMe slot,
   verifies every raw CID and the whole GGUF SHA-256, then commits the head and
   active slot atomically. A failed check or interrupted download boots the
   last-known-good slot. A partial slot is never bootable.
4. The removable USB normally contains AIUEOS boot/recovery only. ADR-0117's
   split-volume bundle remains an explicit offline recovery path, not the
   default model supply.
5. Murakumo may index the immutable revision, scan it, promote it and execute
   it. It does not become the canonical storage origin by doing so.

## Evidence and gap

`aiueos.model-channel` implements the pure admission/update decision with
tests for missing-block reuse, rollback, equivocation, broken history,
compatibility, byte-shape failure and offline fallback. The Kotobase IPNS
publisher accepts explicit increasing sequence and validity instead of the old
hard-coded sequence 1.

This does not yet claim a K16 download. The native guest has a bounded QEMU
HTTPS/CID probe, while physical RTL8125 networking, an NVMe filesystem/cache
adapter, streaming 10.9 GiB reconstruction and real Qwen generation remain
separate measured gates.
