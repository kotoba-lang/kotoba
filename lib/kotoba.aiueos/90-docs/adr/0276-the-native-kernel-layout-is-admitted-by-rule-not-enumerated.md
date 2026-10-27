# ADR-0276 — The native kernel layout is admitted by rule, not enumerated; constants leave the code segment

Date: 2026-10-27

## Status

Proposed (design only). Nothing here is implemented. It records what was measured on 2026-10-27 while the W1 consent surface of
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

## Not decided here

The budget itself (which physical ranges), whether to retire `slot-version`, and whether the data segment is read-only RX-adjacent or its own
PT_LOAD. These are owner decisions of the packager and the layout contract (JUN-450).
