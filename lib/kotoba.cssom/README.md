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

## Q6 fixed-point block vertical (JUN-920 / C2b)

First vertical of the user-domain renderer (ADR-0287: fixed point, no floats, no records): the block-width, margin
collapse and style bridge, as scalar-`i64` canonical `.kotoba` modules next to their f64 oracles. Nothing is wired into
`cssom.layout` (`layout.cljk` is unchanged), and nothing was executed at CPL3; the verdicts below are native macOS
differential runs and AIUEOS compile verdicts.

| module (`src/cssom/`) | role | f64 oracle |
| --- | --- | --- |
| `length_q6` | Q6 / percent resolution, kinds, the one rounding rule | `length` |
| `parse_px_q6` | `[+-]number[px\|%]` scanner, **host-native only** (reads a string) | exact-rational golden table + f64 grid |
| `block_width_q6` | `solve-pick`, `solve-constrained-pick` (CSS 2.2 10.3.3 and 10.4), five packed words | `block_width` |
| `margin_collapse_q6` | positive / negative extrema in one `i64` | `margin_collapse` |
| `block_style_q6` | style lengths to solver, 13 inputs in five packed words | `block_style` |

**Scale and guards.** A length is a Q6 raw integer (1/64 px, the Blink `LayoutUnit` scale), `|raw| <= 2^30` (2^24 px);
a percentage is an integer count of hundredths of a percent, `|H| <= 65535`, so `H * basis < 2^46`. The f64 `finite?`
tests become these range guards; failure is the sentinel `-2^62`, never a plausible zero. The style bridge keeps lengths in
31-bit slots (`|px| < 2^21`). `padding + border` reach the solver only as their sum.

**Rounding rule (the Q6 specification; THE OWNER MUST CONFIRM IT).** Every division is one exact rational division rounded
half up, `floor(x + 1/2)` (toward +infinity, also for negatives: -2.5 becomes -2), the rule of the `Math/round` that
`layout.cljk` `percentage-of` uses. No float is involved, so an exact tie rounds up. Alternatives the owner may prefer:
half away from zero, half to even. Blink was not measured, so the rule is not shown to match a browser. The f64 oracle is
inexact at exact ties and is not copied: `29 %` of `50 px` is `14.5`, the oracle gives `14`, Q6 gives `15`. At most
6 fraction digits of a number are significant; further digits are truncated, not rounded (`0.0078125px`, an exact tie, gives 0).
The auto-margin half of an odd Q6 raw is split `floor` / `ceil` (left `>> 1`, right the rest), so left + right is exact; it differs
from the f64 oracle by 1/128 px.

**Tie report** (measured by `scripts/check-block-q6-native-macos.py`; a tie is `H * basis mod 10000 = 5000`):

| sweep | pairs | exact ties | oracle differs at a tie | oracle differs away from a tie |
| --- | --: | --: | --: | --: |
| Q6 results, grid through `cssom.length/resolve` | 343 resolved percent cases | 30 | 0 | 0 |
| Q6 results, 0.01 % steps 0..300 % x basis raw 0..2047 | 61,442,048 | 47,400 | 846 | 0 |
| integer px (`percentage-of`), integer percent 0..300 x 0..4096 px | 1,233,197 | 31,968 | 1,114 | 0 |
| integer px, 0.01 % steps 0..300 % x 0..4096 px | 122,914,097 | 99,348 | 7,391 | 0 |
| parser grid, 1,383 valid strings (12 percent ties, no px tie within 6 digits) | 1,383 | 12 | 0 | 0 |

The 1,114 and 7,391 reproduce the census (`kotoba.aiueos` evidence `cssom-port-census-20261106`); its denominator
`122,908,097` for the 0.01 % sweep is a miscount, 30,001 x 4,097 = 122,914,097.

**Differential grids** (all printed 42; every Q6 refusal was justified as an input outside the Q6 domain, an invalid
oracle, or an output at the range edge): block width 8,960,320 cases (unconstrained 2,799,360, constrained 5,160,960,
the census LCG sweep 1,000,000) with 3,509,376 compared, 2,428,864 justified refusals and 3,022,080 invalid on both sides;
the largest difference from the f64 module is 1/128 px; margin collapse 41,371 sequences exact; style bridge 1,008,000
cases, 192,000 compared, deviation at most 2/128 px (bound: percent terms + 1); scanner 81 golden strings and 1,680 grid
strings with 0 violations.

**AIUEOS size** (pinned `amu-full-root`, compile only, not run). The arithmetic core, without the string scanner, is 143
code lines (the four f64 oracles: 140):

| | kernel-v1 `.text` | user-v1 |
| --- | --: | --- |
| whole core, two-argument entry | 22,837 B | `E7102` detail 56 (entry shape: user-v1 takes a zero-argument entry) |
| whole core, zero-argument entry | 23,350 B | **`E7104` detail 22,998** (text limit 4,096 B: 5.6x over) |
| `length_q6` alone | 5,642 B | |
| `block_width_q6` alone | 9,753 B | |
| `margin_collapse_q6` alone | 2,344 B | |
| `block_style_q6` (with `length_q6` and `block_width_q6`) | 20,009 B | |
| six-parameter function (control) | `E7102` detail 1 (refused) | |
| the f64 oracles with a trivial `main` | `E2104` type mismatch (record values) | `E2104` |

About 160 B of kernel text per code line (the census prototype saw 170). So the f64 modules cannot be measured on these
targets at all and the Q6 form is the first that can; the whole block vertical is 5.6 times the user-v1 text cap.
The scanner (`parse_px_q6`) reads a string and is refused by the aiueos targets (`E7101` detail 16); an aiueos entry has to read
the request words (see the census prototype `px_parse_q6_user`).

**Not covered.** CPL3 execution, the wiring into `layout.cljk`, the other float groups (transforms, calc, colour, flex), the
half-up rule against Blink, and `parse_px_q6` on a user target.

Run the gate (macOS arm64, about a minute; no JVM, nbb or babashka):

```bash
python3 lib/kotoba.cssom/scripts/check-block-q6-native-macos.py \
  --amu /path/to/amu-cli.macho --amu-full-root /path/to/amu-full-root.macho --output /path/to/new-empty-dir
# prints PASS_NATIVE_CSSOM_BLOCK_Q6
```

## Test

```bash
kbb -M:test
```
