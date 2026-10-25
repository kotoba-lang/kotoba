# kotoba-lang/cssom

CSS Object Model for kotoba documents: selector parsing, cascade resolution,
and the reference box-model/layout projection to renderer draw ops.

Split out of `kotoba-lang/browser` (ADR-2607051140), where it lived as
`browser.css` (cascade) and, via `kotoba-lang/wasm-ui`'s
`kotoba.wasm.layout`, the layout projection. Both now live together here as
`cssom.core` and `cssom.layout`, since cascade and layout are one cohesive
"CSS engine" concern.

**Not to be confused with `kotoba-lang/css`**, an unrelated EDN-as-CSS-data
renderer (`{:rules [...]}` -> CSS text, Hiccup-style). This repo goes the
other direction: it parses CSS text and HTML-derived documents, not the
reverse.

- `cssom.core`: selector tokenizing/parsing (tag/id/class/attribute
  operators/pseudo-classes), specificity, cascade resolution
  (`apply-cascade`) against a `kotoba.wasm.dom` document.
- `cssom.layout`: projection from a `kotoba.wasm.dom` tree to renderer draw
  ops (rects/text/semantic node ops). A host can still replace it wholesale
  while keeping the same `draw-ops` data boundary.

## Maturity

The `cssom.layout` namespace docstring is the authority on exactly what is
and is not implemented, down to the individual property; this table is the
summary. **It was stale until 2026-08-03** — it claimed flexbox/position/
box-model were "not implemented" long after they landed, so trust the
docstrings over any prose that disagrees with them.

| | |
|---|---|
| Role | ui-substrate |
| Tests | `kbb -M:test` (497 tests / 1004 assertions) |
| Box model | padding/border/margin, min/max-width, `content-box`/`border-box` |
| Block flow | implemented |
| Inline flow | implemented (`layout-inline-run`) — text and inline-level elements share line boxes, wrap as one unit, collapse whitespace across fragments, share one baseline |
| Flexbox | `flex-direction`/`flex-wrap`/`justify-content`/`align-items`/`gap` |
| Grid | fixed/`fr` tracks, `repeat()`, `minmax()`, named areas, explicit + auto placement |
| Multi-column | `column-count`/`column-width`/`column-gap` (incl. `normal` = 1em and percentages)/`column-rule`/`column-fill`/`column-span: all`/`columns` — balanced, with a definite height spilling into extra columns. A block is never fragmented across a boundary (it moves whole); direct inline content breaks between its lines |
| Positioning | `absolute`/`fixed` (containing-block anchored, `z-index` ordered), `relative` (block-flow children only) |
| Generated content | `::before`/`::after`, implicit list markers, CSS counters |
| Hit testing | a `:node` op's box is what `getBoundingClientRect` reports; its optional `:hit` rect list is where a click lands, and the two differ for a wrapped inline box, for overflowing lines, and for table rows/row groups (which are never hit) — see `cssom.layout`'s ns docstring |
| Not implemented | `vertical-align` beyond baseline, inline padding/border/margin, block-in-inline box splitting, replaced elements (`<img>`/form controls) as inline-level, floats, real glyph shaping (a host supplies `:measure-text`, else a per-character approximation is used) |

## Test

```bash
kbb -M:test
```
