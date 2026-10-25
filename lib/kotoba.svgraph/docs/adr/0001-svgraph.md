# ADR 0001: SVGraph

## Status

Accepted

## Context

SVG can carry visual geometry, document metadata, and application-specific data in one file. The current converter focuses on editable DrawingML fragments, but an application-level pipeline also needs to preserve structure, inferred meaning, and dependencies so the same SVG source can later emit Android VectorDrawable, DrawingML, PresentationML, or other targets.

## Decision

Introduce SVGraph, an SVG-based semantic graph model exposed by the TypeScript browser/npm package. SVGraph preserves:

- element tree structure with stable node ids
- normal SVG attributes
- `data-*` attributes as application data
- local `<metadata>` text, XML, and JSON payloads
- dependencies such as `href`, `xlink:href`, `url(#id)` paint servers, markers, clipping, masks, symbols, and other local references
- a presentation/package view named `svgraph-presentation`

SVGraph is intentionally independent of a specific output format. Target emitters consume the graph and decide whether a node maps to a native object, a grouped shape, a raster fallback, or an application sidecar.

## SVGraph Shape

```json
{
  "kind": "svgraph",
  "version": "0.1",
  "metadata": {},
  "dependencies": [],
  "presentation": {
    "kind": "svgraph-presentation",
    "slide_size": [1280, 720],
    "slides": [],
    "parts": [
      {
        "part_name": "/ppt/presentation.xml",
        "content_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        "kind": "presentation",
        "source_node_id": null
      }
    ],
    "masters": [],
    "layouts": [],
    "guides": [],
    "rulers": [],
    "text_styles": []
  },
  "root": {
    "node_id": "n0",
    "tag": "svg",
    "attributes": {},
    "data": {},
    "metadata": {},
    "dependencies": [],
    "children": []
  }
}
```

Nodes keep visual SVG data and semantic data together. This makes the SVG itself the source of truth while giving non-SVG targets a normalized read model.

## Metadata Convention

Application data should prefer either JSON in `<metadata>` or small scalar `data-*` attributes:

```xml
<svg viewBox="0 0 400 240">
  <metadata>
    {
      "title": "Architecture",
      "entities": [{"id": "api", "type": "service"}],
      "relations": [{"from": "api", "to": "db", "type": "depends-on"}]
    }
  </metadata>
  <rect id="api" data-kind="service" data-layer="backend" x="20" y="20" width="120" height="60"/>
  <rect id="db" data-kind="database" x="220" y="20" width="120" height="60"/>
</svg>
```

Recommended fields:

- `data-kind`: semantic object type, such as `service`, `database`, `table`, `cell`, `actor`, `flow`, or `annotation`
- `data-role`: presentation role, such as `title`, `label`, `caption`, `node`, `edge`, or `container`
- `data-bind`: external application id or model path
- `data-group`: logical group independent from SVG `<g>`
- `data-order`: application reading or animation order
- `data-kind="slide-master"`: reusable master art, placeholders, theme binding, or background structure
- `data-kind="slide-layout"`: reusable layout and placeholder geometry
- `data-kind="guide"`: non-exporting editor guide, usually with `data-orientation` and `data-position`
- `data-kind="ruler"`: editor ruler definition, usually with `data-origin`, `data-spacing`, and `data-unit`
- `data-kind="style-template"`: PresentationML text style template for roles such as `title`, `lead`, `body`, `caption`, `label`, and `footer`

## SVGraph Presentation View

`svgraph-presentation` is the SVGraph projection for creating a full `.pptx` package rather than a single DrawingML shape fragment. It is not a new rendering format; it is a package intent over the same SVG source.

Slide boundaries are discovered in this order:

- any element with `data-kind="slide"`
- any element with `data-role="slide"`
- any element with `data-slide="..."`
- otherwise, the root `<svg>` is treated as one slide

Slide size is discovered in this order:

- root metadata: `{"presentation": {"slideSize": {"width": 1280, "height": 720}}}`
- root `viewBox`
- first slide `viewBox`

Presentation-level metadata can also describe package authoring state:

```json
{
  "presentation": {
    "slideSize": {"width": 1280, "height": 720},
    "masters": [{"id": "brand-master", "theme": "brand"}],
    "layouts": [{"id": "title-content", "master": "brand-master"}],
    "guides": [{"id": "safe-left", "orientation": "vertical", "position": 96, "unit": "px"}],
    "rulers": [{"id": "x", "orientation": "horizontal", "origin": 0, "spacing": 16, "unit": "px"}],
    "textStyles": {
      "title": {"fontFamily": "Aptos Display", "fontSize": 48, "bold": true},
      "lead": {"fontFamily": "Aptos", "fontSize": 24},
      "body": {"fontFamily": "Aptos", "fontSize": 16}
    }
  }
}
```

This metadata is intentionally richer than the current minimal package emitter. It gives a web editor and future PresentationML writer a stable place to preserve slide masters, layout templates, editor rulers/guides, and text style templates without forcing those concepts into visual SVG shapes.

Example:

```xml
<svg viewBox="0 0 1280 720">
  <metadata>{"presentation": {"slideSize": {"width": 1280, "height": 720}}}</metadata>
  <g id="cover" data-kind="slide" data-title="Cover">
    <text data-role="title">Quarterly Review</text>
  </g>
  <g id="system" data-kind="slide" data-title="System">
    <rect id="api" data-kind="service"/>
    <rect id="db" data-kind="database"/>
  </g>
</svg>
```

The package emitter can then map:

- each slide node to `ppt/slides/slideN.xml`
- the `parts` list to the required package blueprint, including `part_name`, `content_type`, `kind`, and source-node provenance for presentation, slide master, slide layout, theme, and slide parts
- `/customXml/item1.xml` to an SVGraph presentation metadata sidecar part
- `masters` and `layouts` to PresentationML slide master/layout parts
- `guides` and `rulers` to editor metadata or custom XML sidecars
- `text_styles` to PresentationML default text styles and placeholder styles
- root presentation metadata to `ppt/presentation.xml`, theme, layout, notes, tags, or custom XML
- semantic `data-kind="table"` / `data-kind="cell"` nodes to native PresentationML tables where possible
- semantic relations to connectors when they have visual counterparts
- an Office Causal graph part at `/ocz/causal.jsonl` when the package writer needs downstream causal analysis
- unresolved semantics to a package sidecar or custom XML part

## Target Mapping

### Android VectorDrawable / DrawableXML

VectorDrawable is a visual vector format. It has no native table, rich metadata, dependency graph, or presentation object model. Emitters should:

- map supported geometry and paint to native vector paths/groups
- flatten unsupported semantics into visual groups
- preserve SVGraph metadata outside the drawable as a sidecar JSON when semantic round-trip is required

### DrawingML

DrawingML can represent editable shapes, text, tables, and some semantic grouping. Emitters should:

- use native DrawingML tables only when SVGraph identifies table semantics or the geometry is clearly table-like
- keep per-node provenance in non-visual properties where package context allows it
- preserve unsupported semantics in a sidecar when fragment-only output has no safe storage location

### PresentationML

PresentationML can add slide-level structure beyond DrawingML fragments. Emitters should:

- map SVGraph groups to slide shape trees
- map relationships to connectors when they are visually represented
- map `data-order` and metadata to animation, reading order, notes, custom XML, or tags when the package writer supports it
- use `svgraph-presentation` as the package-level contract instead of treating `svg_to_drawingml()` output as a whole deck

### Office Causal

`com-junkawasaki/office-causal` treats Office files as a typed causal graph with deterministic `ocz1:` data ids. SVGraph can interoperate with it without making Office Causal a runtime dependency:

- every SVGraph node projects to an Office Causal payload node with a deterministic `ocz1:svgraph-*` id
- the SVG element tree projects to `contains` edges
- local references such as `href`, `xlink:href`, and `url(#id)` project to `references` edges when the target node is resolvable
- semantic text under a node with `data-*` semantics can project to `mentions` edges
- `data-kind="relation"` / `data-role="relation"` nodes can bind source and target entities with `data-bind="from->to"` or `data-from` / `data-to`
- relation nodes become causal hypotheses only when explicitly marked as causal, for example `data-edge="causes"` or `data-type="causes"`
- generated PPTX packages may include `/ocz/causal.jsonl` plus the Office Causal root relationship so `office-causal readDataPart()` can recover the graph without reparsing slides

## Consequences

The converter remains conservative and deterministic. SVGraph gives the app a richer layer for inference and multi-target expansion without forcing every semantic concept into DrawingML or DrawableXML, where many of those concepts do not exist natively.
