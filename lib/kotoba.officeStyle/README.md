# office-style

[![CI](https://github.com/kotoba-lang/office-style/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/office-style/actions/workflows/ci.yml)

Pure CLJC / EDN StyleIR extraction for PowerPoint `.pptx` packages.

`office-style` reads deterministic PowerPoint style data directly from OOXML:
theme colors (`srgbClr` and `sysClr lastClr`), theme fonts, slide size, slide
parts, layouts, and masters. It can also render a compact SVG preview and
project the result into a svgraph-friendly EDN shape.

Extraction is intentionally tolerant of incomplete decks: missing themes produce
empty color/font maps, missing slide size stays nil, invalid size numbers fall
back to zero, numbered slides/layouts/masters use natural ordering, theme font
attributes decode named/numeric XML entities, and single- or double-quoted XML
attributes are accepted, including pretty-printed color/font scheme XML. Preview
SVG output escapes text and validates colors before writing attributes. The OPC
reader keeps XML and relationship parts only, so binary media never enters the
StyleIR input map. The svgraph projection also normalizes invalid direct IR slide
sizes, including non-finite values, back to the default 16:9 size and emits empty
theme maps when theme data is absent. Direct `style-ir` calls with malformed
package entries fall back to an empty StyleIR instead of throwing.

## Runtime

- Implementation: Clojure / ClojureScript portable `.cljc`
- Host zip support: JVM Clojure for package reads
- Data surface: EDN maps under `:office-style/*`
- JavaScript / TypeScript core runtime: none. The npm package only provides a
  thin `node` bin wrapper that invokes the Clojure CLI.

## API

```clojure
(require '[office-style.opc :as opc]
         '[office-style.style :as style]
         '[office-style.preview :as preview]
         '[office-style.svgraph :as svgraph])

(def bytes (java.nio.file.Files/readAllBytes
            (java.nio.file.Path/of "deck.pptx" (into-array String []))))

(def ir (style/extract-bytes bytes))

(:office-style/colors ir)
(:office-style/fonts ir)
(preview/preview-svg ir)
(svgraph/presentation ir)
```

## Namespaces

- `office-style.opc`: pptx zip reader for XML and relationship parts
- `office-style.style`: deterministic StyleIR extraction
- `office-style.preview`: SVG preview from StyleIR
- `office-style.svgraph`: svgraph-friendly EDN projection

## CLI / npm

The CLI works directly with Clojure or through the npm wrapper. In both cases
`clojure` must be installed on the host.

```bash
kbb -M:cli extract deck.pptx style.edn
kbb -M:cli template deck.pptx template.edn
kbb -M:cli preview deck.pptx preview.svg
kbb -M:cli svgraph deck.pptx svgraph.edn

npx @kotoba-lang/office-style template deck.pptx template.edn
```

## Test

```bash
kbb -X:test
```

The test suite covers StyleIR extraction, XML/relationship input filtering,
natural part ordering, `srgbClr`/`sysClr` theme colors, single/double quoted XML
attributes, pretty-printed color/font scheme XML, theme font entity decoding,
missing style metadata, invalid/non-finite slide sizes, preview SVG fallbacks,
svgraph projection fallbacks, malformed direct package fallbacks, and CLI
commands.
