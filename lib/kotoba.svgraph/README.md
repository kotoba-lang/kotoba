# svgraph

[![CI](https://github.com/com-junkawasaki/svgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/com-junkawasaki/svgraph/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`@com-junkawasaki/svgraph` is the TypeScript browser and npm package for SVGraph SVG presentation IR conversion. It runs in the browser or Node, powers the GitHub Pages editor, and emits DrawingML fragments, PresentationML/PPTX packages, SVGraph JSON, and coverage diagnostics without a Python runtime.

It targets the practical subset needed for generated Office graphics and simple round-trips:

- SVG: `rect`, `circle`, `ellipse`, `line`, `polygon`, `polyline`, linear/quadratic/cubic/arc `path`, simple rect/text, line/text, single-row/column rect grids, rect-background/line-border grids, and simple `foreignObject` HTML tables with editable captions, basic `colgroup` widths, row/column/table background layers, row heights, `colspan`/`rowspan` merges plus inherited, selector, shorthand, presentation attributes, header defaults, text alignment/direction, dashed/dotted/double cell borders, cell padding, line break, and inline text run style/decoration handling as native DrawingML tables, `text`, simple `tspan`, link/group containers, and basic `switch` fallback selection
- DrawingML: preset geometry shapes including common polygon, arrow, symbol, and flowchart presets, custom geometry paths including line/quadratic/cubic segments with closed path point preservation, shape style fill/line/font reference fallback, connector style line reference fallback, line arrowhead import as SVG markers, shape paint fallback for text fill/outline, native table cells, simple merged cells, browser cell fill alpha, text insets/anchors/direction/no-wrap/list-style alignment/default run fill/outline/underline/baseline threshold detail and rich text runs, and individual table cell borders with line paint/cap/dash/join/miter/alpha under `p:graphicFrame` as editable SVG rectangles/lines/text, and text boxes under `p:sp`, with invalid numeric DrawingML attributes ignored where possible
- Geometry: position, size, CSS geometry properties, percent geometry lengths, rounded rectangles, transformed line endpoints, horizontal/vertical flips for lines, and DrawingML line/custom-geometry transform round-trips
- Images: embedded SVG `image` elements with valid base64 PNG/JPEG/GIF/WebP data URI sources, opacity, and legacy `xlink:href`
- Paint: SVG default fill/stroke/stroke-width/line-cap/line-join/miterlimit values including `miter-clip` as a miter approximation, transform-scaled shape and text-outline strokes, `vector-effect="non-scaling-stroke"`, solid fill, stroke color, stroke width including zero-width no-line strokes and percentage widths, line cap/join/miter/custom dash including percentage dash values, DrawingML preset dash fallback, DrawingML RGB/scheme color fallback with luminance modifiers, dash-offset approximation for offsets that start inside dash or gap segments, fill/stroke alpha including fully transparent no-fill/no-line paint, short/long alpha hex colors, CSS rgb/hsl color functions, named colors, `currentColor`, `context-fill`/`context-stroke`, inherited paint values, paint-server fallback colors, CSS-colored linear/radial gradient fallback, and representative pattern fallback colors
- Styling: inline presentation attributes, inline `style`, simple `<style>` rules for element/class/id, compound class, attribute selectors (`=`, `~=`, `|=`, `^=`, `$=`, `*=`), child, and descendant selectors, CSS specificity, `inherit`/`initial`/`unset`, and `!important` cascade priority
- Line markers: `marker-start`, `marker-end`, and `marker` shorthand arrow markers are converted to DrawingML line arrows for lines and open two-end paths/polylines
- Coordinate systems: root, nested SVG, and symbol `viewBox` normalization with `preserveAspectRatio` support
- Visibility: `display:none` is skipped as a subtree, while `visibility:hidden`/`collapse` hide the current element and still allow visible descendants
- Clipping: rectangular `clipPath` on `rect`/rounded `rect`, `circle`/`ellipse`, `line`, two-point open `polyline`/`path`, `text`, and embedded `image` is converted as bounding-box or segment intersection, including `userSpaceOnUse` and `objectBoundingBox` units; browser PPTX export also clips nested SVG viewports with `overflow="hidden"`
- Analysis: unsupported visual/layout attributes such as filters, masks, blend/isolation, fill/clip rules, visible paint order changes, unsupported vector effects, unsupported stroke line cap/join values, word spacing conflicts, dash offsets that cannot be approximated, visible text decoration color/style/thickness/underline offset/skip-ink differences, multi-value text rotation, unsupported text/path length adjustments, unsupported text layout/direction/typography controls beyond simple RTL text, unsupported markers, unsupported `foreignObject` islands outside simple HTML tables, and unresolved paint servers are reported, while default no-op values, normal-equivalent `font-stretch` percentages, zero-equivalent glyph orientation angles and baseline shifts, zero or single-character kerning, non-positioned run-level `tspan` anchors, marker-only paint order changes without markers, matching text decoration colors including default `currentColor`, `pathLength` without a visible dashed stroke, and rendering quality hints are ignored
- Transforms: SVG `transform` attributes and CSS `transform` properties on elements and groups for `matrix`, `translate`, `scale`, `rotate`, `skewX`, `skewY`, absolute-length, keyword, and reference-box percentage CSS `transform-origin`, plus DrawingML rotation/flip output as SVG transforms for supported shapes and pictures
- Reuse: local `defs`/`use` expansion for referenced shapes, groups, and basic `symbol viewBox` scaling, including legacy `xlink:href`, with unsupported missing/external use references reported by the analyzer
- Text: basic font size, weight, italic style, font family, `small-caps` and `all-small-caps` font variants, inherited and per-`tspan` `text-transform`, run-level `tspan` fill/font/outline/decoration/letter-spacing/word-spacing/baseline styling, DrawingML rich text runs as SVG `tspan` styles, text fill/no-fill, text outline color/width/cap/join/dash/miter, underline/strike decoration including `text-decoration-line`, `text-decoration` shorthand, and dashed/dotted/double/wavy underline styles, horizontal/vertical anchor including supported first-`tspan` `text-anchor`/baseline and `alignment-baseline` fallbacks, simple `direction="rtl"` paragraph direction, DrawingML no-wrap text bodies as SVG `white-space="nowrap"`, text-level `baseline-shift` `super`/`sub`, `xml:space="preserve"`, single-value `rotate` including CSS angle units, `letter-spacing`, simple `word-spacing`, `textLength` spacing adjustment, approximate `spacingAndGlyphs`, `dx`/`dy` positioning, first-`tspan` positioning fallback, multi-line `tspan` extraction, and multiple DrawingML paragraph extraction

The converter supports DrawingML shape fragments and can also emit complete `.pptx` packages from SVGraph presentation metadata. It does not read complete `.pptx` or `.docx` packages yet.

## Browser-only SVGraph

The GitHub Pages editor runs a TypeScript converter entirely in the browser:

- `web/app.ts` builds SVGraph, browser-local coverage diagnostics, an SVGraph sidecar JSON, an SVGraph presentation package projection, canonical SVG source download, DrawingML fragment XML, DrawingML-to-SVG import for basic shape, solid-fill/stroke alpha, gradient/pattern fill fallback colors, DrawingML color luminance modifiers and srgb/scrgb/hsl/scheme/system/preset color sources, DrawingML stroke cap/join/dash/miter details, line arrowheads, common preset polygon/arc/flowchart/bevel/snip/symbol/star/arrow/callout/ribbon/action shape, custom geometry/freeform, grouped shape, connector, picture, and native table fragments, PresentationML slide XML, and a `.pptx` ZIP without Python or server APIs.
- `docs/app.js` is the compiled Pages artifact.
- Current browser export coverage supports `rect`, `circle`/`ellipse`, `line`, `polygon`, `polyline`, `M/L/H/V/Z`, quadratic/cubic `Q/T/C/S`, and arc `A` paths as custom geometry, embedded data URI images with CSS/presentation frame geometry, intrinsic-size `preserveAspectRatio` meet/slice handling, and `opacity` as picture alpha, marker arrows, `defs`/local `use` expansion plus root, nested `svg`, and `symbol` viewBox scaling with CSS/presentation frame geometry and `preserveAspectRatio`, linear/radial gradient and pattern paint-server fallback colors, named colors, CSS `rgb()`/`hsl()` colors, `currentColor`, `context-fill`/`context-stroke`, fill/stroke alpha from opacity properties and alpha colors, stroke dash/cap/join styles including `stroke-dashoffset` phase approximation, miterlimit export, negative stroke-width fallback, transform-scaled strokes, line/polyline/basic path `pathLength` dash scaling including CSS-positioned lines, SVG line direction flips, and `vector-effect="non-scaling-stroke"`, `display:none` subtree skipping and inherited `visibility:hidden`/`collapse` with visible-descendant recovery, simple `<style>` selector rules plus screen-compatible `@media` blocks with specificity plus `!important` cascade priority, CSS custom properties with `var()` fallbacks, and `inherit`/`initial`/`unset` on converted properties, CSS/presentation geometry for basic shapes and text metrics with absolute/relative CSS length units including `em`, `%`, `rem`, and basic `calc()`/`min()`/`max()`/`clamp()` expressions, `text` plus inline `tspan` rich text runs, first-`tspan` position fallback, CSS/presentation `text` and `tspan` `x`/`y`/`dx`/`dy` positioning, positioned `tspan` line-break fallback, `text-transform` literal text mapping, `xml:space="preserve"` whitespace retention, CSS/presentation `font` shorthand expansion, font-size keywords, `font-variant` small/all caps, run-level text outline stroke, underline/strike decoration including underline style, color, and thickness, `baseline-shift` super/sub, `letter-spacing`, simple local `text`/`tspan` `word-spacing`, absolute `textLength` spacing approximation including `spacingAndGlyphs` when `letter-spacing` is unset/normal, single-value text `rotate`, simple RTL paragraph direction, text line breaks, and basic `text-anchor`/baseline alignment, inline `style`/basic inherited paint and text styles, CSS/SVG `matrix`/`translate`/`scale`/`rotate`/`skewX`/`skewY` transforms with common angle and absolute length units plus absolute, keyword, and reference-box percentage `transform-origin` over CSS-resolved geometry, rectangular `clipPath` bounds in user space and normalized object bounding-box units with CSS-resolved rect geometry, axis-aligned transforms, and container propagation, nested SVG `overflow="hidden"` viewport clipping, SVGraph multi-slide groups, semantic relation connectors, rect/text SVG grids, line/text SVG grids, and rect background plus line-border SVG grids inferred as native PowerPoint tables, semantic table groups as native PowerPoint tables with `data-text`, `data-colspan`, `data-rowspan`, rect fills, and rect stroke borders including dash/cap/join/miterlimit styles, and simple `foreignObject` HTML tables as native PowerPoint tables with CSS/presentation frame geometry, editable captions, table `width`/`height`, `align`, and margin frame offsets, `colgroup` widths and col/colgroup background fills, alpha colors for cell fills, text runs, and borders, `colspan`/`rowspan`, `cellspacing`/`border-spacing` spacer cells, inline rich text runs, fill, text color, bold headers, uniform and per-side cell padding, RTL/nowrap cell text, alignment, and shorthand/separate/side border styles.
- Browser rect export also follows SVG defaults for invalid negative `rx`/`ry`, including fallback from the valid paired radius.
- Browser marker export only emits DrawingML arrows for resolved arrow-like SVG marker references; unsupported marker definitions remain analyzer diagnostics.
- Browser image sizing scans segmented JPEG data URIs so `preserveAspectRatio` works when APP/EXIF segments precede the SOF size marker.
- Browser data URI image handling validates base64 before conversion or PPTX media embedding.
- Browser CSS keyword handling resets converted properties to SVG defaults for `initial` and falls back correctly for `unset`.
- Browser Assistant can run a local Transformers.js worker with WebGPU, WASM, or disabled policy to propose SVGraph patch JSON; deterministic validation, diff preview, and apply controls remain the only mutation path.
- Browser PPTX export also embeds an `ocz/causal.jsonl` Office Causal data part so `com-junkawasaki/office-causal` can load the SVGraph-derived causal structure without reparsing the visual SVG.

```bash
npm ci
npm run check:web
npm run build:web
npm run check:package
```

## Project links

- Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Maturity matrix: [docs/maturity.md](docs/maturity.md)
- Migration guide: [MIGRATION.md](MIGRATION.md)
- Release checklist: [RELEASE.md](RELEASE.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Repository: <https://github.com/com-junkawasaki/svgraph>
- Issue tracker: <https://github.com/com-junkawasaki/svgraph/issues>
- SVGraph web editor: <https://com-junkawasaki.github.io/svgraph/>

## Install

```bash
echo "@com-junkawasaki:registry=https://npm.pkg.github.com" >> .npmrc
# private package として見える場合は read:packages token も設定
# echo "//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}" >> .npmrc
npm install @com-junkawasaki/svgraph --registry=https://npm.pkg.github.com
```

## Runtime / Dependencies

- Implementation: TypeScript (`web/app.ts`) compiled to `docs/app.js` and `docs/app.d.ts`.
- Runtime: browser or Node.js 18+ plus `nbb` for the ClojureScript CLI.
- Required dependencies: `@xmldom/xmldom` for the CLI DOM shim and `nbb` for `bin/svgraph.cljk`.
- Dev dependency: `typescript`.
- Python is not a runtime, build, CLI, or package dependency. The published package runs through TypeScript-compiled JavaScript, ClojureScript CLI/test harnesses, and Node/browser APIs.

For local development:

```bash
npm ci
npm run check:web
npm run build:web
npm run check:package
```

## CLI

The package installs a ClojureScript `nbb` CLI that uses the TypeScript converter with a Node XML DOM shim:

```bash
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svg2dml input.svg -o shape.xml
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph dml2svg shape.xml -o shape.svg
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svg2pptx deck.svg -o deck.pptx
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svgraph deck.svg -o deck.svgraph.json
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph svgraph-presentation deck.svg -o deck.presentation.json
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph office-causal deck.svg -o deck.office-causal.json
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph office-causal-jsonl deck.svg -o deck.office-causal.jsonl
npm exec --registry=https://npm.pkg.github.com --package @com-junkawasaki/svgraph -- svgraph analyze deck.svg
```

## TypeScript API

```ts
import {
  applyAssistantPatch,
  buildOfficeCausalJsonl,
  buildOfficeCausalPayload,
  buildSVGraph,
  buildSVGraphAssistantPrompt,
  drawingMlToSvg,
  parseAssistantPatchProposal,
  svgToDrawingMl,
  svgToPptx,
  validateAssistantPatch,
} from "@com-junkawasaki/svgraph";

const svgraph = buildSVGraph(svgText);
const officeCausal = buildOfficeCausalPayload(svgraph);
const officeCausalJsonl = buildOfficeCausalJsonl(svgraph);
const drawingMl = svgToDrawingMl(svgText);
const svgAgain = drawingMlToSvg(drawingMl);
const pptxBytes = svgToPptx(svgText);
const prompt = buildSVGraphAssistantPrompt(svgraph, svgraph.presentation);
const proposal = parseAssistantPatchProposal(llmJsonText);
const validation = validateAssistantPatch(proposal, svgraph);
const updatedSvg = validation.status === "accepted" ? applyAssistantPatch(svgText, proposal, svgraph) : svgText;
```

## Supported DrawingML presets

`dml2svg` currently preserves these DrawingML preset geometries as editable SVG shapes. Text bodies keep DrawingML rich text run fill, font, outline, decoration, baseline, spacing, paragraph default run, end-paragraph fallback, bullet, numbering, tab, explicit line-break, body inset, vertical anchor, paragraph alignment, list-style alignment, and RTL details as SVG `text`/`tspan` attributes. Curved presets are converted to editable polygon approximations where SVG does not have a matching primitive:

- Basic primitives: `ellipse`, `line`, `oval`, `rect`, `roundRect`, `straightConnector1`
- Common polygons and corners: `bevel`, `corner`, `decagon`, `diagStripe`, `diamond`, `dodecagon`, `foldedCorner`, `halfFrame`, `heptagon`, `hexagon`, `homePlate`, `nonIsoscelesTrapezoid`, `octagon`, `parallelogram`, `pentagon`, `plaque`, `rtTriangle`, `snip1Rect`, `snip2DiagRect`, `snip2SameRect`, `trapezoid`, `triangle`
- Arc-like shapes: `blockArc`, `chord`, `pie`
- Arrows: `bentArrow`, `bentUpArrow`, `chevron`, `downArrow`, `leftArrow`, `leftRightArrow`, `leftRightUpArrow`, `leftUpArrow`, `notchedRightArrow`, `quadArrow`, `rightArrow`, `upArrow`, `upDownArrow`, `uturnArrow`
- Ribbons and callouts: `funnel`, `leftRightRibbon`, `ribbon`, `ribbon2`, `wedgeEllipseCallout`, `wedgeRectCallout`, `wedgeRoundRectCallout`
- Action buttons: `actionButtonBackPrevious`, `actionButtonBeginning`, `actionButtonBlank`, `actionButtonDocument`, `actionButtonEnd`, `actionButtonForwardNext`, `actionButtonHelp`, `actionButtonHome`, `actionButtonInformation`, `actionButtonMovie`, `actionButtonReturn`, `actionButtonSound`
- Symbols, stars, and math shapes: `cloud`, `heart`, `irregularSeal1`, `irregularSeal2`, `leftBrace`, `leftBracket`, `lightningBolt`, `mathMinus`, `mathMultiply`, `mathPlus`, `moon`, `plus`, `rightBrace`, `rightBracket`, `star4`, `star5`, `star6`, `star8`, `star10`, `star12`, `star16`, `sun`, `teardrop`
- Flowchart shapes: `flowChartAlternateProcess`, `flowChartCollate`, `flowChartConnector`, `flowChartData`, `flowChartDecision`, `flowChartDelay`, `flowChartDisplay`, `flowChartDocument`, `flowChartExtract`, `flowChartInputOutput`, `flowChartManualInput`, `flowChartManualOperation`, `flowChartMerge`, `flowChartOffpageConnector`, `flowChartOr`, `flowChartPreparation`, `flowChartProcess`, `flowChartPunchedCard`, `flowChartPunchedTape`, `flowChartSort`, `flowChartStoredData`, `flowChartSummingJunction`, `flowChartTerminator`

## SVGraph

The TypeScript `buildSVGraph()` API and `svgraph` CLI command expose SVGraph, an SVG-based semantic graph model for app-level pipelines that need more than visual conversion. SVGraph keeps the SVG element tree, normal attributes, `data-*` attributes, `<metadata>` payloads, local reference dependencies such as `href` and `url(#id)`, browser-local coverage diagnostics, and a `presentation` view for slide/package emitters.

This is intended as the stable handoff layer for expanding one SVG source into different targets:

- DrawableXML / Android VectorDrawable: visual geometry is emitted natively, while semantic structure such as tables, entities, relations, and provenance should remain in SVGraph or a sidecar JSON because VectorDrawable has no native table or metadata graph model.
- DrawingML: editable shapes, text, and native tables can be emitted where the target supports them.
- PresentationML: slide-level structure, connectors, reading order, notes, tags, or custom XML can be derived from the same SVGraph document.

The TypeScript `buildSVGraphSidecar()` API and `svgraph-presentation` CLI command expose just the presentation/package view. Slide boundaries are inferred from elements with `data-kind="slide"`, `data-role="slide"`, or `data-slide`; if none are present, the root SVG becomes a single slide. Slide size is taken from root `<metadata>` `{"presentation": {"slideSize": {"width": 1280, "height": 720}}}`, then root `viewBox`, then the first slide viewBox. The view also includes a package part blueprint for `/ppt/presentation.xml`, slide master/layout/theme parts, a custom XML sidecar part, and generated `/ppt/slides/slideN.xml` parts, with each part carrying `part_name`, `content_type`, `kind`, and source-node provenance where available. Generated PPTX custom XML also preserves `source_svg` beside the presentation payload so the editable source can be recovered. Presentation metadata can also carry `masters`, `layouts`, `guides`, `rulers`, and `textStyles` templates for title, lead, body, caption, and other PresentationML text roles.

`buildOfficeCausalPayload()` projects the same SVGraph document into the `office-causal` embedded payload shape. SVGraph nodes become deterministic `ocz1:svgraph-*` node ids; parent/child structure becomes `contains`; local SVG references become `references`; text under semantic nodes becomes `mentions`; and `data-kind="relation"` / `data-role="relation"` nodes can bind source/target nodes via `data-bind="from->to"` or `data-from` / `data-to`. If a relation is explicitly marked with `data-edge="causes"`, `data-kind="causal"`, or `data-type="causes"`, the projection emits a causal hypothesis edge with SVGraph provenance as evidence.

Generated PPTX files include both `/customXml/item1.xml` for SVGraph presentation recovery and `/ocz/causal.jsonl` for Office Causal graph recovery. This keeps SVGraph as the editable SVG/presentation source of truth while giving `office-causal` a typed graph handoff for downstream causal analysis.

See [docs/adr/0001-svgraph.md](docs/adr/0001-svgraph.md) for the design contract.
See [docs/svgraph-web-editor.md](docs/svgraph-web-editor.md) for the browser editor and WebGPU LLM integration design.

## Scope

This is intentionally conservative. Unsupported SVG elements are skipped, and unsupported DrawingML shapes are ignored. Cubic SVG paths and transformed non-rectilinear primitives are approximated as editable DrawingML polylines. The current unit conversion uses Office's common 96 DPI mapping:

```text
1 px = 9525 EMU
1 pt = 1.3333 px
1 pc = 16 px
1 in = 96 px
1 cm = 37.7953 px
1 mm = 3.7795 px
1 q = 0.9449 px
```

## License

MIT
