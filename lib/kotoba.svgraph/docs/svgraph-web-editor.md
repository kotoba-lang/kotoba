# SVGraph Web Editor Design

## Goal

Build a browser-based editor for SVGraph: an SVG-first semantic graph where SVG remains the editable source of truth, `svg_to_svgraph()` exposes SVGraph structure, and `svg_to_svgraph_presentation()` provides the package-level plan for `.pptx` export.

The app should support:

- editing SVG visually and structurally
- editing metadata, `data-*`, dependencies, and slide semantics through SVGraph
- previewing slide boundaries and package parts
- exporting PresentationML/PPTX from deterministic emitters
- running local Web LLM inference in the browser for semantic assistance, not for final conversion correctness

Current implementation status:

- `web/app.ts` is the TypeScript browser runtime.
- GitHub Pages loads the compiled `docs/app.js`.
- The browser can export `svgraph-sidecar.json` with metadata, dependencies, coverage diagnostics, and the presentation/package projection for targets that need semantic state outside the visual output.
- The browser embeds `source_svg` in `svgraph-sidecar.json`, can restore the editable SVG source by opening that sidecar JSON, and reports invalid Open inputs without replacing the current source.
- Browser-generated PPTX custom XML also preserves `source_svg` beside the SVGraph presentation payload for source recovery.
- Browser-generated PPTX also embeds `ocz/causal.jsonl`, an Office Causal compatible graph projection generated from the same SVGraph source. `office-causal readDataPart()` can recover this graph without reparsing slide XML.
- The browser can export DrawingML fragments and `.pptx` without Python for the SVGraph presentation MVP subset: multi-slide SVG groups, editable rect/ellipse/line/text shapes with CSS/presentation geometry, inline `tspan` rich text runs, `text`/`tspan` positioning, basic `text-anchor`/baseline alignment, local `text`/`tspan` `word-spacing`, and absolute `textLength` spacing approximation including `spacingAndGlyphs` when `letter-spacing` is unset/normal, polygon/polyline/quadratic/cubic/arc path custom geometry, embedded data URI images with CSS/presentation frame geometry, marker arrows, SVG line direction flips, local `defs`/`use`, linear/radial gradient and pattern fallback colors, named colors, CSS `rgb()`/`hsl()` colors, `currentColor`, fill/stroke alpha from opacity properties and alpha colors, stroke dash/cap/join styles, negative stroke-width fallback, transform-scaled strokes, line/polyline/basic path `pathLength` dash scaling including CSS-positioned lines, `vector-effect="non-scaling-stroke"`, rectangular `clipPath` in user-space and normalized object bounding-box units with CSS-resolved rect geometry, axis-aligned transforms, and container propagation, nested SVG and `use` viewport clipping with CSS/presentation frame geometry, simple selector styles, inline style/inherited paint, basic transforms with CSS-resolved reference boxes, relation connectors, inferred rect/text and line/text SVG grid tables, semantic tables, and `foreignObject` table CSS/presentation frame sizing/alignment plus alpha fills and text runs.
- The browser can import basic DrawingML shape fragments back into canonical SVG source without Python, including `p:sp` rect/roundRect/ellipse/line fragments, `p:cxnSp` connectors as `data-kind="relation"` SVG lines, native `p:graphicFrame`/`a:tbl` tables as `data-kind="table"` and `data-kind="cell"` SVG semantics, solid fill/stroke colors, stroke width, flips, and simple text body extraction.
- Rect export follows SVG defaults for invalid negative `rx`/`ry`, including fallback from the valid paired radius.
- Marker export only emits DrawingML arrows for resolved arrow-like SVG marker references; unsupported marker definitions stay as analyzer diagnostics.
- Image sizing scans segmented JPEG data URIs so `preserveAspectRatio` still works when APP/EXIF segments precede the SOF size marker.
- Data URI image handling validates base64 before conversion or PPTX media embedding.
- CSS keyword handling resets converted properties to SVG defaults for `initial` and falls back correctly for `unset`.
- The browser Assistant panel exposes deterministic patch proposal/validation preview for SVGraph-level edit operations and can replace the proposal with local Web LLM output after validation.
- The browser Assistant panel shows deterministic patch diff preview rows for SVGraph data and metadata edits before applying future LLM suggestions.
- The browser Assistant panel can apply validated SVGraph patch operations back into the canonical SVG source as `data-*` attributes and `<metadata>` JSON.
- The browser Assistant panel can lazy-load a dedicated Transformers.js worker from the page, choose WebGPU, WASM, or disabled backend policy, prompt with compact SVGraph context, parse JSON-only LLM output, reject invalid operations, and fall back to deterministic proposals without server APIs.
- The browser keeps SVG source undo/redo history across manual edits, file/sample loads, and assistant patch application.
- The browser persists the active SVG source document in IndexedDB, restores it on reload without a server, provides a control for clearing the saved document, and reports storage status in the UI.
- The TypeScript browser/npm package is the only active implementation surface in this repository.

## Product Shape

The first screen is the editor, not a landing page.

Primary panes:

- Canvas: live SVG rendering with slide overlays, selection handles, guides, connectors, and table/cell hints.
- Structure: SVGraph tree, node ids, `id`, `data-kind`, `data-role`, `data-bind`, dependencies, and warnings.
- Properties: geometry, paint, text, metadata, accessibility, table semantics, and slide settings.
- Slides: SVGraph presentation slide list, slide size, titles, notes, and package part mapping.
- Assistant: local WebGPU LLM panel for semantic suggestions and batch edits.
- Export: DrawingML fragment, PresentationML package plan, `.pptx`, SVG, and sidecar JSON.

## Architecture

```text
Browser UI
  |
  |-- SVG document model
  |     |-- raw SVG text
  |     |-- DOM tree
  |     |-- SVGraph JSON
  |     |-- SVGraph presentation JSON
  |     `-- Office Causal JSON/JSONL projection
  |
  |-- Workers
  |     |-- parser/analyzer worker
  |     |-- conversion/export worker
  |     |-- web-llm worker
  |
  |-- Storage
        |-- IndexedDB documents
        |-- IndexedDB model cache
        |-- File System Access API exports
        `-- PPTX sidecars: customXml/item1.xml + ocz/causal.jsonl
```

The editor should not let the LLM directly mutate the raw document. LLM output is always a proposed patch against SVGraph-level commands, then validated by deterministic code before applying.

## Core Data Model

Client-side state should keep four synchronized layers:

1. Raw SVG source.
2. Parsed SVG DOM.
3. `SVGraphDocument`.
4. `SVGraphPresentation` projection.
5. Office Causal projection for downstream causal graph tools.

The app treats SVG as canonical. SVGraph is derived and cached. UI actions should preferably emit structured edit operations and then serialize back to SVG:

```json
{
  "op": "set-data",
  "node_id": "n0.3.1",
  "name": "kind",
  "value": "table"
}
```

Recommended operation groups:

- `set-attribute`
- `set-style`
- `set-data`
- `set-metadata`
- `move-node`
- `group-nodes`
- `mark-slide`
- `mark-table`
- `mark-cell`
- `bind-relation`
- `set-reading-order`

Every operation should be reversible for undo/redo.

## SVGraph Presentation Workflow

### Import

1. User opens `.svg` or pastes SVG.
2. Parser validates XML and normalizes namespaces.
3. Analyzer reports unsupported visual features.
4. SVGraph builder extracts metadata, `data-*`, dependencies, and `svgraph-presentation` view.
5. UI overlays slide boundaries.

### Edit

1. Visual edits update SVG attributes.
2. Semantic edits update `data-*` or `<metadata>`.
3. Slide edits update `data-kind="slide"`, `data-title`, `viewBox`, or presentation metadata.
4. Table edits update semantic markers such as `data-kind="table"`, `data-kind="cell"`, `data-row`, and `data-col`.

### Preview

1. SVG preview uses browser rendering.
2. PPTX preview uses deterministic SVGraph-to-PresentationML preview logic.
3. Warnings distinguish visual fallback from semantic loss.

### Export

Export targets:

- `svg`: canonical source.
- `svgraph.json`: full SVGraph.
- `svgraph-sidecar.json`: semantic sidecar with metadata, dependencies, coverage, and presentation package state.
- `svgraph-presentation.json`: presentation/package projection.
- `drawingml.xml`: current fragment converter output, with browser import support for basic shape fragments.
- `pptx`: full package emitter output.

The `.pptx` exporter should consume the SVGraph `presentation.parts` projection and generate package relationships, content types, presentation properties, slide XML, theme, layouts, and optional custom XML sidecar. Each package part record carries `part_name`, `content_type`, `kind`, and `source_node_id` so the UI can preview the package blueprint and trace generated PresentationML parts back to SVG nodes.

## Web LLM Integration

The Web LLM runs in a dedicated worker. Based on the referenced WebGPU browser guide, the default path uses Transformers.js with `device: "webgpu"` when `navigator.gpu` is available, and the runtime/model cache is left to the browser and Transformers.js cache after the first download. The editor also exposes `wasm` and `disabled` policies so conversion remains available when WebGPU is missing or AI must be off.

Minimal worker loading shape:

```ts
import { pipeline } from "@huggingface/transformers";

const generator = await pipeline(
  "text-generation",
  "onnx-community/gemma-4-e2b-it-ONNX",
  {
    device: "webgpu",
    dtype: "q4",
  },
);
```

The app should support backend policy:

- `webgpu`: preferred for local text generation.
- `wasm`: fallback for small classification or environments without WebGPU.
- `disabled`: enterprise/privacy mode where AI is off.
- `remote`: optional future server-side provider, never required for core editing.

LLM responsibilities:

- infer likely slide titles from SVG text
- classify nodes into `data-kind` / `data-role`
- suggest slide boundaries
- detect table-like grids and propose table semantics
- infer relations between shapes and connectors
- generate speaker notes from visible text
- explain unsupported coverage warnings
- propose batch rename/group/order operations

LLM non-responsibilities:

- final SVG parsing
- final PresentationML generation
- security decisions
- applying edits without user approval
- silently rasterizing unsupported content

## Assistant Patch Protocol

Prompt context should be compact and SVGraph-based:

```json
{
  "task": "suggest-slide-boundaries",
  "slide_size": [1280, 720],
  "nodes": [
    {"node_id": "n0.1", "tag": "g", "id": "cover", "text": "Quarterly Review"},
    {"node_id": "n0.2", "tag": "g", "id": "system", "children": 12}
  ],
  "constraints": {
    "output": "json-patch-ops",
    "allowed_ops": ["mark-slide", "set-data", "set-metadata"]
  }
}
```

Assistant output must be validated against a strict schema:

```json
{
  "summary": "Found two likely slides.",
  "ops": [
    {"op": "mark-slide", "node_id": "n0.1", "title": "Quarterly Review"},
    {"op": "mark-slide", "node_id": "n0.2", "title": "System"}
  ],
  "confidence": 0.82
}
```

The UI then shows a diff before applying.

## Security And Privacy

- Do not execute script from imported SVG.
- Sanitize SVG before preview; disable external resource loading by default.
- Keep local LLM prompts on-device unless the user enables a remote provider.
- Store documents and model cache in IndexedDB with clear user controls.
- Warn before exporting metadata/custom XML that may contain private information.
- Maintain a visible provenance panel for generated suggestions.

## Performance

The article notes that initial WebGPU model download can be hundreds of MB to multiple GB depending on quantization, with later loads served from local cache. Design implications:

- lazy-load the model only when the assistant panel is opened
- prefer quantized models for browser use
- stream tokens into the assistant panel
- keep parsing/conversion in separate workers so the canvas remains responsive
- cap prompt context to selected slide/subtree unless the user requests whole-deck analysis

## UI States

Important states:

- WebGPU unavailable
- model downloading
- model cached
- model loading
- generating
- low memory / model load failed
- patch pending review
- patch rejected by validator
- conversion warnings
- export succeeded

## Roadmap

### Phase 1: SVGraph Editor

- SVG load/save
- SVGraph tree view
- SVGraph presentation slide list
- analyzer warnings
- metadata/data-* inspector

### Phase 2: Deterministic Preview And Export

- DrawingML fragment export
- package part preview
- minimal `.pptx` emitter
- sidecar custom XML export

### Phase 3: Local Web LLM Assistant

- WebGPU capability check
- Transformers.js worker
- model cache UI
- slide-boundary suggestion
- table/relation inference
- schema-validated patch review

### Phase 4: Advanced Authoring

- table editor
- connector graph editor
- reading order and notes
- theme/layout editor
- round-trip `.pptx` package inspection

## Implementation Recommendation

Use a TypeScript frontend with:

- Vite or Next.js for the app shell
- React for editor UI
- Zustand or Redux Toolkit for undoable document state
- Web Workers for parsing/export and LLM
- IndexedDB through a typed wrapper
- SVG canvas as the primary editable surface
- WASM only for browser fallback execution, not server-side runtime parsing

Keep SVGraph as the conversion core and publish the schema as stable JSON so the web editor, CLI, and future package emitter share the same contract.
