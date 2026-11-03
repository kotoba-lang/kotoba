# ADR-0281 -- Kotoba object code gets its own read-only executable segment (JUN-556)

- Status: **implemented** (`os/aiueos/kernel/linker.ld`, `os/aiueos/kernel/paging.c`).
- Date: 2026-10-30
- Owner decision: 2026-10-30, "Third R+X segment". AGENTS.md offered two routes: move `.bss` scratch to `.high_bss`, or give the loader a third R+X segment for Kotoba text.

## Context

The default UEFI kernel had **272 bytes** left in the low region.

- `.bss` ended at 0x1e0ef0, against `ASSERT(aiueos_kernel_bss_end <= 0x1e1000)`.
- Replacing `kernel/tls_aes_gcm.c` with `kotoba/tls-aes-gcm.o` + `kotoba/bytes.o` adds about 5.9 KB of code over the C.
- That moved `.bss` 6,640 bytes past the limit (measured with the assert relaxed).
- Every later C-to-Kotoba move hits the same wall, because objects are larger than the C they replace.

## Decision

The `.text` of every Kotoba object linked from `os/aiueos/kotoba/*.o` goes into `.kotoba_text` at 0x600000, in its own PT_LOAD (R+X).

- The low `.text` rule excludes those input files (`EXCLUDE_FILE(*/kotoba/*.o)`).
- Only code moves. The objects' `.data` contexts, cells and `.bss` / `.high_bss` arrays stay where they were.

`kernel/paging.c` maps the window as one 2 MiB huge page:

- `page_directory[3]` (6..8 MiB) is present and executable, not writable.
- Process address spaces copy it with the other kernel directory entries.

The window is coarser than the low region's 4 KiB W^X pages, so the whole window belongs to the kernel image:

- `aiueos_kernel_end` is 0x800000, so the physical allocator never hands out a page inside a read-only executable mapping.
- The rest of the window is unused.

The boot validity check (`AIUEOS_PAGING_OK`) now also requires:

- `aiueos_kotoba_text_start == 0x600000`;
- `aiueos_kotoba_text_end <= 0x800000`;
- `aiueos_kernel_end == 0x800000`;
- `page_directory[3]` is present + huge, not writable, not NX.

The fatal handler reports a fault in Kotoba code as `rip-kotoba-text=` with the same `insn=` / `ud2=` fields.

An object linked from another path (an `AIUEOS_KOTOBA_*_OBJECT` override, or a copy under `$out`) still lands in the low `.text`. That is correct, just not budget-saving.

## Measured (default `build-uefi.sh`, 2026-10-30)

- `.kotoba_text` is 0x6ca2f bytes (444 KiB), so low `.text` shrinks from 0xc19cf to 0x56a5d.
- Low `.bss` ends at 0x175ef0: about 436 KiB of headroom instead of 272 bytes.
- `smoke-qemu-uefi.sh` (QEMU + OVMF, TCG) passes with `AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp`, `AIUEOS_AES_GCM_OK` and `AIUEOS_TLS13_RECORD_OK`.

## Not covered

- Other images built from this linker script (the PXE node and physical-qualification profiles) were not rebuilt or booted.
- `qualification/low-region-budget.edn` still records the old layout.
- Physical hardware: 6..8 MiB must be free conventional memory when the loader allocates it, as 4..6 MiB already had to be.
