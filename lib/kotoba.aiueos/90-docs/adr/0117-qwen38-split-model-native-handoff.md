# ADR-0117: Qwen3.8 enters pure AIUEOS through a verified split-volume handoff

Date: 2026-08-29
Status: accepted; host and QEMU verified, physical K16 unverified

## Context

The exact Qwen3.8 27B GGUF is 10,934,860,704 bytes.  A FAT32 boot volume cannot
hold it as one file, the native kernel has no filesystem or NVMe model reader,
and replacing AIUEOS with Ubuntu would invalidate the requested native-OS
qualification.  A filename, a downloaded model, or a model shown on screen is
also not evidence that a token was generated.

The kernel's ordinary first-GiB identity map cannot expose the artifact.  A
huge-page mapping that rounds an arbitrary 4-KiB allocation outward would also
make adjacent firmware allocations part of the model mapping.

## Decision

1. The exact artifact is split into three FAT32-safe files of 4,000,000,000,
   4,000,000,000, and 2,934,860,704 bytes under `EFI/AIUEOS`.  Concatenation
   must reproduce SHA-256 `c0b7c303...f3eee`.
2. The AIUEOS UEFI loader searches its boot filesystem and then attached UEFI
   simple filesystems.  This allows PXE to carry the pure native EFI while a
   removable volume supplies weights.  It reads in bounded 16-MiB chunks,
   refuses length, trailing-byte, or SHA mismatch, and never writes an internal
   disk.
3. The loader reserves one contiguous LoaderData region between 4 and 64 GiB.
   It over-allocates by less than 2 MiB so the model mapping begins on an exact
   2-MiB boundary.  Padding stays reserved LoaderData; no unrelated allocation
   is covered by a model huge page.
4. Boot-info v4 passes the exact identity, raw load-cycle observation, and
   bounded low-memory page-table scratch to the kernel.  Production identity
   overrides are refused outside the explicit test-fixture build.
5. The kernel accepts GGUF magic and version 3, exact size/hash/part metadata,
   and maps only the admitted range as supervisor, read-only, and NX.  It shows
   the artifact identity while every inference metric remains `N/A`.

## Evidence and boundary

The host model validates the production 8--18 GiB mapping plan.  The QEMU gate
boots from three files and reaches the native read-only/NX handoff marker.  Its
negative variant changes one byte and proves the loader refuses it before
kernel entry.  The normal, model-disabled AIUEOS build remains a separate
passing configuration.

This does not yet prove that K16 firmware can supply the required contiguous
allocation, that the artifact is attached to the K16, or that Qwen produces a
token.  GGUF metadata/tensor parsing, tokenizer, Qwen operators, threaded SIMD,
and calibrated timing remain later gates.  Throughput is therefore `N/A`.
