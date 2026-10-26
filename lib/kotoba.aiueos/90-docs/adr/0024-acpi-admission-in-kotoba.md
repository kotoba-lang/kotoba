# ADR-0024 — ACPI table admission moves out of C

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0015 (the honest C boundary), ADR-0023 (PCI config in Kotoba)

## Context

The C is being removed a piece at a time. Surveying what remained: `acpi.c` was
the largest kernel file with **zero** decisions moved out — every checksum and
every bound still C — and it validates **firmware-supplied input the kernel
otherwise takes on trust**. Highest-value validation still on the unsafe side.

## Decision

Move the checksum and the table-header admission into Kotoba objects; leave the
walk, the dispatch and the pre-read bounds in C.

**Two objects, not one.** A kernel object exports a single symbol and cannot
call another (the verifier refuses undefined symbols outright), so folding the
checksum into the header check would mean a second verbatim copy of the walk —
under a fuel tier sized for "comparisons only", which is a size-dependent trap.
C composes the two verdicts in `valid_sdt`.

**Dispatch stays in C, deliberately.** The entry loop's `bytes_equal` decides
*which* table it is looking at, not whether it is acceptable. Folding that into
admission could only make a malformed table get **skipped** rather than
hard-fail — and a skipped DMAR leaves `discovered_dmar_drhd_count` at zero,
which is the input to `aiueos_dma_test_policy_allows_unisolated`. That would be
a silent security regression.

## Consequences

- **`AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2`** with the checksums and header
  admission decided by Kotoba, and `AIUEOS_SMP_OK cpus=2` downstream — a loud
  gate, since SMP bring-up reads the MADT this admits. Full boot exit 0
  alongside X25519, PCI, IPv4 and TCP.

- **The 8-bit accumulator is the whole point of the checksum.** C sums into a
  `uint8_t`; the sum wraps at 256. A wider accumulator silently *accepts* tables
  the spec rejects. The differential includes that case on purpose — bytes
  summing to exactly 256 pass under the wrapping accumulator and fail under a
  wide one — because it is the one error a careless port makes.

- **Two guards exist only because i64 is signed.** A `uint64_t` address at or
  above 2^63 arrives negative, and the clause that *looks* like a faithful
  transcription of `bounded_address` would admit precisely the addresses it
  excludes. Measured, not argued: the guard-less variant returns 1 for
  `0x8000000000000000`.

- **Three deliberate narrowings versus the C**, each named rather than absorbed:
  length 0 now fails closed (C was vacuously true); the ceiling is 16 KiB rather
  than C's 1 MiB, because the bounded-load primitives are 512/4096/16384 and
  there is no larger one; and the caller's length must now match the table's
  declared length, which the old code could not disagree about because it re-read
  the field. Nothing `acpi.c` walks is near 16 KiB — it never touches the DSDT.

- **Fuel is load-bearing with the step size.** `acpi-checksum-ok` sits in the
  4096 tier and costs `1 + floor(N/8) + (N mod 8) + 1`, worst case 2056 at
  N=16383 — counted from the disassembly, not estimated. That holds *only*
  because it walks eight bytes per recursive step; the natural one-byte shape
  costs N+2 and would trap on a 4 KiB table. Changing the step without changing
  the tier reintroduces a size-dependent `ud2`.

- Still C: `bounded_address`, the RSDP's 8-byte `"RSD PTR "` compare (these
  objects handle 4-byte SDT signatures), and the dispatch loop.
