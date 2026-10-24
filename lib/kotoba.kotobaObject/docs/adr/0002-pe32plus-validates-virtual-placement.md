# ADR-0002: `encode-image` validates virtual placement, not only file offsets

- Status: accepted
- Date: 2026-09-02

## Context

`encode-image` validated raw file offsets in three ways -- sections do not
overlap in the file, each `:raw-size` is the canonical alignment of its byte
count, and no section starts inside the headers it just wrote. It did not look
at `:rva`, `:virtual-size`, or `:image-size` at all.

That is the half of the layout the loader actually uses. A caller that froze
its RVAs produced a file every one of those checks passed and every byte of
which is present, whose second section is nevertheless mapped over the tail of
the first. Measured 2026-09-02: amu's `package-efi` froze `.text` at RVA
0x1000 and `.data` at 0x2000, so a Kotoba UEFI application whose `.text` grew
past one page was packaged without complaint and corrupted itself at run time.
`package-embedded-kernel` in the same namespace derives its addresses from the
real text size and was never affected -- which is exactly why the defect was
invisible: the repository that owns the container had no opinion, and one of
the two callers happened to be right.

## Decision

`encode-image` additionally validates, before it encodes anything:

- every `:rva` is a multiple of `:section-alignment`;
- no `:rva` is below the mapped headers (`align-up headers-size
  section-alignment`);
- no two sections' mapped spans overlap, where a span is `:virtual-size`
  rounded UP to `:section-alignment` -- the granularity at which pages are
  assigned. Rounding down would admit the overlap this exists to refuse;
- `:image-size` covers every span, and is itself section-aligned.

The reason literals are `"PE section virtual address is not section-aligned"`,
`"PE section virtual address overlaps the headers"`, `"overlapping PE virtual
sections"`, `"PE image size does not cover its sections"` and `"PE image size
is not section-aligned"`. `kotoba.object.pe32plus-test` pins all five plus an
unchanged two-section baseline, so a check that stops discriminating shows up
as a message mismatch rather than as a green run.

## Consequences

- Section placement stays a caller decision, as ADR-0001 requires. This
  repository refuses placements that no PE loader can honour; it does not
  choose them.
- A caller with frozen RVAs now fails at build time. `package-efi` is such a
  caller and is fixed in the same change set.
- Rounding the span up means a caller may not pack two sections into one page
  even when their virtual sizes would fit. No caller does, and a PE loader
  could not honour it if one tried.
