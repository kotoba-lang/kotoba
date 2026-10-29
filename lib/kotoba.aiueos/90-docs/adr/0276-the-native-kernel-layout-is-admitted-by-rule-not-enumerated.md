# ADR-0276 — The native kernel layout is admitted by rule, not enumerated; constants leave the code segment

Date: 2026-10-27

## Status

Accepted as a decision (owner delegation 2026-10-27: the recommendations below are adopted; see Decisions). **Partly implemented
(2026-10-29, checked against the code).** Step (a), the owned-region table: the compiler's definition is `seed/97-aiueos-desktop-regions.kotoba`
(kotoba-lang/amu#1653), the gates read one table (`scripts/native_regions.py`), and the desktop build refuses when the table, or
`native/layout-table.json` (page-table root and text cap per rung), differs from the compiler (kotoba#994); the layout table is still a repository file,
not emitted by the compiler. Step (b), the packager rule: kotoba-lang/amu#1666 (budget, overlap by address and by file offset, text up to the RW file offset
minus a page; ten single-clause negative controls in `check-aiueos-layout-rule-macos-native.py`; the 0x800000 rung is not yet reachable because no slot-version
defines it). Steps (c) the 0x800000 rung and (d) the read-only data segment (Part B) are **not implemented**; the desktop's RX is 1,505,664 bytes (71.8% of the
compiler's 2 MiB v3 text cap, measured 2026-10-29), so neither is blocking. The text below is the original design; Linear JUN-479 carries the evidence.
The implementation is in Amu (compiler and boot packager) and this repository's gates. It records what was measured on 2026-10-27 while the W1 consent surface of
ADR-0275 outgrew the kernel-v1 layout, and the two changes that remove that class of failure. Part A is owned by the Amu packager
and the JUN-450 layout contract and needs their owner's decision; Part B is a compiler change.

## What was measured

- The Amu boot packager (`kotoba-lang/amu` `seed/84-aiueos-boot.kotoba`) admits a kernel only if `eb-admit?` holds: ELF64 x86-64
  ET_EXEC, two PT_LOAD segments (RX then RW), entry inside RX, and `RX end <= RW start` by address. With RW at 0x200000 (kernel-v1)
  and RX at 0x101000 that is at most 1,044,480 code bytes. The desktop with the consent surface was 1,048,064 and was refused with
  `E7111`; the compiler has its own object limit (`E7104`, detail 1,052,637) just above it.
- The dual layouts add `eb-dual-layout?`: `slot-version` 2 (RW offset 1 MiB) or 3 (RW offset 2 MiB, vaddr 0x400000), with fixed
  payload and slot sizes (524,288 each). A larger kernel therefore needs a new enumerated layout, a compiler image that knows its
  target (the repository bootstrap compiler is v1-only), a new expected page-table root in the QEMU gate (v1 `context + 0x30000`,
  v3 `context + 0x130000`) and new pins.
- A character-per-arm `case` for UI text costs kernel code; one packed table already saved bytes. The desktop is about 1 MiB for
  little UI, so code density is part of the problem, not only the ceiling.
- Why the rule exists is sound: after the RX segment come fixed regions (data, the 512 KiB font, the 512 KiB slot, page tables, the
  Browser surface, DMA slots). A kernel that overran RX would corrupt them, so the packager refuses it. The defect is that the limit is
  a constant per enumerated layout, not that there is a limit.

## Part A — admit a layout by rule

Replace "slot-version N" with an admission rule over the ELF program headers and a declared region budget:

1. Every PT_LOAD lies inside the budget (a declared set of physical ranges), page aligned, and no two overlap, by file offset and by address.
2. No segment is writable and executable; the entry lies inside an executable segment; RW is not executable.
3. The fixed regions the image owns (page-table root, guard pages, the Browser surface and context, the font and slot payloads) are
   derived from the segment addresses by one table, not from per-layout constants, and each lies inside the budget and outside every segment.
4. Anything else is refused with the same `E7111`, naming the first violated clause.

The limit is then the budget, not a code size. The QEMU gates read the page-table root and the region offsets from the same table instead of keeping
their own `{0x200000: 0x30000, 0x400000: 0x130000}`. kernel-v1/v2/v3 stay admitted as three points of the rule, so existing evidence stays valid.

Negative controls (each must be refused): overlapping segments, RW+X, a misaligned segment, a segment past the budget, an entry in RW, a
fixed region inside a segment. Positive control: a kernel larger than 1,044,480 bytes that fits the budget.

## Part B — constants out of the code segment

Let Amu place constant data (strings, tables) in a read-only data segment instead of compiling it to compare, branch and immediate code
(today: the packed text in `browser_frame2.kotoba`, and the per-character `case` it replaced). Then the UI text can be a plain table again.
Measure code density on the desktop before and after (bytes of RX per UI line, with the same text as code and as data); inlining and
`case` branch chains are the suspects.

## Acceptance

- A: a kernel above today's ceiling and inside the budget is admitted, each negative control is refused, and the QEMU gate passes with no per-layout table.
- B: the same UI text is smaller as data than as code, measured, and the desktop gates still pass.
- Say in the closing note which of these is a source change, a built candidate, a QEMU result, merged, or deployed.

## Decisions (2026-10-27, owner delegated; recommendations adopted)

1. **Budget.** The kernel image region is physical `[0x100000, 0x1000000)` (15 MiB). A layout is admitted if all its segments and fixed regions lie inside it.
2. **Rungs, not slot-versions.** RW bases form a ladder: `0x200000` (kernel-v1), `0x400000` (kernel-v3), `0x800000`. No new `slot-version` is
   minted. kernel-v1/v2/v3 stay admitted, immutable, as named points so existing evidence stays valid. The driver selects the smallest rung whose
   RX room (`RW - 0x101000`) fits the measured text; the rung is the only thing that changes between builds.
3. **One owned-region table.** The fixed regions (page-table root, guard pages, Browser surface/context, font and slot payloads) are one table keyed by the rung,
   emitted by the compiler in its build state. Gates read it; they keep no per-layout map (today: `check-native-desktop-qemu.py` has
   `{0x200000: 0x30000, 0x400000: 0x130000}` for the page-table root).
4. **Read-only data.** Constants go in their own PT_LOAD, `R` only (never W or X), page aligned, directly after RX and inside the budget; the packager checks it like any other segment.
5. **Order of work.** (a) the table in the build state and gates reading it; (b) the packager rule with all negative controls; (c) the `0x800000` rung;
   (d) the read-only data segment and the removal of the packed-text workaround. Each step has its own acceptance (above) and is independent.

Why these: the budget is large enough for a desktop-class kernel yet small enough to keep the whole image under a few identity-mapped 2 MiB pages; a ladder keeps
the compiler's data addresses constants (no layout fix-point); and a table that the compiler emits cannot drift from the compiler.

## Not decided here (still open)

Whether the budget should later be derived from the firmware memory map instead of fixed; and how `0x800000` interacts with the DMA slots and the user domain pages (it must be
measured on the compiler's region seed before the rung is added).
