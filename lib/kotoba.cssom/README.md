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

## Q6 fixed-point slice 2: calc(), line-height and metrics, aspect-ratio and replaced sizing (JUN-920 / C2b)

Second slice of the same method (census groups G03, G06, G08; evidence `cssom-port-census-20261106`, merged with #1252). Same
rules as slice 1: scalar `i64`, at most five parameters, no heap, round half up, failure is the sentinel `-2^62`, nothing wired
into `layout.cljk`, nothing run at CPL3. Built on the head of #1255 (slice 1, still open when this was written).

| module (`src/cssom/`) | role | native f64 reference (new) |
| --- | --- | --- |
| `pack_q6` | two Q6 lengths in one `i64` (same packing as `block_width_q6`, which keeps its own copy) | |
| `calc_q6` | `calc()` / `min()` / `max()` / `clamp()` evaluator over a bounded postfix program | `calc` (transcribes `eval-calc-node`, core.cljk 977-1048) |
| `line_height_q6` | `resolve-line-height`, `(long (* m fs))`, descent, glyph advance, leading, marker advance, option height, tab stops | `line_height` |
| `aspect_ratio_q6` | `aspect-ratio-block-height` / `-width`, the `replaced-content-size` tables, intrinsic rounding | `aspect_ratio` |

**Calc: the bounded program.** The host parser (not ported) flattens the AST to a postfix program of at most **15 operations
and 4 operands**: `p0` holds one nibble per operation (1 push-number, 2 push-px, 3 add, 4 sub, 5 mul, 6 div, 7 neg, 8 min,
9 max, 10 clamp; a variadic `min`/`max` is a chain; `calc(x)` is `x`), `p1`/`p2` hold the four operands in push order. The
bound comes from the corpus: the largest expression in `core_test.cljk` / `cases.edn` is `max(min(8px, 12px), min(12px, 40px))`
(4 operands, 7 operations). The evaluator runs in two passes with no heap: a type pass over the nibbles (units, stack depth
at most 4, at most 4 pushes, exactly one value left) and a value pass whose stack is a shift register in two `i64`. **Beyond the
bound the program is refused** (`-2^62`, `-1` from `check`): a 16th operation (bit 60 set), a fifth push, depth above 4, a
stray end nibble, underflow, a leftover value, an unknown opcode, an operand beyond `2^30`, a unit violation, division by zero,
an intermediate beyond `2^30`, or a product with no factor below `2^16` raw. Nothing is truncated. Units follow
`eval-calc-node` (`+ - min max clamp` need equal units, `*` at least one plain number, `/` a plain non-zero divisor).

**Scales (a deliberate difference from the census proposal).** px is Q6; a plain number or a multiplier is **D4**, a decimal
with four fraction digits (1/10000), not the census's Q10. Q10 cannot hold `0.1`: `0.1 * 10px` would be 63.75 raw, and the
`long` truncation of the source would then lose a whole pixel the exact decimal gives (`(= (q6/mul-trunc 1000 640) 1)` in the
test). A percentage `H` (hundredths of a percent) is the same integer as a D4 multiplier (150 % = 15000 = 1.5). The cost: a
product needs one factor below `2^16` raw (6.5535) and the other within `2^30` (the `2^46` product rule enforced by the operand
ranges). Where `layout.cljk` applies `long` the result is integer px, not Q6 (`mul-trunc`, `resolve`, `leading-ascent`,
`block-height` / `-width` as multiples of 64 raw). The aspect ratio is an integer pair `(rn, rd)`, each 1..65535 (the census
said "keep the integer pair"); a ratio that does not fit is refused, never rounded.

**Oracle method.**
(1) The f64 references are native transcriptions of the `.cljk` semantics (`calc` is one function per AST node kind and is nested
by the test exactly as the parser would nest the tree, so the postfix words are checked against the trees too).
(2) **The original code could not be run on this machine.** `kbb` and `nbb v1.4.208` stop with `Can only recur from tail position`
while loading `cssom.layout` / `cssom.core`, and `kbb` fails on the repository's `deps.edn` graph; the command, tool versions and
output are recorded in `lib/kotoba.aiueos/90-docs/evidence/cssom-q6-slice2-20261106/oracle-attempt.txt`. So the transcription is checked
against **hand-derived cases**: the assertions of `core_test.cljk` `calc-probe` (24 expressions, flattened to postfix by hand) and the
Brave measurements quoted in the `layout.cljk` comments (leading points, tab stops, the 40x20 image, 3/1 and 120px boxes);
`evidence/.../hand-derived-cases.tsv` lists 33 with file and line. These were not executed against the original; they only agree
with the references and the Q6 modules. (3) Q6 against the references on deterministic grids, below.

**Differential results** (`scripts/check-calc-q6-native-macos.py`, about a minute, all verdicts 42, 0 violations):

| grid | cases | compared | justified refusals | both invalid | edge band (not judged) |
| --- | --: | --: | --: | --: | --: |
| calc: 34 shapes (postfix and tree), 16-value operand catalogue, 1..4 operands | 245,584 | 143,144 | 83,866 | 5,920 | 12,654 |
| line-height `resolve`: 3 kinds x 4 flags x 20 values x 15 font sizes x 7 themes | 25,200 | 19,488 (24 at a boundary) | 5,712 | | |
| aspect block height and width: 2 x 20 x 21 ratios x 10 insets, both directions | 16,800 | 9,088 (12 at a boundary) | 7,712 | | |
| replaced width / height tables | 5,760 / 7,680 | 4,526 / 5,804 | 1,234 / 1,876 | | |
| leading-ascent, marker, option height, tab stop (exhaustive small grids) | 1,139,727 iterations | all equal | | | |

A "justified refusal" is a Q6 refusal where the oracle accepts but an input is outside the Q6 domain, an intermediate or result
leaves `+-2^30`, or a product has no small factor; the grids fail if Q6 accepts what the domain forbids or refuses what it allows.
The edge band is a result within the rounding tolerance of `2^30`; those cases are counted, not judged.

**Maximum deviation** (half-raw units, `|2q - 2*scale*o|`; 1 = 1/128 px for a px result). Exact programs (add, sub, min, max, neg,
clamp, a lone leaf): **0**. One rounding (a `*` or `/`, then exact operations): **1.000**, the half-up bound. Two roundings in a
row: 7.446 (`(p*n)*m`), 7.437 (`(p/n)*m`), 10,000 (`(p*n)/d` with `d = 0.0001`), each inside the per-case bound
`1 + |factor|` or `1 + 1/|divisor|` that the test applies. Line height and aspect ratio have no tolerance: integer results are
equal, or differ by one px at a truncation boundary (below).

**Tie and boundary report** (the exact rule against the inexact f64 oracle; a tie is where the exact value is a half or, for
`long`, a whole number of px):

| sweep | pairs | ties / boundaries | oracle differs there | oracle differs elsewhere |
| --- | --: | --: | --: | --: |
| calc `px * number`, px raw -1024..1023 x D4 0..20000 | 40,962,048 | 31,504 | 805 | 0 |
| calc `px / number`, px raw -1024..1023 x D4 1..20000 | 40,960,000 | 17,416 | 542 | 0 |
| `(long (* m fs))`, 2-decimal m 0.00..5.00 x 1..256 px (the census sweep) | 128,256 | 6,716 | **183** | 0 |
| `(long (* m fs))`, D4 m 0..65535 step 7 x fs raw 0..4096 | 38,360,211 | 14,128 | 17 | 0 |
| `block-height` border-box, ratios 1..24 / 1..24 x 0..2048 px | 1,180,224 | 332,661 | 2,291 | 0 |
| `block-width` border-box, same grid | 1,180,224 | 332,661 | 2,475 | 0 |

The 183 reproduces the census count; the oracle is one px low where the double product misses a whole number (`0.29 * 100 =
28.999999999999996`, Q6 gives 29; `21 / (3/17)` is 118.99999999999999 in doubles, Q6 gives 119). Q6 is the exact value. Whether Blink agrees was not
measured; the half-up and truncation rules need the owner's confirmation as in slice 1.

**AIUEOS size** (pinned `amu-full-root`, compile only, not run). The slice-2 core is 140 code lines (`pack_q6` 6, `calc_q6` 54,
`line_height_q6` 36, `aspect_ratio_q6` 44) plus the 39 lines of `length_q6` they use:

| | kernel-v1 `.text` | user-v1 |
| --- | --: | --- |
| whole slice-2 core, zero-argument entry | 29,789 B | **`E7104` detail 29,437** (limit 4,096 B: 7.2x over) |
| whole core, two-argument entry | 29,662 B | `E7102` detail 66 (entry shape) |
| `pack_q6` alone | 1,425 B | accepted |
| `calc_q6` (with `length_q6`, `pack_q6`) | 16,833 B | `E7104` detail 16,482 |
| `line_height_q6` (with `length_q6`) | 9,788 B | `E7104` detail 9,467 |
| `aspect_ratio_q6` (with `length_q6`, `pack_q6`) | 12,251 B | `E7104` detail 11,939 |
| six-parameter function (control) | `E7102` detail 1 | |
| the three f64 references with a trivial `main` | `E2104` type mismatch (records) | `E2104` |

About 166 B of kernel text per code line (slice 1: 160). Each slice-2 module on its own already exceeds the user-v1 text cap
except the packing helper.

**Negative controls** (each makes the verdict print 7 and a violation counter positive): `calc_q6` product truncates (13 violations
in shape 4), unit equality dropped (199 in shape 19), operand cap removed (caught by the refusal programs); `pack_q6` bias off by one; `line_height_q6` truncation
replaced by rounding (62,480 non-boundary differences); `aspect_ratio_q6` truncation replaced by rounding (461,696); and one mutation
in each f64 reference (`calc` subtraction adds (210 in shape 3), `line_height` natural leading 1.3, `aspect_ratio` ratio inverted).

**Not covered.** The host parsers (calc tokenizer and precedence climbing, `line-height-multiplier`, `aspect-ratio` term parsing,
decimal text to D4 / ratio pair); a decimal with more than four fraction digits or a ratio term above 65535 is outside the domain.
The `%` leaf of a calc is resolved by the caller with `length_q6/percent-of` (slice 1) and pushed as px. `calc-result->number` (whole
results as integers, fractional as doubles) disappears in fixed point. The clamp functions between the two replaced-size tables,
`clamp-width` / `clamp-height`, and `resolve-width` (G02, partly slice 1). G06 sites not ported: `tab-stop-width` (type tower),
`text-lines` / `line-align-offset` (plain `quot`), `ua-control-font` (literal 13.3333 = 853 raw), `atomic-intrinsic-width`
(`Math/ceil` of host text widths), `inline-line-metrics`. G05 (transforms), G07 (flex), G04, G10, G13 are untouched. No CPL3 run,
no browser verdict, no wiring into `layout.cljk`, no comparison with the original `.cljk` (it did not load).

**Doc / code mismatches found (reported, not edited).** (1) `layout.cljk` 4858-4861, the docstring of `line-height-factor`, says
`resolve-line-height` still reads `150%` as `150 x font-size` through `parse-dbl`; the code (`line-height-multiplier`, 4767, and
4816-4818) divides a percentage by 100.0. The code is followed here. (2) The census table (`README.md` section 2.2) lists G08 as
"exact"; the exact integer pair is exact, but the hosted f64 code is one px low at truncation boundaries (2,291 / 2,475 of
332,661 in the sweep above). (3) The census proposes a Q10 multiplier for G03/G06; D4 is used (see Scales).

```bash
python3 lib/kotoba.cssom/scripts/check-calc-q6-native-macos.py \
  --amu /path/to/amu-cli.macho --amu-full-root /path/to/amu-full-root.macho --output /path/to/new-empty-dir
# prints PASS_NATIVE_CSSOM_CALC_LINE_ASPECT_Q6
```

## Test

```bash
kbb -M:test
```
