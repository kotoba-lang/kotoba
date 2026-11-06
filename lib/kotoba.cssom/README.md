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

## Q6 fixed-point slice 3: flex, multi-column, style numbers, inline shifts, colour (JUN-920 / C2b)

Third slice of the same method (census groups G07 flex and multicol, G11, G09, G04; evidence `cssom-port-census-20261106`). Same
rules: scalar `i64`, at most five parameters, no heap, round half up (`floor(x + 1/2)`), failure is the sentinel `-2^62`, nothing
wired into `layout.cljk`, nothing run at CPL3. Built on the head of #1259 (slice 2, open when this was written).

| module (`src/cssom/`) | role | native f64 reference (new) |
| --- | --- | --- |
| `flex_q6` | `resolve-flexible-lengths` (grow / scaled shrink, min / max, freeze-and-redistribute), `place-main-axis` (all justify-content keywords), `place-main-axis-auto-margins` | `flex` |
| `multicol_q6` | `multicol-spec` column count, kept-fractional column width, `lay-w`, column pitch `dx`, rule position | `multicol` |
| `style_num_q6` (+ host-only `parse_d4_q6`) | opacity clamp / product / `(< opacity 1.0)`, flex factors | `style_num` |
| `inline_q6` | `vertical-align` `super` / `sub`, the `middle` box law and the inherited `middle` shift, `leading-ascent` | `inline` |
| `color_q6` | `unit`, rgb / alpha / percent tokens, `hsl->rgb`, the alpha product of `->rgba`, byte and u32 packing | `color` |

**Flex: the bounded line.** At most **four items per line** (`n = 1..4`), refused beyond (the caller splits or falls back; nothing
is truncated). The census suggested 8 or 16; four is what five scalar parameters of 63 bits can carry: the whole line has to
travel in five words because the target has no store, no vector and no sixth parameter (a six-parameter function is refused,
`E7102`, pinned below), and one item needs 70 bits (base 18, min 18, max 18, factor 16). Four items and the header use 300 of the
310 bits. Item `k` is one word `base | min << 18 | max << 36 | (factor & 255) << 54` (`item-word`; max field `262143` = no
maximum, min `0` = no minimum, which is what `(or min 0)` means in the source); the line word holds `net + 2^19`, `n - 1`, the
item to answer for, the grow bit, a pass counter and the high bytes of the four factors (`line-word`, `hi-bytes`,
`with-select`); `solve` returns the final size of the selected item. **Ranges that follow:** base, min, max below `262143` raw
(4096 px), factor 0..65535 D4 (below 6.5535), `net = avail - gaps` within +-524288 raw (+-8192 px), free space below `2^21` raw
(32768 px); outside them the encoders answer `-2^62`. The census proposed lengths to `2^30`; five words cannot carry that. The
justify and auto-margin placement has no item bound (it needs sums only: `offset(mi, container, total, gap, prefix)` with
`mi = mode + 8 safe + 16 n + 4096 i`, `n <= 255`).

**Flex: the solver.** The loop state of `layout.cljk` (`sizes`, `frozen`, `guard`) is rewritten into the words: a frozen item
gets `base := its clamped size` and `factor := 0`, and a zero weight *is* the frozen flag, because the source freezes exactly the
items whose weight is not positive. The source guard (`n` passes) cannot fire (every pass after the first freezes an item), so
the Q6 recursion has none; the f64 reference keeps it literally and it never fired in 2,500,000 comparisons (evidence, not a
proof). The share `R * weight / W` is one exact rational: floor and remainder by long division on 7-bit chunks of `|R|`, every
product below `2^44`, rounded half up once. **Found by the grid, kept as a spec point:** the freeze test must use the *exact*
proposal. Testing the rounded one let an item whose proposal was 99.994 against a minimum of 100 stay unfrozen and absorb 30000 raw
that another item gave back (30100 instead of 100). **Rounding of a line:** every item is rounded on its own, so the sizes of a
line need not add up to the free space (two items sharing 3 raw both get 2). The error is at most `n/2` raw. Largest-remainder
rounding (the census proposal) would conserve the sum; it is an owner decision and is not done here.

**Other scales.** Lengths Q6 raw, factors / opacity / numbers D4 (as slice 2), colour components **Q16** (0..65536 = 0..1, because
`color.cljk` produces unit fractions, not bytes: `unit` is the only byte, `(/ byte 255)`; 255 does not divide a power of ten) and
hue D4 degrees. `multicol_q6` takes lengths up to `2^24` raw and `n <= 255`; the whole-pixel results (`lay-w`, `dx`, rule `x`)
are multiples of 64 raw because the source applies `Math/floor` / `Math/round` there, computed from the exact rational (the
source multiplies the kept-fractional width by `k`, which the doubles do not round). `shift-keyword` is `(fs + 192)/3` and
`-(fs + 320)/5`: one rounding each. `color_q6` keeps a hsl channel within 1.56 raw of Q16 (2.4e-5 of full scale).

**Oracle method.** (1) The f64 references are native transcriptions of the `.cljk` semantics (`flex` keeps `sizes`, `frozen`,
`guard`, `settle` literally, one proposal per item, on doubles; the unused `quot` of the source is an exact half in `center`).
(2) The original `.cljk` still could not be loaded on this machine (slice 2 recorded the kbb / nbb failure as dated data); no
value of it is used. The transcriptions are validated against **hand-derived cases** from the `resolve-flexible-lengths`
docstring (the Brave 151 measurements of 2026-08-06, derived by hand from the algorithm: 150/50, 60/240, 200/50/50, 30/135/135,
30/40/230, 80/80, 140/60, 60/140, 50/250, the scope-cut shape 17.5/95/87.5, 147/7, and the 30/200/70 pair), from the `multicol`
comment (93.33 px columns, the third starting at 206.67 which rounds to 207), and from the CSS Color 4 primaries
(`hsl(0|60|120|180|240, 100%, 50%)`). (3) Q6 and the reference are compared on deterministic grids; oracle disagreements at ties
are reported, never copied.

**Grids and results** (macOS arm64, pinned compiler; every count is pinned in the gate):

| grid | cases | result |
| --- | ---: | --- |
| flex solver, 8 slices of 125,000 pseudo-random lines (1..4 items; bases 0, 1, 63, 64, 65 ... 262143; factors 0 .. 65535; 1,655,847 results sit on a min or max bound) | 1,000,000 lines, 2,500,000 items | 2,500,000 equal after half-up rounding, 0 ties, 0 other, max deviation 0.5 raw (the rounding itself) |
| `share` against the exact integer formula `floor((2 r w + W) / 2W)` | 5,520 | 0 violations, 59 exact ties |
| `offset` (6 modes x safe x up to 6 items, 4,000 lines) against `place-main-axis` | 168,264 | 0 violations, max 0.5 raw, 68 exact ties where the oracle differs |
| `auto-offset` against `place-main-axis-auto-margins` | 672,384 | 0 violations, 60 ties where the oracle differs |
| `multicol` count 11,466, `col-raw` 1,386, `lay-w` 73,728, `dx` 430,080, rule `x` 1,474,560 | 1,991,220 | 0 violations; 1,279 exact `dx` ties, the oracle misses 9; 90,513 exact rule ties, the oracle misses 12; 0 `lay-w` boundary differences |
| opacity product, all `a, b` in 0..10000 | 100,020,001 | 84,000 exact ties, oracle differs at 11,364 of them, **0 away from a tie**; clamp 50,001 and stacking 10,111: 0 differences |
| `parse-opacity` / `parse-d4` string table | 23 | 0 violations, 2 below-one adjustments |
| `shift-keyword` 80,002, `middle-box` 327,184, `middle-inherited` 682,864, `leading-ascent` 119,652 | 1,209,702 | 0 violations (the halves are exact in doubles: 163,592 and 341,432 exact ties, oracle never differs) |
| colour: `unit-byte` 256 (round trip to byte exact for all 256), 4 token grids 8,777 each, `final-alpha` 27,248, hsl 871,926 | 934,538 | 0 violations; max deviation 0.498 raw (unit), 1.560 raw (hsl, Q16); 31,048 hsl channels differ from `round(o * 255)` by one **only within 0.002 of a half** (exact gray `l = 50%` is 127.5: the doubles land on either side), 0 away from it |

**Not covered.** Flex lines of more than four items (and the `flex-wrap` line breaking, `layout-flex-wrap-row`); `flex-item-base-size`
(a `flex-basis` percentage is `length_q6` of slice 1 with the measured size as the `auto` fallback); `flex-main-clamp` (the
box-sizing conversion of the min / max declarations is integer-px addition with the already resolved insets, not ported);
`flex-item-min-content-width` and `flex-item-baseline` (text measurement, with the `half` of `(lh - (ascent + descent)) / 2` at
9546, which is `inline_q6/leading-ascent` for integer metrics); the `quot` sites of the integer-pixel policy (`cross-offset`
center `(quot ... 2)`, 5169 `center` in `place-main-axis`, 15458 / 15462 block centring, 15813 absolute centring, 17200 legend
centring: here `center` is an exact half, the source truncates a whole-pixel difference, **a behaviour difference**). Grid and
table sizing (`distribute-fr`, `distribute-equally-with-caps`, `table-column-widths`, `layout-table`, `layout-grid` `fr` tracks) are
not done: they distribute over an unbounded number of tracks / columns and need the same word-packing as the flex line with a
different loop each; they were left rather than bounded to a size that matches no page. `multicol-balanced-height` (binary
search over fragments), `frag-keep-orphans` and `frag-slice-ops` (`0.5` tolerances are comparisons, `y - 0.5 <= t` is
`y - 32 <= t`). Colour: the tokenizer, the 148-name table, `parse-css-double` (the `Double/parseDouble` grammar) and
`split-fn-args` are not arithmetic. `parse_d4_q6` accepts a decimal only: Java's `Double/parseDouble` also takes an exponent, an
`f` / `d` suffix, `NaN`, `Infinity` and hex floats, which answer `-2^62` there and fall back to the default - **a behaviour
difference**. G05 (transforms), G10, G13 untouched. No CPL3 run, no browser verdict, no wiring into `layout.cljk`, no comparison
with the original `.cljk`. D4 opacity is cumulative: each level of the tree rounds once (the source does not), so k nested
opacities can differ by k/2 raw of 1/10000.

**Doc / code mismatches found (reported, not edited).** (1) The census (section 2.2) estimates the G07 oracle bound at "<= 1 px per
item"; measured, the solver equals the exact rational rounded half up in all 2,500,000 comparisons (0.5 raw), so the bound is
1/128 px. (2) The census proposes largest-remainder rounding for G07; per-item rounding is used (spec: "round half up"), and
the sum is therefore not conserved (above). (3) The census proposes hue Q6 and s / l Q10 for G04; hue D4 degrees (a decimal
degree such as 0.1 is exact in D4 and not in Q6) and Q16 are used. (4) The census counts G04 as "3 float sites in
`color.cljk`"; the file has 3 *strong* hits but the arithmetic is `unit`, the channel and alpha clamps, `hsl->rgb`, and the alpha
product (about 9 lines of arithmetic), all ported. (5) The `resolve-flexible-lengths` docstring says its freeze-everything rule "gives
the same answer on every one of the eleven shapes above"; the table lists ten rows plus the 30/200/70 pair; all of them are
reproduced here (by hand derivation, not by running the `.cljk`), and the docstring's remark that `§9.7.4` freezes by the SIGN
of the total violation is a deliberate difference of the code from the specification, which the port follows. (6) In
`place-main-axis` the divisions `(/ free (dec n))`, `(/ free n)` are written `/` on possibly integer operands: on the JVM they
are ratios, in ClojureScript doubles; the port treats them as real division.

```bash
python3 lib/kotoba.cssom/scripts/check-flex-q6-native-macos.py \
  --amu /path/to/amu-cli.macho --amu-full-root /path/to/amu-full-root.macho --output /path/to/new-empty-dir
# prints PASS_NATIVE_CSSOM_FLEX_COLOUR_Q6
```

**AIUEOS size** (pinned compiler `amu-full-root.macho`, `x86_64-aiueos-kernel-v1` text bytes): `flex_q6` 26,743, `multicol_q6`
10,254, `style_num_q6` 6,288, `inline_q6` 7,012, `color_q6` 11,492; the five together (every export reached, two arguments)
43,993, zero-argument 44,234. `x86_64-aiueos-user-v1`: the two-argument entry is refused `E7102` (detail 96, the entry takes
arguments), the zero-argument core `E7104` (detail 43,882, the 4096-byte text cap), and each module alone `E7104` as well
(`flex_q6` 26,470, `multicol_q6` 9,945, `style_num_q6` 5,937, `inline_q6` 6,679, `color_q6` 11,183). A six-parameter function is
refused `E7102`. The flex solver alone is more than six times the user text cap.

## Test

```bash
kbb -M:test
```
