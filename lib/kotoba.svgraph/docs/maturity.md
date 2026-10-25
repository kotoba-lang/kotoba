# SVGraph Maturity Matrix

SVGraph is currently an alpha TypeScript/browser implementation. The strongest path is controlled SVG authored for presentation export; arbitrary SVG fidelity and complete Office round-trips remain experimental.

## Status Levels

| Level | Meaning |
| --- | --- |
| Stable | Covered by committed tests and expected to remain compatible across minor releases. |
| Alpha | Implemented and used by examples or smoke checks, but still may change as the IR matures. |
| Experimental | Available as a first pass, with known gaps or incomplete fidelity. |
| Diagnostic | Intentionally reported rather than converted. |
| Not implemented | No supported conversion path yet. |

## Core Surfaces

| Surface | Status | Verification |
| --- | --- | --- |
| TypeScript package API | Stable | `npm run check:web`, `npm run check:package` |
| Browser editor and GitHub Pages artifact | Alpha | `npm run build:web`, committed `docs/app.js` |
| ClojureScript CLI shim | Stable | `npm run check:package`; package smoke runs through `bin/svgraph.cljk`. |
| SVG to SVGraph IR | Alpha | `npm run test:maturity`; feature fixtures cover metadata, data semantics, dependencies, and diagnostics. |
| SVGraph sidecar JSON with `source_svg` | Alpha | `npm run test:maturity` |
| Office Causal JSON/JSONL projection | Alpha | `npm run test:maturity`; fixtures cover deterministic ids, containment/reference edges, and causal hypothesis edges from semantic relation nodes. |
| SVG to DrawingML fragment | Alpha | `npm run check:package`, `npm run test:maturity`; fixture tests cover editable geometry, connectors, rich text runs, and diagnostics. |
| DrawingML fragment to SVG | Alpha | `npm run check:package`, `npm run test:maturity`; fixture tests cover line arrows, rich text styles, and table semantics. |
| SVG to complete PPTX package | Alpha | `npm run test:maturity` |
| Complete PPTX import | Not implemented | No package reader yet |

## SVG Coverage

| SVG feature | Status | Notes |
| --- | --- | --- |
| `rect`, `circle`, `ellipse`, `line` | Stable | Editable DrawingML shapes for common geometry. |
| `polygon`, `polyline` | Alpha | Editable approximation for presentation geometry. |
| `path` `M/L/H/V/Z/Q/T/C/S/A` | Alpha | Exported as custom geometry; visual parity is not guaranteed for all path edge cases. |
| Basic text and `tspan` runs | Alpha | Rich text runs, inline positioning, and common style attributes are supported. |
| Advanced text layout | Experimental | Complex typography and layout fidelity remain approximate. |
| Embedded data URI images | Alpha | PNG/JPEG/GIF/WebP validation and PPTX media embedding are supported. |
| `defs`/local `use`/`symbol` | Alpha | Local references and viewBox scaling are supported for common cases. |
| Paint servers | Alpha | Linear/radial gradient and pattern fallback colors are supported, not full native paint fidelity. SVGraph records local paint-server dependencies. |
| CSS cascade | Alpha | Inline style, presentation attributes, simple selectors, variables, and common units are supported. |
| Transforms | Alpha | Matrix, translate, scale, rotate, skew, and common origins are supported. |
| Rectangular clipping | Alpha | Rectangular clip paths and nested SVG viewport clipping are supported. |
| Filters, masks, blend modes | Diagnostic | Reported as unsupported instead of converted. |
| Arbitrary `foreignObject` | Diagnostic | Only simple HTML tables are converted. |

## PresentationML/PPTX Coverage

| Feature | Status | Notes |
| --- | --- | --- |
| Multi-slide SVG groups | Alpha | `data-kind="slide"`, `data-role="slide"`, and `data-slide` are recognized. |
| Slide size metadata | Alpha | SVG metadata and viewBox fallbacks are supported. |
| Slide masters/layout parts | Experimental | Basic package parts are emitted; full PowerPoint theme/layout fidelity is not complete. |
| Text style templates | Experimental | Metadata is preserved and simple defaults are emitted. |
| Rulers and guides metadata | Alpha | Preserved in SVGraph presentation and sidecar JSON. |
| Editable relation connectors | Alpha | Semantic relation lines export as connector shapes with start/end connection ids. |
| Native PowerPoint tables | Alpha | Semantic tables, simple SVG grids, and simple HTML tables can emit native table XML. |
| PPTX custom XML sidecar | Alpha | Source SVG and SVGraph presentation metadata are embedded. |
| Office Causal data part | Alpha | `ocz/causal.jsonl` is embedded for downstream graph tooling. |

## Current Quality Bar

Every change that touches conversion, IR, package output, or public docs should run:

```bash
npm ci
npm run check:web
npm run build:web
npm run test:maturity
npm run check:package
git diff --exit-code docs/app.js
git diff --exit-code docs/app.d.ts
npm pack --dry-run --json
```

The maturity suite and package smoke now run as ClojureScript through `nbb`. Fixture coverage is split between semantic/PPTX maturity tests and feature-focused CLI/package smoke checks for API, generated SVG geometry, text, table, picture, color, Office Causal outputs including causal-edge JSONL and JSON/JSONL parity, stdin/stdout CLI paths, text and binary `-o` output-file writes including PPTX ZIP output, PPTX output-file part-level unzip assertions, and negative CLI behavior for unsupported commands, missing inputs, malformed stdin, malformed output arguments, and invalid output paths. Repeated package-smoke helpers live in shared CLJS support code, and CLI parse-time errors are reported without nbb stack context. The next maturity step is to add Office Causal JSONL package-part parity assertions against standalone CLI output while keeping the API smoke boundary separate from geometry/text/table fixtures.
