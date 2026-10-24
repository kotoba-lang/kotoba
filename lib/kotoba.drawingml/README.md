# kotoba-lang/drawingml

EDN-first DrawingML substrate.

This is a small XML builder layer for common DrawingML shapes, transforms,
fills, lines, text bodies, and tables. Higher-level PPTX package projection
lives in `kotoba-lang/presentationml`.

## Coverage matrix

This repo is the DrawingML *reader* (`src/drawingml/parse.cljk`) — one
element/effect at a time, string-matched against real `<p:sp>`/`<p:pic>`/
`<p:graphicFrame>`/`<p:cxnSp>` XML, no schema-driven codegen. The matching
*writer* for each row lives in `kotoba-lang/slides` (see that repo's own
coverage matrix); "✅ read+write" below means both sides exist and are
round-trip tested end to end.

| Area | Feature | Status | Notes |
|---|---|---|---|
| Geometry & transform | Position/size/rotation/flip (`xfrm`) | ✅ read+write | including nested-group transform composition |
| Geometry & transform | Placeholder geometry inheritance (layout → slide) | ✅ read+write | |
| Geometry & transform | Preset geometry (`prstGeom`) | ✅ read+write | |
| Geometry & transform | Custom geometry (`custGeom` path data) | ✅ read+write | raw path commands preserved verbatim, not re-derived |
| Geometry & transform | Shape adjustment values (`avLst`/`gd`) | ✅ read+write | raw `fmla` strings preserved verbatim |
| Fill | Solid fill (incl. theme color resolution) | ✅ read+write | |
| Fill | Multi-stop gradient fill (shape + master background) | ✅ read+write | angle + full stop list, not just a first-stop approximation |
| Fill | Pattern fill | ⚠️ read-only approximation | resolves to its foreground color; not re-emitted as a real pattern on write |
| Fill | Picture fill (`blipFill` on a non-`<p:pic>` shape) | ✅ read+write | rel-id + resolved part path |
| Fill | Picture crop (`srcRect`) | ✅ read+write | shared by `<p:pic>` and picture-filled shapes |
| Fill | Picture recolor (grayscale + alpha modulation) | ✅ read+write | `<a:grayscl>`/`<a:alphaModFix>` |
| Line | Color/width/dash/cap/join | ✅ read+write | |
| Effects | Shadow | ✅ read+write | |
| Effects | Glow | ✅ read+write | combined into one `<a:effectLst>` alongside shadow/reflection per schema |
| Effects | Reflection | ✅ read+write | |
| Effects | 3D/bevel (`sp3d`) | ❌ not implemented | |
| Media | Image reference (`<p:pic>`'s own blip) | ✅ read+write | reference-metadata only (rel-id + part path), not raw bytes |
| Media | Video/audio reference | ✅ read+write | reference-metadata only |
| Media | Video/audio playback options (loop/rewind/volume) | ❌ not implemented | |
| Media | Picture lock flags (`picLocks`: noChangeAspect/noMove/noResize/noRot) | ✅ read+write | fixed a real bug this session — the writer previously hardcoded `noChangeAspect="1"` regardless of the source picture's actual lock state |
| Text | Paragraph align/level/margin-left/line-spacing | ✅ read+write | |
| Text | Paragraph right-to-left direction (`rtl`) | ✅ read + full regen write only | added this session — full-regen only, matching every other paragraph-level property (align/bullet/level/margin-left/tab-stops): the `update` patch path always copies a paragraph's own `<a:pPr>` through untouched by design, so paragraph-level properties aren't independently patchable |
| Text | Bullets: char/none/auto-numbered incl. `startAt` | ✅ read+write | |
| Text | Tab stops (`tabLst`) | ✅ read+write | |
| Text | Text body autofit/wrap/anchor/margins | ✅ read+write | |
| Text | Vertical text direction (`vert`: East Asian/WordArt-stacked/Mongolian) | ✅ read+write | |
| Text | Run formatting (bold/italic/underline/strikethrough/baseline) | ✅ read+write | |
| Text | Highlight color (`<a:highlight>`) + character spacing (`spc`) | ✅ read+write | added this session — highlight resolves `srgbClr`/`schemeClr` the same as any other color (`first-color`, scoped to the run's own `<a:rPr>` block); character spacing converts OOXML's raw hundredths-of-a-point `spc` to plain points |
| Text | Underline style beyond single (`dbl`/`heavy`/`wavy`/etc) + underline's own color (`<a:uFill>`) | ✅ read+write | added this session — `underline-style`/`underline-color`; a plain `u="sng"` underline (the overwhelming common case) gets neither key, unchanged round-trip |
| Text | Run language (CJK heuristic) | ✅ read+write | |
| Text | Hyperlink: external URL | ✅ read+write | gated on the relationship's own `TargetMode="External"` |
| Text | Hyperlink: internal same-deck slide jump | ✅ read+write | reference-metadata only (target slide's own part path); fixed a real bug this session where this case was misclassified/written as a broken external relationship |
| Text | Hyperlink: built-in navigation action (`ppaction://...`) | ✅ read+write | Next/Previous/First/Last-slide/end-show — a self-contained hyperlink with no relationship at all |
| Table | Cell text, merge (`gridSpan`/`rowSpan`/`hMerge`/`vMerge`), per-cell fill | ✅ read+write | |
| Table | Cell borders (straight: L/R/T/B + diagonal: TL-BR/BL-TR) | ✅ read+write | each side's own `:dash` (`<a:prstDash>`, same value set as shape/connector line-dash) added this session — previously only width/color were captured, so a dashed cell border round-tripped as solid |
| Table | Cell margins + vertical anchor | ✅ read+write | |
| Table | Cell text rotation (`vert` on `<a:tcPr>`) | ✅ read+write | distinct attribute from `<a:bodyPr>`'s own `vert` (shape-level); shares the same value set/keyword mapping |
| Table | Table style flags (firstRow/lastRow/firstCol/lastCol/bandRow/bandCol) | ✅ read+write | fixed a real bug this session — the writer previously hardcoded firstRow+bandRow regardless of source |
| Table | Column widths / row heights (`gridCol`/`tr` dimensions) | ✅ read+write | nil when every column/row is the same size (this writer's own even-division default), so an unmodified table round-trips without a redundant dimension list |
| Chart | Rel-id + chart part + embedded workbook part | ✅ read+write | reference-metadata only |
| Chart/Table | Graphic frame lock flags (`graphicFrameLocks`: noGrp/noDrilldown/noSelect/noChangeAspect/noMove/noResize) | ✅ read+write | fixed a real bug this session — the writer previously hardcoded `noGrp="1"` regardless of the source table/chart's actual lock state; sibling of the `picLocks`/`spLocks` fixes |
| Chart | Chart type, series data, legend, axis titles, data labels | ❌ out of scope for this repo | the chart's own XML (`c:chartSpace`) is parsed nowhere in this package; `slides` writes chart content directly (type/series/legend/axis-titles) with no round-trip reader anywhere |
| Connector | Geometry/line | ✅ read+write | |
| Connector | Shape-to-shape connections (`stCxn`/`endCxn`) | ✅ read+write | |
| Shape flags | Hidden (`cNvPr hidden="1"`) | ✅ read+write | |
| Shape flags | Lock flags (`spLocks`: noGrp/noRot/noChangeAspect/noMove/noResize/noSelect) | ✅ read+write | fixed a real bug this session — the writer previously emitted a bare `<p:cNvSpPr/>` with no lock element at all regardless of the source shape's actual lock state; sibling of the `picLocks` fix above |
| Deferred subsystems | SmartArt (`p:dgm`) | ❌ out of scope | large independent subsystem, not started |
| Deferred subsystems | OLE embedded objects | ❌ out of scope | large independent subsystem, not started |
| Deferred subsystems | Animations (`p:timing`) | ❌ out of scope | large independent subsystem, not started |

## Test

```bash
kbb -M:test
```
