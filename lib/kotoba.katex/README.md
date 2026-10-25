# kotoba-lang/katex

[![CI](https://github.com/kotoba-lang/katex/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/katex/actions/workflows/ci.yml)

A **native, from-scratch** TeX-math parser and MathML renderer for the
kotoba-lang foundational stdlib. This is explicitly **not** a wrapper/interop
shim around the real [KaTeX.js](https://katex.org/) library — no JS interop,
no npm dependency, zero third-party runtime deps. Every namespace is `.cljc`,
so it runs on JVM / SCI / ClojureScript / GraalVM / kotoba-WASM.

## Why not full glyph-level TeX layout?

Real KaTeX does font-metric-based glyph layout — an enormous undertaking to
reimplement natively. `katex` v1 scopes down to something honest and
tractable instead:

1. Parse a TeX-math-like string into a pure **EDN AST** (the real
   deliverable — you can also construct this AST directly, skipping the
   string parser entirely).
2. Render that AST to **MathML** (also just EDN/XML), and let any
   MathML-capable renderer (browsers, OOXML import, etc.) do the actual
   glyph layout.

This sidesteps needing font metrics ourselves while still producing correct,
semantic math markup.

## Supported v1 subset

- Fractions: `\frac{a}{b}` (and TeX's brace-less `\frac12` shorthand).
- Superscript `^` and subscript `_`, in either order, collapsing into one
  `:supsub` node when both apply to the same base (e.g. `\sum_{i=1}^{n}`).
- `\sqrt{x}` and `\sqrt[n]{x}`.
- Accents: `\hat \bar \vec \dot \tilde \ddot`, rendered as MathML `<mover>`.
- Grouping with `{ ... }`.
- Common Greek letters: lowercase `alpha`..`omega`, plus the uppercase
  letters with a distinct glyph from Latin (`Gamma Delta Theta Lambda Xi Pi
  Sigma Upsilon Phi Psi Omega`).
- Common operators/relations: `\sum \int \prod \leq \geq \neq \times \cdot
  \pm \mp \infty \to \rightarrow \leftarrow \in \forall \exists \partial
  \nabla \approx \equiv \subset \supset \cup \cap \cdots \ldots`.
- Numbers, single-letter identifiers, and implicit adjacency/multiplication
  (no dedicated AST node — sibling atoms in a row are simply typeset next to
  each other, exactly as TeX itself does).
- Ordinary operator characters (`+ - = < > ( ) [ ] , .` etc.) pass through
  as `[:op "<char>"]`.
- Unrecognized `\command`s become `[:unknown "command"]` and render as
  literal text — never silently dropped.

**Explicitly out of scope for v1:** matrices/arrays, `\left`/`\right`
auto-sizing delimiters, `\overline` (a variable-width line over a whole
expression, distinct from the fixed-width `\bar` accent above), text mode,
spacing/font commands, multi-letter identifiers via `\mathrm{}`, and the
long tail of TeX symbols beyond the list above. See the
`kotoba.lang.katex.parse` namespace docstring for the exact, authoritative
subset.

## AST shape

```clojure
[:row    [node ...]]        ; top-level sequence of sibling nodes
[:group  [node ...]]        ; a {...} grouped sequence of sibling nodes
[:num    "123.45"]          ; a number literal
[:sym    "x"]               ; an identifier (incl. Greek, spelled as unicode)
[:op     "+"]                ; an operator/relation/large-operator
[:frac   num den]           ; \frac{num}{den}
[:sqrt   index-or-nil rad]  ; \sqrt{rad} or \sqrt[index]{rad}
[:sup    base exp]          ; base^exp
[:sub    base sub]          ; base_sub
[:supsub base sub exp]      ; base with both ^ and _ applied
[:unknown "cmdname"]        ; an unrecognized \cmdname
```

A `{...}`/argument group that parses to exactly one child node is unwrapped
to that child directly rather than wrapped in a redundant `[:group [x]]`.

## Install

```clojure
io.github.kotoba-lang/katex {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.katex.parse :as parse]
         '[kotoba.lang.katex.mathml :as mathml])

(parse/parse "\\frac{1}{2} + x^2_i")
;=> [:row [[:frac [:num "1"] [:num "2"]] [:op "+"] [:supsub [:sym "x"] [:sym "i"] [:num "2"]]]]

(parse/parse "\\sqrt{x+1}")
;=> [:row [[:sqrt nil [:group [[:sym "x"] [:op "+"] [:num "1"]]]]]]

(mathml/ast->mathml-string (parse/parse "\\sqrt[3]{x}"))
;=> "<math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mrow><mroot><mi>x</mi><mn>3</mn></mroot></mrow></math>"

;; The AST can also be built directly, without the string parser:
(mathml/ast->mathml-string [:frac [:num "1"] [:num "2"]])
;=> "<math xmlns=\"http://www.w3.org/1998/Math/MathML\"><mfrac><mn>1</mn><mn>2</mn></mfrac></math>"
```

## Verify

```sh
kbb -M:test
```
