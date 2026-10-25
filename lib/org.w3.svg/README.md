# svg

`kotoba-lang/svg` is the EDN-first Clojure/ClojureScript substrate for SVG
documents.

It is intentionally separate from the SVG-era browser/Office converter restored
as `com-junkawasaki/svgraph`. This repo keeps SVG as small portable data:
Hiccup-like vectors, plain EDN maps, deterministic rendering, and light
validation helpers that other kotoba libraries can consume without Node,
Python, browser APIs, or Office-specific dependencies.

## Usage

```clojure
(require '[svg.core :as svg])

(def doc
  (svg/svg {:viewBox "0 0 120 40"}
    [:rect {:x 0 :y 0 :width 120 :height 40 :fill "#111827"}]
    [:text {:x 12 :y 25 :fill "white"} "kotoba"]))

(svg/render doc)
;; => "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 120 40\">..."
```

## Scope

- EDN shape: `[:tag {:attr value} child ...]`
- Deterministic XML rendering with escaping
- `style` map rendering
- namespace normalization for root `svg`
- basic tree walking and element validation

Out of scope: DrawingML, PPTX, browser editor, SVGraph presentation IR, and
Office causal sidecars. Those live in `com-junkawasaki/svgraph` and
`com-junkawasaki/office-causal`.

## Reading SVG (`svg.reader`)

`svg.core` is the EDN-first *writer*. `svg.reader` is the read side —
parses raw SVG/XML text into shape elements, extracted from
`kotoba-lang/kasane` (`kasane.svg`, ADR-2606272100) as part of the
kotoba-lang reverse-domain media/graphics standards-substrate split. It's
a separate namespace (not merged into `svg.core`) because `svg.core/attrs`
takes an EDN element (write-side) while `svg.reader/attrs` takes a raw
attribute string (read-side) — same name, different input shape.

```clojure
(require '[svg.reader :as reader])

(reader/elements svg-xml-string)     ; => [{:tag :rect :attrs {:x "10" ...}} ...]
(reader/root-attrs svg-xml-string)   ; => {:width "200" :height "100" ...}
(reader/parse-len "12px")            ; => 12
```

R0 extracts top-level shape elements (rect/circle/ellipse/line/path/text/
polygon/polyline/image) via regex — not a full XML parser, good enough for
well-formed SVG produced by design tools.

## Test

```bash
kbb -M:test
```

## License

MIT
