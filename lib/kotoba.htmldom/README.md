# kotoba-lang/htmldom

Small trusted-HTML-subset parser that bridges HTML-like markup into a
`kotoba.wasm.dom` document (`htmldom.core/parse-into-document`).

Split out of `kotoba-lang/browser` (ADR-2607051140), where it lived as
`browser.html`.

**Not to be confused with `kotoba-lang/html`**, an unrelated
Hiccup-compatible EDN HTML renderer (data -> HTML text, the standalone form
of the old `shitsuke.hiccup`). This repo goes the other direction: it parses
HTML text into a DOM tree, not the reverse.

This intentionally does not claim WHATWG HTML compatibility — it only
handles a small trusted subset (start/end/self-closing tags, void tags,
attributes, inline `style=`, and form-control default-value/default-checked/
default-selected initialization). See the `htmldom.core` docstring.

## Maturity

| | |
|---|---|
| Role | ui-substrate |
| Tests | `kbb -M:test` |
| WHATWG HTML compatibility | not a goal (trusted subset only) — **measured at 94% tree shape** vs a real headless Blink browser, see `conformance/` |

## Test

```bash
kbb -M:test
```

## Conformance

`conformance/` parses the same markup through this parser and through a real
headless Blink browser (Brave, over CDP) and compares the tree shape, so
"trusted subset only" is a number rather than a disclaimer. See
`conformance/README.md`.

```bash
kbb --backend sci --classpath "src:../dom-gpu/src:../cssom/src" conformance/run.cljk
```
