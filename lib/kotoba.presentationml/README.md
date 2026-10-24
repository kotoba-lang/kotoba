# kotoba-lang/presentationml

EDN-first PresentationML/PPTX projection helpers.

This repo builds deterministic PresentationML package maps: slides,
presentation.xml, relationships, content types, theme, layout, and master
parts. ZIP writing is intentionally left to host adapters.

## Coverage matrix

This repo is the *deck-assembly* layer: it reads `ppt/presentation.xml` and
every other package-level/deck-level part, resolves `.rels`, and hands each
slide's own shape XML down to `kotoba-lang/drawingml` (see that repo's own
coverage matrix for per-shape/per-effect detail). The matching *writer* for
every row lives in `kotoba-lang/slides`.

| Area | Feature | Status | Notes |
|---|---|---|---|
| Package plumbing | Generic `.rels` reader (`relationships`) | ✅ | resolves `Target` to a package path via `resolve-target`, and captures `TargetMode` when explicitly present |
| Package plumbing | `TargetMode` capture | ✅ | added this session — without it, an internal same-deck hyperlink relationship was indistinguishable from an external one at this layer, the root cause of a real write-side bug fixed the same session |
| Package plumbing | Slide-size, theme colors, theme fonts | ✅ | |
| Package plumbing | Slide master / slide layout path + color-map override resolution | ✅ | |
| Package plumbing | Multiple masters, multiple layouts, per-slide master/layout ref | ✅ | |
| Background | Master background, incl. multi-stop gradient | ✅ | falls back through gradient → first-stop solid approximation → `bgRef` theme color |
| Background | Per-slide background override | ✅ | takes precedence over the master's for that one slide; shares the same reader as the master's own background |
| Slide-level metadata | Title derivation (first text shape, or fallback) | ✅ | |
| Slide-level metadata | Slide transition | ✅ | |
| Slide-level metadata | Speaker notes text | ✅ | reused via `notesSlide`'s own shape parsing rather than a bespoke reader |
| Deck-level metadata | Slide sections (`p14:sectionLst`) | ✅ | resolves `sldId` → 0-based slide position |
| Deck-level metadata | Handout master | ✅ | presence flag only (a print-layout template with no per-deck data to extract) |
| Deck-level metadata | Custom XML parts (`customXml/item*.xml` + `itemProps*.xml`) | ✅ | preserved as opaque raw XML strings, cross-referenced via the item's own `.rels` (works even for a self-closing `<a:tcPr/>`-style part with no paired closing tag) |
| Deck-level metadata | Embedded font declarations (`p:embeddedFontLst`) | ✅ read-only | reference-metadata only (typeface + rel-id + part path per style variant) — no font *bytes* are ever captured anywhere in this pipeline, so there's no write-side counterpart |
| Deck-level metadata | Legacy PowerPoint comments (`p:cmLst` + `commentAuthors.xml`) | ✅ | per-slide comments + shared, package-wide author table |
| Chart | Reference resolution (rel-id → chart part → embedded workbook part) | ✅ | the chart's own content (type/series/legend/axis) is out of scope here — see `drawingml`'s coverage matrix |
| Deferred subsystems | SmartArt / OLE / animations (`p:timing`) | ❌ out of scope | large independent subsystems, not started |

## Test

```bash
kbb -M:test
```
