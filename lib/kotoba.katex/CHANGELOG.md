# Changelog

All notable changes to kotoba-lang/katex are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/). Semver per the
kotoba-lang stdlib compatibility policy (kotoba-lang/kotoba-lang/docs/lang/stdlib-versioning.md).

## [0.1.0] - 2026-07-01

Initial public release. A native, from-scratch TeX-math parser (v1 subset)
producing a pure EDN AST, plus a MathML renderer (AST -> MathML EDN -> XML
string). Not a wrapper/interop shim around KaTeX.js — zero third-party
runtime deps, JVM/cljs/GraalVM/kotoba-WASM portable via `.cljc`.

### Added

- `kotoba.lang.katex.parse` — recursive-descent parser: fractions,
  superscript/subscript (including combined `:supsub`), `\sqrt`/`\sqrt[n]`,
  grouping, common Greek letters, common operators/relations, numbers,
  identifiers, implicit adjacency, and an `:unknown` fallback node for
  unrecognized commands (never silently dropped).
- `kotoba.lang.katex.mathml` — AST -> MathML Hiccup-like EDN -> MathML XML
  string renderer.
- Tests covering parser edge cases (nested fractions, combined sup+sub,
  brace-less shorthand, unknown commands, malformed input) and renderer
  correctness (leaf/structural nodes, XML escaping, end-to-end round trips).
- CI and library scaffolding.
