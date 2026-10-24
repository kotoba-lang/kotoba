# kotoba-lang/tex

[![CI](https://github.com/kotoba-lang/tex/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/tex/actions/workflows/ci.yml)

**EDN-first LaTeX document generator** — the `svg.core` / `kotoba.lang.html` /
`kotoba.lang.css` sibling for LaTeX source text. `tex` turns a Hiccup-like EDN
AST into valid `.tex` source deterministically. Zero third-party runtime
deps; every namespace is `.cljc`, so it runs on JVM / SCI / ClojureScript /
GraalVM / kotoba-WASM.

**Scope: generation, not compilation.** This library does not run pdflatex,
compute font metrics, or lay out pages. It produces a `.tex` string; pipe
that to your own TeX toolchain (or a CI job) if you want a PDF.

## Canonical shape

Commands are `[:command-kw {opts} & args]`; each `arg` becomes its own
`{...}` group, and `:opt` in `opts` becomes a `[...]` group:

```clojure
[:section {} "Introduction"]                  ;=> \section{Introduction}
[:frac {} "1" "2"]                            ;=> \frac{1}{2}
[:documentclass {:opt "12pt"} "article"]      ;=> \documentclass[12pt]{article}
[:item {}]                                    ;=> \item   (no args -> no braces)
```

Environments are `[:env "name" {opts} & body]`; body children are rendered
and concatenated as siblings (not one-per-brace):

```clojure
[:env "itemize" {} [:item {} "a"] [:item {} "b"]]
;=> \begin{itemize}\item a\item b\end{itemize}
```

Plain strings are escaped automatically (`# $ % & _ { } ~ ^ \`); wrap
already-literal TeX source in `[:raw "..."]` (or `(tex/raw ...)`) to emit it
verbatim — this is how math-mode content stays unescaped.

## Current surface

`kotoba.lang.tex.core`:

- `render` — EDN node (or fragment) -> LaTeX string, deterministic
- `escape` — escape `# $ % & _ { } ~ ^ \` in a plain string
- `raw` — wrap a literal TeX string to bypass escaping
- `command` / `env` — generic escape hatches that build `[:name {} & args]` /
  `[:env name {} & body]` nodes for anything not covered by a named helper
- `document` — `\documentclass[opt]{class}` + `:preamble` commands +
  sibling `\begin{document}...\end{document}`
- `section` / `subsection` / `subsubsection` — with `{:star? true}` for the
  unnumbered `*` variant
- `item` / `itemize` / `enumerate` — list building (bare values are coerced
  to `item` nodes)
- `math` / `display-math` — `$...$` / `\[...\]` wrapping verbatim content
- `frac` / `sqrt` — `\frac{a}{b}`, `\sqrt{x}` / `\sqrt[n]{x}`
- `tabular` — `\begin{tabular}{colspec}` with rows of individually-escaped
  cells joined by `&` / `\\`

This is a focused surface, not an attempt to reimplement every LaTeX
package — reach for `command`/`env` for anything else.

## Install

```clojure
io.github.kotoba-lang/tex {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.tex.core :as tex])

(tex/render
  (tex/document {:opt "12pt" :preamble [(tex/command "usepackage" "amsmath")]}
                (tex/section "Introduction")
                "Body text with 50% done."
                (tex/itemize "first" "second")
                (tex/math "x^2 + y^2 = z^2")))
;=> "\\documentclass[12pt]{article}\\usepackage{amsmath}\\begin{document}
;    \\section{Introduction}Body text with 50\\% done.
;    \\begin{itemize}\\item first\\item second\\end{itemize}$x^2 + y^2 = z^2$
;    \\end{document}"
```

## Verify

```sh
kbb -M:test
```
