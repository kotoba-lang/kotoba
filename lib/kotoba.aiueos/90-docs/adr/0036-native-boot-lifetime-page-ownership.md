# ADR-0036 — Native page ownership has to survive the next allocator operation

Date: 2026-08-11

## Status

Accepted and executable as a bounded boot-lifetime slice.

## Context

The first C-free allocator evidence selected two physical pages, kept the first
address in scalar control flow while finding the second, zeroed both, and
printed `MP`. That proved bounded UEFI-map traversal, non-overlap, and
zero-before-publish. It did not provide allocator state that a later claim or
release could consult. Calling the scalar exclusion "ownership" would repeat
the error that a name or comment establishes a runtime fact.

The immediate next paging dependency is also concrete: a four-level x86-64
page-table root needs its own zeroed physical page. Allocating it is separable
from populating it and loading it into CR3.

## Decision

The native kernel admits a contiguous three-page extent from one bounded UEFI
Conventional Memory descriptor. Requiring three pages is deliberately stricter
than a general allocator and keeps the current compiler ABI within its
five-argument function limit.

- page 0 is a three-byte boot-lifetime ownership bitmap in a zeroed 4 KiB page;
- page 1 is claimed as the zeroed future page-table root;
- page 2 is claimed, released, rejected on a second release, and claimed again.

`claim-slot` changes only zero to one and verifies the stored byte. A second
claim of the root slot must return false. `release-slot` changes only one to
zero and verifies the stored byte; a second release must return false. The
positive path reads all three final bits back as owned before publishing `MPR`.

This state persists across allocator calls during the boot. It is intentionally
not a disk-persistent structure and does not survive reboot.

## Executable evidence

The ELF verifier records three published pages, the boot-lifetime bitmap,
duplicate-claim and double-free rejection, reuse, and page-table-root
allocation. The normal KVM/OVMF run must emit `MPR` and debug-exit status 33.

`smoke-qemu-kotoba-native-owner-state.sh` mechanically reverses the one free
predicate in `claim-slot`. The mutated kernel must emit only `M` and exit with
status 45. Source occurrence checks make the mutation fail closed if the
implementation shape drifts. Existing full-map exhaustion and overlap
mutations remain separate failures.

## Consequences and next boundary

The scalar exclusion is gone, and release/reuse is now an observed state
transition. This remains a three-slot proof, not a production physical-memory
manager. ADR-0037 subsequently expands the bounded proof to five pages and
activates a first-GiB identity map. A map-indexed allocator and explicit
supervisor/RW/NX policy remain separate work.
