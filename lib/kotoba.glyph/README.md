# kotoba-glyph

[![CI](https://github.com/kotoba-lang/glyph/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/glyph/actions/workflows/ci.yml)

**KAMI glyph — CPU-side SDF text-layout CONTRACT**, ported from `kami-text`
(Rust, SDF text rendering for wgpu). `kami-text` was deleted from
`kotoba-lang/kami-engine`'s working tree without being committed (still
fully recoverable from git history) as part of
[ADR-2607010930](../../../90-docs/adr/2607010930-clj-wgsl-migration.md)
Phase 4 ("restore the deleted-not-migrated crates as `kotoba-lang` CLJC
repos"). This repo gives it a CLJC home: `kami-text` is renamed `glyph`
here because `kotoba-lang/text` already exists as an unrelated
foundational stdlib repo.

Zero-dep, portable `.cljc`. No network, no GPU, no font parsing.

## What this is

The **pure, CPU-side layout/packing math** that decided *where* every
glyph goes — the part of `kami-text` that was genuinely portable, not
GPU- or font-library-bound:

- `kotoba.glyph.slot` — `FontSlot`/`GlyphKey` classification: CJK / emoji /
  combining-mark / RTL codepoint-range predicates.
- `kotoba.glyph.text` — codepoint-correct string utilities (`codepoint-seq`
  splits UTF-16 surrogate pairs back into one-codepoint units — most emoji
  are supplementary-plane codepoints, which a bare JVM/JS `char` cannot
  represent).
- `kotoba.glyph.segment` — grapheme clustering (base + combining marks +
  ZWJ sequences + variation selectors + regional-indicator flag pairs) and
  script/direction/font-slot run segmentation.
- `kotoba.glyph.atlas` — **uniform-grid** atlas rect packing for both the
  mono/SDF atlas and the color/emoji atlas (kami-text was never a general
  bin-packer — every cell is the same size, derived from `font-size`
  alone), plus a fully self-contained **procedural placeholder SDF atlas**
  (`ascii-procedural-atlas`, a box-distance-field needing no font backend
  at all).
- `kotoba.glyph.layout` — instanced-quad generation: glyph placement,
  advance accumulation, combining-mark cluster handling, line breaks, UV
  rect computation from atlas coordinates.
- `kotoba.glyph.dynamic` — capacity-bounded, LRU-evicted key-set
  management for a dynamically-growing atlas (mirrors
  `DynamicGlyphAtlas`/`DynamicColorGlyphAtlas`'s shared eviction loop).
- `kotoba.glyph` — thin facade re-exporting the above.

```clojure
(require '[kotoba.glyph :as glyph])

(def atlas (glyph/ascii-procedural-atlas 16.0))
(glyph/layout-text atlas "Hello" {:x 0.0 :y 0.0} [1 1 1 1] 1.0)
;; => [{:position [...] :uv-rect [...] :size [...] :color [1 1 1 1]} ...]

(glyph/graphemes "👨‍👩‍👧‍👦")      ;; => ["👨‍👩‍👧‍👦"]  (ZWJ family stays one cluster)
(glyph/segment-text-runs "Disk 日本語 Mix") ;; => runs split by script/font-slot
```

## Unported (host/platform-adapter concerns, on purpose)

The original `kami-text` mixed portable layout math with things that
genuinely need a native font/OS/GPU backend. Those stay out:

- **Real SDF rasterization from font outlines** — `ab_glyph`'s
  `outline_glyph(...).draw(...)` coverage rendering parses actual OpenType
  glyph outlines and rasterizes them into the SDF/AA buffer. This needs an
  OpenType/TrueType parser + outline rasterizer; `ascii-procedural-atlas`
  ports the *procedural placeholder* path instead (a pure box-SDF, which
  was itself a real, self-contained function in the Rust source — not a
  reduced stand-in).
- **OpenType shaping (rustybuzz/HarfBuzz, GPOS kerning)** — `FontManager`'s
  `shape_run` calls into `rustybuzz` (a HarfBuzz port) for real per-glyph-
  pair kerning and complex-script shaping. This ns ports the *unshaped
  fallback* layout path instead (`layout_text_shaped`'s no-manager
  branch): per-glyph advance/bearing accumulation with no font-shaper
  dependency — real production code in the original (used whenever a
  `FontManager` wasn't available), not a simplification invented for this
  port.
- **UAX#9 bidi visual reordering** — `unicode_bidi::BidiInfo` /
  `reorder_visual_text` implements the full Unicode Bidirectional
  Algorithm to visually reorder RTL/LTR runs before segmentation. This is
  a large, independent, table-driven algorithm (arguably itself a "host
  library" dependency, akin to a font shaper). `kotoba.glyph.segment`
  segments in **logical order** with correct per-run `:direction`
  classification, but does not reorder runs for RTL display — a caller
  that needs true bidi display order must reorder externally.
- **UAX#29 grapheme clustering** — `unicode-segmentation`'s `graphemes`
  implements the full table-driven Unicode extended-grapheme-cluster
  algorithm. `kotoba.glyph.segment/graphemes` is a practical approximation
  (combining marks, ZWJ sequences, variation selectors, regional-indicator
  flag pairs) covering the Latin/CJK/emoji cases kami-text's own tests
  exercised; it does not special-case e.g. Hangul jamo or Indic syllable
  clustering.
- **Native emoji color rasterization** (`macos_emoji_raster.m` +
  `build.rs`'s conditional Objective-C compile) — renders a real color
  emoji glyph via AppKit's `NSFont`/`NSBitmapImageRep` into RGBA pixels.
  Platform-specific by construction; `build.rs` itself does nothing but
  compile that one `.m` file behind `#[cfg(target_os = "macos")]`, wiring
  `AppKit`/`Foundation` — there is no cross-platform "font baking" build
  step to port. The atlas *packing* for emoji clusters
  (`pack-color-atlas`) is ported; the pixel-blit/procedural-fallback-color
  math that consumed the native raster (`blit_color_glyph_rgba`,
  `procedural_color_glyph_rgba`, `color_bounds`) is not — it operates on
  already-rasterized bytes from that native call and is lower-priority
  "visual fallback" rendering, not text layout.
- **Bundled font files** (`fonts/NotoSansJP-Regular.otf`,
  `fonts/Poppins-Regular.ttf`) — binary assets, not portable source; a
  real deployment picks its own font files for whatever font backend
  implements the rasterization/shaping steps above.

## Constants

Every packing ratio, capacity floor, pinned-entry set, and codepoint range
used above lives in `resources/kotoba/glyph/constants.edn`
(`kotoba.glyph.constants/defaults`) with a comment naming the exact Rust
symbol it mirrors.

## Maturity

| | |
|---|---|
| Role | capability (CPU-side text-layout contract) |
| Source | recovered from `kotoba-lang/kami-engine` git history (`kami-text`, uncommitted deletion) |
| Rasterization / shaping / bidi-reorder | not ported — host/platform adapter concern (see `Unported`) |
| Tests | parity tests against the original Rust `#[test]` suite where the ported subset overlaps |

## License

Apache License 2.0.
