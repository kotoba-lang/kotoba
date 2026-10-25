# Conformance: cssom vs a real Blink browser

Differential testing against a real browser, because unit tests can only
check what someone thought to assert. This renders the same markup through
`htmldom` → `cssom.core` → `cssom.layout` and through a real headless
Brave/Chrome, and compares three axes: **line structure**, **geometry**,
and **computed style**.

```bash
kbb --backend sci --classpath "src:../dom-gpu/src:../htmldom/src" conformance/run.cljk \
  [--browser "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"] \
  [--width 800] [--only inline/] [--ledger path/to/ledger.edn] \
  [--debug-geometry] [--debug-style] [--debug-paint] \
  [--dump-ops path/to/ops.txt]
```

A second script drives one-off probes rather than the corpus:

```bash
kbb --backend sci conformance/probe.cljk <probes.edn> [browser]
```

where `probes.edn` is `[{:id … :html "…" :js "…"} …]`. Each probe is written
to its own file and opened in its own browser TAB — a fresh document, so one
probe's CSS structurally cannot reach another's markup. That hazard is real
and is described under "One probe page per probe" below; this is the fix for
it that does not depend on remembering.

`--dump-ops` writes every case's `:node` ops, in emitted order, to a plain
text file made to be `diff`ed between two commits. The scoreboard cannot
answer "did this change break anything" — it is four sums over 501 cases,
and a sum hides an exchange. This corpus has already been bitten by one: a
5/5 → 0/5 regression on the table group went unnoticed in a round where
three other cases improved by as much. Diffing two dumps names every case
whose boxes moved, in both directions.

`--dump-style` (added 2026-08-06) is the same instrument for the CASCADE,
and it exists because the ops dump cannot see the changes a cascade round
makes: round forty-nine's six nesting cases "are not in either list …
their divergence is a colour, which the ops dump cannot see". It writes one
line per DISAGREEING computed-style value under its case id, plus each
case's agree/total, so a case that starts or stops diverging on any
property — or stops being scored at all — is an added or removed line.

## Why line structure and not pixels

This engine has no glyph shaping — widths come from a
`(long (* 0.6 font-size))` per-character approximation unless a host
supplies `:measure-text` (see `cssom.layout`'s namespace docstring). Its
absolute coordinates therefore *cannot* match a real font's, and comparing
them would measure the approximation rather than the layout. What text
shares a line, in what order, and how many lines there are is what both
engines agree on when the layout is right — and it is exactly what this
engine got wrong for all inline content until 2026-08-03.

Both sides are measured **per word** (a `Range` per word in the browser,
draw-op text split by the engine's own width model on this side) and then
grouped into lines by the *same* vertical-overlap clustering function, so
neither side gets a grouping rule the other doesn't. Comparison is
whitespace-normalized and case-folded (`text-transform` genuinely rewrites
what this engine emits, while a browser upper-cases at paint time — both
are correct).

## Three axes

**Line structure** — what text landed on which line, in what order. This is
what the harness measured first, and it saturated at 93%.

**Geometry** (added 2026-08-04) — every element's own box, matched between
the two sides by tag and occurrence order and compared within 2px on all of
x/y/w/h. It exists because the line axis is blind to whole classes of
divergence: a `colspan` cell is alone on its row either way, a button's
label sits in the same line box whether it is centered vertically or not,
and an `<h1>` that renders at body size still lands on its own line. The
first geometry run scored **47%** on a corpus the line axis scored 93% on,
and its per-tag breakdown pointed straight at the causes.

**Computed style** (added 2026-08-04) — what `cssom.core`'s CASCADE
resolved for each element, against the browser's own `getComputedStyle`.
Both layout axes read only the *result* of the cascade through
`cssom.layout`, so selector matching, specificity, `!important`, layers,
custom properties and shorthand expansion were an entire unmeasured
subsystem: a cascade that silently dropped a declaration still lays out
*something*, and both older axes score the something. See "The
computed-style axis" below for its first run.

## Result — 2026-08-04

**Line structure: 248/280 = 89%. Geometry: 937/1138 element boxes (82%),
199/291 cases with every box in agreement. Computed style: 13779/15886
cascade-resolved values (87%), 285/291 cases with no mismatch attributable
to the cascade itself**, on a corpus of 292.

Two of those three numbers just fell, because the corpus grew 200 → 292 in
territory it had never entered. The before/after, so the drop is
attributable to coverage rather than to a regression in `src/`:

| axis | 200 cases | 292 cases |
|---|---|---|
| line structure | 184/190 = **97%** | 248/280 = **89%** |
| geometry (boxes) | 638/719 = **89%** | 937/1138 = **82%** |
| geometry (clean cases) | 166/200 = **83%** | 199/291 = **68%** |
| computed style (values) | 8537/9982 = **86%** | 13779/15886 = **87%** |
| computed style (cases clean of a cascade mismatch) | 197/200 | 285/291 |

The 291 denominators are 292 minus one case that produces no boxes and no
styles at all: `grid/row-span-two` makes `cssom.layout` **throw**, which is
its own finding and is described below.

`src/` was not touched between the two columns; 542 unit tests and the
linter are unchanged and green either side (0 failures, 0 errors; 0 lint
errors, 22 pre-existing warnings, all in `test/`). See "Round twenty-one"
below for what the 92 new cases found.

The computed-style figures are after the two shorthand bugs this axis found
on its first run were fixed — cascade-attributed mismatches 41 → 5, cases
clean of them 190 → 197. See "The 41 that were actually the cascade's".

That geometry number dipped to 85% on the round the font-metrics model
landed, which was the right trade at the time — see "the font-metrics
model" below — and has since come back up past the earlier 87%. A
percentage that falls when the corpus grows is the corpus doing its job:
the corpus has gone 32 → 98 → 105 → 150 → 200 → 292 cases, and every one of
those steps cost points that the following rounds earned back.

**The per-group table immediately below is HISTORICAL** — it is the
98-case run, kept because the prose around it refers to it. The current
per-group numbers are in the harness's own output.

| group | | |
|---|---|---|
| inline | 18/18 | 100% |
| inline-replaced | 8/8 | 100% |
| table | 9/9 | 100% |
| flex | 9/9 | 100% |
| box | 5/5 | 100% |
| page | 5/5 | 100% |
| inline-block | 1/1 | 100% |
| visibility | 2/2 | 100% |
| block | 7/8 | 88% |
| grid | 6/7 | 86% |
| wrap | 6/7 | 86% |
| text | 8/10 | 80% |
| position | 4/5 | 80% |
| float | 1/2 | 50% |

The seven remaining failures are all genuine gaps, now measured rather
than asserted: no float positioning, no `block-in-inline` split, `fixed`
anchored to its containing block rather than the viewport, grid
auto-placement not resuming after an explicitly placed item, one wrap
point inside a nested inline, and CSS-driven `white-space: pre-wrap`/
`pre-line` (the parser collapses newlines before layout ever sees them —
it cannot see CSS).

## The computed-style axis

### What it compares, and against what

Fourteen properties, chosen because each one has a normal form both sides
can be reduced to without guessing: `color`, `font-size`, `font-weight`,
`font-style`, `display`, `text-align`, and the four sides each of `margin`
and `padding`.

`getComputedStyle` returns the browser's **computed** value — cascade, then
inheritance, then defaulting from the UA stylesheet, collapsed into one
absolute normal form (`rgb(255, 0, 0)`, `"14px"`, `"700"`). This engine's
`:style/*` attrs hold only the FIRST of those three stages, in author-ish
form (`"red"`, `14`, `"bold"`). So each side is normalised per property
kind — colours parsed to `[r g b a]`, lengths to bare pixels (0.5px
tolerance, for the browser's fractional device pixels), `bold`/`normal` to
700/400 — and the two later stages are supplied on the engine's behalf,
**labelled** so every value's provenance is in the report:

| source | meaning | count, first run |
|---|---|---|
| `:direct` | the cascade wrote a value for this element. The only source this axis genuinely MEASURES. | 68 |
| `:inherited` | no value here, but an ancestor had one and the property inherits. Supplied by the harness walking up the engine's own document — exactly the `(or (:prop st) (:prop inherited))` fallback `cssom.layout` applies at paint time. | 709 |
| `:initial` | nobody in the ancestor chain declared it, so CSS's own INITIAL value stands. **Not** the browser's UA value. | 9205 |

That `:initial` row is the whole story of the number, and it was a real
architectural fact rather than nine thousand bugs: **this engine's UA
stylesheet lived in `cssom.layout`** (`node-style`'s `(or (style node :x)
<ua default>)` chains), so nothing reading the cascade's output —
`cssom.core/computed-style`, a devtools panel, a live page's
`getComputedStyle` — could see that a `<b>` is bold or a `<div>` is a block.

**Both halves of that sheet moved into the cascade on 2026-08-05
(ADR-2800003100), and this axis is now 100%.** The first half was the
declarations whose value is an absolute length or a keyword (87% → 97%,
layout byte-identical). The second was everything `em`-relative —
`p { margin: 1em 0 }`, `h1 { font-size: 2em }`, a fieldset's
`padding: 0.35em 0.75em 0.625em` — which needed the cascade to compute a
font size at all, since `em` resolves against the element's OWN computed
size and a font-size's own `em` resolves against its parent's. That landed
the axis at **18687/18763 (100%)**, `ua-default` 2123 → 557 → **35**, and
the cascade-attributed residual at **1**. What is left in `ua-default` is
not `em` and not a length: `<th>`/`<button>` `text-align: center`,
`<caption>`'s `-webkit-center`, and `<option>`'s padding — three UA rules
this engine does not have at all, which are new knowledge to be measured
against geometry rather than a move.

The axis reads the cascaded document directly and **never touches
`cssom.layout`**, so it shares no machinery with the geometry axis: a
layout bug cannot resurface here as a cascade bug. That is also why
elements are matched by tag + occurrence order rather than by the geometry
axis's nearest-box pairing.

### Every mismatch is attributed, not just counted

An 85% headline made of one repeated architectural fact would be unreadable
and would hide the handful of real divergences underneath it. So each
mismatch is classified against a **UA baseline measured in the oracle
itself** — a bare element of each tag, in the same font context, with no
author CSS anywhere near it:

| cause | first run | meaning |
|---|---|---|
| `ua-default` | 1407 | the engine declared nothing and the browser's value is exactly what its UA sheet gives that tag bare |
| `cascade` | 41 → **5** | the two sides disagree about a value the cascade is responsible for. **This is the bucket worth reading** |
| `blockified` | 23 | a `display` mismatch on a flex/grid item, a float, or an absolutely positioned box — real CSS blockifies all three at computed-value time |
| `ua-inherited` | 10 | the browser's value here is simply its parent's. Whatever diverged happened at an ancestor and is already scored there; charging it again at every descendant would multiply one cause by the depth of the tree |

The probe is measured rather than assumed for a reason: a bare `<a>` is
**not** a link, so probing without an `href` reported plain black and
charged all 19 link-colour divergences to the cascade. An `<input>` is
probed per `type`, because a checkbox's UA `margin: 3px 3px 3px 4px` is not
a text field's. `<td>`, `<li>`, `<option>` and friends are probed inside
the minimal legal ancestor chain they need to get their real UA style at
all.

`--debug-style` prints the whole cascade-attributed residual rather than
its head.

### The 41 that were actually the cascade's — both fixed

Two bugs, both invisible to 502 unit tests and to both layout axes, both
reproduced directly through the real pipeline. **Both are fixed; the
cascade bucket went 41 → 5 and cases clean of it 190 → 197.** What they
were:

- **An inline `style="..."` shorthand is not expanded into longhands.**
  `htmldom.core`'s inline-style declaration splitter expands `border`,
  `text-shadow`, `box-shadow` and `outline` — but not `margin`/`padding`,
  which `cssom.core`'s stylesheet path *does* expand
  (`expand-box-side-shorthand`). Two independent copies of the same idea,
  drifted. Measured: `.a { padding: 12px }` yields
  `{:style/padding 12, :style/padding-top 12, …}` (all five), while
  `style="padding: 12px"` yields `{:style/padding 12}` alone. Worse,
  `style="margin: 4px 8px"` is stored as the raw **string** `"4px 8px"`,
  which the per-side box model cannot read at all. 34 of the 41.

  **Fixed by deleting the second copy, not by adding margin/padding to it.**
  An inline `style="..."` *is* a CSS declaration block, so `htmldom.core`
  now hands the text to `cssom.core/parse-declarations-with-importance` —
  the same entry point a `<style>` rule body goes through — and its own
  ~330-line copy of the declaration parser (the `calc()` pipeline, five
  shorthand expanders, the value coercion, the `!important` regex) is gone.
  htmldom depends on cssom; cssom does not depend on htmldom, so there is
  no cycle. The drift was not confined to margin/padding either:
  `content`/`counter-reset`/`counter-increment` also meant different things
  inline than in a rule, and now do not.
- **Shorthand expansion runs BEFORE `var()` substitution.**
  `padding: var(--pad)` is not a length at declaration-parse time, so
  `expand-box-side-shorthand` correctly declines to expand it — and nothing
  re-expands it after `style-element` resolves the custom property. Result:
  `:style/padding 20` with no longhands. 4 of the 41.

  **Fixed by admitting a whole-token `var()` reference as expandable**, so
  each side carries the reference and substitutes independently. Expansion
  deliberately stays at declaration-parse time: re-expanding after the
  cascade merged would be simpler and wrong, because it would clobber a
  longhand that legitimately won by being declared later
  (`padding: 12px; padding-left: 0` and its reverse do resolve
  differently, and there is now a test that says so). The follow-on case —
  a custom property whose own value is a whole shorthand, `--pad: 4px 8px`
  — is re-sliced per side after substitution, which is the one place a box
  shorthand is legitimately re-read post-cascade.

Neither fix moved geometry (634/719 before and after, byte-identical
report). That is expected rather than disappointing: `cssom.layout` falls
back to the uniform `:padding`/`:margin` key when a side is missing, so a
one-value inline shorthand already laid out correctly. What was wrong was
the *computed style* — the values `getComputedStyle` actually reports, and
the ones a multi-value shorthand needs.

The 5 that remain are a different cause, not a residue of these two: four
are a `<p>`'s UA `margin: 1em 0` resolved against a font size the two sides
disagree about (`:cascade/inherited-font-size-chain`,
`:text/font-size-percentless-inheritance`), and one is a disabled
`<input>`'s UA text colour (`:form/disabled-input`).

### Excluded from comparison, explicitly

Nothing is dropped silently; every exclusion is counted, reasoned and
printed with its case ids.

- **`:element-count-mismatch` (70 values, 2 cases)** — the two sides
  disagree on how many elements of a tag exist, so there is nothing to zip
  the surplus against. Both cases are the same htmldom divergence:
  `<p>text <span>a <div>b</div> c</span> end</p>` nests the `<div>` inside
  the `<p>`, where HTML5's "in body" insertion mode auto-closes an open
  `<p>` on a block-level start tag. Not a cssom bug — recorded here because
  this axis is where it became visible.
- **Non-absolute lengths** (`1em`, `50%`, `auto`, a relative `calc()`) —
  the cascade legitimately holds the SPECIFIED value and resolves it at
  paint time against a font size and containing block it does not have
  here, while `getComputedStyle` reports the already-resolved used value.
  Comparing them would compare two *stages*, not two answers.
- **`lighter`/`bolder`** — relative to the parent's computed weight, a
  resolution step the cascade does not perform.
- **Colours neither side's parser recognises** — reported with the raw text
  rather than scored as a mismatch, because a value nobody parsed says
  nothing about who is wrong.

And three limits of the UA probe itself, which land in the `cascade` bucket
and are named here rather than tuned away:

- A UA value expressed in `em` (`p { margin: 1em 0 }`) scales with the
  element's own font size, so the bare-tag baseline only matches at the
  corpus's default 14px. 4 values, in the two cases that change the
  inherited font size.
- State-conditioned UA rules (`:disabled`, `:checked`) are not probed — the
  probe sets attributes, not states. 1 value (`form/disabled-input`, where
  Chrome greys a disabled field to `rgb(84, 84, 84)`).
- `ua-default` cannot distinguish "the engine's cascade has no UA sheet"
  from "the cascade dropped a declaration that happened to restate the UA
  value". Both look like *engine declared nothing, browser matches its own
  default*.

### Why the score is where it is, and why that is fine

85% on contact, with **0/200 cases fully clean** — no case in the corpus
avoids the UA-stylesheet divergence, because every case contains at least
one `<div>` or `<p>`. The actionable number beside it is **190/200 cases
with no cascade-attributed mismatch**, and the per-property table says the
same thing from the other direction: `display` is 134/713 = 19% (almost
entirely `inline` where the browser says `block`/`table-cell`/`list-item`),
while `font-style` and `text-align` are at 98%.

The number was not tuned to look better. Making it look better means either
moving the UA stylesheet up into the cascade — a real change to `src/`,
with real consequences for `getComputedStyle` consumers, and not this
harness's decision — or quietly excluding `display` and the margins, which
would be exactly the kind of measurement this corpus exists to prevent.

### What the geometry axis found in its first hour

- A table filled its container instead of shrink-wrapping to its columns
  (`width: auto` on a table is shrink-to-fit in real CSS). One decision put
  every `<table>`, `<tr>` and row-group box in the wrong place: table 0/9,
  tr 0/15.
- Row groups had no box at all — `<thead>`/`<tbody>`/`<tfoot>` were
  flattened away, so `tbody` scored 0/9 against a browser that has a box
  there.
- No UA stylesheet whatsoever: `<b>` was not bold, `<em>` was not italic,
  every heading rendered at body size. Authors never write those rules.
- `border-spacing: 2px` and `td { padding: 1px }` — Chrome UA defaults —
  were absent, which is exactly why a two-cell table measured 49x20 here
  against the browser's 59x26.
- `line-height: normal` was a flat theme constant rather than ~1.2x the
  font size, so an `<h1>` at 28px got a 20px line box and the next block
  painted on top of it. This one only became visible once headings had
  their UA size.

After fixing those: geometry 47% → 56%, td 6/29 → 21/29, tr 0/15 → 9/15,
table 0/9 → 5/9, tbody out of the worst-tag list entirely.

### Round two on the geometry axis (per-side box model)

The uniform-box-model ceiling is gone: `margin`/`padding` now expand to
four per-side longhands (real CSS's 1-to-4 value rule), so the UA
stylesheet's one-axis rules are expressible and applied — `p { margin: 1em
0 }`, heading margins from `.67em` to `2.33em`, `ul, ol { padding-left:
40px }`, `blockquote` side margins. `li` left the worst-tag list entirely.

Three further real rules had to follow, each one found by the oracle
disagreeing rather than by reading a spec:

- **Adjacent vertical margins collapse** to the larger of the two, not
  their sum. Without it every gap between paragraphs doubled.
- **A parent's first child's top margin collapses THROUGH the parent** when
  the parent has no top border or padding — which is why a browser puts the
  first `<p>` of a plain wrapper at the wrapper's own top edge, not 1em
  below it.
- **An inherited explicit `line-height` beats the `normal` floor.** The
  1.2em floor added last round is right for `normal`, but a container
  saying `line-height: 20px` means 20px for the 28px heading inside it too,
  however cramped — the engine reported a 33px box where Chrome reports 20.

And one plain bug the same work exposed: `layout-block` added a child's
margin AGAIN after the parent had already positioned it — a double count
that was invisible while every margin was zero.

Inline boxes now report the font's **content area** (~1.2em, centred in the
line box by half-leading) rather than the line box, matching what a browser
reports for a `<span>`/`<a>`/`<b>`.

### The bold-width mystery: the harness was wrong

`b` scored 0/11 and it looked like an engine bug. Measured directly in the
browser instead of assumed:

| | per character |
|---|---|
| `<b>manual</b>` as rendered | 7.94px |
| 40 `M`s, bold, same font/size | 11.05px |
| 40 `M`s, regular | 7.00px |
| plain text as rendered | 7.00px |

This system's `monospace` face is fixed-pitch in **regular** and
**proportional in bold**. The harness's single-character probe used `M` —
the widest glyph — so it overstated every bold run by ~40%. The engine was
being fed a wrong number and faithfully laying out to it.

The probe is now a **per-character advance table** (ASCII 32–126, normal
and bold) measured in the oracle and summed by `:measure-text`. b 0/11 →
4/11, a 3/12 → 8/12, td 21/29 → 23/29, and one line-structure case
recovered as well.

The lesson is the one the loop keeps teaching: measure before attributing.

### Then: a real box-model bug the axis exposed

`div{width:300px;padding:16px}` reported 300px wide with 268px of content,
where a browser reports 332 and 300. This engine read a declared `width` as
the BORDER box in both modes; real CSS's default `box-sizing: content-box`
means it is the CONTENT width and padding/border add outside it. Fixed —
with the theme's own decorative padding deliberately excluded from that sum,
since it is a host styling choice and not CSS.

`<br>` also had no box at all (0/4); it now reports the same content-area
box every other inline element does.

### Reading the tail by DIMENSION, not by case

The harness now reports, per tag, WHICH of x/y/w/h disagrees, how often,
and the median delta. A tail is far easier to attribute from "always `w`,
always −750" than from a list of failing case names. Three causes fell out
of one run:

- **`div w −750`, `x −389`**: a form control as a flex item took the whole
  container. Intrinsic sizing lived only on the inline path; it is now
  shared, so an `<input>` is ~153px wherever it appears rather than 800.
- **`p h +8`, `p y +12.25`**: a harness asymmetry, not an engine error.
  The browser page sets `line-height: 20px` on the case container and the
  engine was never told, so it applied its own `normal` (1.2em) rule and
  gave an `<h1>` a 33px line box where the browser inherits 20. The engine
  wrapper now carries the same declarations.
- **`td`/`tr w +730`**: `colspan` was not implemented. A spanning cell sat
  in ONE column, making that column as wide as the spanning content. Now a
  spanning cell widens the columns it covers only if they cannot already
  hold it (sharing the shortfall), and is laid out across them plus the
  border-spacing that no longer separates anything. That case went from 1/7
  boxes in agreement to 7/7.

### Round three: the deltas name their own causes

With per-dimension deltas attributed to case ids, three more fell out:

- **A space belongs to the run that contains it.** The gap in
  `a <b>b</b>` is a space in the PARAGRAPH's font; this engine charged the
  *following* fragment's font, and since this system's bold face is
  proportional (3.88px space against the regular 7.00px), every following
  inline box landed ~3px left of where the browser draws it.
- **`display: flex` is a BLOCK-level flex container.** It fills its
  containing block; only its ITEMS shrink-to-fit. This engine shrink-wrapped
  the container, so a row of three one-character items was 21px wide where
  a browser reports 800 — and `justify-content` then distributed space
  inside that 21px box. Ten boxes, all of them scored as passes by the line
  axis.
- **The explicit-line-height flag was dropped on the way into inline
  boxes**, so a larger inline inside a declared `line-height: 20px` grew
  the line box to 1.2 × its own size instead of overflowing it the way a
  browser does.

### Round four

- **`justify-content` had no free space to distribute.** The main-axis size
  it centres within was the sum of the items, not the container's content
  width, so `justify-content: center` pinned every row hard against the
  left edge (items at x=0,7 where the browser centres them at 393,400).
- **An absolutely positioned box with `width: auto` is shrink-to-fit**, not
  fill-the-container: a corner-pinned label measured 800px against the
  browser's 21, covering the whole row it was pinned over.
- **Mixed inline content has a max-content width.** `go <b>now</b>` in a
  table cell fell back to the container width, so a two-cell table filled
  800px where a browser shrink-wraps to 72. Computed by reusing the inline
  fragments and tokenizer, so whitespace collapses exactly as it will when
  the run is really laid out.
- Harness: **italic is a third face.** This system's `monospace` is
  fixed-pitch in regular but proportional in BOTH bold and italic, so an
  `<em>` measured 7.0px/char here against the browser's 10.28.
- Harness: **boxes are matched by nearest, not by index.** The browser
  lists elements in document order while this engine emits draw-ops in
  PAINT order, so an absolutely positioned box (painted last) lined up
  against the wrong sibling and reported two mismatches where the boxes
  were identical.

### Round five, and where the line-box story stops

- **A line box's height comes from the line-heights on it, not the font
  sizes.** Real CSS lets a larger run OVERFLOW a line box its declared
  `line-height` made too small; this engine grew the box instead. An atomic
  inline is the exception — a replaced box cannot overflow its line, and a
  browser does grow the line to fit it.
- **A trailing `<br>` leaves no empty line box.** `<p>line<br></p>` is 20px
  tall in the browser; this engine produced a second, empty 20px line.

What this axis can no longer decide without new machinery: the browser
positions each inline box by the font's REAL ascent and descent and takes
their union, so `small <span style="font-size:24px">big</span>` gets a 24px
line box where the line-height rule alone says 20. Same for `<sub>`/`<sup>`,
whose vertical shifts are font-relative. This engine models no ascent or
descent at all — every inline box is approximated as 1.2em centred by
half-leading. Closing those cases means adding a font-metrics model (real
ascent/descent per face, measurable by the same probe that already measures
advances), not tuning constants until one browser on one machine agrees.
That is a deliberate stopping point, recorded rather than fitted.

### Round six: the last two structural gaps on the line axis

- **Grid auto-placement shares its cursor with explicitly placed items.**
  `<div style="grid-column: 2">right</div><div>next</div>` in a two-column
  grid put `next` beside and BEFORE the explicit item; a browser wraps it to
  the next row, because the cursor is already past column 2. The cursor now
  walks every child in DOM order and only ever moves forward.

- **Whitespace collapsing is a CSS decision, not a parser one.** The parser
  collapsed newlines along with spaces, which destroyed the information
  `white-space: pre-line`/`pre-wrap` need before layout ever ran — both were
  permanent failures for a reason no amount of layout work could fix.
  kotoba-lang/htmldom now keeps newlines (collapsing only space/tab runs)
  and cssom.layout collapses them for `normal`/`nowrap`, per the declared
  property. Both modes now match the browser. (Round forty-two finished
  the sentence: the space/tab half was a CSS decision too, and the parser
  now collapses nothing at all.)

### Round seven: floats

`float: left|right` is implemented, bounded and documented rather than
pretended: a floated box is blockified, taken out of the inline run, placed
against its container's edge, and NARROWS the content beside it for its own
height. Before this there was no float concept at all — a right-floated
badge sat at the START of the text (x=0 against the browser's 233 in a 240px
box). Three corpus cases were added (a tall float with text wrapping beside
it, two left floats side by side, and a left plus a right float); all three
agree with the browser on both axes.

Not implemented, and named: floats that appear AFTER other content in their
container (v1 places floats at the container's top, the shape real markup
almost always uses), floats stacking vertically when they do not fit side by
side, and `clear`.

### Round twenty-two: the float band, and all three of round seven's exclusions

Round seven's three named exclusions are gone, and so is the fourth thing it
did not name (a float's own margins). Every number below was read out of a
real headless Brave 151 over CDP first — one isolating shape per behaviour,
each wrapped in its own `overflow: hidden` box, because floats leaking
between probe cases moved a float from x=0 to x=80 and another from y=0 to
y=28 before the wrappers went on.

Measured against the main this landed on (`3cace9b`, i.e. with the flex
round already in): line **255 → 263 / 280**, geometry **981 → 995 / 1142**
(220 → 228 cases fully clean), paint order **6978 → 7006 / 7285** (239 →
244 cases fully clean), float group **9/13 → 13/13**, page **24/28 →
27/28**. Eight cases went red to green and none went the other way.
Computed style is unchanged, as it should be: the only cascade-facing part
of this round is that `clear` is now read at all.

The v1 band was one `{:h :left :right}` rectangle pinned to the container's
top. It is now a list of placed float MARGIN boxes and three pure functions
over them — `float-band` (the `[left right]` edges on a scanline),
`float-clearance-y` (the lowest bottom edge on a cleared side),
`place-float` (CSS 9.5.1's placement: never above the flow position or an
earlier float's top, pushed down until the band is wide enough). Every float
rule in the file is now stated in terms of those three.

| what changed | browser | before | after |
|---|---|---|---|
| two 120px floats in 200px | (0,0) (0,20) | (0,0) **(120,0)** | (0,0) (0,20) |
| `float:left; margin:10px` | (10,10) | **(0,0)** | (10,10) |
| a float written after a `<p>` | y=34 | **y=0** | y=34 |
| `clear:left` past a 40px float | y=40, container 64 | **y=20, container 40** | y=40, container 60 |
| `clear:both`, floats 30 and 50 tall | y=50 | **y=0** | y=50 |
| plain `<div>` holding only a float | 200×0 | **200×60** | 200×0 |
| the same div, `overflow:hidden` | 200×60 | 200×60 | 200×60 |

Four findings worth keeping:

- **Containment and margin-collapsing are different questions.** The engine
  had one `fc-free?` flag doing both. `border-width` stops a margin
  collapsing through an edge but does NOT establish a formatting context, and
  `display: flow-root` — which exists for no other purpose than to establish
  one — was in neither list. Splitting them fixed
  `display/flow-root-establishes-a-context`, which had been failing for the
  margin half while passing the containment half by accident (the old code
  contained every container's floats unconditionally).
- **A float must be transparent to inline grouping.** It is blockified, so it
  never joins a line box — but leaving it in the sequence `inline-runs`
  partitions splits `text <float> more` into two one-child runs on two lines,
  where every browser keeps them on one. Floats are lifted out, the rest is
  grouped, and each float is put back in front of the entry its following
  sibling landed in. That re-insertion is also what lets a float be placed at
  the flow position it was WRITTEN at rather than hoisted to the top.
- **A float that escapes keeps rising, and only the paint-order axis
  noticed it did not.** The first cut of the containment rule asked each
  container about its own direct float children, which gets the clearfix
  wrong the moment the `overflow: hidden` box is not the float's own
  parent — `<div overflow:hidden><div width:200px><div float>` left the
  outer box 0px tall instead of 60. Floats a box does not contain are now
  returned as `:float/escaped` and carried up by `layout-block`, the same
  journey `:margin/collapsed-top`/`-bottom` already make, and they join
  the receiving container's band rather than being a height contribution
  bolted on the side — so they narrow its lines, push its later floats
  down and answer its `clear`s. Worth recording HOW this was caught: the
  geometry axis was happy (it compares each box against the browser and
  those boxes are the ones the corpus samples), while the paint-order axis
  landed all 25 of that case's sample points on nothing at all. "What
  would a user click" answering `none` for a page that visibly contains a
  float is a failure the other three axes had no way to express.
- **`page/hero-with-floated-image` was the harness, not the engine.** It
  reported `got []` — an empty line structure for a page that rendered
  correctly. `engine-lines` skips text inside a replaced box geometrically
  (draw-ops carry no parentage) and its rectangle test had the right and
  bottom edges INCLUSIVE, so the headline at x=80 counted as "inside" the
  80px `<img>` it was flowing beside and all three lines were discarded. A
  float is the one construct that reliably puts text at exactly a replaced
  box's right edge. Making those two edges exclusive — a point on a box's
  right edge is adjacent to it, not in it — also fixed
  `page/article-with-figure` and `page/login-form`, which is the evidence
  that it was a real bug in the proxy and not a fix aimed at one case.

**Still not implemented, and named:** the band is consulted by the line boxes
of the float's OWN container only. `layout-node` does not carry a float
context into a child, so a block DESCENDANT lays its lines out at full width
where a browser narrows them. Border boxes — what the geometry axis compares —
are unaffected either way; what this costs is a wrap point in text long enough
to break. Pinned by
`a-float-narrows-its-own-containers-lines-and-not-a-descendants` so it stays a
recorded cut rather than a silent wrong answer.

Three smaller ones, all pinned by tests too: clearance does not suppress the
cleared box's own margin collapsing; `float-band` is queried at a line's top
scanline rather than over its full height (a run gets ONE content width from
`layout-inline-run`, so a paragraph that starts beside a float keeps the
narrow width for the lines continuing below it); and whether a LONE inline
child flows as a run — and so consults the band at all — is decided before
the loop from whether the container has a float CHILD, so a lone text child
beside a float that ROSE from a descendant is not narrowed. Deciding that one
correctly means re-deriving the formatting-context rule recursively over the
whole subtree before laying anything out, for a shape the corpus does not
contain.

### Round twenty-three: grid flow, track sizing and item alignment

Every gap round twenty-one recorded under "Grid: one crash, and
flow/gap/alignment" is closed except the crash, which round nineteen had
already fixed. Each behaviour was read out of a real headless Brave 151 over
CDP *before* it was written — three probe rounds of isolating shapes, not
one — because none of these rules is derivable from the spec text alone.

The one that had to be measured to be believed is `auto` track sizing. A
browser gives an `auto` track its items' **min-content** width as a floor and
their **max-content** width as a growth limit, and then shares whatever is
left **equally** — not proportionally. `grid-template-columns: auto auto` in
a 400px grid holding `short` (max-content 41.625) and `a much longer cell`
(145.312) comes out **148.156 / 251.844**: each track's own content plus
exactly half of the 213px leftover. Proportional distribution would have
given 85 / 315, and both numbers sum to 400, so a corpus case checking only
"do the tracks fill the container" would have passed either. The equal share
is also what makes the narrow case work: at 200px the same two tracks are
48.156 / 151.844, because `short` freezes at its max-content, its unspent
share moves to the other track, and only the remainder is shared. And at
60px they are 41.625 / 50.141 — the min-content floor, overflowing the box
rather than crushing the words.

Two more that a guess would have got backwards:

- The stretch step does **not** run when an `fr` track is competing for the
  same space. `auto 1fr` leaves the auto track at exactly 41.625; `auto
  100px` stretches it to 300.
- Auto **rows** stretch the same way against a definite container height.
  `grid-template-rows: 30px` with three items in a 200px-tall grid is
  **30 / 85 / 85** — the explicit track keeps its size and the two implicit
  rows share the rest. But `auto 1fr` is 20 / 180, the same fr rule.

`grid-auto-flow: column` is the row-major algorithm with the two axes
swapped, so it is implemented by transposing the placement request on the
way in and the placement on the way out rather than by a second placement
engine; the bounded axis becomes the ROW track count (1 when no
`grid-template-rows` is declared) and columns become the axis that grows
implicit tracks. Measured: three items with `grid-auto-columns: 70px` sit at
x=0/70/140 on one row, and adding `grid-template-rows: 30px 30px` makes the
second item go DOWN rather than right.

`justify-items`/`justify-self` and `align-items`/`align-self` are a **size**
decision before they are a position one: `stretch` (the initial value) fills
the track, and anything else makes the item fit-content and places it
inside. A one-character item in a 120px column is 9.2px wide at x=55.4 under
`center` — an engine that only computed the offset and left the item
track-width would have centred a 120px box in a 120px track and moved
nothing.

One bug, and it is a placement bug rather than a sizing one: an item with a
definite **row** was moving the auto-placement cursor. CSS Grid §8.5 runs
that cursor in step 4, which only ever sees items with a definite COLUMN or
none at all — an item locked to a row is placed in step 2 and never touches
it. `<div style="grid-row: 2">t</div><div>b</div>` in a two-column grid puts
`b` at row 1 column 1 in a browser; this engine advanced the cursor past `t`
and put them on the same row, which the line axis reported as
`want ["b" "t"] got ["t b"]`.

`display: inline-grid` joins `inline-flex` on the inline path now that
`layout-grid` has the shrink-to-fit branch that set was waiting on: an
inline-level grid is its tracks' max-content sum plus the gaps between them,
so a two-30px-track grid in a sentence is 60px wide and the sentence stays
one line instead of becoming three.

`row-gap`/`column-gap` and the two-value `gap: <row> <column>` are resolved
in `node-style` rather than in the cascade, which loses one thing and says
so: declaration ORDER between the shorthand and a longhand. `row-gap: 24px;
gap: 5px` — where the later shorthand should reset the longhand — still
reports 24.

Named, still not implemented: `justify-content`/`align-content` on the
container (tracks are always placed from the start edge, which is also why
the `auto` stretch step runs unconditionally — an authored
`justify-content: start` should suppress it and cannot be told apart from
the default here), implicit COLUMN creation in row flow (an out-of-range
`grid-column` is still clamped, so `grid-auto-columns` only reaches the
tracks `grid-auto-flow: column` creates), a spanning item's contribution to
the intrinsic size of the tracks it crosses, and `min-content`/`max-content`/
`fit-content()` as track keywords.

Fourteen corpus cases were added for the shapes that had no case of their
own — the `auto` floor and the two `auto`-versus-`fr`/`fixed` interactions,
`justify-items: end`, `justify-self`, `align-items: end`, `align-self`,
column flow with explicit rows and past an explicit template, the two-value
`gap`, `grid-auto-rows` past the template, implicit rows against a definite
height, an auto row beside an fr row, and an inline-grid with auto tracks.
All fourteen were measured first and all fourteen pass. The grid group is
**37/37 on the line axis with 136/136 boxes**.

Corpus-wide: line 280/301 → **289/301**, geometry 1032/1214 →
**1086/1214** (234 → **256** clean cases), paint order 7499/7805 →
**7539/7805**. Twenty-two cases improved on geometry and none regressed.

### Round twenty-four: intrinsic width, and the viewport a fixed box belongs to

Two gaps, one of them the largest single number the geometry axis was
reporting.

**A shrink-to-fit box took the whole container whenever its content was
not a shape the intrinsic sizing recognised.** `flex-item-main-width` —
which despite the name is *every* shrink-to-fit width in the engine (flex
item, grid item, table cell, inline-block, all through `measure-child`) —
recognised a single text child, an all-inline run, an empty box and a
single element child, and ended with `:else content-w`. Everything else
swallowed its container. Two corpus cases were sitting on that fallback
with `td` **+761px** and `tbody` **+755px**, and they had two different
causes underneath one symptom:

- **An absolutely positioned child.** `<td style="position:relative">
  <span style="position:absolute">abs</span>cell</td>` has two children,
  and the absolute one is (correctly) not an inline-flow candidate, so the
  cell was neither all-inline nor single-element. Real CSS excludes
  out-of-flow boxes from intrinsic sizing outright — measured in Brave, td
  is **30**, the width of `cell` alone. Same for `fixed`: a
  `position: fixed` div in a cell leaves the cell **9** wide.
- **Block children.** `<td><ul><li>one</li><li>two</li></ul></td>` and
  `<td><div>alpha</div><div>bb</div></td>` are block containers, whose
  max-content width in real CSS is the **widest** of their children's,
  with each maximal run of adjacent inline children forming one anonymous
  block measured on a single line. Measured in Brave: 63 and 37.

Both are implemented (`intrinsic-flow-children`,
`block-max-content-width`), and two things fell out of doing it that the
old fallback had been hiding:

- **A child's horizontal MARGINS are part of its contribution.**
  `<td><blockquote>q</blockquote></td>` is **89** in Brave — the UA
  `margin: 1em 40px` is 80 of it — where the single-element rule this
  generalises measured the border box alone and said 9.
- **The intrinsic path and layout disagreed about what the children
  ARE.** A `<ul>` was measured from its bare `<li>` text and then laid out
  with the `• ` marker `with-implicit-list-markers` adds, so every item
  came out 14px wider than the box it had just been given and wrapped to
  two lines. Both now go through one `laid-out-children`.

**`position: fixed` is anchored to the viewport, not to an ancestor.**
It already left the flow correctly; what it did not do was escape its
ancestor. Measured in Brave on a probe page shaped like this corpus (800px
cases, 756px viewport): a `left: 0` fixed box inside a `margin-left: 120px`
wrapper is at **x=0**, not 120; `left: 10px` is at **10**, not 130;
`left: 50%` is at **378** = half the *viewport*, not half the 200px
wrapper; `right: 0` is at **749** = 756 − 7. `draw-ops` now assembles a
viewport from its own `:x`/`:y`/`:width` (plus a new optional `:height`)
and `layout-absolute-children` resolves a fixed box's offsets against it.
An offsetless fixed box still uses its static position, which is what
Brave does too (measured x=40 inside a `margin-left: 40px` container).

**This harness cannot score the block axis of a fixed box, and says so
rather than pretending.** Every case shares one long scrolling page and a
fixed box is measured against the viewport, so the browser's answer for
its `y` relative to a case is `-(that case's distance from the viewport
top)` — measured **−47.84** for `:position/fixed-leaves-flow`, **0** if
the same case is placed first on the page, and a different number again as
soon as a case is added above it. No engine behaviour can agree with a
number that moves when an unrelated case is inserted. So that case keeps
one permanently disagreeing box (3/4), **no new `fixed` case was added**,
and the inline-axis behaviour is pinned by unit tests against the measured
Brave numbers instead. The same measurement rules out the other case that
suggested itself — an absolutely positioned box in a cell with *no*
positioned ancestor, which Brave anchors to the initial containing block
and reports at **y=−304**, i.e. this case's own offset down the page.

Three cases were added that ARE honest — `:table/cell-holding-two-blocks`,
`:table/cell-holding-a-block-with-margins`,
`:flex/item-with-an-absolutely-positioned-child` — and all three agree with
Brave on **every box, exactly**, on first contact.

Corpus-wide, 313 → 316 cases: geometry 1120/1212 → **1142/1229**
(267/313 → **271/316** clean), paint order 7575/7805 → **7693/7880**,
line 297/301 → **300/304**, computed style 14782/16964 → **14984/17202**.
Five cases' boxes changed and **none regressed**;
`:position/absolute-inside-table-cell` went 1/6 → **6/6**.

The one that did not move: `:table/cell-with-a-list` is still 0/8, but
every box is now the right shape and **13.7px** too wide instead of
**+769**, and the whole residual has one named cause — this engine paints
an `<li>`'s marker inside the item's own line, where a browser's
`list-style-position: outside` puts it in the list's padding and leaves it
out of the item's width. That property is named as out of scope in
`with-implicit-list-markers`, and the honest fix is that property, not a
wider cell.

### Round fifty-three: the form-control cluster, and the cross-repo half round fifty-one had to revert

Round fifty-one ended with a fix it had written, measured and then thrown
away:

> **`:read-only` is not a second list, it is `(not :read-write)`** … it was
> written, and it passed, and the corpus went green on three more cases.
> It is not in this round, and the reason is not doubt about the
> measurement. **`:read-only` and `:optional` are consumed by
> `kotoba-lang/browser`'s `query-selector`, and that repo's suite asserts
> the answers this engine gives today.**

This round lands both halves. Every expected value was re-measured from
scratch in a real headless Brave 151.1.93.129 over CDP on 2026-08-06, one
probe page per probe, through `Element.matches()` rather than through a
colour — so the browser's own selector engine answers, and this side is not
also relying on being right about the cascade.

| axis | before | after |
|---|---|---|
| line structure | 800/805 | **800/805** |
| geometry (boxes) | 2676/2714 | **2688/2714** |
| geometry (clean cases) | 812/835 | **818/835** |
| paint order (points) | 20767/20837 | **20780/20837** |
| paint order (clean cases) | 816/834 | **818/834** |
| computed style (values) | 38166/38191 | **38175/38191** |
| computed style (cases clean) | 817/835 | **825/835** |
| cascade-attributed residual | 17 | **9** |

**`--dump-ops` diffed corpus-wide: exactly six cases' box lists changed,
every one of them TO the browser's number, and the other 829 are
byte-identical. `--dump-style` diffed as well, because a cascade change is a
colour the ops dump cannot see: exactly eight cases changed, every one of
them from a divergence to full agreement, and no case lost a value.**

| case | base | after | Brave |
|---|---|---|---|
| `:form/read-only-matches-a-disabled-input` | input x 0, 153 | **30, 183** | 30, 183 |
| `:form/default-on-a-checked-checkbox` | 4, 24 | **30, 50** | 30, 50 |
| `:form/indeterminate-on-a-radio-group-with-none-checked` | 5, 26 | **30, 76** | 30, 76 |
| `:form/indeterminate-on-a-progress-with-no-value` | progress x 0, 140 | **30, 170** | 30, 170 |
| `:form/in-range-and-out-of-range` | input 153 wide at 0, 153 | **42 at 0, 42** | 42 at 0, 42 |
| `:form/in-range-does-not-match-a-disabled-control` | 153 at 0, 183 | **42 at 0, 72** | 42 at 0, 72 |

The style dump's eight are those six minus the two `:in-range` ones (whose
divergence was a box and not a value), plus
`:form/read-write-matches-a-contenteditable`,
`:form/required-still-matches-a-disabled-control`,
`:form/placeholder-shown` and `:form/default-on-the-first-submit-button`.

#### One predicate, and the row the previous round's table got wrong

`user-alterable?`: a text-entry control that is neither `readonly` nor
`disabled`, OR any element in an editable `contenteditable` subtree.
`:read-write` is the whole of it and `:read-only` is the complement, which
is what puts a `<p>`, a `<button>`, an `<option>`, a `<legend>`, a
`<progress>` and a `<fieldset>` all in `:read-only` — measured, all six.

The two halves do **not** compose, and that had to be measured rather than
assumed. Inside a `<div contenteditable="true">`, a `readonly` input and a
`disabled` input are both `:read-only` and only a plain one is
`:read-write`: a control's own state wins over an editable ancestor. And the
walk stops at the nearest `contenteditable`, not at any editable ancestor —
a `<p>` nested inside a `contenteditable="false"` inside an editable div is
`:read-only`.

**Re-measuring found one row of round fifty-one's table wrong, and it is the
row that said "same".** That table lumped a checkbox with `<button>` and
`<select>`:

> | `<button>`/`<select>`/a checkbox | read-only | same |

`<button>` and `<select>` were same. A checkbox was **not**:
`editable-form-control?` is every `<input>` bar `hidden` and `file`, so this
engine reported `input[type=checkbox]` `:read-write` where Brave reports
`:read-only`. Nineteen types were measured one at a time this round
(`text-entry-input-types`): twelve are `:read-write` and seven are not, and
the twelve are exactly HTML's own "the `readonly` attribute applies to"
list.

`editable-form-control?` is still right where it is *used*, and that is a
second measurement rather than an assumption: `readonly` bars a control from
constraint validation whether or not the attribute applies to its type.
`<input type="checkbox" readonly required>` is `:required` and **not**
`:invalid`, while `<select readonly required>` **is** `:invalid` because
`readonly` reaches no `<select>` at all. So the two sets answer different
questions and both are now stated.

#### `:required`/`:optional` were not "the attribute alone" either

The part round fifty-one named *is* the attribute alone: `disabled` and
`readonly` do not touch either pseudo-class, where they do take a control
out of `:valid`/`:invalid`/`:in-range`/`:out-of-range` and Brave agrees that
they should. The part it did not name is that the attribute has to
**apply**, and that is a measured set across twenty-two input types:

| | Brave |
|---|---|
| `text search url tel email password date month week time datetime-local number checkbox radio file` + `required` | `:required` |
| `hidden range color submit image reset button` + `required` | `:optional` |
| `<button required>` | `:optional` — never `:required` |
| `<select required>` / `<textarea required>` | `:required` |
| `<fieldset>` / `<output>` / `<object>` / `<p>` | neither |

`file` being in the first row closes half of the scope cut round fifty-one
recorded at `matches-pseudo?`. The other half is deliberately still open and
is written there with its number: Brave reports `<input type="file"
required>` `:invalid` as well, and closing that means deciding what a file
input's VALUE is, which this file has no reader for.

#### `:indeterminate` is three elements, three rules, and one of them is unreachable

The one everybody names first cannot be reached from static markup at all,
and saying so is the finding:

| markup | Brave |
|---|---|
| `<input type=checkbox indeterminate>` | **no** |
| `<input type=checkbox indeterminate="true">` | **no** |
| `<progress>` | yes |
| `<progress value="">` / `<progress value="abc">` | **no** |
| two `<input type=radio name=g>`, neither checked | **both** |
| the same with one `checked` | neither |
| `<input type=radio>` with no `name` | yes |
| `<input type=radio name=x disabled>` beside an unchecked sibling | yes |

A checkbox's indeterminacy is an IDL property with no content attribute
behind it, so both attribute spellings match nothing. That is asserted as a
gate — `an-indeterminate-attribute-on-a-checkbox-is-not-a-browser-behaviour`
— because writing that clause would be inventing a browser behaviour, which
is the same mistake the three downstream assertions this round corrects were
making. A `<progress>` is indeterminate iff it has no `value` **attribute**;
presence is the whole test, and an unparseable value is still determinate. A
radio's is a property of its **group**, scoped by the same real form
ownership `:required` already uses.

#### `:placeholder-shown` and `:default`, and the two rows a spec reading gets wrong

`:placeholder-shown` is attribute presence plus an **empty** value, over
seven types. `placeholder=""` still shows a placeholder — the test is that
the attribute is there, not that it says anything — and a value of a single
space hides one, so the placeholder is hidden by whitespace the reader
cannot see. `type=date` is `:read-write` and never shows a placeholder,
which is why that set is its own and not `text-entry-input-types` reused.

`:default` is three unrelated rules: a `checked` checkbox/radio, a
`selected` `<option>`, and the form's first submit button in **document**
order (a button nested three elements deep still wins over a shallower later
one). The pair that says it is three rules and not one: a checked checkbox
with no form at all **is** `:default`, and a `<button>` with no form is
**not**.

A `<textarea>`'s value now comes from its **text** rather than from a
`value` attribute HTML does not give it. `:placeholder-shown` needed it, and
it fixes a second thing on the way: `<textarea required>typed</textarea>` is
`:valid` in Brave and this engine called it invalid, because
`control-value` fell through to an attribute that can never exist.

#### A bounded number field is as wide as the longest number it can hold

Round fifty-one recorded this as a pre-existing gap it had surfaced without
being about — the two `:in-range` cases reporting an `<input type="number">`
at 153 where Brave says 42. It is a control's own sizing rule, and `size`
never reaches it: `<input type=number size=2>` and `size=40` are both the
same width as one with no `size` at all.

All widths in the corpus frame are `7n + 28` — `n` characters of the control
face, plus the box (8), one glyph's slack (5) and the spin buttons (15):

| attributes | Brave | n | longest rendering |
|---|---|---|---|
| none | 153 | 20 | — (`size`) |
| `min=1 max=9` | 35 | 1 | `9` |
| `min=1 max=10` | 42 | 2 | `10` |
| `min=-999 max=999` | 56 | 4 | `-999` |
| `min=1 max=1000000000000` | 119 | 13 | thirteen digits |
| `min=0.5 max=1.5` | 49 | 3 | `0.5` |
| `min=1 max=10 step=0.01` | 63 | 5 | `10.00` |
| `min=0 max=100 step=1.0` | 63 | 5 | `100.0` |
| `min=-100.25 max=0` | 77 | 7 | `-100.25` |
| `max=100` alone / `min=0` alone | 153 | 20 | — |
| `min=1 max=10 step=any` | 153 | 20 | — |

Three things fall out that a spec reading does not give. **Both** bounds are
needed. The fraction is the widest of the step's, the min's and the max's
own **written literals** — `min=0.5 max=1.5` carries no step and is still
three characters, and `step=1.0` widens `min=0 max=100` from three to five —
which is why the rule reads literals and not parsed doubles. And `step=any`
opts out entirely while a non-numeric `step` is merely ignored.

The 15px of spin buttons is a constant, and that is measured rather than
assumed: a bounded number field against `<input type=text size=2>` in the
same font is 15px wider at all seven font/size pairs tried (Arial 10/13.3333
/20/40, monospace 20/28, serif 13.3333). It is a fixed-size platform widget
like `select-arrow-width`'s 20, not a multiple of the em — which is why a
40px number field is 15 wider and not 45. It is also **not** charged to an
unbounded one: `<input type=number>` is 153, exactly a text field, so the
decoration enters the width precisely when the bounds do.

One divergence this **introduces** rather than closes, named at
`strict-number-attr`: `min=0 max=1e3` is 35 in Brave and is 153 here, the
same scientific-notation cut `cssom.core/parse-number` already documents for
`min`/`max` validation, arriving by a second route. Two other rejections
agree with Brave for the same reason and are controls: `min=" 1 "` and
`max=+50` are both 153 on both sides.

#### `::file-selector-button`: measured in full, deliberately not implemented

Twelve declarations on the pseudo-element, with the control's box and the
button's own box beside each:

| declaration | control | button |
|---|---|---|
| (none) | 253×27 | 108.656×27 |
| `padding: 0` | 253×25 | 96.656×25 |
| `padding: 5px` | 253×35 | 114.656×35 |
| `padding: 20px` | **261×65** | 136.656×65 |
| `padding: 40px` | 301×105 | 176.656×105 |
| `padding: 0 20px` | 261×25 | 136.656×25 |
| `border: 5px` | 253×33 | 114.656×33 |
| `margin: 12px` | 253×51 | 108.656×27 |
| `font-size: 30px` | 349×51 | 224.5×51 |
| `width: 300px` | **253**×27 | 300×27 |
| `height: 80px` | 253×80 | 108.656×80 |
| `display: none` | 253×**21** | — |

Both of the control's dimensions are computed from that button:

```
width  = max(ceil(34 × advance("0")), ceil(button border box) + 4 + ceil(label))
height = max(button MARGIN box, the label's 21px line)
```

Two of those rows are rules a spec reading misses. A `margin` on the button
counts toward the control's **height** and not toward its width. And an
explicit `width` on the button does not reach the control's intrinsic width
at all — the button simply overflows.

The height half is derivable from numbers this engine already has (27 is its
own 21px button box). **The width half is not, and that is why neither is
in.** Its second term is `ceil(92.656 + padding + border) + 4 +
ceil(119.313)`, and those two numbers are this machine's Japanese UA strings
— `ファイルを選択` and `選択されていません`. Writing them down is the measurement of
a UI language, which is exactly what round forty-five refused for this same
control and for the same reason. Implementing only the height would leave
the case red on `input w` anyway. `:form/file-selector-button-padding-grows-
the-control` therefore stays at 253×27 against Brave's 261×65 — `input w`
−8, `input h` −38, `p h` −38 and 15 paint points, all of them one case, and
the table above is at the `file` branch of `atomic-intrinsic-width` for
whoever closes it.

#### The three downstream assertions, and what they actually encoded

Round fifty-one named three. There are seven answers, in three deftests, and
the extra four are the same rules reaching further — the landed fix also
corrects `:required` for a file input and `:read-only` for a checkbox, and
both of those inputs are the FIRST input in their markup, so the
document-order answers move together.

| test | assertion | was | is |
|---|---|---|---|
| `dom_bridge_test` | `input:required` | `"required"` | `"file-required"` |
| | `input:optional` | `"checked"` | `"disabled"` |
| | `input:read-only` | `"readonly"` | `"disabled"` |
| | `input:read-write` | `"checked"` | `"required"` |
| | `#file-required:required` | `nil` | the node |
| `quickjs_execution_test` | the same four, as positions 4/6/7/13 of one vector | | |
| `css_test` | `#file-required` padding | `not= 4` | `4` |

The sharpest of them is `input:read-write` returning `"checked"`: that
assertion said a **checkbox is read-WRITE**. And the `css_test` one gave its
reason as "a file input with a value is `:valid`, so `input:required` must
not apply", which conflates two pseudo-classes — `:required` asks about the
attribute, not about validity. Each is corrected with its own measurement
written beside it, and the quickjs vector gains a twenty-eighth query,
`#readonly:read-only`, which answers the same on both sides: a control that
says the predicate was rewritten rather than merely inverted.

#### One stale test, corrected with the reason

`length-constraints-do-not-apply-to-non-text-like-controls` asserted
`maxlength` against a `<textarea value="12345">`. Measured, that textarea's
`.value` is `""` — HTML gives a `<textarea>` no `value` attribute — so the
string it was written to constrain was never in the control at all. It uses
a real text child now. Recorded beside it, pre-existing and **not** this
change's: Brave applies `maxlength`/`minlength` only once a control's dirty
value flag is set, so `<input type=text value=12345 maxlength=3>` and
`<textarea maxlength=3>12345</textarea>` are both `:valid` there and both
invalid here. Closing that means modelling the dirty flag.

#### Verification

1082 unit tests / 2952 assertions, 0 failures; lint 0 errors and 22
warnings, all in `test/` — one fewer than this branch started with, because
`control-value`'s unused `type` binding went with the rewrite. **Fourteen
new `deftest`s, of which twelve fail on the base commit (36 assertions) and
pass after**; the other two are pure controls that pass on both sides.
Downstream, all against this branch's cssom: `browser` **754/0** (with its
own `agent/form-controls`), `dom-gpu` **130/0**, `htmldom` **180/0**.

### Round fifty-two: `@scope`, and the seventh key in the cascade sort

Round forty-four measured `@scope` and left it. Round forty-nine measured
it in full and named exactly why it was still open:

> one of its rules is a **new dimension in the cascade sort tuple**, not a
> parse or a value change. `resolve-style-and-flow` sorts on
> `(juxt :important? :origin :inline? :layer :specificity :order)`; scope
> needs a seventh key computed per (rule, element) pair from the ancestor
> distance to the matched root.

That key is this round, and the whole of the design question was **where in
the six it goes**. The answer is a measurement, not a spec reading, and it
took a shape for each neighbour.

Three columns, because the corpus growing and the engine changing are two
different things and a single before/after would let one pay for the other.
This round has the confound round forty-nine had, twice over: **two other
rounds landed on `main` while it was in flight** — fifty (three value
grammars) and fifty-one (selector state, pseudo-elements, alignment
shorthands) — so the middle column is **`main` AS MERGED (`4440220`)**, the
engine including both of them, on this round's finished 835-case corpus and
through this round's own harness. Column one to column two therefore mixes
coverage with two other agents' work, and **only column two to column three
is attributable to this round**. Everything here was re-measured after the
merge; no pre-merge number is reported.

| axis | 736 cases, `08c8a4e` | 835, `main` (`4440220`) | 835, after |
|---|---|---|---|
| line structure | 704/707 | 800/805 | **800/805** |
| geometry (boxes) | 2376/2384 | 2676/2714 | **2676/2714** |
| geometry (clean cases) | 728/735 | 812/835 | **812/835** |
| paint order | 18343/18362 | 20767/20837 | **20767/20837** |
| paint order (clean cases) | 724/735 | 816/834 | **816/834** |
| computed style (values) | 33481/33487 | 38143/38191 | **38166/38191** |
| computed style (cases clean) | 731/735 | 805/835 | **817/835** |
| cascade-attributed residual | 5 | 42 | **20** |

The residual is the number to read, and the 42 → 20 is the whole of what
this round moved on that axis. It accounts for itself exactly: the twelve
cases in the table below, plus the one `@scope` case that already existed.
**Not one `:scope/*` value and no `@scope` value of any kind is left in
it** — the twenty that remain are other rounds' named gaps (`:form/*`
state, `:selector/dir`, `:selector/has-*`,
`:container/a-percentage-width-container-is-not-queryable`,
`:text/font-size-absolute-keyword`).

Line structure, geometry and paint order are **identical to the value**
across the last two columns, which is what a change confined to the cascade
should look like.

`src/` was NOT touched by the corpus half of this round: the middle column
is `main`'s own engine.

1069 unit tests / 2880 assertions, 0 failures; linter 0 errors, 23
pre-existing warnings, all in `test/`. **33 of this round's 72 new
assertions, in 18 of its 21 new tests, fail on `main`'s `src/` and pass
after** — measured by running this round's test file against `4440220`'s
`src/`, and the same 33 fail against `08c8a4e`'s. The remaining three tests
are pure controls that pass on both sides and are here to say so:
`layer-order-beats-proximity` (the new key must not have jumped above the
layer key), `a-scoped-rule-keeps-the-layer-and-the-media-condition-it-was-written-in`
(recursing into `@scope` must not lose either), and
`a-stylesheet-with-no-scope-in-it-parses-exactly-as-before`. Downstream,
all run against this checkout of `cssom`: `browser` 754/0, `dom-gpu` 130/0,
`htmldom` 180/0 — htmldom delegates its style parsing to `cssom.core`, and
a cascade change has turned its suite red twice before.

#### Where proximity sits, proved from both sides

`.far > .near > p` throughout, and every pair run in BOTH source orders so
that "the later rule won" is never a possible explanation. One probe page
per probe, headless Brave 151.1.93.129 over CDP, 2026-08-06.

| probe | Brave |
|---|---|
| `@scope (.near) { p }` red vs `@scope (.far) { p }` blue | **RED** — the nearer root wins |
| ...source order reversed | **RED** — so proximity beats ORDER |
| `@scope (.near) { p }` red vs `@scope (.far) { div p }` blue | **BLUE** — so SPECIFICITY beats proximity |
| ...source order reversed | **BLUE** |
| `@layer la, lb; @layer lb { @scope (.far) { p } }` blue, `@layer la { @scope (.near) { p } }` red | **BLUE** — so LAYER beats proximity |
| ...both scopes in `lb` instead (the control) | **RED** |
| both declarations `!important`, nearer written first | **RED** |
| ...source order reversed | **RED** — importance does NOT reverse proximity the way it reverses layers |
| `<p style="color:blue">` against `@scope (#r) { p }` red | **BLUE** — element-attached beats proximity |

So the order is
`importance → origin → inline → layer → specificity → PROXIMITY → source
order`, and the tuple becomes

```clojure
(juxt :important? :origin :inline? :layer :specificity :proximity :order :decl-index)
```

The two specificity rows are the ones worth dwelling on, because "between
layer and order" was the guess and it is not the same claim as "below
specificity": a proximity key placed one position higher reads BLUE→RED on
the third row and nothing else changes. The control on the fourth-from-last
row is what makes the pair evidence rather than a coincidence — the
identical shape at EQUAL specificity answers the other way.

**An unscoped declaration is at INFINITE proximity, and that is a
measurement too.** `@scope (#r) { p { red } }` followed by a plain
`p { blue }` — same specificity, same layer, the unscoped rule written
LATER — is **RED**. Put both inside one `@layer za` and it is still red.
Put the unscoped rule in a later layer and it is BLUE, which is the control
that says the layer key above still decides first. So an unscoped
declaration is not merely "unranked by proximity"; it is at the worst
proximity there is and loses every tie to a scoped one.

**What proximity counts** is the hop count from the ELEMENT up to the root,
not the root's own depth: `.o1 > div > .o2 > div > div > p` is blue (`.o2`
at 3 hops beats `.o1` at 5) and `.o2 > div > div > div > .o1 > p` is red
(`.o1` at 1 beats `.o2` at 5) — same two rules, opposite answers. When one
root SELECTOR matches several ancestors it is the nearest that counts
(`.r > .m > .r > p` with `@scope (.r)` red and `@scope (.m)` blue is RED,
against a `.r > .m > p` control that is BLUE).

#### The other half: `@scope` is a range, and the prelude has no specificity

| probe | Brave |
|---|---|
| `@scope (#r) { .x }` | inside red, outside black |
| `@scope (#r) { div }`, root itself a `div` | the ROOT is out — a scoped selector carries an implicit `:scope ` DESCENDANT prefix |
| `@scope (#r) { div > p }` | a `<p>` whose parent IS the root is out — the prefix attaches to the WHOLE complex selector, not per compound |
| `@scope (#r) { :scope }` | ...and `:scope` is how you reach the root |
| `@scope (.r) { div:scope }` / `.r :scope` / `:is(:scope) p` | all three suppress the implicit prefix — `:scope` ANYWHERE counts |
| `@scope (#r) { p }` vs `div p` | **BLUE** — the prelude contributes NO specificity |
| `@scope (#r) { :scope p }` vs `div p` | **RED** — `:scope` is an ordinary (0,1,0) pseudo-class |
| `@scope (#r) to (.lim)` | donut hole, and the limit element ITSELF is out |
| `@scope (#r) to (:scope > .lim)` | the limit is a SELECTOR evaluated against the scope, not a class test |
| `@scope (.r) to (.r)` over `.r > p` | red — a limit matching the root does not cut the root |
| `@scope (.ra, .rb)` / `to (.l1, .l2)` | both halves are selector LISTS |
| `@scope (div > .r)` | a root may be a complex selector |
| `@scope (#a) { @scope (.b) { p } }` | red only where BOTH are ancestors |
| `.r > .lim > .r > p` under `@scope (.r) to (.lim)` | **RED** — every matching ancestor roots its OWN scope, and a cut one does not suppress the others |
| `.far > .near > .lim > p`, `@scope (.near) to (.lim)` red vs `@scope (.far)` blue | **BLUE** — when the nearer scope is cut, the farther one decides |
| `:scope p` OUTSIDE any `@scope` | matches — and `:scope { outline-color: red }` lands the outline on `<html>` and nothing else, so an unscoped `:scope` is `:root` |

The last row is a second, smaller fix riding along: `matches-pseudo?`
returned `false` for `:scope`, and the namespace docstring listed it as
deliberately out of scope. It is now `*scope-roots*` when a `@scope` is
being matched and the document root otherwise — both halves measured.

#### The implementation, and what the seventh key cost

The `:scope ` prefix is applied **at parse time**, as a real first part of
the selector flagged `:selector/scope-implicit?`, which
`simple-selector-specificity` returns `[0 0 0]` for. That flag is the whole
of the difference between the prelude and a written `:scope`, and it is
what lets `specificity`, `pseudo-element-of` and `matches?` all read one
selector value and never disagree about which one they got. The combinator
walk in `matches-parts?` then does the range check for free — a scoped
selector is an ordinary complex selector once `:scope` can answer.

Proximity is per (rule, element), so it cannot be precomputed. But it is
only ever computed for a rule that HAS a `:rule/scope`, and the ancestor
index it needs is a `delay` that a stylesheet without `@scope` never
forces. Roots are tried NEAREST FIRST and the first that matches wins, so
the answer is the nearest root the selector could actually use rather than
the nearest root that exists — which is measurable, and is what the
"nearer scope is cut, farther one decides" row above pins.

Measured cost, same machine, base `src/` against this round's:

| configuration | base `src/` | this round |
|---|---|---|
| 42 elements, 50 rules, no `@scope` | 61.9 / 67.2 / 54.6 ms | 57.2 / 52.6 / 69.1 ms |
| the same plus two `@scope` blocks | 57.9 / 65.6 / 61.2 ms | 61.5 / 56.1 / 82.1 ms |

Three alternating JVMs per engine, min-of-six-trials within each, 20
warm-up cascades before the first measurement — and **the cost is below
this benchmark's noise floor**. The spread of one engine against itself on
one stylesheet (54.6-67.2 ms) is wider than any gap between the two
engines, and the two distributions overlap completely. Reporting a
percentage here would be reporting the machine.

What the key costs *structurally* is the honest answer: for a stylesheet
with no `@scope`, one extra `:proximity` lookup per declaration per
comparison in the sort tuple, one `(:rule/scope rule)` lookup per rule per
element, and one unforced `delay` allocation per element. Every declaration
carries the same `##-Inf`, so the key is a pure tie and the sort falls
through to `:order` exactly as before — which is why the ops dump is
byte-identical on 835 cases.

A second comparator for the no-`@scope` case was considered and NOT
written. It would make the cost provably zero, and it would make two sort
tuples that have to be kept in step by hand — on the function every
declaration of every case goes through. An unmeasurable cost is not worth
that.

The first version of this benchmark ran the two configurations
sequentially and reported the second as 27% FASTER than the first on the
base commit, for a stylesheet with two more rules in it. That was the
second configuration inheriting the first one's JIT warm-up. Both are now
timed alternately inside one JVM.

#### `--dump-style`, because the ops dump cannot see a colour

`--dump-ops` exists because "four sums over 735 cases" hides an exchange.
A cascade round needs the same instrument for the axis it actually moves,
and round forty-nine said so in passing without building it: its six
nesting cases "are not in either list … their divergence is a colour, which
the ops dump cannot see". `--dump-style` writes one line per disagreeing
value under its case id, plus each case's agree/total, so a case that
starts or stops diverging on any property — or stops being scored at all —
is an added or removed line.

Both dumps were diffed corpus-wide, in both directions, between the two
right-hand columns.

**Ops: 0 of 835 cases changed.** Every case's box list is byte-identical,
in both directions. A cascade change that moved a box would be a bug, and
this is the instrument that says none did.

**Computed style: exactly 12 cases changed, every one of them TOWARDS the
browser, and no case's compared TOTAL changed** (so no case quietly stopped
being scored):

| case | before | after |
|---|---|---|
| `:cascade/a-scope-rule-does-not-reach-outside-its-root` | 55/56 | **56/56** |
| `:scope/the-scope-root-itself-does-not-match-a-bare-descendant-rule` | 40/42 | **42/42** |
| `:scope/the-scope-pseudo-class-reaches-the-root` | 40/42 | **42/42** |
| `:scope/an-explicit-scope-pseudo-class-does-add-specificity` | 55/56 | **56/56** |
| `:scope/proximity-beats-source-order` | 55/56 | **56/56** |
| `:scope/a-limit-cuts-the-limit-element-and-everything-under-it` | 96/98 | **98/98** |
| `:scope/the-limit-element-itself-is-out` | 66/70 | **70/70** |
| `:scope/a-limit-selector-is-relative-to-the-scope-root` | 94/98 | **98/98** |
| `:scope/a-cut-root-does-not-suppress-a-nearer-uncut-one` | 83/84 | **84/84** |
| `:scope/nested-scopes-both-have-to-contain-the-element` | 109/112 | **112/112** |
| `:scope/proximity-is-measured-to-the-nearest-matching-root` | 69/70 | **70/70** |
| `:scope/important-does-not-reverse-proximity` | 55/56 | **56/56** |

The other 823 are byte-identical on both dumps. The six remaining `:scope`
cases are controls that agree on BOTH sides and are not in this list:
`a-scope-prelude-contributes-no-specificity`,
`proximity-and-source-order-pointing-the-same-way`,
`specificity-beats-proximity`, `layer-order-beats-proximity`,
`a-scoped-rule-keeps-the-layer-it-was-written-in`,
`a-scoped-rule-keeps-the-media-condition-it-was-written-in` and
`proximity-with-only-one-matching-root-per-scope`. Each is beside a case
that DOES move, and only the pair is evidence.

#### The harness could not express a scoped rule either

`scope-css` prefixes every selector with the case's own container id. A
scoped selector carries an implicit `:scope ` descendant prefix, and the
container is an **ancestor** of the scope root — so the rule reaching the
browser was `:scope #case-N .x`, which matches nothing. Measured:

| CSS on the page | Brave |
|---|---|
| `@scope (#sc) { #cN .x { red } }`, `#cN > #sc > .x` plus a `.x` beside it | BOTH black |
| `@scope (#sc) { #cN :scope .x { red } }` | inside red, outside black |
| `@scope (#sc) { .x { red } }`, no prefix at all | inside red, outside black, and a `.x` in another container black |

The third row is the fix: a rooted `@scope` prelude already confines its
rules to that root's subtree, so the id prefix buys nothing and costs the
whole feature. The body of a rooted `@scope` is now emitted unprefixed. A
prelude-less `@scope` is not given that treatment — it would scope to the
shared `<body>` and reach every case.

**This means the case that existed before this round was measuring
something else.** `:cascade/a-scope-rule-does-not-reach-outside-its-root`
reported two cascade-attributed mismatches, and its comment said Brave
reddens the paragraph inside and leaves the one outside black. Under the
prefix Brave read BOTH as black, so the divergence was real and its
explanation was not.

**And it has a cost, named where it bites.** The two sides of this harness
now receive different CSS in one respect: `cascaded-document` hands the
engine the raw `:css`, so an unscoped selector carries one more id in the
browser than in the engine, while a rooted `@scope` body carries the same
in both. That was always true and always harmless — before the `:scope`
group every competing selector in a case was unscoped and they all gained
the same id — and it inverts a specificity comparison the moment a scoped
rule competes with an unscoped one.

#### Measured and deliberately NOT added

- **"An unscoped declaration is at infinite proximity", as a corpus case.**
  A real rule and a real divergence, and not expressible on the shared
  page for the reason just above: equal specificity on one side is unequal
  on the other, by construction. The case was written, found to agree on
  the BASE commit, and removed — the engine's red came from specificity and
  the browser's from proximity. It lives in the unit tests, which call
  `apply-cascade` directly and therefore have one CSS text rather than two.
- **A prelude-less `@scope`, as a corpus case.** On the corpus page the
  stylesheet is in `<head>`, so the owning element is `<head>` and Brave
  matches nothing — which this engine also does, for an entirely different
  reason. It would pass for precisely the wrong reason, the same test
  `revert-layer` on an unlayered declaration failed in round forty-four.
  Measured in both directions and kept as a unit test.
- **`:scope` outside any `@scope`, as a corpus case.** Same shape: the
  harness's prefix makes it `#case-N :scope p`, and `<html>` is not a
  descendant of `#case-N`, so both sides say black and the case would
  prove nothing.

#### Merging `main` mid-flight: two conflicts that were not append-at-end

Rounds fifty and fifty-one landed while this was in flight, and three of
the five conflicts were the usual append-at-end kind (both sides kept). The
other two are worth naming because both are two rounds touching the same
few lines for unrelated reasons:

- **`simple-selector-specificity`.** Round fifty-one gave `:is()` arguments
  a recursive `arg-specificity` that sums over a COMPLEX argument's own
  compounds — closing exactly the gap round forty-nine's nesting
  desugaring named as its own cost. This round wrapped the same function in
  a `:selector/scope-implicit?` guard returning `[0 0 0]`. The guard now
  wraps their version; neither change is expressible as a hunk that beats
  the other.
- **`scope-css`.** Round fifty-one replaced the prelude's `str/split` on
  `,` with `split-selector-list`, which respects parentheses. This round
  made the prefix conditional so a rooted `@scope` body can be left
  unprefixed. Both, plus both docstring paragraphs.

Everything above is measured after that merge. Nothing pre-merge is
reported.

#### The one scope cut, with the browser numbers a future fix needs

**A prelude-less `@scope { … }` applies to nothing here.** It scopes to the
element that OWNS the stylesheet — the `<style>` element's own parent — and
`parse-rules` is handed CSS text with no owner attached. Measured in Brave
151, 2026-08-06:

| probe | Brave | here |
|---|---|---|
| `<style>@scope { p { red } }</style>` inside `<div id=w>`, `<p>` in the same div | RED | black |
| ...the `<p>` outside that div | black | black |
| the same `@scope` in a `<head>` `<style>` | black | black |
| `@scope to (.lim) { p { red } }` in a div, `<p>` before the limit | RED | black |
| two `<style>@scope {…}</style>`, one per div | each div's own `<p>` takes its own colour | both black |

So it fails **closed**, which is the safe direction and is already right for
two of the five shapes. Closing it means carrying the owning element id from
the `<style>` element through `parse-rules`, which every caller —
`apply-cascade`, this harness, `htmldom` — would have to learn to pass.
That is a signature change to the whole stylesheet pipeline rather than a
scope change.

Smaller, and named where they are made:

- **Nested `@scope` proximity is counted from the INNERMOST scope.** An
  element must be inside every enclosing scope (measured), and no probe
  discriminates what the outer scopes' own proximity would contribute, so
  nothing is claimed about it.
- **`names-scope?` reads the selector's raw text.** A literal `:scope`
  inside a quoted attribute value (`[data-x=":scope"]`) would be mistaken
  for the pseudo-class — the same bounded reader every at-rule scan in this
  file uses.

### Round fifty-one: selector STATE, the pseudo-elements with no box, and the alignment shorthands

Round thirty-two put forty-three cases into selectors and found the engine
mostly right. What it did not enter was **state** — and the inventory that
opened this round is the finding, before any measurement: `matches-pseudo?`
implements THIRTEEN form-state pseudo-classes (`:checked`, `:disabled`,
`:enabled`, `:required`, `:optional`, `:read-only`, `:read-write`, `:valid`,
`:invalid`, `:in-range`, `:out-of-range`, `:focus`, `:focus-within`) and
`grep ':checked' cases.edn` found **zero**. So did `:root`, `:lang`,
`:only-of-type`, `::marker` and `place-items`. Implemented and never
differentially tested is exactly the state `@layer` was in before round
forty-four, and it is where the defects were.

Seventy-three cases went in, in four areas, **thirty-three of them controls** --
cases written to AGREE, so that the divergence beside each one measures a rule
rather than a number.
Every expected value was read out of a real headless Brave 151.1.93.129 over
CDP on 2026-08-06, **one probe page per probe**, in this corpus's own frame,
before the case was written.

Three columns, because the corpus growing and the engine changing are two
different things. All three share ONE harness — this round's, including two
harness fixes whose neutrality is proved separately below. **They are
pre-merge numbers by construction and are re-measured below**: round fifty
(the value grammars) landed on `main` while this was in flight, so the
post-merge scoreboard is at the end of this entry.

| axis | 735, base engine | 808, base engine | 808, after |
|---|---|---|---|
| line structure | 704/707 | 773/778 | **773/778** |
| geometry (boxes) | 2376/2384 | 2557/2605 | **2567/2605** |
| geometry (clean cases) | 728/735 | 778/808 | **785/808** |
| paint order (points) | 18343/18362 | 20087/20157 | **20087/20157** |
| paint order (clean cases) | 724/735 | 789/807 | **789/807** |
| computed style (values) | 33480/33487 | 36628/36665 | **36636/36665** |
| computed style (cases clean) | 730/735 | 781/808 | **787/808** |
| cascade-attributed residual | 6 | 32 | **24** |

Geometry went 100% → 98% and the cascade residual 6 → 32 on coverage alone,
which is the round working. `src/` was not touched between columns one and
two.

**The residual accounts for itself exactly.** Of the 24 left, **six are
pre-existing and are the same six, with the same causes, as column one**:
`:cascade/a-scope-rule-does-not-reach-outside-its-root` (2),
`:text/font-size-absolute-keyword` (2),
`:container/a-percentage-width-container-is-not-queryable` (1) and
`:nesting/an-ampersand-carries-the-parent-lists-maximum-specificity` (1).
Nothing pre-existing regressed. The other eighteen are new gaps this round
measured and did not close, listed below. Sixteen new cases are also dirty on
geometry, against the seven pre-existing ones that are unchanged.

**`--dump-ops` was diffed corpus-wide between columns two and three, on the
same 808 cases. Exactly seven cases' box lists changed, every one of them TO
the browser's number, and the other 801 are byte-identical:**

| case | base | after | Brave |
|---|---|---|---|
| `:selector/any-link-and-link-both-match-an-href` | a 7 wide | **67** | 67 |
| `:grid/place-items-centers-both-axes` | 0,0 120×60 | **56,20 7×20** | 56.5,20 7×20 |
| `:grid/place-items-is-align-then-justify` | 0,0 120×60 | **0,40 7×20** | 0,40 7×20 |
| `:grid/place-self-single-value-is-both-axes` | 0,0 120×60 | **113,40 7×20** | 113,40 7×20 |
| `:grid/place-self-two-values` | 0,0 120×60 | **56,40 7×20** | 56.5,40 7×20 |
| `:flex/place-content-on-a-row` | x=0, 7 | **286, 293** | 286, 293 |
| `:flex/place-items-applies-only-on-the-cross-axis` | 0,0 7×80 | **0,30 7×20** | 0,30 7×20 |

The computed-style axis was read separately, because a cascade change shows
up as a colour and the ops dump cannot see one: that is the residual
arithmetic above. And the blast radius is bounded by construction — **no
pre-existing case's CSS mentions any pseudo-class or property this round
touched**, which was checked mechanically over all 735.

1036 unit tests / 2733 assertions, 0 failures; lint 0 errors and the same 23
pre-existing warnings, all in `test/`. **Eighteen new `deftest`s, of which
eleven fail on the base commit (21 assertions) and pass after**; the other
seven are pure controls that pass on both sides. Downstream, all against this
branch's cssom: `browser` 754/0, `dom-gpu` 130/0, `htmldom` 180/0.

#### Two harness defects, and the proof they are not a thumb on the scale

Both are in `scope-css`/`cascaded-document`, both were found by writing cases
that could not otherwise be expressed, and **the modified harness was run
against the UNMODIFIED engine at the base commit on the UNMODIFIED 735-case
corpus.**

**A selector list was split on every comma, including the ones inside
parentheses.** `div:has(b, i)` became `#case-N div:has(b, #case-N i)` — still
valid CSS, still matching something, so nothing anywhere reported an error.
Measured on `<div><i>i</i></div><div><b>b</b></div><div><u>u</u></div>`: the
correct rule paints the first two divs red and the mis-scoped one paints only
the second, because `:scope #case-N i` needs a `#case-N` *inside* the div.
Every functional pseudo-class that takes a list is affected. The corpus
contained exactly one such prelude (`p:not(.x, .y)`) and it survived **by
luck** — `#case-N .y` matches the same element either way. `split-selector-list`
now tracks parenthesis and bracket depth.

*Proof:* with only this fix, the base engine on the base corpus reproduces
the published baseline **to the value on all five axes** — line 704/707,
geometry 2376/2384 with 728/735 clean, paint 18343/18362 with 724/735 clean,
computed style 33481/33487 with 731/735 clean, residual 5.

**The two sides were not evaluating the same selector.** The browser page
scopes every rule by `#case-N` because 808 cases share one document; this
side handed `cssom.core` the RAW css, because each case is its own document.
But the wrapper is an ELEMENT either way, and `<div id="root">` was reachable
where `#case-N` was held out of reach. Measured on
`:selector/has-takes-a-selector-list`: a bare `div:has(b, i)` matched the
wrapper, and the red it declared there INHERITED into the one div the rule is
supposed to miss. **Four cases were written before this was noticed and all
four looked like engine bugs.** `cascaded-document` now scopes by `#root`.

*Proof, and it goes the OTHER way:* with both fixes, the base engine on the
base corpus is byte-identical on the op dump and on line, geometry and paint,
and **loses one computed-style value** — 33481 → 33480, residual 5 → 6. A
harness change that costs a point is not one aimed at the score. What it
costs is named: `:nesting/an-ampersand-carries-the-parent-lists-maximum-specificity`
used to be handed a parent list of two COMPOUND selectors where the browser
had two COMPLEX ones, and scoping this side lands it squarely on
`expand-nested-selector`'s documented third branch. Round forty-nine already
measured that branch and named the fix — letting this engine's `:is()` hold a
complex selector — and it is not a nesting change. The case now carries the
new cause.

#### What the state pseudo-classes turned out to be, measured

Not one of these is derivable from the pseudo-class's own name, which is why
they are one table rather than one sentence each.

| shape | Brave | this engine, before |
|---|---|---|
| `<option selected>` | `:checked` | not checked |
| `<option checked>` | **not** `:checked` | checked |
| `<div checked>` | not `:checked` | **checked** |
| `<input required disabled>` | `:required` | neither |
| `<input disabled>` | `:optional` | neither |
| `<input disabled>` | `:read-only` | neither |
| `<p contenteditable>`, and a `<p>` inside it | `:read-write` | neither |
| `<p contenteditable="false">` inside it | `:read-only` | read-only |
| `<textarea readonly>` | `:read-only` | same |
| a bare `<option>` / `<fieldset>` | `:enabled` | neither |
| a `<legend>` | not `:enabled` | not |
| `<input type=number>` with no `min`/`max` | neither range | neither |
| the same, `disabled` | **not** `:in-range` | not |

Two rules fell out and were landed, and each replaced a list rather than
extending one:

- **`:checked` names the state of the control it is on.** `checked` on a
  checkbox, `selected` on an `<option>`. The old rule read the `checked`
  attribute off *any* node, so the two `<option>` cases came out exactly
  inverted and a `<div checked>` matched.
- **`:enabled` and `:disabled` are complements over what CAN be disabled**,
  not over form controls. `:disabled` already used the wider set, so the pair
  disagreed with itself: a bare `<option>` was neither.

#### The rule that was written, measured, and then REVERTED

> **Closed in round fifty-three**, which could land both halves. What that
> round found by re-measuring rather than re-reading is below: one row of
> the table in this section is wrong.


**`:read-only` is not a second list, it is `(not :read-write)`**, and
`:required`/`:optional` decide on the attribute alone. One predicate —
`user-alterable?`: an editable form control that is neither `readonly` nor
`disabled`, OR any element in a `contenteditable` subtree — makes all eleven
measured rows above fall out, and it was written, and it passed, and the
corpus went green on three more cases.

It is not in this round, and the reason is not doubt about the measurement.
**`:read-only` and `:optional` are consumed by `kotoba-lang/browser`'s
`query-selector`, and that repo's suite asserts the answers this engine gives
today.** With the fix in, three assertions fail:
`dom_bridge_test`'s `query-selector-supports-form-state-pseudo-classes`
requires `input:read-only` to skip a disabled input and return the `readonly`
one, and `input:optional` to skip it too; `quickjs_execution_test`'s
`quickjs-dom-query-uses-shared-form-state-pseudo-classes` pins the same node
ids. All three encode a browser answer that does not exist — and correcting
them is a change to a repo this round does not touch.

So the fix was reverted, the measurement is written at `matches-pseudo?` as a
table with the eleven rows and the three downstream assertions named, and
four corpus cases carry it red. Closing it is a cross-repo change and belongs
in a round that can land both halves. **The alternative — keeping the fix and
reporting `browser` at 751/3 — would have been shipping a red downstream
suite to make this one greener, which is the trade this corpus exists to
refuse.**

One scope cut in the same family survives either way, recorded at
`matches-pseudo?` with its number: a `type="file"` input is declined via
`validation-barred-control?`, where Brave reports
`<input type="file" required>` as BOTH `:required` and `:invalid` — only
`type="hidden"` is really barred.

#### `place-items` is align then justify, and that had to be measured

The three CSS Box Alignment shorthands were in neither the cascade's
expanders nor `cssom.layout`'s readers. The order is the whole content of
the fix and a guess gets it backwards half the time: `place-items: end start`
reports `align-items: end` / `justify-items: start` and puts the item at
(0, 40) in a 120×60 track, where reading the two values the other way round
puts it at (113, 0). Block axis before inline axis — the same order
`grid-area` uses and the opposite of `background-position`'s.

`expand-place-shorthand` deliberately does **not** validate the tokens
against an alignment vocabulary, for the reason `expand-border-box-shorthand`
gives: `cssom.layout` is the file that knows which keywords it can act on,
and a value this cannot check must reach it unchanged. Named cut: a
`<baseline-position>` is two words and one value, so `place-items: first
baseline` is read here as align `first` / justify `baseline`.

Five of the seven `place-*` cases went exact. The sixth,
`:grid/place-content-is-align-then-justify`, is the honest half-answer: the
shorthand expands correctly and the LONGHANDS are not read, because
`justify-content`/`align-content` on a grid container are unimplemented —
which is what the three cases beside it measure.

#### `::marker` has no box and its effect has a number

Round thirty-two called `::first-letter` unscorable and was half right;
`::marker` is the same shape. The pseudo-element produces nothing the
geometry axis can see, and it is an inline box on the item's first line, so
its font size grows the line: **800×29 against 800×20**, 9px and well outside
the 2px tolerance, on a `<ul>` and on an `<ol>` alike. Its `content` is
readable the other way, through a shrink-to-fit box: an inside marker written
`content: "XXXX "` makes the item **56** wide against 40 — and 40 is exactly
what this engine's own inside-marker advance formula gives, so the control
was already pinned.

`pseudo-element-pattern` recognises three pseudo-elements and deliberately
nothing else, so a rule naming any other one becomes an unrecognised
pseudo-CLASS and matches nothing. That is fail-CLOSED, and
`:generated/an-unknown-pseudo-element-does-not-restyle-its-element` is the
control that says so: Brave drops `p::frobnicate` from the stylesheet
entirely (two rules survive on the page instead of three) and this engine
reaches the same black by a different route. Two right answers for two
reasons.

**Three pseudo-elements were measured and deliberately NOT added**, because
no axis can see them at any value, and saying so is worth more than a case
that passes for the wrong reason:

| | measured in this frame |
|---|---|
| `::placeholder` | a 40px `font-size` on it leaves the `<input>` at **153×21**, exactly its box without the rule |
| `::selection` | nothing is selected, so a colour on it changes neither the box nor any of the fourteen compared properties |
| `::backdrop` | a `<dialog open>` is not MODAL and has no backdrop; the dialog's box is **41×54** either way |

`::first-line` stays out for round forty-four's reason, unchanged.

#### Two selectors the harness cannot reach, and why

- **`:root`.** Every case's CSS is scoped by its container id on both sides
  now, and `#case-N :root` matches nothing in a browser — measured, black.
  A case would measure the scoping, not the engine.
- **`:target`.** The corpus page is loaded with no fragment (`location.hash`
  is `""`, measured), so `:target` matches nothing on either side. Both would
  agree for the wrong reason.

Neither is a limitation of the engine, and both are recorded rather than
worked around.

#### Re-measured after the merge, which is the number that counts

Round fifty (the value grammars) landed on `main` while this was in flight,
so the three columns above are pre-merge. Everything was re-run against
`main` AS MERGED (`2a33209`), on the merged 817-case corpus, and the middle
column is that commit's own engine — so column two to column three is
attributable to this round and nothing else.

| axis | 735, base engine | 817, `main` as merged | 817, after |
|---|---|---|---|
| line structure | 704/707 | 782/787 | **782/787** |
| geometry (boxes) | 2376/2384 | 2583/2631 | **2593/2631** |
| geometry (clean cases) | 728/735 | 787/817 | **794/817** |
| paint order (points) | 18343/18362 | 20322/20392 | **20322/20392** |
| paint order (clean cases) | 724/735 | 798/816 | **798/816** |
| computed style (values) | 33480/33487 | 36994/37029 | **37002/37029** |
| computed style (cases clean) | 730/735 | 792/817 | **798/817** |
| cascade-attributed residual | 6 | 30 | **22** |

`--dump-ops` diffed across the merge as well: **the same seven cases changed
and no others**, which is what says the two rounds do not overlap. They touch
different parts of `cssom.core` — round fifty's grammars sit in the
declaration parser, this round's in `matches-pseudo?` and one new shorthand
expander — and the merge needed no resolution in `src/` at all. Line
structure and paint order are byte-identical across the last two columns,
which is what a change confined to the cascade and to two alignment
longhands should look like.

Downstream, re-run after the merge and all against this branch's cssom:
`browser` **754/0**, `dom-gpu` **130/0**, `htmldom` **180/0**. 1048 unit
tests / 2808 assertions, 0 failures; lint 0 errors, 23 pre-existing warnings.

#### The new divergences that are NOT closed, with their numbers

Ranked by how cheaply a fix would follow from what is already here.

| case | Brave | this engine |
|---|---|---|
| `:form/read-only-matches-a-disabled-input`, `:form/read-write-matches-a-contenteditable`, `:form/required-still-matches-a-disabled-control` | see the table above | the fix exists, was measured, and was reverted -- cross-repo blocker |
| `:selector/empty-ignores-a-comment` | a `<p>` holding only a comment IS `:empty` | not empty — `empty-pseudo-matches?` counts child nodes of every type |
| `:form/placeholder-shown` | matches an empty field with a `placeholder` | unimplemented |
| `:form/default-on-a-checked-checkbox` / `-on-the-first-submit-button` | margin-left 30px / red | unimplemented |
| `:form/indeterminate-on-a-progress-with-no-value` | margin-left 30px | unimplemented |
| `:form/indeterminate-on-a-radio-group-with-none-checked` | 30px on BOTH radios | unimplemented |
| `:form/valid-matches-a-form-element` | a `<form>` is `:valid` when its controls are | `constraint-valid?` requires a form CONTROL |
| `:selector/dir-matches-the-direction` | rtl red / ltr blue | `:dir()` unimplemented |
| `:selector/dir-reads-the-attribute-and-not-the-css-property` | **blue** — `direction: rtl` in CSS does not change `:dir()` | same |
| `:selector/a-lang-selector-list-is-not-valid-in-this-browser` | the rule is DROPPED — Blink 151 has not shipped `:lang(fr, de)` | matches; this engine is AHEAD of the oracle here, and the corpus records which |
| `:selector/not-takes-a-complex-argument` | `p:not(.w p)` excludes only the nested one | over-excludes |
| `:selector/has-nested-in-has-is-invalid` | `:has()` inside `:has()` invalidates the rule | matches |
| `:selector/has-a-descendant-through-a-combinator` | `div:has(section b)` matches one div | matches both |
| `:grid/justify-content-*`, `:grid/align-content-end`, `:grid/place-content-*` | tracks placed in the leftover space | placed from the start edge |
| `:grid/auto-flow-dense-backfills-a-hole` | the third item goes back to (0,0) | (120,20) |
| `:grid/order-reorders-grid-items` | `order` reorders grid auto-placement | flex only |
| `:box/justify-self-on-a-block-child` | **x=120** — box alignment is not grid-only | x=0 |
| `:form/file-selector-button-padding-grows-the-control` | 261×65 with `padding: 20px` on the button | 253×27 |

Two of those are worth naming as findings rather than as gaps.
`:box/justify-self-on-a-block-child` is the one in this round a spec reading
would have got wrong: `justify-self: center` on an ordinary block-level child
of an ordinary block container centres it, and `align-self: end` on the same
child moves nothing (its control, measured at (0,0)). And
`:selector/a-lang-selector-list-is-not-valid-in-this-browser` is the first
case in this corpus where the ENGINE is ahead of the oracle — Selectors 4
gives `:lang()` a comma list, Blink 151 drops the whole rule, and the case
carries the browser's answer rather than the spec's.

**One pre-existing gap this round surfaced without being about it**, recorded
here so it is not rediscovered: the two `:in-range` cases report an
`<input type="number">` at **153** wide where Brave reports **42**. That is
this engine's default text-field intrinsic width reaching a control that does
not want it, and it is unrelated to the pseudo-class the cases are named for.
### Round fifty: three value grammars, and one premise that was wrong

Three gaps, each already measured by the round that left it, and each
closed by finding out where the grammar it needed actually lives.

| axis | 735, base (`08c8a4e`) | 744, after |
|---|---|---|
| line structure | 704/707 | **713/716** |
| geometry (boxes) | 2376/2384 | **2402/2410** |
| geometry (clean cases) | 728/735 | **737/744** |
| paint order | 18343/18362 | **18573/18592** |
| paint order (clean cases) | 724/735 | **733/744** |
| computed style (values) | 33481/33487 | **33845/33851** |
| computed style (cases clean) | 731/735 | **740/744** |
| cascade-attributed residual | 5 | **5** |

Every mismatch COUNT is unchanged — 8 boxes, 19 paint points, 6 style
values, 5 of them cascade-attributed, and the same 4 `color` values in the
per-property table either side. The denominators grew by this round's nine
cases and nothing else moved. That is what a round whose engine changes are
invisible to the existing corpus looks like, and it is why the nine cases
exist: **`--dump-ops` was diffed per case, corpus-wide, and ZERO of the 735
pre-existing cases changed a single box**, in either direction. The
computed-style axis was diffed the same way — the harness's whole output is
byte-identical outside the nine new lines, the four group counts they land
in, and the totals.

The engine change was also run against the UNCHANGED 735-case corpus on its
own, before the cases were added: every one of the five axes reproduced the
base commit's numbers exactly, and the ops dump was byte-identical. A
cascade change that moves nothing is a claim, and that run is the evidence
for it.

1030 unit tests / 2767 assertions, 0 failures (1018/2692 at the base);
linter 0 errors, 23 pre-existing warnings, all in `test/`. **29 of this
round's 75 new assertions fail on the base commit's `src/` and pass after**,
and every control beside them passes on both sides — including
`supports-still-fails-open-where-the-value-space-is-open`, which is the one
that would have caught an over-enumerated oracle. Downstream, all run
against this checkout of `cssom`: `browser` 754/0, `dom-gpu` 130/0,
`htmldom` 180/0.

#### One probe page per probe, enforced by a script this time

Round forty-nine wrote down the rule after a shared page gave it four wrong
answers. This round has `conformance/probe.cljk`: an EDN file of
`{:id :html :js}` probes, each written to its own file and opened in its own
browser TAB, evaluated, closed. A fresh target is a fresh document, so the
leak is structurally impossible rather than remembered.

It also fixes a hazard the manual method has: `/json/new?url=` returns when
the TAB exists, not when the document has parsed, and a fixed sleep lost one
probe in ten to that race — always as a null `getElementById`, which reads
as a wrong ANSWER rather than as a failure. Two measurements were taken from
that state before it was found. The driver now polls `readyState` and
retries a null element.

151 conditions were read out of Brave 151.1.93.129 this way.

#### 1. `:is()` holds a complex selector — and it was never only specificity

Round forty-nine named the cost of not doing this as one specificity row.
Measuring the argument grammar itself found **eleven divergences in
twenty-two shapes**, and the first of them is a MATCHING bug:

| shape | Brave | this engine, before |
|---|---|---|
| `:is(.wA .wB) span` on `.wA > .wB > span` | RED | black |
| `:is(.wA .wB) span` on `.wA.wB > span` | black | **RED** |
| `:is(.wA > .wB) span`, direct child | RED | black |
| ...one level skipped | black | black |
| `:is(.wA + .wB) span` | RED | black |
| `:is(:is(.wA .wB)) span` | RED | black |
| `:is(:not(.q) .wB) span` | RED | RED |
| `:is(> .wB) span` | black | **RED** |
| `:is(%%bad, .wA .wB) span` | RED | RED |

`.wA .wB` and `.wA.wB` are different sets of elements, and the compound-only
parser answered for the wrong one — in both directions. This file's own
prose said `:is(.wrap section) p` "works, so the docstring is stale rather
than the engine incomplete"; it worked because `section` is not a class and
the class regex found only `.wrap`, so the argument silently degraded to
`:is(.wrap)`. `:is(.a .b)` has no such luck.

Specificity, measured, is the SUM over a complex arm's compounds, and the
list still contributes the MAXIMUM over its arms:

| shape | Brave | before |
|---|---|---|
| `:is(.wA .wB) span` vs `div.wB span` | RED (0,2,1) > (0,1,2) | BLUE |
| `:is(.wA .wB) span` vs `div.wA .wB span` | BLUE (0,2,1) < (0,2,2) | BLUE |
| `:is(.wA .wB) span` vs `.wA .wB span` later | BLUE — equal, order decides | BLUE |
| ...earlier | RED | BLUE |
| `:is(#zz, .wA .wB) span` vs `div.wA .wB span` | RED — max over an arm that matches nothing | BLUE |
| `:where(.wA .wB) span` vs `span` later | BLUE — still always zero | BLUE |

and `:not()` takes one too, which is a second matching fix:
`span:not(.wA .wB span)` on a span inside `.wA .wB` is BLUE in Brave (the
`:not` held) and was RED here; the control `span:not(.wQ .wB span)` is RED
on both sides.

**What it cost, concretely.** Four edits, no new concept, and the
specificity rule was already right:

- `selector-parts`, the combinator-walk BUILDER, factored out of
  `parse-selector` and moved above `parse-simple-selector`, taking its
  compound parser as an argument — the same
  pass-the-function-in shape `has-group-matches?` already uses, because this
  namespace avoids `declare`. `parse-selector` is now four lines.
- `parse-arm` inside `parse-simple-selector`: an argument with one token
  stays a bare compound map, byte-for-byte what it always was; one with two
  or more becomes a `:selector/parts` map; one starting with a combinator is
  DROPPED, because `:is()` is forgiving and a relative selector is not a
  complex one (`:has()` keeps its own parser, where the leading combinator
  is the point).
- `parts-match?`, the walk itself, factored out of `matches-parts?` the same
  way and moved above `matches-simple?`, which needs it for a complex arm.
  `parent-index` moved with it.
- `arg-specificity` inside `simple-selector-specificity`: sum over
  `:selector/parts`, recursively.

The one thing it costs at RUNTIME is `parent-index`, which `matches-simple?`
has to build itself because it is given `document` and not `parents`. That
was the part that looked expensive and measured cheap: **`matches?` already
rebuilds `parent-index` on every call**, once per (rule, element) pair, so a
complex argument pays exactly what the rest of this engine pays, and a
stylesheet without one pays nothing — the index is built inside the
`:selector/parts` branch and nowhere else.

`expand-nested-selector` then lost a condition rather than gaining one: the
`:is(p1, p2, …)` branch was gated on `(every? compound-selector? parent)`,
and with complex arguments there is nothing left for that gate to protect.
`compound-selector?` is gone.

#### 2. `@property`'s `syntax` is a grammar, and Brave honours all of it

Twenty-three registrations were measured, each with an invalid value, a
valid value, AND an element declaring nothing — that third read is what
separates "the syntax is not enforced" from "the whole registration was
dropped", because an unset registered property reports its initial value and
an unset unregistered one reports the empty string.

**Brave enforces every component type in the spec**: `<length>` `<number>`
`<integer>` `<percentage>` `<length-percentage>` `<color>` `<image>` `<url>`
`<angle>` `<time>` `<resolution>` `<transform-function>` `<transform-list>`
`<custom-ident>` `<string>`, the `|` alternation, literal idents
(`auto | <length>`), and both multipliers (`<length>+`, `<length>#`,
`<integer>+`). `*` accepts anything and still registers.

Two rows had to be measured rather than reasoned about, and they are the
ones that changed the shape of the fix:

| syntax | bad value | unset | what it says |
|---|---|---|---|
| `<flurb>` | kept | **`""`** | an unknown component name invalidates the WHOLE at-rule |
| `<length>\|<flurb>` | kept | **`""`** | ...and one unknown alternative poisons an alternation whose other arm is fine |

So the engine now knows **every** name the spec has — that is what makes the
drop rule right — and CHECKS the ones an axis of this corpus can observe:
`<length>` `<number>` `<integer>` `<percentage>` `<length-percentage>`
`<color>` `<custom-ident>`, plus the structure (`*`, `|`, literal idents,
`+`, `#`). The rest are known-but-unchecked: they keep the registration
alive and accept any value. Nothing in this engine reads a `<time>` or a
`<resolution>`, the computed-style axis compares fourteen properties none of
which takes one, and rejecting a value it cannot check is how a working
declaration disappears.

`initial-value` needed a SECOND, narrower gate rather than a wider syntax
check. `2em` is a perfectly good `<length>` and Brave rejects it anyway,
because an initial value has to be computationally independent — so
`computationally-independent?` sits beside `registered-value-valid?` and is
applied only at registration time, PER REPETITION (an `initial-value:
1px 2px` for `<length>+` is two absolute lengths, which a whole-value
`parse-style-value` reads as one unparseable string).

**The scope cut this leaves, with its numbers, and it is structural rather
than a choice.** Six of the twenty-three rows still diverge, all from ONE
cause: at use time a declared value has already been through
`parse-style-value`, so `--x: 200px` arrives as the NUMBER 200 and the unit
is gone before any check can see it. The engine cannot tell `7` from `7px`
there.

| syntax | bad value | Brave | this engine |
|---|---|---|---|
| `<length>` | `7` | initial | `7` |
| `<number>` | `3px` | initial | `3` |
| `<percentage>` | `7` | initial | `7` |
| `<length-percentage>` | `7` | initial | `7` |
| `<length> \| <percentage>` | `7` | initial | `7` |
| `<integer>+` | `1px` | initial | `1` |

Closing them means keeping a custom property's raw text alongside its parsed
value, which is a change to `parse-declarations` and not to this grammar.
The seventeen other rows agree exactly, including `<color>` with `7`
(`red` in Brave, and `7` here until this round), `<custom-ident>` with `7`,
`<string>` with `7`, `<integer>` with `1.5`, and both dropped registrations.

#### 3. The `@supports` value oracle — the premise was wrong, and that is the finding

Round forty-eight named two rows as a scope cut and gave the reason:

> `@supports (color: #zzz)` and `@supports (text-decoration: flurb)` are
> both black in Brave and true here, because the colour grammar and the
> text-decoration grammar live in `cssom.layout`.

**Neither grammar lives in `cssom.layout`.** That file does not parse a
colour anywhere — it threads the author's string straight onto the draw-op —
and it does not enumerate `text-decoration` either.

- The only colour parser this engine has is
  `kotoba.wasm.host.color/parse-color`, one layer **below** `cssom.core`, in
  the very dependency `kotoba.wasm.dom` already comes from. The colour half
  needed a `require`. Not a move, not a mirror, not a gate, and no change to
  the dependency direction: **the grammar was already underneath.**
- `text-decoration`'s line keywords live in dom-gpu's `.cljs` RENDERERS
  (`draw-text-decoration!`, in `webgpu.cljs` and `webgl.cljs`), which a
  `.cljc` namespace cannot require without breaking the JVM path. That one
  IS a copy — and it gets the gate a copy needs, in exactly the shape
  `layout-read-properties`'s own gate has: re-extract the `case` keys from
  BOTH renderers and fail if the table has drifted from either. Shortening
  the table by one keyword turns it red.

All 35 colour and text-decoration rows now agree with Brave, and the
`:unknown` arm of the colour predicate is a measurement rather than a hedge:

| condition | Brave | before | after |
|---|---|---|---|
| `(color: #zzz)` `(color: flurb)` `(color: 7)` `(color: 0)` | black | true | **false** |
| `(background-color: #zzz)` `(border-top-color: flurb)` `(outline-color: #zzz)` | black | true | **false** |
| `(color: red)` `(#f00)` `(#ff000080)` `(currentcolor)` `(transparent)` `(rgb(1,2,3))` `(hsl(…))` | red | true | true |
| `(color: oklch(…))` `(lab(…))` `(color-mix(…))` `(light-dark(…))` | **red** | true | true |
| `(text-decoration: flurb)` `(text-decoration: 7)` | black | true | **false** |
| `(text-decoration: underline)` `(none)` `(line-through)` `(overline)` `(underline dotted red)` | red | true | true |

A number, a dimension and an unknown bare identifier are genuinely not
colours — the named list is closed at 148 — and an unknown FUNCTION
genuinely might be, which is why the predicate is three-valued and not a
boolean call on `parse-color`.

The colour set is DERIVED from `engine-properties` (`:color` plus every
property whose name ends in `-color`) rather than listed, so it cannot fall
behind the registry the way a fourth hand-maintained table would.

**Thirty conditions still diverge, all fail-OPEN, and all written down** in
`cssom.core` next to the oracle so the next round starts from the browser:
`opacity` `z-index` `flex-grow` `order` `column-count` `font-weight` with
their numeric grammars, and fourteen keyword properties with `flurb`. Each
has a real value beside it that is red on both sides.

The reason to stop there rather than enumerate onward is a measurement too:

| condition | Brave |
|---|---|
| `(font-family: flurb)` | **red** |
| `(list-style-type: flurb)` | **red** |
| `(will-change: flurb)` | **red** |

Three properties whose value space genuinely admits an arbitrary
identifier. An oracle that reasoned its way from `(color: flurb)` to "an
unknown ident is never supported" would have taken these with it, so closing
the other thirty means a vocabulary per property and not one more rule.
`supports-still-fails-open-where-the-value-space-is-open` pins all three.

#### Tried and withdrawn

- **A numeric-value grammar for `opacity`/`z-index`/`flex-grow`/`order`/
  `column-count`.** Twenty measured rows, and it looked like one rule until
  `@supports (flex-grow: auto)` came back BLACK while `(z-index: auto)` and
  `(column-count: auto)` came back red. Three properties, three different
  keyword sets, and the "one numeric rule" it looked like does not exist.
  Measured and left, with the rows above.
- **A vocabulary for `text-decoration` as a keyword property.** It would have
  made `(text-decoration: underline dotted red)` FALSE where Brave says red
  — the fail-CLOSED direction this oracle exists to avoid. The per-component
  walk is what the multi-value form forces.
- **`split-top-level` as the name for the multiplier splitter.** There is
  already one, for media queries, defined LATER in the file — so the new
  definition compiled, the old one won at runtime, and `<length>+` was
  sliced by a comma-only splitter. Renamed to `split-value-components`. It
  cost half an hour and is the reason the whitespace half is not folded into
  the existing function.

### Round forty-nine: CSS nesting, which is a desugaring and not a splitter fix

Round forty-four measured six nesting shapes, found the failure was
DESTRUCTIVE rather than absent, and named the trap in the same breath:

> **Not fixed:** making the brace splitter depth-aware without
> implementing nesting would trade one wrong answer for another — the
> outer declaration would survive and the nested rule would stop applying
> at all, and the control above would go red. The honest fix is
> desugaring (`& span` → `:is(#nc1) span`), which is a feature and not a
> bug fix.

That is the fix this round landed, plus three of the five value functions
that round left measured and unimplemented.

Three columns, because the corpus growing and the engine changing are two
different things and a single before/after would let one pay for the
other. This round has a confound the earlier ones did not: **two other
rounds landed on `main` while it was in flight** — forty-seven (`all` /
`::first-letter`) and forty-eight (the at-rules) — so the middle column is
`main` AS MERGED (`c17735c`), the engine including both of them, on this
round's finished 735-case corpus. Column one to column two therefore
mixes coverage with two other agents' work, and **only column two to
column three is attributable to this round**. Everything below was
re-measured after the second merge; no pre-merge number is reported.

| axis | 711 cases, `aa18bab` | 735, `main` (`c17735c`) | 735, after |
|---|---|---|---|
| line structure | 679/683 | 704/707 | **704/707** |
| geometry (boxes) | 2315/2331 | 2368/2384 | **2376/2384** |
| geometry (clean cases) | 697/711 | 720/735 | **728/735** |
| paint order | 17713/17762 | 18343/18362 | **18343/18362** |
| paint order (clean cases) | 699/711 | 724/735 | **724/735** |
| computed style (values) | 32713/32745 | 33465/33487 | **33481/33487** |
| computed style (cases clean) | 688/711 | 722/735 | **731/735** |
| cascade-attributed residual | 31 | 21 | **5** |

`src/` was NOT touched by the corpus half of this round. The residual's
21 → 5 is the whole of what this round moved on that axis, and it accounts
for itself exactly: eight values from the six original nesting cases, and
eight from the four new nesting cases that carry a colour divergence
(2 + 2 + 1 + 3). The two `&`-specificity cases contribute none, for a
reason given below.

**What is left in that residual is five values in three causes**, and
`@scope` is two of them — see the last section here for its full
measurement. Line structure and paint order are byte-identical across the
last two columns, which is what a change confined to the cascade should
look like.

**`--dump-ops` was diffed per case, corpus-wide, in BOTH directions,
against `main` as merged and on the same 735 cases.** Exactly eight cases'
box lists changed, every one of them TO the browser's number and none away
from it; **the other 727 are byte-identical**:

| case | `main` | after | Brave |
|---|---|---|---|
| `:cascade/a-registered-custom-property-has-an-initial-value` | 800×20 | **60×20** | 60×20 |
| `:cascade/an-invalid-value-for-a-registered-property-becomes-its-initial` | 800×20 | **70×20** | 70×20 |
| `:cascade/a-registered-property-with-inherits-false-does-not-inherit` | 200×20 | **80×20** | 80×20 |
| `:cascade/env-resolves-a-known-variable-rather-than-its-fallback` | 800×20 | **0×20** | 0×20 |
| `:cascade/env-with-an-unknown-name-uses-its-fallback` | 800×20 | **130×20** | 130×20 |
| `:cascade/attr-in-a-length` | 800×20 | **55×20** | 55×20 |
| `:cascade/attr-falls-back-when-the-attribute-is-unusable` | 800×20 | **30×20** | 30×20 |
| `:cascade/attr-resolves-inside-calc` | 800×20 | **65×20** | 65×20 |

The same diff was run against the 711-case baseline this round started
from, where three of those eight exist and all three changed, and the
other 708 did not.

That the six nesting cases are not in either list is the point of running
both dumps: their divergence is a colour, which the ops dump cannot see.
The ops diff proves the rule splitter — which every case's CSS goes
through — moved nothing; the computed-style axis proves the nesting cases
actually changed.

**Three of the new cases, and two more, agree on BOTH sides, and the
round says so rather than counting them.** `a-registration-with-a-relative-initial-value-is-invalid`,
`env-with-no-fallback-invalidates-the-whole-declaration` and
`the-legacy-string-attr-is-not-valid-in-a-length` all report 800 on an
engine that has none of these features, because "kept the raw string" and
"correctly declined" both read as `auto`. Each is paired with a case that
DOES move (800→60, 800→130, 800→55), and only the pair is evidence.
The two `&`-specificity cases are the same shape for a different reason:
the old splitter recovered `& span { color: red }` as a rule of its own
and ignored the stray `&`, which lands on the same two colours by
coincidence — they are regression guards on the desugaring's own choice,
not divergences, and the residual arithmetic above accounts for zero of
their values.

1018 unit tests / 2692 assertions, 0 failures after both merges (966/2475
at `aa18bab`, 983/2521 for this round alone); linter 0 errors, 23
pre-existing warnings, all in `test/`. **34 of this round's new
assertions fail on `aa18bab`'s `src/` and pass after**, and every
control beside them passes on both sides — the nested-rule-in-its-own-block
case, the one-parent specificity case, the unregistered-custom-property
case, the whole-value `var()` case, and both `attr()` invalidity cases. Downstream: `browser`
754/0, `dom-gpu` 130/0, `htmldom` 180/0, all run against this checkout of
`cssom` — htmldom delegates its style parsing to `cssom.core`, and a
cascade change has turned its suite red twice before.

#### One probe page per probe, because a shared page leaks

The first version of this round's measurement put sixteen nesting probes
on ONE page and got four wrong answers out of it. A single

```css
p span { color: rgb(0,0,255) }
```

written for probe F reached the `<span>` of probes A, B, C and D — and
because those four were the `@layer` probes, and an unlayered declaration
beats every layered one, it read as "a nested rule does not keep its
layer", which is a real and plausible bug. It is the same hazard the top
of `cases.edn` names for the corpus page, and it bites a probe harness
harder: the corpus prefixes every selector with its case's own id, and a
throwaway probe page has no such thing.

Every measurement below is one page per probe, launched into headless
Brave 151.1.93.129 over CDP one at a time. It costs ~1.3s per probe and
removes the whole class of error.

#### What `&` actually is, and it is not textual substitution

The forms are the easy half, and all of them were measured:

| written | Brave |
|---|---|
| `#x { color: blue; span { color: red } }` | paragraph blue, span red |
| `#x { span { color: red } color: blue }` | the same — a declaration AFTER a nested rule still applies |
| `#x { color: blue; span {…} color: green }` | **green** — the parent's own declarations cascade among themselves in source order |
| `#x { b {…} & i {…} }` | both match — a nested selector with no `&` gets an implicit DESCENDANT one |
| `#x { > b {…} }` | `& > b` — a leading combinator is the relative form |
| `#x { @media (min-width: 1px) { color: red } }` | red; and blue when the query does not match |
| `& span {…}` at TOP level | matches — `&` there is `:scope`, i.e. `:root` |

The hard half is specificity, and it is the one place a textual `&`
gives the wrong answer:

```css
#zz, .c { & span { color: red } }
div.c span { color: blue }        /* Brave: RED */
```

`#zz` matches nothing on the page. `.c span` alone is (0,1,1) and would
lose to `div.c span`'s (0,1,2). It wins because `&` is
`:is(#zz, .c)` — **the MAXIMUM over the parent list, including an arm
that did not match**. The control that places the same rule from the
other side, and which a careless desugaring turns red:

```css
.c { & span { color: red } }
div.c span { color: blue }        /* Brave: BLUE */
```

Both are in the corpus, as
`:nesting/an-ampersand-carries-the-parent-lists-maximum-specificity` and
`:nesting/one-parent-does-not-raise-a-nested-rules-specificity`. Neither
means anything without the other.

This engine already implements `:is()` and its max-of-arguments
specificity exactly, so the desugaring reuses it rather than inventing a
specificity concept. `expand-nested-selector` therefore has three cases,
and only the third gives anything up:

- **one parent** — plain textual substitution, and it is EXACT: `:is(X)`
  and `X` have identical specificity and identical matching for every X,
  complex ones included, so there is nothing for the `:is()` form to buy.
- **several parents, all compound** — `:is(p1, p2, …)`, which this engine
  parses and scores correctly. This is the case the measurement above
  pins.
- **several parents, at least one COMPLEX** — one expansion per parent.
  Matching is still exact (`.a .b span` selects what `:is(.a .b) span`
  selects); each expansion carries its own specificity instead of the
  list's maximum. Measured cost: `#zz, .a .b { & span { color: red } }`
  against `div.a .b span { color: blue }` is RED in Brave and would be
  BLUE here. Closing it means letting this engine's `:is()` hold a
  COMPLEX selector, which is a change to `parse-simple-selector`/
  `matches-simple?` and not to nesting.

#### Why the desugaring rewrites TEXT, and above every splitter

Two reasons, and the second is the safety argument.

A nested conditional at-rule has to come out as a top-level one *before*
`split-media-segments`/`split-layer-segments`/`split-container-segments`
run. `parse-rules` `assoc`s `:rule/media` onto whatever `parse-rules-raw`
returns, so an inner condition would be CLOBBERED rather than composed
with. Desugaring to text lets nesting compose with all three at-rules in
both directions with no new code in any of them — which is why
`:nesting/a-media-block-nested-in-a-style-rule`,
`:nesting/a-nested-rule-inside-media-keeps-the-condition` and
`:nesting/a-nested-rule-keeps-the-layer-it-was-written-in` all went green
without any of them being handled specially.

That last one is the guard worth naming: a nested rule is an ordinary
member of its enclosing layer, and Brave confirms it (nested rule in the
earlier layer, plain rule in the later one, later wins). The failure mode
it protects against is the one round forty-four measured on the
`@media`-inside-`@layer` cut — losing a layer tag does not merely forget
the layer, it promotes the rule to **unlayered**, which is the strongest
normal position there is.

And: `desugar-nesting` returns its input **unchanged** unless a nested
rule is actually present. `parse-rules` is on the path of every
stylesheet this engine has ever parsed, and a rewrite that only fires on
the shape it was written for cannot move a stylesheet that does not have
that shape. That guard is what the empty ops diff on 705 untouched cases
is measuring, and it has a unit test of its own asserting byte-identical
output.

The scanner is string- and comment-aware (`css-scan-skip`), so a
`content: "}"` or a commented-out block cannot end a rule early;
`@keyframes` is deliberately NOT recursed into, because its `0% { … }`
steps would read as nested style rules.

**One ordering cut, named where it is made.** All of a block's
declaration runs are folded into ONE rule emitted before its nested
rules, which is what makes `#x { color: blue; span {…} color: green }`
come out green. What it costs is a nested `& { … }` block competing with
a declaration written after it in the same block: both land on the same
selector at the same specificity, and here the parent's declaration is
emitted first and loses, where a browser would let source order decide.
No corpus case has that shape.

#### `@property`, `env()` and `attr()` — three of round forty-four's five

Each one is a value function, each was measured before it was written,
and each has a control in the corpus that must NOT move.

**`@property`.** The registration is threaded out of `parse-rules` as one
selector-less pseudo-rule, so no caller — `apply-cascade`, this harness,
`htmldom` — had to learn about a value it did not previously pass. What
the browser said:

| probe | Brave |
|---|---|
| registered `<length>`, `initial-value: 60px`, nothing declares it | 60×20, `getComputedStyle` reports `"60px"` |
| the same reference with NO registration | 800×20, `getComputedStyle` reports `""` |
| parent `--pv: 200px`, element `--pv: notalength`, registered initial 70px | **70×20** |
| `inherits: false`, parent declares 200px | 80×20 (the initial) |
| `inherits: true`, parent declares 200px | 200×20 |
| `syntax: "*"` with no `initial-value`, read as `var(--ps, 90px)` | 90×20 (the fallback) |
| `syntax: "<length>"; initial-value: 2em` | 800×20, `getComputedStyle` `""` |

Two of those are rules that had to be measured rather than assumed. The
third row is the one the task asked about: **an invalid value for a
registered property falls back to the registered INITIAL VALUE**, not to
the inherited 200px and not to `unset`. An *unregistered* custom property
with the same shape is invalid-at-computed-value-time and does inherit —
two different rules, and registering the property is what switches
between them.

The last row is the boundary, and a convenient one: an `initial-value`
has to be computationally independent, so Brave rejects the WHOLE
at-rule for `2em` and reports the property as if it had never been
registered. That is exactly the set of values this engine can carry
anyway. Its control, in the unit tests, is the identical registration
with `32px`, which must still work.

**Scope cut, in `registered-value-valid?`:** only `<length>`,
`<number>` and `<integer>` are really checked; every other syntax
(`<color>`, `<image>`, `<custom-ident>`, an alternation, `*`) accepts
anything, because this engine has no grammar for them and rejecting a
value it cannot check would silently drop declarations that work today.
Measured cost: `@property --c { syntax: "<color>"; initial-value: red }`
with `--c: 7` is `red` in Brave and `7` here.

**`env()`.** The table is a measurement, not a placeholder:

| probe | Brave |
|---|---|
| all four `safe-area-inset-*`, fallback 120px | **0** — defined, so the fallback is not used |
| `keyboard-inset-height`, `safe-area-max-inset-bottom` | 0 — defined |
| `titlebar-area-width`, fallback 131px | **131** — the fallback, so NOT defined here |
| `env(unknown-name, 130px)` | 130 |
| `width: 140px; width: env(unknown-name)` | **800** |
| `calc(env(safe-area-inset-left, 120px) + 50px)` | 50 |

The fifth row is the one that pins the failure mode: an unresolvable
`env()` with no fallback makes the DECLARATION invalid at
computed-value time, and it does **not** fall back to the `140px`
written before it in the same block — it becomes `unset`, and
`width: unset` is `auto`. `titlebar-area-*` is deliberately absent from
this engine's table rather than zero, because defining it would answer 0
where the browser answers the author's fallback.

**`attr()`, and only the TYPED form.** The legacy string form and the
CSS Values 5 typed form behave differently and only one of them is
supported per property — that had to be measured separately, and it was:

| probe | Brave |
|---|---|
| `attr(data-w px, 30px)`, `data-w="55"` | 55 |
| ...attribute absent | 30 (fallback) |
| ...`data-w="abc"` | 30 (fallback) |
| `attr(data-w px)`, `data-w="65"` | 65 |
| ...attribute absent | 800 (invalid) |
| `attr(data-w type(<length>), 35px)`, `data-w="85px"` | 85 |
| `calc(attr(data-w px, 30px) + 10px)`, `data-w="55"` | 65 |
| `width: 150px; width: attr(data-w)`, `data-w="75px"` | **800** |
| `#x::after { content: attr(data-label) }` | `"HELLO"` |

The last two are one control read from both sides: the LEGACY string
form is invalid in a `width` even though the attribute holds a perfectly
good length, and it works in `content`. So `resolve-attr-values` handles
the typed form only and never touches `:content`, whose older,
differently-shaped `attr()` support is left exactly as it was. Custom
properties are skipped too — `--x: attr(data-w px)` is legal CSS and
unsupported here, an honest gap rather than a silent one.

`attr()` is also the only one of the three that runs in `style-element`
rather than in `resolve-value`: `env()` and a `@property` registry are
document-global, an attribute is not.

#### A `var()` gap the `@property` cases exposed

`@property --pn { syntax: "<number>"; initial-value: 3 }` with
`width: calc(var(--pn) * 20px)` is 60px in Brave and came out of this
engine as the literal string `calc(3 * 20px)`, which `cssom.layout`
reads as `auto`. The cause was not `@property`: `resolve-value`
substituted an EMBEDDED `var()` — one that is part of a value rather
than the whole of it — textually, and did not re-parse the result. The
whole-value form has always re-parsed, which is why the gap survived
this long: **every `var()` in the corpus before this round was a whole
value**, so the branch was reachable and untested at the same time.

It now re-parses, and that is corpus-neutral by construction rather than
by luck. `parse-style-value` returns a multi-token value (`"10px 20px"`
from a two-`var()` `padding`) unchanged, so the box-shorthand re-slice
below it still sees the string it expects.

#### Measured and deliberately NOT added

**An embedded `var()` in a `calc()`.** The unit test for it is real and
fails on the base commit — `:style/width` is the literal string
`calc(3 * 20px)` there and the number 60 here. A corpus case for it is
not, and it was written and then removed: `cssom.layout` re-parses a
`calc()` string downstream, so the box is 60×20 on BOTH sides, and
`width` is not one of the fourteen properties the computed-style axis
compares. It would have been a case that passes for precisely the wrong
reason — the same test `revert-layer` on an unlayered declaration failed
in round forty-four. The fix stays, because a cascade that hands
`cssom.layout` a string it happens to recover is not the same as one that
hands it a number, and `cssom.core/computed-style` and a live page's
`getComputedStyle` read the cascade directly.

#### `@scope` — measured in full, deliberately not implemented

**LANDED IN ROUND FIFTY-TWO**, above, which re-measured every row below from
the browser rather than trusting them and found one of them incomplete:
proximity is below SPECIFICITY as well as below layer, which the "sits
between specificity and order" phrasing here does not quite say. See that
round for the shapes that place it from both sides, and for the two rows
this section does not have — that an unscoped declaration is at infinite
proximity, and that `!important` does not reverse proximity the way it
reverses layer order.

The fourth value function of round forty-four's five, and the reason it
is not in this round is a specific one rather than "ran out of time":
one of its rules is a **new dimension in the cascade sort tuple**, not a
parse or a value change. Measured, so the next round starts from the
browser rather than from the spec:

| probe | Brave |
|---|---|
| `@scope (#r) { .x { … } }` | inside red, outside black |
| `@scope (#r) { div { … } }` | the scope ROOT ITSELF does not match — a scoped rule carries an implicit `:scope ` DESCENDANT prefix |
| `@scope (#r) { :scope { … } }` | ...and `:scope` is how you reach the root |
| `@scope (#r) to (.lim)` | donut hole: `<p>` before `.lim` red, `<p>` inside `.lim` black, `<p>` outside `#r` black |
| the limit element `.lim` itself | **black** — the limit is excluded |
| `@scope (#r) { p }` vs `div p` | **blue** — the scope root contributes NO specificity; `p` stays (0,0,1) |
| `@scope (#r) { :scope p }` vs `div p` | **red** — `:scope` is a pseudo-class, so `:scope p` is (0,1,1) |
| `.o1 > .o2 > p`; `@scope (.o1)` red FIRST, `@scope (.o2)` blue SECOND | blue |
| `.o3 > .o4 > p`; `@scope (.o4)` blue FIRST, `@scope (.o3)` red SECOND | **blue** |
| `@scope { p { … } }` (no prelude, in a `<head>` `<style>`) | no match |

The last pair is the one that costs. Reversing the source order does not
reverse the answer, so **PROXIMITY — the nearer scope root — beats
source order**, and it sits between specificity and order in the cascade.
`resolve-style-and-flow` sorts on
`(juxt :important? :origin :inline? :layer :specificity :order)`; scope
needs a seventh key computed per (rule, element) pair from the ancestor
distance to the matched root, which is a different kind of change from
anything in this round. The two specificity rows are the other half of
why it is not a parser change: the prelude contributes nothing, but
`:scope` written explicitly contributes a pseudo-class, so the two cannot
share one implementation shortcut.

`:cascade/a-scope-rule-does-not-reach-outside-its-root` stays in the
corpus, still red, still carrying the browser's numbers. (Round fifty-two found
that it was red for a DIFFERENT reason than this section says: the
harness's own id prefix defeated the scope, so Brave read both its
paragraphs as black. `scope-css` is fixed and the case now measures what it
claims.)
### Round forty-eight: the at-rules stop being decoration

Round forty-four put seventy-one at-rule cases into the corpus and found
eleven divergences it did not fix, in three clusters: `@supports` was not
implemented at all and failed OPEN, `@media` had three grammar gaps behind
a working feature set, and `@layer` had four. This round closes all eleven,
and every rule below was read out of a real headless Brave 151.1.93.129
over CDP on 2026-08-06 before a line of it was written.

Three columns, because the corpus growing and the engine changing are two
different things. The middle column is the **unmodified engine at the base
commit** on the unmodified 711-case corpus — it reproduces round
forty-six's published numbers to the value, which is what says the two
right-hand columns are comparable. The third is this round's engine on the
same 711 cases; the fourth adds this round's nine new cases.

| axis | 711, base engine | 711, after | 720, after | 720, merged |
|---|---|---|---|---|
| line structure | 679/683 | **679/683** | 688/692 | 689/692 |
| geometry (boxes) | 2315/2331 | **2316/2331** | 2334/2349 | 2338/2349 |
| geometry (clean cases) | 697/711 | **698/711** | 707/720 | 710/720 |
| paint order | 17713/17762 | **17713/17762** | 17938/17987 | 17968/17987 |
| paint order (clean cases) | 699/711 | **699/711** | 708/720 | 709/720 |
| computed style (values) | 32713/32745 | **32724/32745** | 32976/32997 | 32983/32997 |
| computed style (cases clean) | 688/711 | **699/711** | 708/720 | 711/720 |
| cascade-attributed residual | 31 | **20** | 20 | 13 |

The fourth column is after merging round forty-seven (`all` and
`::first-letter`), and the gain in it is theirs, not this round's:
`--dump-ops` diffed across the merge changes exactly four cases, and all
four are `:cascade/all-*` and `:selector/first-letter-changes-the-line-box`.
The two rounds touch the same three declaration-entry constructors in
`resolve-style-and-flow` and nothing else — `all`'s `:decl-index` and this
round's `:layer-key` answer different questions and neither reads the
other.

`--dump-ops` was diffed corpus-wide between the first two columns.
**Exactly one case's box list changed, in one direction, and it is the
intended one**: `:layer/revert-layer-rolls-back-to-the-previous-layer`,
800×20 → 200×20, which is Brave's own number. Nothing else moved a pixel
in 711 cases. That is the whole geometry delta — the other ten divergences
are colours, which only the computed-style axis can see. Diffed again
between the second and third columns: the nine new cases add nine new box
lists and **change none of the 711 that were already there**.

#### `@supports` needed a support oracle, not a parser change

Round forty-four declined to fix this and said why: "answering `@supports`
honestly means a real support oracle for this engine's own property/value
grammar". That is right, and the oracle turned out to have **two halves
that live in different places**, which is the interesting part.

The **property** half is a registry assembled from four sources, three of
which are tables this engine already maintains for its own reasons —
`inherited-properties` and `initial-values` (what the CSS-wide keywords
need), `em-resolvable-properties` (what relative-length resolution needs),
and every property the engine's own UA stylesheet declares, read back out
through `parse-rules`, so the parser genuinely answers for that part. The
fourth is `layout-read-properties`, the 137 `(style node :k)` call sites in
`cssom.layout`. That one is a copy, because `cssom.layout` requires
`cssom.core` and not the other way round — so it is **gated**: a test
re-extracts the call sites from the source and fails if the two ever
disagree.

The **value** half cannot come from the property registry, because
`display` and `flurb` are equally well-formed identifiers and only a
per-property vocabulary tells `display: grid` from `display: flurb`. It is
three separate answers depending on what kind of property it is: a
keyword-valued property is checked against its own vocabulary; a
length-valued one against the length grammar (which is why
`@supports (width: 10)` is false and `(width: 10px)` is true, exactly as
`@media`'s own length parser decides one line away); and a **shorthand is
answered by running the engine's own expander** — `padding: 1px 2px`
expands to four longhands and `padding: flurb` expands to nothing, so the
parser answers for itself.

`selector()` has its own oracle and it is a real one: `matches-pseudo?`
returns false for an unrecognised pseudo-class, which is indistinguishable
at match time from a recognised one that did not match, so the set of
implemented names is stated and gated the same way against that function's
own `case` keys.

**What Brave does with a condition it cannot parse, measured — and it is
not what it does with a false one.** Forty-four `@supports` rules were
written onto one page and `document.styleSheets[0].cssRules` read back:
**forty survived**. The four that did not were `garbage`, `not garbage`,
an unparenthesised `display: grid`, and `(display: grid) or garbage`. Set
against the ones that did:

| condition | Brave | what it says |
|---|---|---|
| `(grid)` | black | a `<general-enclosed>` is FALSE |
| `not (grid)` | **red** | ...and `not` inverts it |
| `frobnicate(x)` | black | an unknown FUNCTION is general-enclosed too |
| `not frobnicate(x)` | **red** | ...same inversion |
| `garbage` | black | does not parse: the whole at-rule is invalid |
| `not garbage` | **black** | ...and a `not` cannot rescue what was never there |
| `(display: grid) or garbage` | black | one unparseable arm poisons a true one |

So the evaluator is three-valued internally — true, false, and a third
value that propagates through `not`/`and`/`or` instead of being inverted —
even though the two failure modes hide the same rules and are
indistinguishable from outside. `:supports/a-general-enclosed-condition-is-
false-and-not-inverts-it` and `:supports/an-unparseable-condition-is-not-a-
false-one` are the pair in the corpus; neither alone measures anything.

Scope cut, with its numbers: the value half only speaks for properties
whose value space this engine writes down. `@supports (color: #zzz)` and
`@supports (text-decoration: flurb)` are both **black in Brave and true
here**, because the colour grammar and the text-decoration grammar live in
`cssom.layout`. The fail direction is deliberate and matches `@media`'s:
a real declaration is never called unsupported.

#### `@media` was a feature list where it needed to be a grammar

The three divergences were `not all and (…)`, range syntax, and `em`. They
look like three missing features and are one missing distinction: the
documented default that "unrecognized features match, so nothing is
silently hidden" is **right for a feature and wrong for grammar**, and on
grammar it does not widen an answer, it inverts one.

The engine now parses the whole `<media-query-list>` — the comma list, the
`not`/`only` qualifiers, media types, `and`/`or`, nested parens and Media
Queries 4 range syntax — and keeps the fail-open default for exactly one
thing: a feature NAME inside well-formed parens that it does not
implement. `:media/an-unrecognized-feature-still-applies`
(`min-resolution: 1dppx`) is what that default buys, and
`:media/an-unknown-media-type-does-not-apply` (`@media flurb`, black in
Brave) is its boundary — a media type is a closed vocabulary, a feature set
is not.

Two numbers that had to be measured rather than reasoned about:

- **`em` in a media query is 16px, not the root element's font size.**
  Measured on a page declaring `html { font-size: 32px }`:
  `(min-width: 40em)` still matched at a 756px viewport, and
  `(min-width: 47.25em)` matched *exactly* — 47.25 × 16 = 756.0. Against
  the root's 32 it would have been 1280 and 1512.
- **A unitless non-zero length is invalid, not px.** `(min-width: 100)` is
  black where `(min-width: 100px)` is red, so the query is invalid rather
  than false-by-comparison. `(min-width: 0)` and `(min-width: -5px)` are
  both red.

And one that decides the shape of the top level: `@media (min-width:
5000px), garbage garbage` is reported back by Brave as `(min-width:
5000px), not all` **with the rule still standing**. An unparseable query
becomes `not all`; it does not invalidate its neighbours in the list. That
is the opposite of `@supports`, where one unparseable arm drops the whole
at-rule, and the two evaluators differ in exactly that place for exactly
that reason.

Where this engine still diverges, measured and deliberate: Brave is
three-valued about unknown FEATURES too, so `(min-width: 100px) and
(flurb: 1)` and `(min-width: 5000px) or (flurb: 1px)` are both black there
and red here. That is the cost of the fail-open default, and it is the same
cost `min-resolution` is the benefit of.

#### `@layer` is a tree, and three separate walks could not see it

All four `@layer` divergences came from one shape: layer context was
computed by three `split-*-segments` passes chained in a fixed order,
media → container → layer. A `@layer` inside a `@media` was seen and a
`@media` inside a `@layer` was not — and losing the tag does not forget the
layer, it promotes the rule to **unlayered**, the strongest normal position
in the author origin. One recursive walk carrying the context each nested
rule inherits has no order to get wrong, and it made `@supports` nesting
free.

The other three needed the layer *order* to stop being a flat list of
first-appearance names. Measured, on one page:

| shape | Brave | what it says |
|---|---|---|
| `@layer { p#x {red} } @layer { #x {blue} }` | blue | each anonymous block is its OWN layer |
| `@layer n { … } @layer { … }` | the anonymous one | ...and it takes its place in the order like any other |
| `@layer o { @layer i { p#x {red} } } @layer o.i { #x {blue} }` | red | the nested form and the dotted form are ONE layer |
| `@layer o { red @layer i { blue } }` | **red** | a layer's own declarations beat its sublayers |
| `@layer o { @layer i { blue } red }` | **red** | ...and the source order of the two does not matter |
| `@layer x.y {red} @layer x {blue}` | blue | `x.y` creates `x` too, and the same rule applies |

Which is a **post-order traversal of the layer tree**: children first, in
first-appearance order, then the node itself. Rows four and five are what
a flat list cannot express at all, and are why the fix is a tree rather
than a second sort key.

`revert-layer` was stored as the literal string `revert-layer`, which
`cssom.layout` cannot read as a width — 800×20 against Brave's 200×20, and
the `div w` +600 in the geometry residual. It is now the fifth CSS-wide
keyword, and it resolves to "the value this property would have had if no
declaration in the winner's own LAYER existed". That phrasing, rather than
"in an earlier layer", is what six measured shapes say:

| stylesheet | Brave |
|---|---|
| `@layer a { w:200 } @layer b { w:120; w:revert-layer }` | **200** |
| `@layer a { w:300 } @layer b { w:200 } @layer c { w:120; w:revert-layer }` | **200** — the previous layer, not the first |
| `@layer a { w:120; w:revert-layer }` | **auto** — past the whole author origin |
| `#x { w:120 } #x { w:revert-layer }` | **auto** — unlayered is a layer for this purpose |
| `@layer a { w:200 } #x { w:120; w:revert-layer }` | **200** — an unlayered `revert-layer` rolls back INTO the layers |
| `@layer a { color:green } @layer b { w:120; w:revert-layer }` | **auto** — a previous layer declaring nothing is not one declaring the initial value |

Rows four and five together are why it is not `revert` with a layer test.

The control that had to survive all of this is
`:layer/important-reverses-the-layer-order`: `!important` reverses layer
order *and* flips unlayered from strongest to weakest, the engine already
got it right, and turning a list into a tree must not disturb it. It is in
the unit suite three times over, and it passes on both sides of the commit.

#### Proved to fail first

Twenty new `deftest`s, 109 assertions. Run against the **base commit**, 42
assertions fail across 17 of the 18 behavioural groups; the eighteenth is
`important-still-reverses-the-layer-order-after-the-tree-rewrite`, which is
pure control and passes on both sides. Every group also carries controls
that pass on both sides — an `and`-joined media query that does match
beside one that does not, a range below the viewport beside one above it,
an `em` that fits beside one that does not, `not (display: flurb)` beside
`not (display: grid)`, `@layer` inside `@media` beside `@media` inside
`@layer`.

Two of the twenty are drift gates rather than behaviour: they re-extract
`layout-read-properties` and `implemented-pseudo-classes` from the sources
they claim to mirror and fail if the copies fall behind. They are the price
of `cssom.layout` requiring `cssom.core` and not the reverse.

### Round forty-six: `writing-mode`, which is a change of basis and not a second engine

`:text/writing-mode-vertical-rl` had been in the corpus for eleven rounds
with a note saying why it was not being chased: *"a vertical writing mode
is a second axis convention through every function in cssom.layout, not a
property to read."* Half of that was right. It **is** a second axis
convention. What it is not is a convention *through every function* — it is
a change of **basis**, applied once, at the boundary where the mode
changes, and the horizontal algorithm underneath is already the right
algorithm in that basis.

That claim is a measurement, not a design preference, and it was made
before a line was written. Brave 151 over CDP, 2026-08-06, in the corpus's
own page shape (800px, monospace 14/20 — this browser's monospace advances
7px per character):

| shape | Brave | this engine, before |
|---|---|---|
| `<div w:300 h:120><div wm:vertical-rl>alpha beta` | inner box **20 × 70** | 300 × 20 |
| ...the same in a **400**-tall parent | still **20 × 70** | 300 × 20 |
| ...the same in a **60**-tall parent | **40 × 60**, two lines | 300 × 20 |
| `alpha` word rect | (3, 0) 15 × 35 | one horizontal run |
| `beta` word rect | (3, **42**) 15 × 28 | on the same line |

Every one of those is the horizontal answer with the two axes exchanged:
70 is the text's own advance, 20 is the line-height, 60 is where a 70px
run wraps against 60px of room. Nothing in the list is a new rule about
text, or about boxes. It is the same rule, read along the other axis.

#### The four modes are two bits, and one of them is not a rotation

Measured with one probe per mode — `margin-inline-start: 40px;
margin-block-start: 13px` on a box in a 300 × 200 parent, read back through
`getComputedStyle` — plus a second (`inline-size: 70px`, then two block
children of declared block sizes 30 and 50) for what the boxes do:

| mode | dir | 40px lands on | 13px lands on | children stack |
|---|---|---|---|---|
| horizontal-tb | ltr | margin-left | margin-top | downward |
| horizontal-tb | rtl | margin-right | margin-top | downward |
| vertical-rl | ltr | margin-**top** | margin-**right** | right to left |
| vertical-rl | rtl | margin-**bottom** | margin-right | right to left |
| vertical-lr | ltr | margin-top | margin-**left** | left to right |
| vertical-lr | rtl | margin-bottom | margin-left | left to right |
| sideways-rl | ltr | margin-top | margin-right | right to left |
| sideways-rl | rtl | margin-bottom | margin-right | right to left |
| sideways-lr | ltr | margin-**bottom** | margin-left | left to right |
| sideways-lr | rtl | margin-**top** | margin-left | left to right |

Two bits, then, and `direction` is not one of them: it swaps the inline
pair in a vertical mode exactly as it does in a horizontal one, and it
cancels out of the physical→canonical mapping entirely, because it swaps
inline-start and inline-end on **both** sides of that mapping.

**`sideways-rl` and `vertical-rl` are the same box geometry in every shape
measured.** They differ only in how the glyphs of an upright script are
oriented, and no box in this corpus can see that. `sideways-rl` is in the
corpus as `vertical-rl`'s control, and that is exactly what it is worth.

**`sideways-lr` is the one mode that is not a rotation of the other three:
its inline axis runs UP the page.** `inline-size: 70px` puts its single
word at y=63 in a 70-tall box where every other mode puts it at y=0, and a
two-line `alpha beta` in a 40-tall parent packs `alpha`'s 35px of ink at
y=5..40 and `beta`'s 28 at y=12..40 — both ending at the far edge. It is
the reason the basis table holds a signed permutation per mode rather than
a rotation count.

#### What that bought, and what it cost

`writing-mode` is now **three tables** (`writing-mode-basis`,
`writing-mode-sides` in cssom.layout, `logical-flow-sides` in cssom.core),
two style rewrites built from them, and one block of bindings at the top of
`layout-node`'s element branch — below which nothing knows a vertical mode
exists. The style map arrives in the box's own canonical frame, `avail-width` is its available
*inline* size, the dispatch lays out at the origin, and one matrix puts the
result back into the parent's frame — reusing `transform-ops`, which
already documents a quarter turn as the case where its axis-aligned
bounding box is EXACT rather than approximate.

Corpus-wide, 688 → **711** cases (rounds forty-four and forty-five landed
underneath this one; both columns are measured after merging both), and the
entire pre-existing residual is byte-identical on all four axes — every
count of DISAGREEING points below is unchanged, and every case that was
failing before is failing for the same reason after:

| axis | main, 688 cases | this branch, 711 cases |
|---|---|---|
| line structure | 656/660 | **679/683** |
| geometry (boxes) | 2251/2267 | **2315/2331** |
| geometry (clean cases) | 674/688 | **697/711** |
| paint order (points) | 17138/17187 | **17713/17762** |
| paint order (clean cases) | 676/688 | **699/711** |
| computed style (values) | 31819/31851 | **32713/32745** |
| computed style (clean cases) | 665/688 | **688/711** |

Read the DISAGREEING halves rather than the agreeing ones, because that is
where a regression would show: geometry 16 → 16 boxes, paint 49 → 49
points, computed style 32 → 32 values, line 4 → 4 cases. Every one of those
four counts is identical, and the composition changed by exactly one entry
in each of the two axes that moved at all: `:text/writing-mode-vertical-rl`
left both, `:writing-mode/aspect-ratio-is-not-rotated` took its place in
geometry and
`:writing-mode/a-horizontal-box-inside-a-vertical-one-turns-back` took it
on the line axis — both deliberately, see the scope cuts below. The new
group scores **22/23**.

**One line of the corpus-wide `--dump-ops` changed**, and it is the case
this round is about: `:text/writing-mode-vertical-rl`'s inner box,
`300 × 20` → `20 × 70`, which is Brave's number exactly. 688 case blocks
diffed, 23 added, **zero pre-existing cases moved** — which is the property
that mattered, because an axis swap can reach every layout path in the
file, and the whole corpus outside this group is `horizontal-tb`. It is
guaranteed structurally rather than by luck: `horizontal-tb` is the
identity in all three tables and both style rewrites return their argument
unchanged for it. (Measured three times, against three successive merge
bases as main moved underneath this branch; the same one line each time.)
966 unit tests / 2475 assertions, 0 failures; 0 lint errors and the same 25
pre-existing warnings. Fifteen new or rewritten unit tests, of which
**fourteen were confirmed failing against the base commit's `src/`** (42
assertions) before this round's `src/` was written, each with a control
beside it that passes on both sides. The fifteenth is the one whose entire
job is to be that control and pass on both sides:
`nothing-outside-a-vertical-subtree-is-rotated`, three horizontal shapes
covering the four property families the rotation touches.
Downstream: `browser` 754/0, `dom-gpu` 130/0, `htmldom` 180/0, all against
this branch's cssom. **No new draw-op key**, so `dom-gpu`'s
`retained_draw_ops.edn` golden needed no regeneration.

#### The gate that was opened, and why it was there

Round thirty-six implemented logical properties and **gated the whole
logical→physical rename on `horizontal-tb`**, with a unit test asserting
the gate so it could not drift into a silent half-implementation. Its
reasoning is worth quoting because it was right: adding the rotated rows
*"would make `getComputedStyle` right while every box stayed laid out
horizontally, a mapping neither layout axis of this corpus could check."*

That is the condition this round removes. The rows are in, and the geometry
axis checks them: `inline-size: 70px; block-size: 20px` is a 20 × 70 box on
both sides (`:writing-mode/logical-sizes-name-the-other-axis`),
`padding-block-start: 12px` widens the box's right edge without moving its
content (`:writing-mode/block-start-is-the-right-edge`), and
`padding-inline-start: 12px` is its control on the other axis. The test that
asserted the gate is now the test that asserts the rotation, with the
reason recorded in it rather than only the number.

#### Three rules that had to be right and are not the axis swap

**A box establishing an orthogonal flow shrink-wraps.** `inline-size: auto`
is **fit-content** against the containing block's *block* size, not
fill-available. This is what the 120 / 400 / 60 row of the first table
measures, and it is what makes the corpus case 70 tall rather than 120.
Getting the ORDER wrong here is a real trap and was hit once: the two
percentage bases *exchange* at an orthogonal boundary, and reading the
available inline size out of the map after the exchange had already
rewritten it handed the box its parent's inline size — the case stopped
wrapping at a 60-tall parent and sat at its 80px max-content.

**It also establishes a block formatting context.** Measured rather than
cited, both halves: a child's block-start margin stays inside it (the box
is **45** wide for `margin-right: 25px` on the child, against a horizontal
control that collapses the same margin out to the page), and a float stays
inside it (**40 × 30**, with the following sibling at y=30).

**Its margins are read by whoever places it, in *that* box's frame.** This
is the one property family the rotation must leave alone, and the
distinction only exists at the boundary: `margin: 10px 20px 30px 40px` on a
vertical-rl box between two ordinary blocks puts it at **(40, 30)** — its
physical margin-left and its physical margin-top, applied physically —
while one level in, `margin-top: 10%` on a child of a vertical box is 12px
applied *down the page*, along the inline axis. Same property, same
spelling, opposite axis, and the mode that decides is the parent's both
times. Hence the ambient mode rides on `theme` rather than on the inherited
style map: `node-style` is called by a box's PARENT (to read its margins,
to measure it) as often as by the box itself, and `theme` is the one
argument every one of those calls shares.

That placement is also what makes the intrinsic-size readers right, and
finding out cost one wrong number: with the rotation applied a level up in
`layout-node`, two `width: 30px` / `width: 50px` children of a vertical box
gave it a canonical width of 50 — their *unrotated* `width` — where Brave
says 21, the max-content of their text. `measure-child`,
`block-max-content-width`, the flex base size and a grid track's intrinsics
all read a child's style map through `node-style` and never through
`layout-node`.

#### `text-orientation`, of which exactly one value is implemented

`text-orientation` changes what a *character* advances along the inline
axis, which is a text-measurement rule and not a layout one. Measured,
`alpha` inside `vertical-rl`:

| value | inline extent | rule |
|---|---|---|
| `mixed` (initial) | 35px | latin is set sideways: its horizontal advance |
| `sideways` | 35px | identical, for latin |
| `upright` | **70px** | 5 × the 14px em |

`upright` is implemented, because the rule is exact without a Unicode
table: **every** character advances by the em, the space included (`alpha
beta` is 140, which does not fit a 120-tall parent, so Brave wraps it and
reports 40 × 120 — and so does this). It is applied by substituting the
theme's `:measure-text`, not by a branch in `glyph-advance`, and finding
out why cost one wrong number: `layout-text`, the flex base size, the table
caption's intrinsic width and the text-selection caret all read
`(:measure-text theme)` directly, so a branch in `glyph-advance` sized the
box correctly and never reached the line breaker — `alpha beta` stayed on
one 140px line inside a 120px box instead of wrapping.

**`mixed` is NOT implemented for the scripts it actually distinguishes**,
and that is the scope cut. `mixed` sets the em advance *per character*, for
upright scripts only. Measured, `あいう えお` inside `vertical-rl`: **77px**
under `mixed` (three ems, a 7px sideways space, two ems) and **84** under
`upright` (six ems). So this engine is right for `mixed` on latin and
digits — which is what the corpus holds — and 7px per CJK character short
otherwise. Closing it needs a script-property table, which is a different
kind of change from this one.

#### Scope cuts, each with the number a fix will need

- **Glyphs are not rotated.** A `:text` op is a string at an origin laid out
  along +x, and there is no rotated-glyph primitive here or in this
  engine's hosts — the same thing `transform-ops` already says about
  `rotate()`. Two consequences, one repaired and one not.

  Repaired: under a quarter turn the words of one line are at different
  physical y's, so one op cannot express the line at all. A rotated run is
  emitted as **one op per word**, each at its own transformed origin, and
  each re-anchored to the top-left corner of its transformed em box rather
  than left at the transformed origin point (which is the top-*right*
  corner under vertical-rl and the *bottom*-left under sideways-lr).
  Without the re-anchoring a `sideways-lr` op reports y=40 for ink that
  starts at y=5.

  Not repaired, and it is the one case in this group that fails: a page
  that MIXES orientations cannot be scored on the line axis.
  `:writing-mode/a-horizontal-box-inside-a-vertical-one-turns-back` has
  every box exact, every paint sample exact, every computed value exact,
  and reports `["x alpha beta"] ["y"]` where Brave reports `["x"] ["alpha
  beta"] ["y"]`. A rotated word's ink in Brave is 15 wide and 7 tall; this
  engine's is 7 wide and 15 tall at the same origin, so the vertical
  sibling's `x` overlaps the horizontal child's line band and the same
  clustering function merges them. Fixing it means a `:text` op that
  carries its orientation — a new op key, and `dom-gpu`'s
  `retained_draw_ops.edn` golden pins whole op maps.

- **`aspect-ratio` is not rotated**, and it is the group's other failing
  case, deliberately. Its two terms are the physical width and height even
  inside a vertical mode: `inline-size: 60px; aspect-ratio: 2` is **120
  wide × 60 tall** in Brave and 30 × 60 here, the ratio inverted. It is one
  more entry in `rotate-box-style`, but the ratio is resolved in three
  places and none of them is measured against a vertical mode yet.

- **`overflow-x`/`overflow-y` and `scroll-left`/`scroll-top` are not
  rotated.** They name physical axes in the DOM — `element.scrollTop` is
  physical in a vertical mode — so rotating them on the way in without
  rotating them on the way out would be worse than leaving them.

- **An orthogonal flow whose containing block has no definite block size
  does not wrap.** Brave falls back to the nearest **scrollport's** block
  size, and both halves are measured: inside `<div style="width:300px;
  height:150px; overflow:auto">` a long vertical-rl run is 150 tall, and
  with no scroll container anywhere it is **419** — exactly
  `window.innerHeight` for this headless window, read back in the same
  probe and unchanged by pushing the box 300px down the page. This engine
  has no viewport block size: `draw-ops` takes a `:width` and nothing else.
  Inventing one would be inventing the answer, so an unconstrained
  orthogonal flow resolves `fit-content` to `max-content`. `max-height`
  also counts as definite in Brave (**90** in a `max-height: 90px` parent)
  and `definite-content-height` does not answer it, so such a parent takes
  the same fallback.

- **An element's own CSS `transform` is applied inside the rotation.** A
  `translateX(10px)` in a vertical-rl box moves its content 10px *down* the
  page where Brave moves it 10px right. All ten of the corpus's transform
  cases are `horizontal-tb`, where the two orders are the same matrix.

- **An orthogonal child's contribution to its parent's intrinsic size is
  its canonical inline size, not its block size.** Measured, `<div
  style="width:max-content"><div style="writing-mode:vertical-rl">alpha
  beta</div></div>` is **20 wide** in Brave — the vertical child's *block*
  size. The general fix needs the child laid out before the parent is
  sized, a second pass this file's single-pass intrinsic readers do not
  have.

- **`writing-mode` on a non-atomic inline.** Measured, a `<span
  style="writing-mode: vertical-rl">` inside a sentence computes
  `display: inline-block` in Brave and lays out as a 20 × 28 atomic inline.
  No blockification is implemented; the corpus has no case.
### Round forty-seven: `all`, and the pseudo-element with no box

Two features round forty-four measured and left, and they are the largest
remaining residual on the geometry and paint axes respectively. Both landed.
Every number below was read out of a real headless Brave 151.1.93.129 over
CDP on 2026-08-06, in the corpus's own frame (800px, 14px monospace, 20px
line-height), before a line was written.

| axis | base commit | after |
|---|---|---|
| line structure | 679/683 | **680/683** |
| geometry (boxes) | 2315/2331 | **2319/2331** |
| geometry (clean cases) | 697/711 | **700/711** |
| paint order (points) | 17713/17762 | **17743/17762** |
| paint order (clean cases) | 699/711 | **700/711** |
| computed style (values) | 32713/32745 | **32720/32745** |
| computed style (cases clean of a cascade mismatch) | 689/711 | **692/711** |
| cascade-attributed residual | 31 | **24** |

`--dump-ops` was diffed corpus-wide. **Exactly four cases' box lists
changed, and all four are the four targeted** — the three `:cascade/all-*`
and `:selector/first-letter-changes-the-line-box`. Nothing else in 711 moved
a pixel, in either direction, which is the number that matters for a change
that reaches every property in the cascade.

#### `all` is not a phase, it is a declaration

The temptation is to read `all: initial` as "reset, then apply the rest".
Six shapes say it is not, and the fourth is the one that decides the design:

| shape | Brave's width |
|---|---|
| `#a { width: 120px; all: initial }` | auto |
| `#a { all: initial; width: 120px }` | 120px |
| `#a { all: initial } #a { width: 120px }` | 120px |
| `div#a { width: 120px } #a { all: initial }` | **120px** |
| `#a { all: initial !important } #a { width: 120px }` | auto |
| `#a { all: initial } #a { width: 120px !important }` | 120px |

A higher-specificity longhand beats `all` even though it is written first.
So `all` is a shorthand whose longhands take part in the cascade with `all`'s
own specificity, origin, layer, importance and position — and the
implementation is to expand it into exactly that: one clone per property,
spliced into the ALREADY-SORTED entry list at the `all` entry's own place.
All six rows then fall out of `group-by` with no code of their own.

That placement — above the flow resolution and above the logical→physical
rename — is the other half. `all` reaches `writing-mode` (below), so the flow
this element hands its children has to be resolved after it; and
`p { margin-inline-start: 40px; all: initial }` reports margin-left **0**
where the reverse order reports **40**, which only works if the clone
written for `margin-inline-start` is renamed alongside the declaration it
beats.

#### Which longhands, and the three that are not

`all` is "every property", and a cascade cannot enumerate those. What it can
enumerate is the set that has anything to say: **everything anyone declared
for this element** (which is what beats the author's own earlier `width` and
the UA sheet's `p { margin: 1em 0 }`), plus **`initial-values`** (the
properties whose initial value is not the same as absence), plus
**`inherited-properties`** (where absence means *inherit*, so `initial` has
to be written to stop it). For `initial` and `unset` that is provably
complete: a property outside all three has an initial value of absence,
which is already what it computes. `inherit` needs a fourth — the parent's
own resolved properties, because `all: inherit` copies a `width: 300px` this
element has never heard of (measured: 300px, purple).

The exemptions were measured rather than recalled, on a parent declaring all
three: under `all: initial` the child reports the parent's `direction: rtl`,
the same `unicode-bidi` its plain sibling does, and the parent's
`--mycustom: 42px`, while the other 44 properties on it are reset.

**`writing-mode` is not exempt**, and that had to be measured separately
because it looks like it belongs with the pair above. Inside a
`writing-mode: vertical-rl` parent, `all: initial` reports `horizontal-tb`
while `all: unset` and `all: revert` both report `vertical-rl`.

#### `medium` is answerable under `all` and nowhere else

`initial-values` has deliberately held no `font-size` entry since the UA
sheet moved into the cascade: `font-size: initial` is `medium`, and `medium`
is keyed on the default size of the FAMILY in use — 13 on a monospace page,
16 on a proportional one — which a cascade with no font-family model cannot
answer. Measured on one page, all four:

| declaration | computed font-size |
|---|---|
| `font-size: initial` | 13px |
| `font-size: initial; font-family: initial` | 16px |
| `all: initial` | 16px |
| `all: initial` under a 30px parent | 16px |

`all: initial` resets the family in the same operation, so `medium` has
exactly one value there. The last row is what makes it an absolute answer
rather than an inherited one, and `all: unset`/`all: revert` are NOT this
number — `font-size` inherits, so both report the parent's own size, which
the ordinary keyword resolution already gives.

Six more rows joined `initial-values` for the second reason it exists —
stopping an inherited property inheriting — each measured with an `unset`
sibling beside it that reports the parent's value and so separates the two
keywords: `writing-mode` `horizontal-tb`, `text-orientation` `mixed`,
`list-style-position` `outside`, `hyphens` `manual`, `orphans` and `widows`
`2`. `quotes`, `list-style-image`, `font-variant` and `font-stretch` were
measured too and deliberately left out: nothing in this repo reads any of
them as a style property.

#### A guarantee the engine had only by accident

`width: 120px; all: initial` and `all: initial; width: 120px` are two
answers and one block, so declaration ORDER inside a block became
load-bearing. It was not expressible: `parse-declarations-with-importance`
returns a map, a Clojure map is an array-map to eight entries and a hash-map
beyond, and every declaration of one rule shares that rule's `:rule/order`
— so past the boundary the tie was broken by map iteration order. One
`border` shorthand plus one `margin` already reaches nine.

Each declaration now carries its own `:index`, and the sort tuple ends with
it. The gate is `all` past the boundary in both orders; with the `:index`
removed from the new engine, the `all`-first half flips to auto.

#### What `all` still gets wrong, and it is not the font size

`:cascade/all-initial-resets-every-property` is the one of the three that
does not go fully clean, and both sides agree the font size is 16. What is
left is the two things the FAMILY decides:

| quantity | initial family | monospace |
|---|---|---|
| `line-height: normal` at 16px | **24** | 17 |
| advance of `a` at 16px | 9.2 | 9.6 (this engine's 0.6-em estimate) |

so the case reports an 800×21 line box against Brave's 800×24 and the letter
at y=1.3 against y=4. The width is inside the 2px tolerance; the line box is
not. Closing it needs a font-family model in the cascade — the same missing
piece `resolve-font-size`'s absolute-keyword table has been waiting on since
2026-08-05.

#### `::first-letter` needed no layout machinery at all

Round thirty-two called it unscorable; round forty-four found the sharper
statement (the pseudo-element has no box but its effect grows the
paragraph's). What neither said is that its effect is not a rule of its own:

| `::first-letter { font-size: N }` | 10 | none | 20 | 28 | 40 | 60 |
|---|---|---|---|---|---|---|
| the `<p>`'s box height | 21 | 20 | 22 | 25 | 29 | 36 |

That is the ordinary inline line-box model this file already implements,
applied to a one-character box: content area at N, the INHERITED
`line-height: 20px` giving a half-leading that goes negative past about
20px, and the line box being the union of that against the block's own 14px
strut. Which is why the 40px letter **overflows** the paragraph rather than
fitting inside it — Brave puts the letter's rect at y=37..79 against a
paragraph box of 48..77 — and why a 10px first letter still leaves a 21px
paragraph.

So the whole feature is: make the first letter a separate inline box with
its own style. That shape already exists — it is what a `::before` is
(`:generated/pseudo`, which `inline-fragments` and `layout-node` already
carry a font, colour and metrics for). The one thing it must not do is take
part in `with-generated-content`'s adjacent-text merge, which would fuse it
straight back into the run it was just split from; so it runs after that
merge rather than inside it.

The rest of the feature is deciding which characters the box holds.

#### What "the first letter" is, measured character by character

51 leading characters, each on its own `<p>?Alpha beta</p>` under a 40px
`::first-letter`, classified by which of the first two came back enlarged:

- **Joined by the letter after them** — `" ' ( [ { ) ] } ! # % & * , . / : ; ? @ \`
  and the Unicode quotes, brackets, `…`, `¡`, `¿`, `•`, `§`, `¶`, `【`, `「`.
- **Enlarged alone**, i.e. the character IS the first typographic unit and
  the `A` after it stays 14px — `- _ + < = > | ~ $ ^ \`` , en dash, em dash.

The second row is the finding. It is exactly Pd, Pc and the maths/currency/
modifier symbols — none of which are punctuation in the sense the property
means, however much they look like it. **A `\p{P}` regex would have swept up
all three dashes and been wrong on all three**, so the set is written out as
a literal (also because `\p{gc=Ps}` needs a different spelling in Java's
Pattern and in JavaScript's `u`-flagged RegExp, and this is a `.cljc` file).

Five more shapes, each of which the implementation now reproduces:

| markup | first letter |
|---|---|
| `Alpha beta` | `A` |
| `(((Alpha` | `(((A` |
| `A"lpha` | `A"` — **trailing** punctuation joins it too |
| `123 Alpha` | `1`, and only the first digit |
| `((( Alpha` | **none at all** — the paragraph stays 800×20 |
| `   Alpha` | the collapsed spaces and the `A` |
| a leading emoji | both halves of the surrogate pair |

#### Where the pseudo-element's effect lives, given it has no box

`::first-letter` applies to a block container's first FORMATTED line, and an
inline box does not have one — measured, the same rule on a `<span>` leaves
it at 112×15 with every character at 14px, where on the `<div>` beside it
it gives 800×29. Stating that as a `display` predicate was tried first and
got it wrong: this engine's cascade writes no `:style/display` for a
`<span>` at all (`inline` is the initial value and the UA sheet has no rule
to state it), so the predicate passed and the span got a first letter.

The CALL SITE is the gate instead. The split is applied in
`laid-out-children` and nowhere else, and `laid-out-children` is what
prepares the children of a box this file lays out as a block container; an
inline `<span>`'s children are walked by `inline-fragments` and never come
through it. Two earlier splices — in `inline-fragment-bearing?` and in the
`inline-fragments` walk — were removed for exactly that reason.

A leading inline element is still reached, because the descent happens from
the BLOCK's own children and the rebuilt `<span>` is what `inline-fragments`
then walks. That also gets the composition right for free:
`<span><b>Alpha</b></span>` under a 40px first letter reports 29.1×50 in
Brave — 40px AND bold, the pseudo-element's size composed with the `<b>`'s
own weight rather than replacing it — because the box is left where it was
found instead of being lifted out. An `<img>` before any text ends the
search, and Brave agrees: no first letter after an atomic inline.

#### Which properties actually apply to `::first-letter`

Measured one declaration at a time, reading `getComputedStyle(el,
'::first-letter')` back beside the paragraph's own box:

- **Apply and are observable**: `font-size`, `font-weight` (p 21, the bold
  face is taller), `font-style` (21), `line-height` (60px → p 60),
  `vertical-align` (`super` → p 25.7), `margin`, `padding`, `border`,
  `letter-spacing` (the letter's advance goes 7 → 27), `color`,
  `background`, `text-decoration`, `text-transform`, `visibility`.
- **Do not apply**: `display`, `position`, `width`/`height` — all three
  leave the paragraph at 800×20 with the letter at 7×15.
- **`float` applies and changes the model**: `float: left` takes the letter
  out of the line entirely, so the paragraph is 800×20 with the letter's own
  20×42 box beside it, against 800×29 unfloated.

Of these the engine now honours the ones the generated-node style already
carries. `float` is the one with a number attached to what is missing: the
declaration is carried and ignored, so a floated first letter leaves the
paragraph 9px too tall.

#### Scope cuts, each with the number a fix will need

- **The first letter of a `::before`'s generated content.** Brave applies it
  (`p::before { content: "Xyz" }` with a 40px first letter reports 800×29);
  this runs after `with-generated-content`, sees a `:generated/pseudo` node
  rather than text, and declines. Running before it instead would put the
  split back inside the adjacent-text merge, which is the one thing that
  must not happen.
- **A block container whose first child is another block.** Real CSS pushes
  the pseudo-element down to the innermost first block; this stops at the
  first non-inline child.
- **`::first-line`** stays out, for round forty-four's reason: Brave reports
  the same 800×20 paragraph with and without
  `::first-line { font-weight: bold }`.
- **An inline `style="..."` attribute past eight declarations** still has no
  within-block order. `inline-style` iterates a map that htmldom parsed, and
  the `:index` fix belongs upstream in the repository that parses the
  attribute.

#### Tried and withdrawn

- **A `display`-based block-level predicate** on `with-first-letter`
  (above). It let a `<span>` take a first letter, which the corpus does not
  contain and the unit test did.
- **Asserting the layout gates through `gen-boxes`.** Without a host's
  `:font-metrics` hook this file keeps its long-standing approximation —
  line box = the tallest line-HEIGHT — under which a 40px letter on a 20px
  line cannot make the paragraph taller and `::first-letter` has no
  observable effect at all. `gen-boxes` reported 800×20 for every font size,
  which is that bargain and not a bug; the tests carry a metrics-bearing
  theme of their own and say why.

### Round forty-five: four named leftovers, and the one that turned out to be a rule after all

Four things earlier rounds found, measured and deliberately left, each with
its reason written down. Three landed; the fourth landed as a rule with a
narrower scope than the whole of Blink's, and the fourth's original reason
for being left turned out to be **measuring the wrong strings**.

Everything below was measured in Brave 151 over CDP on 2026-08-06, before
anything was written, in the harness's own frame (14px monospace, a 20px
line, 7px per character) unless another font is named.

#### `position: relative` on an atomic inline was one key wide

`inline-fragments` computes the accumulated offset onto the fragment
(`:rel`) and `layout-inline-run`'s atomic branch reads it off the *piece* —
and `inline-line-breaker`'s `select-keys`, which is what turns a fragment
into a piece, never listed the key. So the declaration was accepted,
resolved, accumulated and then dropped one function short of the only place
that reads it. Brave puts

```
ab<span style="display:inline-block; position:relative; left:30px; top:10px"></span>cd
```

at **x=44, y=10** where this engine left it at 14, 0, and an `<img>` with
the same declarations lands in the same place. An earlier round put the key
in, saw it work, and **took it back out** because the change was outside its
four cases and had no corpus case for it.

The one-key version is right, and the round that wrote it was right not to
ship it blind: three interactions it could not have known about were probed
before it landed this time, and all three already worked once the key was
there.

- **A relatively positioned atomic inline is a containing block, and its
  absolutely positioned child follows the shift.** Brave: the span at 44,0
  and the child at 49,3 — the child's own 5,3 measured from where the parent
  ended up. It works for free because the child is laid out inside the
  atomic's own `layout-node` call and `translate-ops` moves the whole run.
- **`z-index` on it creates a stacking context, and the hoisted ops keep the
  shift.** Probed both ways round: `z-index: 0` on the inline-block confines
  a `z-index: 5` descendant so a `z-index: 2` sibling of the wrapper paints
  over it (Brave answers `lime`), and `z-index: auto` does not confine, so
  the descendant wins (Brave answers `red`). The engine already agreed on
  both — `stacking-context?`/`stack-level` never cared what kind of box it
  was — and the hoisted `<i>` comes out at the shifted x=44, y=5, because
  `absorb-stacking-contexts` runs at the ancestor context, after the line has
  already translated the atomic's ops. **The two shapes have identical
  geometry**; only the paint axis can tell them apart, which is why both are
  in the corpus.
- **The shift moves nothing else.** The line box is 20 tall and the block
  after it sits at y=20 with the offset and without it, on both sides. It is
  a paint-time translate, as the code comment already claimed.

And the hit region moves with it: `translate-ops` carries `:hit`, and Brave's
`elementFromPoint` answers the span over the shifted box and the container
over where it used to be. That is what `browser.session/node-at` and
dom-gpu's `retained` host consume, and their suites are green.

Two smaller measurements, recorded because they cost nothing to take: offsets
**accumulate** through a relatively positioned inline box around a relatively
positioned inline-block (10 + 20 = x=51, 4 + 6 = y=10, and the engine's
`rel+` already did this), and a percentage `top` on an atomic inline in an
auto-height container resolves to **0** (`left: 10%` of a 300px block is 30
and `top: 50%` is nothing).

#### The soft hyphen: the glyph is U+2010, and it lives on the piece that ends the line

The round that measured `&shy;` wrote that what was missing "is not the
opportunity but the inserted glyph: a break here changes the text that is
measured and painted, and a piece in this file is a substring of its token."
That diagnosis was exactly right, and it is what the shape of this
implementation follows.

**The glyph is U+2010 HYPHEN, not U+002D HYPHEN-MINUS**, and the difference
is measurable rather than pedantic. In this platform's monospace face `-` is
7px at 14px and **U+2010 is 14** — the face has no U+2010 and what the
fallback supplies is not fixed-pitch — while in 14px Arial both are 4.67.
Both of Chromium's hyphenating paths report the wider number:
`super&shy;califragilistic` at 90px gives a first line of 35 + **14**, and
`hyphens: auto` splitting `hyphenation` gives 42 + 14. That 14 is what
identified the glyph; a spec reading would have written `-` and been 7px
wrong on every hyphenated line in this font.

Where it ended up living: **appended to the text of the last piece on the
line being closed**, and nowhere else. Not a piece of its own — a second op
is a second *word* to anything reading the ops (this harness splits an op's
text back into words), and Brave reports the glyph as part of the first
line's own run, a 14px fragment butted against the 35px `super` at x=35. The
soft hyphen character itself **stays in the text** rather than being
stripped, which is what keeps a word that never breaks byte-identical to what
the engine produced before: a host measures U+00AD at zero (the oracle's own
advance table says 0, measured) and paints nothing for it.

There are two packers, because there are two paths, and both had to learn it:
`soft-hyphen-lines` for a lone text child and `inline-line-breaker` for a
text run with siblings. The first is new; the second needed the opportunity
in `steps` and a `hyphenated` helper beside `flush`. `soft-hyphen-parts` is
shared.

Seven shapes, every one a pair so the rule can be told from the shape:

| markup                                     | box   | Brave                   |
|--------------------------------------------|-------|-------------------------|
| `super&shy;califragilistic`                | 90px  | 40 tall, 35+14 then 105 |
| `supercalifragilistic`                     | 90px  | 20 tall, one 140px line |
| the first under `hyphens: none`            | 90px  | 20 tall, one 140px line |
| `super&shy;cali`                           | 300px | 20 tall, 63 wide        |
| `su&shy;per&shy;cali&shy;fragi&shy;listic` | 90px  | 40 tall, 63+14 then 77  |
| `aaa&shy;bbb&shy;ccccccccccccccc`          | 120px | 40 tall, 42+14 then 105 |
| `aaaaaaaaaaaa&shy;bb`                      | 90px  | 40 tall, 84+14 then 14  |

The fourth row says the character costs nothing where it sits, the fifth and
sixth that greedy takes the **last** opportunity that fits rather than the
first, and the last that a hyphenated line may overflow its box (84 + 14 is
98 in a 90px box).

**The scope cut, measured, and it is the interesting one.** A hyphenated line
has to FIT, and when it does not Blink falls back to an earlier opportunity
rather than breaking there. `alpha bravo&shy;charlie` at **91px** is 77 + 14
= 91 on line one and `charlie` on line two — which this engine produces — but
the same markup at **88px** is `alpha` alone on line one and `bravocharlie`
(84, unhyphenated) on line two, where this engine still breaks at the soft
hyphen and overflows to 91. The threshold is exactly the inserted glyph's
width, which is what identifies the rule; what it needs that this greedy
forward-only loop does not have is the ability to *reject* an opportunity
after seeing where the pen lands and re-pack from the previous one. **No
corpus case carries that shape on purpose**: both answers are two lines and
40px tall, so it would pass the geometry axis while being wrong, which is the
one failure mode this corpus exists to prevent.

A second, smaller cut: a soft hyphen at the very END of a word yields no
opportunity here. Measured, `alphabetagam&shy; delta` in a 90px box is 40
tall in Brave with line one 84 wide **plus a 14px hyphen hanging past the
90px edge** and `delta` on line two — the break is the ordinary space break
and the hyphen is drawn anyway, because the line happens to end right after a
soft hyphen. Same line structure here, different paint.

`hyphens: auto` is untouched and stays measured-but-not-implemented:
`hyphenation example` at 70px with `lang="en"` is 60 tall against 40, with
Chromium's own dictionary splitting `hyphen-ation` (42 + 14, then 35). It
needs a dictionary, and nothing in this round brings one closer.

#### A harness artifact this exposed, and why the case is now `:oracle/blind`

The line axis cannot read a soft-hyphenated case, and the reason is the
inserted glyph rather than the engine. A word that spans two lines is
measured one CHARACTER at a time (there is no other way to say which line
each part landed on), and **Chromium attributes the hyphen it inserted to the
character after the break**. Measured: the range covering the `c` of
`califragilistic` reports `getClientRects()` = `[[35,2,14,15],[0,22,7,15]]` —
the hyphen's rect on line ONE and its own on line two — and
`getBoundingClientRect()`, which is what the harness reads, is their union
`[0,2,49,35]`. That union's midpoint falls inside line one's vertical span,
so the clustering function merges the two lines and the oracle reports
`["super<shy>c alifragilistic"]` for a box it has itself rendered as two
lines.

The two sides also spell the glyph differently and legitimately: the oracle's
line one ends with the SOFT HYPHEN it found in the document, this engine's
with the U+2010 it inserted, and neither is in the other's line — the same
class of difference `normalize` already case-folds for `text-transform`.

Both are fixable in the harness — take the LAST client rect per character
rather than the bounding box, and fold the two hyphen characters in
`normalize` — and both were left alone. Changing what the oracle *says*
rewrites the `want` side of every case in the corpus, and this round already
had four engine changes in flight. The measurement above is what a future
round needs to do it. Meanwhile the three breaking cases are `:oracle/blind`,
which excludes only the line score; geometry and paint are still compared and
are the honest axes here.

The harness did change in exactly one place, and it is an addition rather
than a rewrite: **U+2010 joined the measured per-character advance table**,
beside the 0x2013/0x2014 already there, because the engine now emits it.
Adding a key to that table cannot change an existing value.

#### `input[type=file]`: there was a rule, and the reason it was left was measuring the wrong strings

The round that declined to hard-code 253 gave a reason: the shadow `<button>`
holding "Choose File" is 87.141 wide and "No file chosen" is 84.484, they sum
to 171.625, that is **81 short of 253**, and both strings are en-US — so a
253 in the engine would be a measurement of this machine's UI language.

Refusing the constant was right. The premise was wrong. Read out of the UA
shadow tree over CDP (`DOM.getDocument` with `pierce`), **this machine's
browser UI is Japanese**:

| shadow part      | text                 | width   |
|------------------|----------------------|---------|
| button           | `ファイルを選択`     | 108.656 |
| gap              |                      | 4       |
| filename label   | `選択されていません` | 119.313 |

108.656 + 4 + 119.313 = **231.97**, which does not reach 253 either — so the
81 was never a "reserved filename column", it was two strings the control
does not contain.

Blink's width is `ceil(max(34 × advance("0"), button + 4 + label))`, and here
the **first** term wins: 34 nominal `0` glyphs of the UA control face (Arial
13.3333) measure 252.063, which ceils to exactly 253. That term is a property
of the FONT and not of the UI language, which is what makes it implementable.
Eight font/size pairs, all of them `ceil(34 × w0)`:

| font                 | 34 × `0` | Brave |
|----------------------|----------|-------|
| Arial 13.3333 (UA)   | 252.063  | 253   |
| Arial 10             | 189.094  | 190   |
| Arial 16             | 302.547  | 303   |
| Arial 20             | 378.188  | 379   |
| Arial 40             | 756.375  | 757   |
| serif 13.3333        | 266.500  | 267   |
| monospace 20         | 340.000  | 340   |
| monospace 28         | 476.000  | 476   |

Two controls that separate this from a constant: `<input type=file size=5>`
is still 253 (HTML does not apply `size` to a file input), and one with
`padding: 10px; border: 3px solid` is 279 — the 34 characters are the
content and the border box adds to it.

**Verdict: a rule, and half of Blink's.** The localized term genuinely does
win at some fonts — at `monospace 14px` the CJK label is full-width, the
second term is 113.313 + 4 + 126 = 243.313, and Brave reports 244 against
this branch's 238 — so the engine is correct exactly while the nominal-
character term wins and narrow otherwise, which is written at the branch with
those numbers. Reproducing the other term means carrying every UA string in
every UI language, which is not a CSS fact and is not derivable from the
document. The corpus case is NOT `:oracle/blind`: it agrees at 253, for the
right reason, at the font the corpus uses.

#### `visibility: collapse` on a column, and the ordering that turned out to be the easy way round

The round that landed the row axis was right that the mechanism is the same
track removal turned ninety degrees, and right that a `rowspan`/`colspan`
crossing a collapsed track needs no special case. What it expected to be hard
was the outer size: a `width: 300px` table whose three declared 100px columns
include one collapsed column renders at 200, so "the collapse has to run
before the table's width is final", which is the reverse of the row axis.

Measured, it is the other way about, and the measurement is what makes the
change small. The collapsed column is sized **exactly as a visible one** —
declared width, shared surplus and all — and only then is its width plus one
border-spacing taken off the table:

| shape (`width: 300px`, 3 columns, middle collapsed) | columns          | table   |
|-----------------------------------------------------|------------------|---------|
| three declared `100px`, control                     | 97.31 / 97.34 / 97.34 | 300 |
| the same with the middle collapsed                  | 97.31 / **0** / 97.34 | 200.66 |
| three `auto`, control                               | 94 / 103.58 / 94.42 | 300   |
| the same with the middle collapsed                  | 94 / **0** / 94.42 | 194.42 |

The surviving columns keep the numbers the control gives them, to two
decimals, in both pairs — so nothing is re-distributed, and the collapse runs
*after* the widths are final exactly like the row half. 300 − 103.58 − 2 =
194.42. A third pair says it from the other side: a collapsed column holding
a twelve-character word still measures 86 wide, and the table goes 112 → 24.

**And the columns found a bug in the rows.** Asking the same question in each
of the three positions turned up an asymmetry the row axis had shipped
without: a collapsed track takes exactly ONE adjacent gap with it, and the
gap that goes is the one BEFORE it — except for track 0, where the space in
front is the table's own leading border-spacing, which belongs to the table
and stays, so the gap AFTER it goes instead.

| collapsed | Brave, rows y=  | Brave, columns x= | table h / w |
|-----------|-----------------|-------------------|-------------|
| first     | 10, 10, 46      | 2, 2, 22          | 82 / 42     |
| middle    | 10, 36, 46      | 2, 20, 22         | 82 / 42     |
| last      | 10, 46, 72      | 2, 22, 40         | 82 / 42     |

All six totals are the same, which is the invariant. The row axis had been
spelled as "the gap after row i is 0 when row i+1 is collapsed", which is
correct for a collapsed middle or last row and says nothing whatever about a
collapsed *first* one: that table came back 88 tall in the border-spacing form
against Brave's 82, with its second row 10px low. Both axes now go through
one `collapsed-track-offsets`.

Three more, each measured because a spec reading leaves it open:
`visibility: collapse` on the TABLE collapses every row and leaves the width
alone (42×4 against the control's 42×50), so the column test is
self-or-column-group where the row test is self-or-ancestor; the same
declaration on a `<td>` collapses nothing (it is `hidden` there, and the table
stays 62 wide); and a collapsed `<col>` reports a **0×0** box where its
siblings report `width × rows-height`, as does a `<colgroup>` all of whose
columns are collapsed.

### Round forty-four: the cascade machinery, and the harness that could not see it

**The corpus contained zero at-rules.** 601 cases, 48 of them about
selectors and the cascade, and `grep '@' cases.edn` found two email
addresses. `@layer`, `@supports`, `@media`, `@container`, CSS nesting,
`min()`/`max()`/`clamp()` and the `all` shorthand were an entire
unmeasured dimension — and three of those are *implemented* in
`cssom.core`, implemented and never differentially tested. Seventy-one
cases went in, in seven new groups, and every expected value was read out
of a real headless Brave 151.1.93.129 over CDP before the case was
written.

**Thirty-four of the seventy-one are controls**, and on a feature this
engine does not evaluate at all they are the whole point: an `@supports`
block applies unconditionally here, so `(display: grid)` agreeing proves
nothing on its own — it is `(display: flurb)` NOT agreeing beside it that
turns the pair into a measurement. Wherever a control and a divergence
are two directions of one rule they are written as a pair
(`@media screen` beside `@media print`, a named container query beside
the same query under a name the container does not have, the `clamp()`
ceiling beside its floor).

Three columns, because the corpus growing and the engine changing are two
different things and a single before/after would let one pay for the
other. The middle column is the **unmodified engine at the base commit**
on the finished 672-case corpus; the right is after this round's two
fixes, on the same corpus.

| axis | 601 cases | 672, base engine | 672, after |
|---|---|---|---|
| line structure | 572/576 = **99%** | 642/647 | **642/647** |
| geometry (boxes) | 2030/2036 | 2157/2186 | **2168/2186** |
| geometry (clean cases) | 595/601 | 648/672 | **656/672** |
| paint order | 14987/15009 | 16710/16789 | **16732/16789** |
| paint order (clean cases) | 589/601 | 656/672 | **658/672** |
| computed style (values) | 28615/28618 | 30681/30717 | **30685/30717** |
| computed style (cases clean) | 599/601 | 648/672 | **649/672** |
| cascade-attributed residual | **2** | 35 | **31** |

The residual is the number to read, and it went 2 → 35 on purpose: those
33 new values are what a corpus that could see the cascade found in it,
and four of them were closed the same round.

`--dump-ops` was diffed corpus-wide between the two right-hand columns.
**Eight cases' box lists changed and all eight are the intended ones** —
the seven `:math/*` shapes the comparison functions close, and
`:container/container-type-establishes-a-containment-context`. Nothing
else in 672 cases moved a pixel, in either direction.

`src/` was NOT touched by the corpus half of this round: the middle
column is the base commit's own engine, so the drop from column one to
column two is coverage and nothing else.

#### The harness could not express a single one of these cases

`scope-css` prefixes every selector with the case's own container id so
601 cases can share one page. It was `split` on `}` and then on `,`, and
its own docstring said a real at-rule "would be visible as a mis-scoped
rule rather than silently wrong". Measured on the first shape this round
needed:

```
@media (min-width: 600px) { p { color: red } }
  ->  #case-0 @media (min-width: 600px) { p { color: red }
@layer a, b;
  ->  #case-0 @layer a, #case-0 b;
```

Three things wrong in one line: the at-rule's PRELUDE prefixed with an id,
so the browser drops the whole block; the inner `p` left UNSCOPED, so had
it parsed it would have reached every other case on the page; and the
closing brace lost. The layer-ordering statement got the selector-list
comma split applied to a *layer-name* list. None of it had ever run,
because no case had ever contained an `@`.

It is now brace-balanced, with one rule per shape: an at-rule STATEMENT is
emitted verbatim (there is nothing in `@layer a, b;` to scope); a
conditional group at-rule keeps its prelude and has its body scoped
*recursively*, so `@media (…) { @layer x { p { … } } }` reaches
`#case-0 p`; a style rule has its selector list scoped and its body
emitted verbatim, because a nested rule (`p { & span { … } }`) is relative
to its parent and prefixing it again would make it `#case-0 & span`, which
matches nothing. `@font-face`/`@property`/`@keyframes` hold declarations
rather than rules and are emitted verbatim.

**Two numbers the harness was assuming and had wrong.** Cases are 800px
wide; the headless window's `innerWidth` is **756**; and
`cssom.core/default-viewport-width` is 800. Every `@media` threshold
between those two would have diverged over WHICH VIEWPORT rather than over
the cascade. And `default-color-scheme` is `"light"` while headless Brave
151 answers `(prefers-color-scheme: dark)` with **true** — a matched pair
of false divergences waiting for the first two cases to use it. Both are
now measured in the oracle and handed to `apply-cascade`
(`*oracle-viewport-width*` / `*oracle-color-scheme*`), which is the same
correction as the case wrapper carrying the page's own `line-height`:
what is being compared is whether the two sides evaluate the same
condition the same way, and the number it is evaluated against has to be
the same number. `:media/a-threshold-between-the-case-width-and-the-viewport`
is the case that measures exactly this, at 780px.

**Proof that none of it is a thumb on the scale:** the modified harness
was run against the **unmodified engine at the base commit**, on the
unmodified 601-case corpus, and reproduced the baseline to the value —
line 572/576, geometry 2030/2036 with 595/601 clean, paint 14987/15009
with 589/601 clean, computed style 28615/28618 with 599/601 clean. Which
is what a corpus with no at-rules and no `@media` in it should do.

#### What the 71 found

**`@layer` — three real divergences under six agreements.** Layer order,
the `!important` reversal, unlayered-beats-layered, the ordering
statement, layer-beats-specificity and layer-inside-`@media` all agree
exactly, which is the first evidence that the feature works rather than
merely exists. The one worth naming among them is
`:layer/a-layered-important-beats-an-unlayered-important`: this engine's
own docstring says "any unlayered declaration beats every layered one of
the same importance", and that sentence is only true of the *normal* half
— for `!important` the unlayered declarations are the weakest, and the
engine gets it right anyway. Then:

| case | Brave | this engine |
|---|---|---|
| `two-anonymous-layers-are-two-layers` | blue — the second anonymous layer beats the first regardless of specificity | red — both are tagged with the same empty-string name, so they land in ONE layer and specificity decides |
| `a-nested-layer-is-the-layer-its-dotted-name-names` | red — `@layer o { @layer i { … } }` and `@layer o.i { … }` are the SAME layer, so specificity decides | blue — the nested block is flattened to its OUTER name and `o.i` is read as an unrelated third name |
| `media-inside-a-layer-keeps-the-layer` | blue | red |
| `revert-layer-rolls-back-to-the-previous-layer` | 200×20 | 800×20 — the literal string `revert-layer` is stored as the width |

The `@media`-inside-`@layer` one is a documented cut in `parse-rules`
("loses the outer layer tag on that block") and the measurement changes
what the cut costs: losing the tag does not merely forget the layer, it
promotes the rule to **unlayered**, which is the strongest normal position
there is. A rule written to be overridable becomes unoverridable.

**`@supports` — absent, and absent in the fail-OPEN direction.**
`parse-rules` does not recognise the at-rule at all, so the plain selector
parser picks up its inner rules as if the wrapper were not there and every
`@supports` block applies **unconditionally**. Measured, that is right
half the time and wrong the other half: `(display: grid)`, `or` with one
true arm, and `selector(p:has(b))` agree; `(display: flurb)`,
`(flurb: 1px)`, `not (display: grid)`, `(grid) and (flurb)` and
`selector(:frobnicate)` do not. The four controls are in the corpus
because "applies when it should" is not evidence on an engine that applies
everything. **Not fixed:** answering `@supports` honestly means a real
support oracle for this engine's own property/value grammar, which is a
design decision with a wide blast radius and not a parser change.

**`@media` — three grammar gaps behind a working feature set.**
`min-width`/`max-width`/`and`/`screen`/`print`/`prefers-color-scheme` all
agree. The three that do not are all cases where `media-condition-matches?`'s
documented "unrecognized features match, so nothing is silently hidden"
default *inverts* an answer rather than widening one:

| case | Brave | this engine |
|---|---|---|
| `(width >= 5000px)` (range syntax) | black | red |
| `(min-width: 60em)` — 960px against a 756px viewport | black | red |
| `not all and (min-width: 5000px)` | red | black |

`:media/an-unrecognized-feature-still-applies` (`min-resolution`) is the
control beside them: for a genuine unknown FEATURE the default is right
and both sides agree. What the three above show is that `not`, range
syntax and a unit are **grammar**, not features, and a fail-open default
aimed at features reaches them anyway.

**`@container` — implemented, correct, and it was hiding a layout bug.**
Seven of the eight query cases agree with Brave exactly on first contact:
`min-width`, `max-width`, the exact `(width: N)` form, a named container,
a named query against a *different* name, and — the one that separates
"the condition is evaluated" from "the condition is ignored" — a 400px
wrapper with no `container-type`, which never matches. The eighth is the
engine's own documented cut, now measured:
`:container/a-percentage-width-container-is-not-queryable` sizes the
container `50%`, which is 400px once layout runs and which
`resolvable-container-width` correctly declines to guess at before it.
Brave applies the rule; this engine honestly does not.

But all eight failed on GEOMETRY while agreeing on every colour they were
written for, and that is where the round's second engine fix came from —
see below.

**CSS nesting — not unsupported, DESTRUCTIVE.** The interesting finding is
not that a nested rule fails to apply. `parse-rules` splits on braces
without tracking depth, so a block holding both declarations and a nested
rule **loses the declarations**:

```
#nc1 { color: blue; span { color: red } }
   Brave:  paragraph blue, span red
   here:   span red, and the paragraph has NO colour at all
```

`:nesting/an-ampersand-descendant-rule-in-its-own-block` is the control
that isolates it: with the nested rule in a block of its own, both sides
agree — and the engine's `& span` matches for the wrong reason (a stray
`&` in a compound selector is ignored rather than resolved against a
parent), which is exactly why the case is here. Five nesting forms
diverge: a declaration beside a nested rule, `& > b`, `&.on`, `& + p`, and
a `@media` block nested inside a style rule. **Not fixed:** making the
brace splitter depth-aware without implementing nesting would trade one
wrong answer for another — the outer declaration would survive and the
nested rule would stop applying at all, and the control above would go
red. The honest fix is desugaring (`& span` → `:is(#nc1) span`), which is
a feature and not a bug fix. **Landed in round forty-nine, as exactly
that desugaring — see it above for what `&` turned out to be, which is
not textual substitution.**

**`all`, `@property`, `env()`, `attr()`, `@scope`** — five separate
features, five measured divergences, none of them fixed *in this round*
and all of them carrying the browser's numbers. **`@property`, `env()`
and `attr()` landed in round forty-nine; `all` landed in round
forty-seven; `@scope` landed in round FIFTY-TWO, as the seventh key in the
cascade sort tuple that round forty-nine's measurement said it would need
— see it above.**

| case | Brave | this engine |
|---|---|---|
| `all: initial` on a `<div>` | 9.2×16 inline box, font-size 16px | 120×30 block, 14px |
| `all: unset` on a `<p>` | 7×15 inline box, colour inherited | 800×20 block, red |
| `all: revert` | margin-left **0** | margin-left **40** |
| `@property --x { initial-value: 60px }` + `var(--x)` | 60×20 | 800×20 |
| `env(safe-area-inset-left, 120px)` | **0**×20 (the variable is defined and is 0, so the fallback is not used) | 800×20 |
| `attr(data-w px, 30px)` | 55×20 | 800×20 |
| `@scope (#root) { .sp { … } }` | the `.sp` inside is red, the one outside is black | both red |

The two `env()`/`attr()` fallbacks are deliberately values that are
neither the resolved answer nor the container width, so "used the
fallback", "resolved the variable" and "read neither" are three
distinguishable answers. `all: revert` is the one of these the
computed-style axis scores as a mismatch rather than excluding, because
both sides' answers are plain numbers.

**`::first-letter` — round thirty-two named it unscorable and was half
right.** "Neither produces an element box, so neither the geometry axis
nor the oracle's element probe can see one" is true of the
pseudo-element and not of its EFFECT: a 40px first letter grows the
paragraph's own box, which the geometry axis reads directly. Brave:
**800×29** against a plain 800×20, which is 9px and well outside the 2px
tolerance. `::first-line { font-weight: bold }` really is unscorable —
measured, the paragraph stays 800×20 — and no case was added for it.

#### Two engine fixes, both rules rather than cases

**`min()` / `max()` / `clamp()`, over exactly `calc()`'s constant
subset.** These are not a new pipeline: a math function is a PRIMARY in
the expression grammar `parse-calc-level` already implements, so adding
one token kind makes them nest in both directions —
`calc(min(100px, 50px) + 10px)` is 60 and `min(calc(10px + 5px), 20px)` is
15 — and `clamp(lo, v, hi)` is literally `max(lo, min(v, hi))`, which is
what makes `clamp(90px, 5px, 300px)` come out **90** and not 5. The
boundary is the one `calc()` already draws and is unmoved:
`min(50%, 300px)` and `max(10px, 2em)` still degrade to a raw string
rather than being guessed at against a containing block or a font size
this pass does not have, and `min(10px, 2)` is invalid rather than 2
because real CSS requires every argument to be the same type.
`math-function-names` is the single authority — the whole-value pattern is
built from it and the tokenizer tests membership against it — so
`round()`/`mod()`/the trigonometric family are declined by name rather
than by omission.

Seven corpus cases went green (`min`, `max`, three-argument `min`, both
`clamp` directions, `min` inside `calc`, and `min` in a `padding`
shorthand — the one the computed-style axis can score, 0 → 4px on all four
sides). `:math/constant-calc-multiplication-and-division` is the control
that places the boundary from inside, and
`:math/a-percentage-calc-is-resolved-against-the-container` from outside.

**`container-type` applies layout containment.** Found by the eight
`@container` cases failing on geometry while agreeing on every colour.
`container-type` was a CASCADE-only property — `cssom.core` read it to
decide what an `@container` rule may query, and nothing downstream read it
at all. It is also a layout declaration: `inline-size` and `size` both
apply layout containment, and a box with layout containment is an
independent formatting context. Measured in Brave, both shapes on one
page:

| wrapper | box | its `<p>` |
|---|---|---|
| `container-type: inline-size; width: 400px` | **400×48** | y=**14** |
| `width: 400px` | 400×20 | y=0 |

It joins `scroll-container?` / `flow-root` / `:independent-fc?` in all
three places that ask the formatting-context question (`fc-free?`,
`contains-floats?`, and the self-collapsing test), because it is the same
question. The eight query cases now pin `margin: 0` on their paragraph so
they measure the QUERY and nothing else, and
`:container/container-type-establishes-a-containment-context` measures the
containment beside a control that is the identical wrapper without the
declaration.

Both fixes were proved to fail first: 12 assertions in
`cssom.core-test` and 3 in `cssom.layout-test` fail on the base commit and
pass after, and each has a control beside it that passes on both sides
(`min(50%, 300px)` stays a raw string either way; a wrapper with no
`container-type`, and one with `container-type: normal`, are 400×20
either way).

#### Measured and deliberately NOT added

- **`::first-line`.** Brave reports the same 800×20 paragraph with and
  without `::first-line { font-weight: bold }`, and the computed-style
  axis compares fourteen properties on ELEMENTS. There is nothing for
  either side to disagree about, at any value.
- **A `revert-layer` on an UNLAYERED declaration.** Brave rolls it back
  past the whole author origin, so `#x { width: 120px } #x { width:
  revert-layer }` is 800px wide — and this engine, holding the literal
  string, is also 800px wide. It would have been a case that passes for
  precisely the wrong reason. The layered form
  (`:layer/revert-layer-rolls-back-to-the-previous-layer`) discriminates,
  and it is the one in the corpus.

### Round forty-three: where a box sits on a line

Four residuals in one cluster — everything left that was about a box's
place on a line rather than its size. All measured in Brave 151 over CDP
on 2026-08-06, and all measured *before* anything was written, because
this is exactly the area where a one-case constant looks right.

**`vertical-align` on an atomic inline — the largest remaining geometry
cluster.** Round thirty-three localised it precisely: `middle` reached an
inline-block *exactly* (both sides y=31.828125) and everything else came
out at the engine's baseline default. `<length>` had since landed. Five
values had not, and probing them one shape at a time would have produced
five constants. Instead: **13 shapes × 14 values**, varying the
line-height and the font-size on the container and on the box
*independently*, because that is the only thing that separates a
font-relative rule from a line-relative one.

| value | where it aligns | the reading that proves it |
|---|---|---|
| `top` / `bottom` | the **line box**'s edges | y=0 / y=36 on a 46px line; both follow the line-height |
| `text-top` / `text-bottom` | the **parent's content area** | y=28 / y=33 at `line-height` 10, 20 **and** 40 — unmoved |
| `<percentage>` | the element's **own line-height** | `50%` raises 10 normally, **20** when the box declares `line-height: 40px` |

`text-top`/`text-bottom` are `baseline − ascent` and
`baseline + descent − h` in the parent's face, and the face is the parent's
and not a constant: a **bold** parent (ascent 14, descent 4 against the
upright face's 12/3) reads 26 and 34 where the upright one reads 28 and 33,
and 28px and 8px parents read 16/35 and 33/32. A `font-size` or a
`line-height` **on the box itself** moves neither. So they are resolved in
`inline-fragments`, which has the parent's metrics, where `top`/`bottom`
need the second pass in `inline-line-metrics` that the text path already
had.

The percentage is the discriminating pair in the other direction: the
box's own `line-height: 40px` doubles the raise and the *container's*
`font-size: 28px` does not change it, so the base is a line-height and it
is the element's own. That is why the round that landed `<length>`
deliberately did not admit it — and it is now measured rather than
guessed.

**The growth rule when a `top` and a `bottom` box ask at once.**
`inline-line-metrics` said in its own docstring that it grew both sides
independently, that CSS 2.1 is circular here, and that the corpus had no
such line — "an honest approximation rather than a claim". Measured, in
both document orders, with a 40px baseline-aligned box setting a 46px
line:

```
top 60 + bottom 50  ->  line 60, baseline unmoved      (the top box grew it DOWN)
top 60 + bottom 80  ->  line 80, baseline 34 lower     (the bottom box grew it UP)
```

Only the **larger** request is served; the smaller box then fits inside
the line it made. The independent model gives the second shape 94. The two
agree whenever only one side asks, which is every line in the corpus — so
this changed no case and is a rule the next such line will need.

**`super`/`sub` are affine in the font size, and the table was a
one-point fit.** The constants were `0.404em` and `0.271em`, measured at
14px and recorded as "the font's own superscript/subscript offsets, which
a real browser reads from the OS/2 table". Swept at 17 sizes from 6 to 40,
including fractional ones, the ratio is not constant at all — 0.457em at
8px, 0.404 at 14, 0.369 at 28, 0.358 at 40 — and the actual law is:

```
super =  font-size/3 + 1        sub = -(font-size/5 + 1)
```

exact at every one of the 17 (to LayoutUnit's own 1/64, which the browser
floors and this engine does not), and **identical in monospace, Arial,
Georgia and Verdana** at 20px, so it is a function of the size and of
nothing else — not of any font table. The affine term is what a fraction
cannot express. The old constants were 0.42px out at 8px and 0.98px out at
28px: **both inside the geometry axis's 2px tolerance**, which is why the
corpus never failed on it and could not have. A sweep found it; no case
could.

**`display: inline-table` — three stacked 400px blocks.** It needed no
sizing rule at all, unlike `inline-flex` and `inline-grid` before it: a
table already shrink-wraps to its columns, so the only thing missing was
that it was never inline-*level*. Brave: one 20px line, the table 28×20 at
x=49 — the cell's four monospace characters, through the anonymous row and
table boxes `table-rows` already generates. Its baseline is its first
row's, which is the rule the atomic path already gives an inline-block
holding a line of text: a cell forced to `height: 40px` centres its text
(a cell's UA `vertical-align: middle`) and takes the line box to 40 with
it.

**`list-style-position: inside` — the 5.29px round twenty-nine recorded
rather than modelled.** That round measured a `<ul>`'s inside marker at
19px at 14px, 14 at 10 and 37 at 28, called it "a function of the
font-size only", and wrote the observation into `list-style-inside?`
because three points are not a rule. Swept at **every integer size from 6
to 40** and at five fractional ones:

```
advance = font-size + ceil(2 x (font-size + 2) / 7)
```

Exact at all forty. Identical for `disc`, `circle` and `square`, and
identical in Arial and in monospace — **whose space advances differ by
3px** — so Blink is not laying out the `"• "` string this engine draws at
all. That string is 13.70625 wide here against the browser's 19, and the
difference is the whole of the case's residual. An `<ol>`'s inside marker
*is* its string (21px for `1. `, 28 for `10. `, 35 for `100. `, in
monospace), so the two list-style-types keep two rules and the `<ol>` is
the control.

Landing it exposed a second thing: the marker was being **merged into the
item's own text run**, both in `with-generated-content` and again in the
line breaker's adjacent-piece merge. A merged `:text` op has one x and one
string, so the item's first word would be painted inside the gap the
advance exists to reserve, and the whole run measured as the marker alone
— the `<td>` shrink-wrapped to 61px where Brave says 82. An inside marker
is a box of its own, exactly as an outside one is, and is now held out of
both merges.

**Before → after**, both measured on the corpus of 601 at this round's
merge base (`bbe20e5`, i.e. with the whitespace-deferral round already in
— these ran concurrently and only these deltas are this round's):

| axis | before | after |
|---|---|---|
| line structure | 569/576 | **570/576** |
| geometry (boxes) | 2013/2036 | **2021/2036** |
| geometry (clean cases) | 585/601 | **591/601** |
| paint order (points) | 14987/15009 | 14987/15009 |
| paint order (clean cases) | 589/601 | 589/601 |
| computed style (values) | 28615/28618 | 28615/28618 |
| computed style (clean cases) | 599/601 | 599/601 |

`--dump-ops`, corpus-wide, before and after: **eight cases changed and
none regressed.** Six are the targets —
`:display/inline-table-in-a-sentence`, the four `:inline/vertical-align-*`
that sat on the baseline, and `:list/list-style-position-inside`. The
seventh is `:inline/vertical-align-text-top`, which was *inside* the 2px
tolerance at 30 against 28 and is now exact — a case that was passing
while being wrong, which is the reason the per-case dump is read and not
only the sums. The eighth is `:inline/sub-and-sup`, which moves 0.017px
under the new super/sub law and stays clean.

Downstream, all against this branch's `cssom`: `browser` 754/0, `dom-gpu`
130/0 (its `retained_draw_ops.edn` golden needed no regeneration — no new
op key), `htmldom` 180/0. cssom's own suite 925 tests / 2336 assertions,
0 failures; lint 0 errors, 25 pre-existing warnings.

**Still open, with the numbers a fix needs**, stated in code at
`vertical-align-shift`: `text-top`/`text-bottom` on a **non-atomic** inline
box. What they align there is the box's own *inline* box (its
`line-height`, `leading-ascent` of it above the baseline), not its content
area, so the two differ even when parent and child are the same face —
measured, `text-top` moves an identical child **down by 2px** and takes the
line from 20 to 22. Four measured rows are recorded there. No corpus case
covers it.

### Round forty-two: a block cut in half, and the two rectangles a browser reports for it

`layout-multicol` landed with a scope cut written into the code: **nothing
was ever fragmented** — a block that did not fit moved whole into the next
column. Two corpus cases recorded the gap and together they were the top of
the geometry residual (`div h` 13 boxes at median −20, `div w` 8 at +230).
The code named the consequence too: `break-inside: avoid` was satisfied by
construction and therefore scored nothing, anywhere.

Measured on this round's own merge base, `eb9dca9` — rounds forty-one and
forty-two were in flight at the same time and landed within hours of each
other, so these are not the numbers on today's main. The op dump they are
diffed against is from the same base.

```
                    LINE      GEOMETRY (boxes / clean)   PAINT (points / clean)   STYLE
before   546/556    1926/1973  549/581                   14450/14514  561/581     27735/27740
after    546/556    1930/1973  551/581                   14450/14514  561/581     27735/27740
```

**Two cases changed in the whole 581-case op dump**, both the ones that
recorded the gap, both now exact. `:multicol/a-block-splits-across-the-
column-boundary` and `:multicol/break-inside-avoid-moves-the-whole-block`
each go from two wrong boxes to two right ones. Nothing else in the corpus
moved — which mattered here more than usual, because the balancing rule the
same function owns (the smallest height at which the content still fits in
the used column count, snapped to a real break, deliberately *not*
`ceil(total / count)`) is measured and correct and had to survive.

The corpus then grew 581 → 597 with sixteen cases that say what the rule
**is** rather than that it is missing, all clean: 1989/2032 boxes,
567/597 cases, paint 14845/14909 and 577/597.

#### The harness did not change, and that is the finding

A fragmented element has one rect **per fragment** in `getClientRects()`
and the **union** of them in `getBoundingClientRect()` — a rectangle
spanning both columns, covering ground the element does not occupy, inside
which `elementFromPoint` answers the container rather than the element.
Measured on the first corpus case: rects `[0,0,140,25]` and `[160,0,140,5]`,
bounding rect `[0,0,300,25]`.

Both of those already had a home. The geometry axis compares
`getBoundingClientRect` against the engine's single `:node` box, and the
paint axis compares `elementFromPoint` against that op's `:hit` rects —
a pair this engine needed once before, for a **wrapped inline box**, and
for exactly the same reason. So the engine emits the union as the box and
the fragments as `:hit`, and `conformance/run.cljk` is byte-identical to
what it was: `git status` on the landing commit lists `src/cssom/layout.cljk`,
`test/cssom/layout_test.cljk` and `conformance/cases.edn` and nothing else.
There is no thumb on the scale to disprove, because there is no harness
change to disprove it about.

It also shows the two axes are not redundant. `box-decoration-break: clone`
is not implemented, and the geometry axis **cannot see that** — slice
reports fragments of 40 and 16 where clone reports 40 and 32, and both
unions are `[160,0,300,40]`. The paint axis sees it at 2 sample points in
the 16..32 band. A gap invisible to one axis and visible to the other is
the argument for having both.

#### Fifty-nine shapes measured before a line was written

The corpus had two fragmentation cases; the rule has at least five parts.
Fifty-nine probe shapes were rendered in the same headless Brave first and
the engine was then measured against all of them (via the same harness,
under a temporary `:frag/` group). Where a break may fall:

| | |
|---|---|
| inside a line box | never |
| in the empty band inside a block, below its last line or between two children | anywhere, **continuously** — a 90px block holding one 20px line cuts at 45 |
| above a block's first line, or below its last | never. `padding-top: 40px` over a line is 60 tall and does **not** split, where `height: 60px` over the same line splits at 30. `padding-bottom` reads the same |
| inside a monolithic box | never: `overflow: hidden`, a replaced element, `break-inside: avoid` |
| with nothing legal left | it cuts anyway, by **pushing** the straddling line rather than halving it — a `padding-top:10px` block (30 tall) in a forced 25px column reports 25 and 20, which sum to *more* than 30 because the first fragment is a 10px slice stretched to the column bottom |

Two of those five contradict a plausible first guess, and neither would
have been found by reading the spec:

- **`orphans` decides whether a two-line block splits at all**, and
  **`widows` is ignored**. Default (`orphans: 2`), two lines: 40 tall, one
  rect. `orphans: 1; widows: 2`: 20 tall, two rects — it splits leaving a
  single widow. `orphans: 2; widows: 1`: 40, one rect. So this engine reads
  `orphans` and deliberately does not read `widows`, because honouring it
  would diverge from the browser.
- **The balanced height is floored at `ceil(total / count)`.** Blink's
  balancer starts there and only grows. Two 30px blocks with a 60px margin
  between them fit one per column at height 30 — the margin is dropped at
  the break — and Brave still reports the box 60 tall. A 20px margin in the
  same shape reads 40. Before fragmentation nothing could drop a margin, so
  the search never returned less than the floor and the floor was invisible.

The scope cuts are listed at the function that owns each, with the browser
numbers a future fix will need: `clone` (40/32 vs 40/16), an item
containing a `:stack` push (a positioned or z-indexed descendant — the one
cut here whose browser number is **not** measured), `break-before`/
`break-after`, and a declared `orphans` on the multicol box's own direct
content.

One measured divergence was left alone because it is not about
fragmentation: a `<br>` in the **second** column reports x=7 in Brave where
the engine says 167, i.e. the browser gives a zero-width `<br>` its
pre-fragmentation x. It costs 2 boxes on a six-line probe shape, which is
therefore not in the corpus.

### Round forty-one: where a line is allowed to break

The line breaker had no model of a break OPPORTUNITY at all. It would
break between any two tokens, and `white-space: nowrap` never reached the
inline path in the first place — `inline-flow-candidate?` refused every
non-`normal` value, so a paragraph with one `nowrap` child fell apart into
block rows.

Measured on this round's own merge base (`782d555`, round forty already
in), because round forty landed on main while this one was in flight and
its numbers are not this one's to claim:

```
                    LINE      GEOMETRY (boxes / clean)   PAINT (points / clean)   STYLE
before   547/556    1933/1973  555/581                   14462/14514  563/581     27733/27736
after    548/556    1942/1973  559/581                   14490/14514  569/581     27733/27736
```

On the commit this branch was actually cut from (`eb9dca9`, before round
forty) the same change reads 546 -> 547, 1926 -> 1935 / 549 -> 553,
14450 -> 14478 / 561 -> 567 -- the same six cases either side, which is
what says the two rounds do not overlap.

**Six cases changed in the whole 581-case op dump**, all in the intended
direction, the same six before and after the merge:
`:overflow/nowrap-inline-blocks-do-not-wrap`,
`:text/nowrap-inline-inside-a-wrapping-paragraph`,
`:text/overflow-wrap-break-word-keeps-min-content` and
`:generated/before-display-block-makes-its-own-line` now match the oracle
exactly; `:position/sticky-right-in-a-horizontal-scroller` stopped
wrapping (what is left of it is `sticky` in the inline axis, which this
round did not touch); and `:sizing/overflow-hidden-releases-the-flex-floor`
gave up an overflow hit region it should never have had.

#### `nowrap` collapses whitespace exactly as `normal` does

That is the whole reason it can be admitted here, and the guard that
excluded it said the opposite: *"`pre`/`pre-wrap`/`pre-line`/`nowrap` each
mean the run must preserve or re-interpret newlines and runs of spaces"*.
Three of those four do. `nowrap` changes exactly one thing — whether a
collapsed space is a place to break — and that is a line-breaker question,
not a tokenizer one. So the old `#{nil "normal"}` test became two
predicates that ask the two questions separately (`collapsing-white-space`
and `soft-wrappable-white-space?`), and `nowrap` passes the first.

Measured in Brave 151 on 2026-08-06, in the harness's own 14px monospace /
20px line page, `alphaalpha<span style="white-space:nowrap"> betabeta
</span>` at 120px puts `betabeta` at x=77 on one line: the leading space
inside the nowrap span is collapsed to a single 7px space and rendered,
and only the break at it is gone.

#### Which element's `white-space` governs a break

Two rules, and neither is guessable from the other. Nine shapes decided
them, all at 120px unless stated:

| markup | lines |
|---|---|
| `alphaalpha<span nowrap> betabeta</span>` | ONE — the space is the span's |
| `alphaalpha<span> betabeta</span>` | two |
| `alphaalpha <span normal>betabeta</span>` in a **nowrap div** | ONE — the space is the div's, and the normal span does not rescue it |
| the same with `betabeta gammagamma` in the span | breaks before `gammagamma` — that space IS the span's |
| `alphaalpha<span nowrap>xx </span> betabeta` | two — the span forbids, the div permits, they collapse to one that permits |
| `alphaalpha <span nowrap> betabeta</span>` | two — the mirror image, same answer |
| two 40px inline-blocks, no whitespace at all, 60px box | two — an atomic boundary is an opportunity with no space in it |
| the same inside `<span nowrap>` | ONE |
| the same with `nowrap` on the FIRST inline-block only | two |

So: **a collapsible space is an opportunity when the element containing it
permits one**, several collapsing runs are an opportunity if ANY of them
does, and **a boundary with no space is an opportunity only at an atomic
inline**, where the NEAREST COMMON ANCESTOR governs it. The last is what
distinguishes `nowrap` on one side of a boundary from `nowrap` on the box
around both, and the engine's owner stacks already carry exactly the
information it needs.

`inline-tokens` was already tracking `:space-style` — which run's font the
space is drawn in — and that answers the first rule almost for free. It
does **not** answer the third: `:space-style` keeps the FIRST contributor
while the opportunity ORs every one of them, and rows five and six above
are the two spellings that force the two to be tracked separately.

#### A text boundary with no space is not a break, and `<wbr>` was working by accident

The corollary cost a case and paid for a better one. `abcdefgh<span>ijkl
</span>` in a 60px box is ONE line in Brave — 84px of text overflowing —
and so is the same run split across two spans. This engine broke at every
inline box edge, because it broke between any two tokens.

Closing that broke `:wrap/wbr-is-a-break-opportunity`, which the corpus
note said this engine got right *"by treating the unknown element as an
inline that splits the text into two runs"* — i.e. by the same accident.
`<wbr>` now emits a fragment of its own, and it is **unconditional**:
measured, `aaaaaaa<wbr>bbbbbbb` in an 80px box is 40 tall both plainly and
under `white-space: nowrap`, where a literal U+200B in the same two places
is 40 and **20**. A `<wbr>` is not a zero-width space, and `nowrap`
suppresses one and not the other. It reports no box either
(`getClientRects()` is empty), which is why it never becomes a piece.

#### The unit a line packs is a cluster, not a token

Suppressing an opportunity is not enough on its own. Measured, `alpha
<span nowrap>beta gamma delta epsilon</span> zeta` at 120px is 60 tall
with the span **alone on line two at 168px wide, overflowing** — the
browser gives up the line rather than the run. Testing one token at a time
keeps `epsilon` on line one, because each of the span's own words fits
where it stands.

So the wrap test measures the whole UNBREAKABLE CLUSTER a token begins:
itself plus every following token with no opportunity in front of it. Two
folds over the token stream produce it, and the arithmetic is arranged so
that **a cluster of one reduces to exactly the `open-adv + ww + tail-adv`
this function always tested**. That identity is the safety property: on
every stream this engine saw before `nowrap` arrived, the new test is the
old test.

#### `overflow-wrap: break-word` does not make a box narrower

The distinction the case is named for, and it needed the half of
shrink-to-fit this file never had. Real CSS is `min(max-content,
max(min-content, available))`; `atomic-intrinsic-width` ended at
`min(content-w, natural)`, so an atomic inline in a container narrower
than its own content was simply squeezed to the container — and then
`break-word`, which the engine already honoured for line breaking, broke
the word to fit the width it had just been given.

A 15-character word in a `display: inline-block` inside a 60px block, and
the same word at `width: min-content` inside a 200px one:

| | box | at `min-content` |
|---|---|---|
| (no break property) | 105x20 | 105x20 |
| `overflow-wrap: break-word` | **105x20** | **105x20** |
| `word-break: break-all` | 60x40 | 7x300 |
| `overflow-wrap: anywhere` | 60x40 | 7x300 |

Two pairs of numbers saying the same thing twice. `break-word` breaks a
word that has nowhere else to go once a width is chosen; it does not
change what the box asks for. Nine more shapes fix the floor's own shape:

| in a 60px block | box |
|---|---|
| `aaaaaaa bbbbbbb` | 60x40 — min-content 49 < 60 |
| `aaaaaaaaaaaa bbbbbbbbbbbb` | 84x40 — the longest WORD, not the text |
| the 15-char word with `overflow: hidden` | 105x20 |
| ...with `padding: 5px` | 115x30 |
| ...with `max-width: 40px` | 40x20 |
| ...with `white-space: nowrap`, four words | 105x20 |
| ...wrapped around a `<div>` | 105x20 |
| `<button>` with the same one-word label | 111.2x15 |
| `<select>` / `<input size=20>` / `<img width=200>` | 134 / 153 / 200 |

The last two rows are why a box whose content cannot break at all — a
replaced element, a form control, an inline-flex/-grid sizing itself from
its own children, or any `white-space` that forbids a soft wrap — is its
own floor and is simply not clamped.

#### A block-level `::before` is a box, not the first thing on a line

`with-generated-content` merged every `::before` with the text after it
into a single run, which is right for the numbered-list idiom it was
written for and wrong the moment the pseudo-element declares a display.
Eight spellings on a 300px `<p style="margin:0">tail</p>`:

| | `<p>` |
|---|---|
| `::before { content:"head"; display:block }` | 300x40, `tail` at y=22 |
| `::before { content:"head" }` | 300x20 |
| `::before { content:"head"; display:inline-block }` | 300x20 |
| `::before { content:"head"; display:flex }` | 300x40 |
| `::before { content:"head"; display:block; height:30px }` | 300x50 |
| `::after { content:"foot"; display:block }` | 300x40, `tail` at y=2 |
| both block spellings at once | 300x60, `tail` at y=22 |
| `::before { content:""; display:block }` | 300x20 |

It is not `block` that matters but inline-LEVEL-ness — `flex` makes its
own row too — and the last row is why the rule is applied to the merge
rather than to the layout: an empty block `::before` has no line box, and
making it a row of its own would have reported 40.

#### A harness defect, and the engine half it was hiding

The two `nowrap` scroller cases were still losing 10 paint points after
their geometry went clean, and the cause was not in the engine's layout at
all. cssom.layout's own comment at the clip emitter says that *"a line that
overflows a box which CLIPS is not hit outside it"* and that the engine
expresses this with `:clip` push/pop ops which *"every hit-tester that
reads `:node` ops already tracks"*. `browser.session/hit-nodes` does. **This
harness did not** — it read one half of the engine's answer and charged the
engine for the other.

Measured, a 300px inline-block in a `width: 200px; overflow: auto` box at
x=240: `visible` answers the span, and `auto`, `hidden`, `scroll`, `clip`
and `overflow-x: auto` all answer neither the span nor the box.

Tracking the clips in `engine-topmost-at` — a fold rather than a filter,
because clip state is order-dependent — turned those 10 points from
`none -> span` into `none -> div`, and named the second half, which IS the
engine's: a box's `:node` op is emitted BEFORE its own clip-push (it has
to be, the clip is for its content), so the overflow region attached to it
survives its own clip and answers clicks in space the box does not
occupy. A clipping box now gets no overflow region at all.

**The harness change is not a thumb on the scale**, and the proof is a run
of the modified harness against the UNMODIFIED engine at this round's base
commit: line structure 546/556, geometry 1926/1973 with 549/581 clean and
computed style 27735/27740 — **identical to the baseline on all three**.
Paint moved by exactly +2 points and +1 case
(`:overflow/x-auto-reserves-height-only`), which is the only place in the
corpus where a clip was already being ignored on its own.

#### What was measured and deliberately not implemented

Four break opportunities, each recorded at `inline-line-breaker` with the
numbers a future round will need, because each needs something this file
does not have rather than a line there:

- **`&shy;`** (U+00AD) — `super&shy;califragilistic` at 90px is 40 tall,
  breaking after `super` with a **visible hyphen** and putting a 105px
  second line in a 90px box; the same word without it is 20 tall, and so
  is the same markup under `hyphens: none`. What is missing is not the
  opportunity but the inserted glyph: a break here changes the text that
  is measured and painted, and a piece in this file is a substring of its
  token.
- **`hyphens: auto`** — `hyphenation example` at 70px with `lang="en"` is
  60 tall against 40 without, Chromium's own dictionary splitting
  `hyphen-ation`. Not derivable from the text at any width.
- **`text-wrap: balance`** — not an opportunity at all but a different
  ALGORITHM; this loop is greedy by construction. `alpha beta gamma delta
  epsilon` at 200px is 40 tall BOTH ways, and only the lines differ
  (`alpha beta gamma` / `delta epsilon` against `alpha beta gamma delta` /
  `epsilon`). The geometry axis cannot see it; the line axis can.
- **`white-space: break-spaces`** never reaches the line breaker, and
  neither do `pre-wrap` and `pre-line`. Measured, a 60px box holding `aa`,
  six spaces and `bb` is 60x40 with the same word positions under BOTH
  `break-spaces` and `pre-wrap` — that content does not discriminate them,
  and finding content that does is the first step of implementing either.

And one cluster left alone on purpose. `:text/white-space-pre-keeps-
leading-spaces`, `:text/tab-in-pre-advances-to-the-next-eight-column-stop`
and `:text/tab-size-four-in-pre` are red for a reason that is not in this
repository: `htmldom` collapses whitespace at parse time on an
HTML-structural rule, so `<span style="white-space: pre">   indented
</span>` reaches layout as `" indented"` and the characters are gone
before cssom can measure them. cssom's own half is implemented and
asserted in `<pre>` form, where they survive — 63 / 35 / 42, the browser's
numbers exactly. Fixing it means making htmldom defer collapsing to
layout, which changes the text every corpus case sees, and belongs in a
round where nothing else is measuring.

**That round is round forty-two, immediately below. Both paragraphs above
are now HISTORY** — the parser defers, the three cases are green, and the
content that discriminates `break-spaces` from `pre-wrap` was found.

### Round forty-two: the parser stops collapsing whitespace

Two of the four things round forty-one recorded as not-implemented, and the
cluster it named as blocked upstream, were the same blocker: **htmldom
collapsed runs of spaces and tabs while building text nodes**, so no
`white-space` value that preserves whitespace could ever see the characters
it is defined in terms of.

The belief underneath it was that space collapsing is HTML-structural.
Measured, it is not. htmldom's `conformance/ws_probe.cljs` reads text nodes
back codepoint by codepoint with no normalisation; Brave 151, 2026-08-06:

| markup | text node in the DOM |
|---|---|
| `<div>   a   b   </div>` | `SP SP SP a SP SP SP b SP SP SP` |
| `<div>a⇥b</div>` | `a TAB b` |
| `<div>\n  <p>a</p>\n</div>` | `LF SP SP` between the blocks |
| `<table>\n<tr><td>a` | the newline stays INSIDE the table |
| `<pre>\nx` / `<pre>\n\nx` / `<pre> \nx` | `x` / `LF x` / `SP LF x` |

**The parser drops exactly one thing: the single leading newline after a
`<pre>`/`<textarea>` start tag** (last row — one, and only when it is the
very first character). Everything else a browser keeps and collapses at
LAYOUT time, from CSS. htmldom now does the same, and additionally
normalises CR/CRLF to LF on the source before tokenizing (WHATWG 13.2.3.5),
which is where `<pre>` and raw text can be reached at all — previously a CR
became a SPACE outside a `<pre>` and survived as a literal U+000D inside
one.

#### The equivalence is the whole safety property, and it was asserted first

Deferring the collapse changes the text every case sees, so before anything
else: **under a collapsing `white-space`, this file must lay verbatim text
out byte-identically to the text the old parser would have handed it.**

It does, and by construction rather than by luck. `layout-text` and
`inline-tokens` both map any whitespace RUN to a single space; a run the old
parser had already shortened is still a run, so both land on the same
single space. `a-collapsing-white-space-lays-out-verbatim-text-identically`
asserts it over ten shapes — runs between words, a source newline, indented
block children, the whitespace-only text node between two inlines, leading
and trailing runs, a tab, `nowrap`, a list and a table — by parsing each one
twice, once as written and once with the old rule applied, and comparing
whole draw-op vectors.

Its **control is an inequality**: the same comparison under `white-space:
pre` must DIFFER. That assertion fails at the base commit, which is what
makes the ten equalities mean something rather than being satisfied by an
engine that collapses everything anyway. It also caught a real defect in
this work — a first run had cssom's `deps.edn` resolving `../dom-gpu` to a
dom-gpu whose own `../htmldom` was the unmodified shared checkout, so the
unit suite was scoring the old parser. The equality assertions all passed.
Only the control noticed.

#### The blast radius, per case

```
                LINE      GEOMETRY (boxes / clean)   PAINT (points / clean)   STYLE
before  564/572  2005/2032  577/597                  14885/14909  585/597     28559/28562
after   569/576  2013/2036  585/601                  14987/15009  589/601     28615/28618
```

**Exactly four cases changed in the 597-case dump, all four in the intended
direction, none in the other**, plus four cases added:

| case | before | after | browser |
|---|---|---|---|
| `:text/white-space-pre-keeps-leading-spaces` | span 63 | **77** | 77 |
| `:text/tab-in-pre-advances-to-the-next-eight-column-stop` | span 21 | **63** | 63 |
| `:text/tab-size-four-in-pre` | span 21 | **35** | 35 |
| `:text/white-space-break-spaces-keeps-newlines` | div 200x20 | **200x40** | 200x40 |

The parser change ALONE accounts for the first three and moved nothing else
at all — that intermediate run (htmldom changed, `src/` untouched) is the
cleanest evidence the equivalence holds: 3 boxes, 577 → 580 clean cases,
paint and computed style byte-identical.

#### What the surviving characters then exposed in this file

Two bugs, both invisible while the parser was collapsing, because a
preserving `white-space` never actually received a run of spaces:

- **`break-spaces` was not in the segment split at all.** It is the fourth
  preserving value and it fell through to the collapsing branch, so its
  newline was collapsed away like any other whitespace. It also missed the
  tab-expanding set and measured `a⇥b` at 21px instead of 63.
- **`pre-wrap` rejoined its own spaces.** `text-lines-measured` packs WORDS
  and rejoins them with ONE space, which is correct under a collapsing
  value and silently rewrites the text under a preserving one. `<div
  style="width:60px;white-space:pre-wrap">aa` + six spaces + `bb</div>`
  measured 60x20 against Brave's 60x40: the six spaces became one and
  `aa bb` fits where the real text does not. This one was a pre-existing
  divergence that only became REACHABLE now.

Both are fixed by one function, `preserved-space-lines`, which packs ATOMS
(a run of non-whitespace, or one whitespace character) instead of words.

#### The content that discriminates `break-spaces` from `pre-wrap`

Round forty-one looked for it and reported, correctly, that a 60px box
holding `aa`, six spaces and `bb` is 60x40 under both. The reason is that a
space run which merely ends the line it sits on **hangs** under both. They
part company only once the spaces THEMSELVES overflow, and the cheapest
shape that does it has nothing after them at all:

| in a 60px box | `pre-wrap` | `break-spaces` |
|---|---|---|
| `aa` + 10 spaces | 60x20 | **60x40** |
| `aa` + 20 spaces + `bb` | 60x40 | **60x60** |
| `aa` + 6 spaces + `bb` | 60x40 | 60x40 |
| `aaaa` + 6 spaces + `bbbb` | 60x40 | 60x40 |

All four are now corpus cases, in pairs, because a single height cannot
tell "the rule is implemented" from "this shape does not discriminate" —
which is exactly the trap the previous round fell into and named.

`pre-line` needed nothing: it collapses spaces and keeps newlines, and it
was already right. Measured for completeness — a shrink-to-fit `   indented`
is 56 under `pre-line` and `normal`, 77 under `pre`, `pre-wrap` and
`break-spaces`; `a⇥b` is 21 under `pre-line` and `normal`, 63 under the
other three.

#### Two divergences this round measured and did NOT fix

Both are pre-existing — they read the same at the base commit — and both
are now recorded with the numbers a future round needs rather than left to
be rediscovered.

- **Collapsible whitespace at the start of a line is collapsed but not
  REMOVED.** A shrink-to-fit `   indented` under `normal` or `pre-line` is
  **56px** in Brave (eight characters: the leading space is gone) and 63
  here (nine: collapsed to one, then kept). `inline-tokens` already drops a
  line-leading space on the inline path; `layout-text` does not. Pinned at
  `a-preserved-leading-space-run-is-in-the-measured-width`.
- **Content HANGING past a box's edge gets a full-height hit region.** The
  one paint point `:text/white-space-pre-wrap-hangs-a-run-of-spaces` loses,
  and it is a general rule rather than anything to do with `pre-wrap` — a
  `white-space: pre` control overflowing the same 60px box behaves
  identically. Measured with `elementFromPoint` across and down the box: at
  y=7 and y=13 the browser answers the overflowing div out to x=75, and at
  y=1 and y=19 it answers the box behind it. The browser hit-tests the
  overflow over the LINE's content area (~15px, centred in the 20px line);
  this engine uses a rectangle the full height of the box.

### Round forty: three divergences, one missing capability

`width: min-content | max-content | fit-content` behaving as `auto`, flex
`min-width`/`max-width` never giving their surplus back to the line, and
`<dialog open>`'s box. The third depended on the first: the previous round
measured the whole of the dialog's UA rule, added it, and found **not one
box moved**, because `width: fit-content` was still `auto` and the
`margin: auto` it is centred by had nothing to split.

```
                    LINE      GEOMETRY (boxes / clean)   PAINT (points / clean)   STYLE
before   546/556    1926/1973  549/581                   14450/14514  561/581     27735/27740  578/581
after    547/556    1933/1973  555/581                   14462/14514  563/581     27733/27736  579/581
```

**Six cases changed in the whole 581-case op dump**, all in the intended
direction, all now matching the oracle exactly:
`:sizing/min-width-min-content` (which also cost 12 paint points as
`div -> none`), `:sizing/width-max-content`, `:sizing/width-fit-content`,
`:sizing/min-width-on-a-flex-item`, `:sizing/max-width-on-a-flex-item`,
`:interactive/dialog-open-is-a-bordered-block` (6 paint points as
`div -> dialog`). Nothing else moved, in either direction.

The computed-style DENOMINATOR falls by 4 and the numerator by 2, which is
the previous round's own prediction landing: the dialog's four auto margins
go from scored to `non-absolute-length`-EXCLUDED, and two of the four
(`margin-left`/`margin-right`) were the last two cascade-attributed
mismatches outside `:text/font-size-absolute-keyword`. The residual is now
**2 values in 1 case**.

#### What Brave actually said

**The keywords, on `alpha beta` in the corpus's 14px monospace (7px/char).**

| container | `min-content` | `max-content` | `fit-content` | `auto` |
|---|---|---|---|---|
| 300px | 35 | 70 | 70 | 300 |
| 60px | 35 | 70 | 60 | 60 |
| 50px | 35 | 70 | 50 | 50 |
| 40px | 35 | 70 | 40 | 40 |
| 20px | 35 | 70 | **35** | 20 |

So `fit-content` is exactly `min(max-content, max(min-content, available))`
— it stops narrowing at min-content and overflows — and `max-content`
never narrows at all.

**`available` is net of the box's own margins AND its own insets.** All in
a 60px container:

| box | Brave |
|---|---|
| `fit-content` | 60 |
| `fit-content; padding: 0 6px; border: 2px` | 60 border box (44 content) |
| `fit-content; margin: 0 10px` | 40 |
| `fit-content; margin-left: auto; margin-right: 15px` | 45 |

A resolved margin takes room away, an `auto` one does not. The margins are
*not* subtracted by the new code: `layout-children-block` already hands a
block child `(- content-w ml mr)` through the same `margin-side`.
Subtracting them twice was measured doing it — the 40px row came out 35 and
the 45px row 35, both having fallen back to min-content on a room 20px too
small.

**The keyword yields a CONTENT size in BOTH `box-sizing` modes**, which is
the fact that decides where the resolution has to live. `width:
max-content; padding: 0 6px; border: 2px` over `alpha beta` is **86 under
`content-box` and 86 under `border-box`**, where `width: 70px` is 86 and
70. A declared length differs by the inset between the modes; a keyword
does not.

**min-content is a recursion, not the longest word in the subtree.**

| content of a `width: min-content` box | Brave |
|---|---|
| `alpha beta` | 35 |
| `<span>alpha</span> <span>bb</span>` | 35 |
| `<div>alpha beta</div><div>bb</div>` | 35 |
| `<div style="padding:0 10px">alpha beta</div>` | **55** |
| `<div style="width:40px;height:5px"></div>` | **40** |
| a 40x20 `<img>` | **40** |
| nothing at all, 1px border | 2 |

The last four are why `flex-item-min-content-width`'s longest-word-in-the-
subtree rule — which is right for what IT answers, a flex item's automatic
minimum — could not be reused: it reports 35 for the padded row and nil for
the other three.

**The flex clamp needs the whole frozen-item loop.** Eleven shapes, in both
directions and in both the growing and the shrinking case:

| shape | Brave |
|---|---|
| 200px row, `flex: 1` x2, `min-width: 150px` on one | 150 / 50 |
| 300px row, `flex: 1` x2, `max-width: 60px` on one | 60 / 240 |
| 300px row, `flex: 1` x3, `min-width: 200px` on one | 200 / 50 / 50 |
| 300px row, `flex: 1` x3, `max-width: 30px` on one | 30 / 135 / 135 |
| ...with `max-width: 30px` AND `max-width: 40px` | 30 / 40 / 230 |
| ...with `max-width: 30px` AND `min-width: 200px` | 30 / 200 / 70 |
| **...with `max-width: 30px` AND `max-width: 110px`** | **30 / 110 / 160** |
| 100px row, `min-width: 80px` on both of 2 | 80 / 80 (overflows) |
| 200px row, two `width: 150px`, `min-width: 140px` | 140 / 60 |
| 200px row, two `width: 150px`, `max-width: 60px` | 60 / 140 |
| 300px row, `flex: 1` `max-width: 50px` vs `flex: 2` | 50 / 250 |
| 200px row, 3x`width: 100px`, `max-width: 20px` + `min-width: 95px` | 20 / 95 / 85 |

**The bolded row is the one that proves it is a loop.** One pass proposes
100/100/100, freezes the first at 30 and offers its 70 to the other two
(135/135) — and only *then* is the second item's own maximum violated. A
clamp-once-and-redistribute rule reports 30/110/**135** and leaves 25px in
nobody's hands. Every other row above is satisfied by the simpler rule, so
that one shape is the whole evidence, and it was written because the simpler
rule predicted the other ten.

CSS Flexbox §9.7.4 resolves a pass with BOTH kinds of violation by the SIGN
of the total (freeze only the min-violated when positive, only the
max-violated when negative). This engine freezes everything the clamp
moved, in either direction. The two rows written to discriminate them —
`max-width: 20px` + `min-width: 95px`, and `max-width: 30px` +
`min-width: 200px` — give the same answer under both rules, so the simpler
one is what is implemented and this paragraph is why.

Two more measured facts the flex loop needed. **`max-width` limits the
CONTENT box**: `flex: 1; max-width: 60px; padding: 0 10px; border: 2px` in
a 300px row is **84** wide (60 + 24), and 60 under `box-sizing:
border-box`, with the sibling taking 216 and 240. And **an explicit
maximum caps the AUTOMATIC minimum**: `flex: 1; max-width: 20px` holding
`averylongunbrokenword`, whose min-content is 147, is **20**, its sibling
280 (CSS Flexbox §4.5).

**`<dialog open>` is centred by `margin: auto` between two zero insets.**
Measured, `<dialog open>Hi</dialog>` in a 300px `position: relative`
parent: 48x54 at x=126, `getComputedStyle` reporting `width: 14px`,
`height: 20px`, `margin: 0px 126px`, `left: 0px`, `right: 0px` — and `top`
resolved to the box's own STATIC position, which is what says `top` is
`auto` in the UA sheet and only the INLINE insets are declared. Confirmed
by moving the same dialog into a case with no positioned ancestor: it
centres in the 756px viewport (x=354) and its `top` reads back as that
case's own offset down the page (124px), a number no declared `top` could
produce.

The general rule underneath it, measured on a plain 70px absolutely
positioned box in a 300px `position: relative` parent:

| declaration | x |
|---|---|
| `left:0; right:0; margin:auto` | 115 |
| `left:0; right:0; margin-left:auto` | 230 |
| `left:0; right:0; margin-right:auto` | 0 |
| `left:0; right:0` (no auto margin) | 0 |
| `left:20px; right:0; margin:auto` | 125 |
| `left:0; right:0; margin:auto; width:400px` | 0 |
| `left:0; margin:auto` (no `right`) | 0 |
| **no `width` at all** | 0, and 300 wide |

and the same rule on the block axis (`top:0; bottom:0; margin:auto` on a
20px box in a 60px parent is y=20). The last row is why this round could
close the dialog and the last one could not: without a `width` the box is
stretched between the two insets, the leftover is zero, and `margin: auto`
has nothing to distribute.

Measured but deliberately NOT written into the UA sheet: the dialog's
`background-color: rgb(255,255,255)` and `color: rgb(0,0,0)`. Neither
changes a box, a hit region, or any of the fourteen properties the
computed-style axis compares, and this engine's default page is dark.

#### Where the keyword resolution ended up living, and why

In **`layout-node`**, not in `resolve-width`. `resolve-width` takes
`[st avail]` and an intrinsic width needs the NODE (and the theme, for
`:measure-text`) — its own docstring said so and left the three keywords
behaving as `auto`. `layout-node` is the one place a box's style map is
built for layout: it holds the node, the theme, the available width, the
opacity and the inherited context at once, and every sub-layout function
(block, flex, grid, table, form control, absolute) is handed the `st` it
produces. So resolving once there resolves for all of them — exactly as
the percentage padding/margin rewrite three lines above it already does.

The used value is written back onto `st` as a plain length, which is
`measure-child`'s own write-the-used-value-back technique for stopping a
percentage width resolving twice. Because a keyword yields a content size
in both box-sizing modes, a `border-box` box gets the insets folded in at
the write rather than losing them.

#### Scope cuts, each with the number a future round needs

- **A PERCENTAGE-width child inside an intrinsically sized box** is
  measured at its percentage of the OUTER containing block, where real CSS
  treats a percentage as indefinite while sizing the box it would resolve
  against. Measured: `<div style="width:max-content"><div
  style="width:50%">alpha beta</div></div>` in 300px is **70 / 35** in
  Brave and **150 / 75** here. Pre-existing — `child-outer-max-content-
  width` goes through `measure-child`, whose percentage write-back already
  answered this way for a table cell and a flex item — and the fix belongs
  in that write-back.
- **A flex item's base size is already clamped** when it reaches the §9.7
  loop, because it comes from `measure-child`, which runs `clamp-width`.
  Real CSS feeds the loop the UNCLAMPED flex base size. One shape measured
  to differ: a 200px row of three `width: 100px` items, the first
  `max-width: 20px` and the second `min-width: 95px`, is **20 / 95 / 85**
  in Brave and **17 / 95 / 87** here. Every `flex: N` shape is unaffected
  (its basis is `0%` and cannot be clamped away).
- **`clamp-width` reads `min-width`/`max-width` as BORDER-box limits**, so
  the same declaration clips the inset twice everywhere except the new
  flex path (`flex-main-clamp`, which converts). Not corrected here
  because `clamp-width` is called from `resolve-width`, i.e. from every
  box in the document. `force-main-width` now neutralises it for a
  resized flex item, since §9.7 has already applied both bounds.
- **A percentage `min-width`/`max-width` on a flex item** resolves against
  the item's own resolved width rather than the container's, because
  `measure-child` hands the child its own width as `avail-width`.
  Measured: `flex: 1; max-width: 20%` in a 300px row is **60** in Brave;
  the line reserves 60 here and the item draws itself 12 wide (20% of 60).
- **`flex: 1 1 0`** (a unitless zero basis) is not parsed as a basis:
  `flex: 1 1 0` vs `flex: 2 1 0` in a 300px row is 100 / 200 in Brave and
  7 / 7 here, while `flex: 1 1 0%` is 100 / 200 both sides. A `flex`
  shorthand parsing gap in `cssom.core`, unrelated to clamping.
- **An absolutely positioned box's own margin does not offset it.**
  Measured, `position:absolute; left:0; margin-left:20px` is at x=20 in
  Brave and x=0 here. `left` is the offset to the MARGIN edge. Untouched
  by this round; the auto-margin rule added here is a different clause of
  the same section.
- **`min-content` of a FLEX CONTAINER** falls through to the block rule
  (widest item) where real CSS sums the items' min-contents along a nowrap
  row. Measured: a `display: flex` holding `alpha beta` and `gamma delta`
  under `width: min-content` is **70** = 35 + 35, and **35** here. Same
  cut, same reason, as the grid branch of `intrinsic-max-content-width`.
- **`text-indent` is counted in the max-content size and not in the
  min-content one.** The max-content rule was measured (an
  `inline-block; text-indent: 30px` holding `abcd` is 58); the min-content
  one has no corpus case and no measurement, so it is absent rather than
  guessed.

#### Tried and withdrawn

**Subtracting the box's own margins inside `resolve-intrinsic-width`.**
It reads like the rule — `available` is demonstrably net of margins — and
it is double-counting: `layout-children-block` has already done it. Caught
by the two margin rows of the 60px table above, which came out 35 and 35
instead of 40 and 45.

**Reusing `flex-item-min-content-width` for the `min-content` keyword.**
Its longest-word-in-the-subtree rule matches on plain text and on the two
nested shapes above it, and misses everything with a box in it: 35 instead
of 55 for a padded child, and nil (no text to measure) for a
declared-width child and for an `<img>`. Replaced by a recursion that
mirrors `block-max-content-width` branch for branch. That function is
untouched and still answers what it always answered.

### Round thirty-nine: four numbers where there was one, and the summary a browser writes for you

Two gaps, each named in three earlier rounds from three directions and
each declined for the same reason: the box model carried ONE uniform
`:border-width`.

```
                    LINE      GEOMETRY (boxes / clean)   PAINT (points / clean)   STYLE
before   546/556    1915/1973  545/581                   14426/14514  558/581     27735/27740
after    546/556    1926/1973  549/581                   14450/14514  561/581     27735/27740
```

**Five cases changed in the whole 581-case op dump**, all in the intended
direction, all now matching the oracle exactly:
`:box/border-top-width-only`, `:box/border-left-width-only`,
`:logical/border-inline-start`,
`:box/margin-top-percentage-is-of-the-width` and
`:interactive/details-with-no-summary`. The paint axis reads **100%** for
the first time.

#### The per-side shorthand was not read at all

Round twenty-six named "per-side border widths" as not implemented on the
grounds that the engine has one uniform width. Measured, it was sharper
than that: `border-top` fell through to the generic declaration path and
was stored as the raw string `"10px solid"`, which nothing reads — not ten
pixels on four sides, **zero on all of them**.

Twenty-seven declarations on one probe page in Brave 151, 2026-08-06, each
on a 300px block wrapping one `<p style="margin:0">` (bare box 16.797
tall, `<p>` at 0,0):

| declaration | box | `<p>` at | computed widths |
|---|---|---|---|
| `border-top: 10px solid` | 300x26.797 | (0,10) | 10 0 0 0 |
| `border-left: 5px solid` | 305x16.797 | (5,0) | 0 0 0 5 |
| `border-width: 10px 5px` + `border-style: solid` | 310x36.797 | (5,10) | 10 5 10 5 |
| `border-width: 10px` + `border-style: solid none` | 300x36.797 | (0,10) | 10 0 10 0 |
| `border-style: solid` (no width) | 306x22.797 | (3,3) | 3 3 3 3 |
| `border-width: 10px` (no style) | 300x16.797 | (0,0) | 0 0 0 0 |
| `border-top: solid` | 300x19.797 | (0,3) | 3 0 0 0 |
| `border-top: 10px` | 300x16.797 | (0,0) | 0 0 0 0 |
| `border-width: thin medium thick 0` + `border-style: solid` | 303x22.797 | (0,1) | 1 3 5 0 |
| `border: 5px solid` + `border-top: none` | 310x21.797 | (5,0) | 0 5 5 5 |
| `border-top-width: 9px` then `border-top: 2px solid` | 300x18.797 | (0,2) | 2 0 0 0 |
| `border-top: 2px solid` then `border-top-width: 9px` | 300x25.797 | (0,9) | 9 0 0 0 |
| `border-top: 10px solid red` then `border: 2px solid blue` | 304x20.797 | (2,2) | 2 2 2 2 |
| `border: 2px solid blue` then `border-top: 10px solid red` | 304x28.797 | (2,10) | 10 2 2 2 |

The last six are what constrain the fix, and none of them is guessable
from the first two. **An omitted width is `medium` = 3px** and **an omitted
style is `none`, which zeroes whatever width was declared** — so
`border-top: solid` costs three pixels and `border-top: 10px` costs none.
And because a shorthand resets the components its value does not name, a
`border` shorthand has to write **all twelve** per-side longhands or a
later `border` cannot overwrite an earlier `border-top`: the two order
rows above differ only in which declaration comes second.

That is the whole cascade half. `cssom.core` now expands the four
`border-<side>` shorthands into three longhands each, the three
`border-width`/`-style`/`-color` 1-to-4 shorthands into four each
(**keeping the uniform key beside them**, the way `expand-box-side-
shorthand` already did, so every existing reader goes on working), and
`border` into all fifteen. `thin`/`medium`/`thick` ride through as
keywords, because this namespace holds SPECIFIED values and `cssom.layout`
resolves them.

#### Four numbers, and the twenty-two places that read one

`node-style` resolves four USED widths, each through its own side's style,
falling back author-side → author-uniform → UA-sheet-side →
UA-sheet-uniform → the control constant → `medium`. **The author and the
UA sheet are read as two separate origins here**, not through the shadowed
`style` accessor every other property uses, and that is not tidiness: a
shorthand and a longhand meet in this one property, `style` resolves per
KEY, and a single chain let the UA sheet's expanded `border-top-width: 2px`
beat an `<iframe>`'s own `border-width: 0` — the iframe came back 304x154
with its border explicitly turned off. A document that went through
`apply-cascade` cannot hit that (the author's shorthand expands and wins on
all four); this is the no-stylesheet host path, and ordering the origins is
what makes it agree with the cascaded one.

`border-side`/`border-x`/`border-y` read the four, and every site was
converted one at a time rather than by a global rename: `inset-side`,
`declared-inset-side`, `border-ops` (one `:rect` per side, each gated on
its OWN width — before this a box with a per-side border painted a full
ring or nothing), the intrinsic-width inset, both baseline paths, the
inline edge advance, the inline owner rects, `<select multiple>`'s option
box, the fieldset legend band, the collapsed table's outer edges, the
absolutely positioned descendant's padding box, `fc-free?` and
`self-collapsing-block?`.

**Two workarounds went with it.** `self-collapsing-block?` tested the
block-axis border TWICE, the second time against the node's raw
declarations, with a comment saying so — precisely because `st` could not
see a `border-top`. Its docstring called the real fix "a much larger change
[that] would make this test one line", and it is now that one line. It also
stopped being over-conservative, which the browser had to settle:

| empty box, `margin: 14px 0`, sibling below | container | sibling |
|---|---|---|
| no border | 20 | y=0 |
| `border-top: 1px solid` | 35 | y=15 |
| `border-bottom: 1px solid` | 35 | y=15 |
| `border-top: none` | 20 | y=0 |
| `border-left: 5px solid` | 20 | y=0 |

The last two are the ones the raw-declaration test got wrong. And the last
one is why both gates read **block-axis borders only**: measured on the
same page, a `border-left: 5px solid` parent still lets its first child's
20px top margin collapse out (child at y=0, parent 10 tall), where
`border-top: 1px` puts the same child at y=21.

#### One regression, caught by the dump and fixed rather than accepted

`:table/border-collapse` went 26 → 28 tall on the first run. Under
`border-collapse: collapse` a cell keeps half its own border, which the
table implements by rewriting the cell's uniform `:style/border-width` —
and the cascade now also puts `border-top-width: 2px` and friends on that
same cell, which the halving did not touch, so the cell kept its whole
border. The four longhands are removed with the rewrite. The net scoreboard
would have shown this as +7 and hidden it; the corpus-wide op diff named it.

#### Left uniform, with the numbers a future fix will need

Flex, grid and table CONTAINERS still read `content-inset`, whose other
half is the uniform `:padding` — converting one means converting the other,
which is a second change with its own measurements. Written at that
function: on a 300px container with `border-top: 10px solid; border-left:
4px solid` around one 50x20 item, Brave puts the item at **(4,10)** in a
300x30 box for `display:flex` and for `display:grid` alike, and a `<td>`
with the same borders is **32** tall; this engine puts all three at (0,0)
in 300x20. A collapsed table's CELL border is also still uniform, and that
one is deliberate: which edge a cell contributes to depends on which edge
is being resolved, and the half-border written back is uniform too, so
splitting one without the other would make a cell paint an edge its column
width did not reserve.

#### A `<details>` with no `<summary>`

The largest single paint residual left in the corpus, and a previous round
declined it with a reason worth checking: *"the oracle also reports a `<p>`
box the engine cannot emit, so the case cannot go clean on geometry
anyway."* **That is true, and it is not a reason to leave the other three
boxes wrong.** Brave reports the closed `<p>` as a real 300x20 box at y=34
and never paints it — Chromium hides a closed `<details>`'s content with
`content-visibility: hidden`, not `display: none` — and an engine that
emits draw-ops cannot report a box it does not paint. That is exactly the
limit `:interactive/details-closed-shows-only-the-summary` already records,
and it now applies to one box in this case rather than four.

What Brave actually generates, measured with `getBoundingClientRect`,
`elementsFromPoint` and a `Range` on 2026-08-06:

| markup (`line-height: 20px`) | box | `<p>` at |
|---|---|---|
| `<details><p>Body</p></details>` | 300x20 | y=20, never painted |
| `<details open><p>Body</p></details>` | 300x40 | y=20 |
| `line-height: 40px` | 300x40 | |
| `font-size: 30px` | 300x20 | |
| `padding: 8px` | 300x36 | (8,28) |
| `border: 5px solid` | 300x30 | (5,25) |
| `<details></details>` | 300x20 | |

Three readings decide the implementation. The band is **one line box in the
element's own line-height** — not its font size and not a constant. It sits
**inside** the padding and the border, where a real first child would. And
the generated summary is **shadow content**: every interior point of the
box reports `DETAILS` rather than `SUMMARY` (a real `<summary>` child
reports `SUMMARY`), and a `Range` over the element reads only the author's
own text. So an engine that synthesised a `<summary>` ELEMENT would report
a box the oracle has not got, and `details-summary-band` reserves a band
instead — folded into the block-start inset exactly as the fieldset legend
band is, so the box's height and where its content starts cannot drift
apart.

**The label is deliberately not drawn.** Chromium paints the word
`Details` and a disclosure triangle in that band; both are shadow content
the oracle's own `Range` cannot read, and both are localised — an `en-US`
browser's string is not a rule. Reserving the line and drawing nothing in
it is the honest half, and it is what the geometry and paint axes actually
compare.

Measured alongside and **not** implemented, recorded at the same function:
Chromium renders the first `<summary>` in DOM order FIRST wherever it sits,
so `<details><p>A</p><summary>S</summary></details>` puts the SUMMARY at
y=0 and the `<p>` at y=20. This engine keeps a late summary at its own
index. No corpus case has one.

#### One repository downstream

`htmldom`'s inline-`style` tests assert the shape of
`parse-declarations-with-importance`'s output directly, so five of them
moved with this change and one was added — a test-only update, landed
separately as `kotoba-lang/htmldom` `agent/border-longhand-expectations`.
`browser` (754/0) and `dom-gpu` (130/0) are unchanged.

### Round thirty-eight: a resource this engine cannot see, and a gap that has to be measured twice

Two gaps that round thirty-seven and round thirty-six each named and left,
because each one needed something the code around it did not have: a fact
only a host knows, and a size that is not known until after it is used.

**Before → after**, both measured on the corpus of **576** at this round's
merge base (`f1c0db4`), so the columns are the same cases either side and
the movement is entirely `src/`:

| axis | before | after |
|---|---|---|
| line structure | 541/551 | 541/551 |
| geometry (boxes) | 1892/1959 | **1901/1959** |
| geometry (clean cases) | 535/576 | **540/576** |
| paint order (points) | 14285/14389 | **14301/14389** |
| paint order (clean cases) | 550/576 | **553/576** |
| computed style (values) | 27539/27544 | 27539/27544 |
| computed style (clean cases) | 573/576 | 573/576 |

`--dump-ops` diffed corpus-wide names **five changed cases and no others**,
in one direction: `:gap/percentage-column-gap-on-a-grid`,
`:gap/percentage-row-gap-on-a-grid`, `:replaced/img-intrinsic-size`,
`:replaced/img-width-only-keeps-the-ratio` and
`:replaced/img-height-only-keeps-the-ratio`. All five now agree with Brave
exactly. Nothing moved anywhere else in either direction.

Five cases were then **added** for rules this round measured that the
corpus had no case for, taking it to 581, and all five agree:
`:gap/percentage-row-gap-with-a-definite-height`,
`:gap/percentage-row-gap-on-an-auto-flex-column`,
`:gap/percentage-column-gap-on-an-inline-grid`,
`:replaced/img-max-width-clamps-before-the-ratio` and
`:replaced/img-border-and-padding-sit-outside-the-resource-size`. On 581:
line 546/556, geometry 1915/1973 (545/581 clean), paint 14426/14514
(558/581 clean), computed style 27735/27740 (578/581 clean).

#### An image's size is not in the document, and the hook that says so

`replaced-content-size` could already solve either axis of a replaced box
from a ratio — it does exactly that for a `<canvas>`, whose bitmap is its
attributes. What it had no way to reach was the size of an `<img>`'s
**resource**, which is a property of the bytes at the far end of a URL.
This engine has no loader, no decoder and no network: `cssom.layout` is
handed a DOM tree and a theme.

So the answer arrives on the theme, as the OPTIONAL
**`:image-size`** hook — `(fn [src] {:w <px> :h <px>})`, nil for a
resource the host has not resolved — the fourth member of the
`:measure-text` / `:font-metrics` / `:avg-advance` family and the same
bargain as all three: **absent means the engine keeps exactly the answer
it always had**, which for an `<img>` is 0x0. `cssom.layout` runs on hosts
that have no images at all (the JVM test suite is one), so that absence is
part of the API and
`replaced-image-without-an-image-size-hook-is-unchanged` in
`test/cssom/layout_test.cljk` asserts it — including that a hook returning
`nil`, or a zero size, is indistinguishable from no hook.

Every number below was measured in Brave 151 over CDP on 2026-08-06, on
the corpus's own 40x20 SVG data URI, **before** any of it was written:

| declaration | Brave | where the answer comes from |
|---|---|---|
| (none) | 40x20 | the resource, both axes |
| `width: 200px` | 200x100 | CSS width, the ratio solves the height |
| `height: 60px` | 120x60 | CSS height, the ratio solves the width |
| `max-width: 20px` | 20x10 | the clamp lands **before** the ratio |
| `width:200;height:60` | 200x60 | both declared, the ratio unused |
| `height="40"` attribute | 80x40 | a HINT is a declaration too |
| `width="80" height="40"` + `width:200px` | 200x40 | **not** 200x100 |

That last row is the control that made this a resource finding rather than
a box-model one, and it passed before the hook existed and still passes:
the attributes are presentational hints, i.e. ordinary lowest-priority
declarations, so a CSS `width` replaces the width hint, the height hint
stands, and the resource's 2:1 ratio has nothing to solve. What was
missing was never the ratio machinery.

**The engine still emits no image draw-op.** `cssom.layout`'s four ops are
`:node`, `:rect`, `:text` and `:clip`, and `dom-gpu` has no `drawImage`
path. What the hook buys is the **box** a browser reserves for the
picture, which is the same thing the 300x150 default object size buys for
a `<video>` nothing here can decode either.

#### How the harness learns an image's size honestly

The harness has to play the host, and there were two candidate decoders:
its own, or the oracle's. It uses the **oracle's** — a per-src
`naturalWidth`/`naturalHeight` table read off the corpus page, alongside
the per-character advance table and the per-face metrics that are already
measured there — and the reason is in this corpus rather than in a
principle.

Ten cases use the data URI `R0lGODlhAQABAAAAACw=`. It has a **well-formed
GIF header saying 1x1 and no image data at all**. A header-sniffing
decoder in the harness reports 1x1; Brave rejects it, reports
`naturalWidth` 0, and paints a 16x16 broken-image icon. Feeding the engine
1x1 for it would make an `<img style="width: 200px">` come out 200x200
here against Brave's 16x16 — an argument between two decoders, dressed up
as a layout bug. Measuring the fact in the oracle removes the one
difference this comparison cannot legitimately judge (whether the harness
has a decoder) and leaves the actual question — what **box** the engine
builds from a size, a ratio and the declarations — entirely on the engine.

It is not laundering the answer, with exactly one honest exception. In
`:replaced/img-width-only-keeps-the-ratio` the fact is 40x20 and the box
is 200x100; in `:replaced/img-height-only-keeps-the-ratio` it is 120x60.
In `:replaced/img-intrinsic-size` the box **is** the fact, so that case
asserts the size is consulted at all and nothing more, and its comment in
`cases.edn` says so.

`complete` is reported per image alongside the size, and the harness
prints a WARNING if any image had not finished loading when the page
measured, so a load race can never quietly look like a resource of size
zero.

#### What an `<img>` does when the resource is BROKEN, and why it is out

Round thirty-seven recorded that "a bare `<img>` and an `<img>` whose src
404s are **both** 0x0 in Brave". The first half is right; **the second half
was wrong**, and re-measuring it was the first thing this round did. A
broken image (a connection-refused URL, or that truncated GIF) is a
broken-image **icon**, and it stops behaving like a replaced box at all:

| declaration on the broken `<img>` | Brave |
|---|---|
| (none) | 16x16 |
| `width: 200px` | **16x16** — the width is ignored |
| `width: 200px; height: 50px` | 200x50 |
| `width: 200px; display: block` | 200x16 |
| `width="40" height="20"` | 40x20 |
| `alt="some alt text here"` | 142x20 — the alt text, laid out |

i.e. an inline broken image with fewer than two definite axes is sized
like **non-replaced inline content** — its icon, or its alt text — which
is why the CSS width alone does not take. This engine keeps 0x0 for all
six rows and that is now recorded as a scope cut rather than as agreement.
No corpus case is affected: every `<img>` in the corpus that uses the
truncated GIF declares **both** axes, the one row where 0x0 and the
browser reach the same box anyway.

Also measured and deliberately not wired to the hook, each with the number
a fix needs: a `<video poster=...>` with no `src` **is** 40x20 (the poster
is the intrinsic size while there is no video, but a `<video src>` takes
its size from frames, which is not an image decode); an
`<object data=...>` pointing at the same SVG is 40x20 too, but `<object>`
is not a replaced element here at all (its fallback renders); an
`<iframe srcdoc>` is 304x154 whatever document is inside it. And the one
shape the hook's contract cannot express: an SVG with a `viewBox` and no
`width`/`height` is an intrinsic **ratio with no intrinsic size**, which
reports `naturalWidth` 300x150 and which Brave lays out at **400x200** in a
400px block (200x100 under `width: 200px`) — closing that needs a hook
that can answer a ratio with no size.

One older bug this work uncovered and did **not** fix, recorded at
`replaced-content-size`: a **percentage `width` on an inline-level replaced
box is resolved twice**, once by `inline-max-content-width` to get the
atomic inline's natural width and again by `layout-node`'s replaced branch
against that answer. Measured through this engine in a 400px block,
`width: 50%` is 100, `25%` is 25 and `10%` is 4, where Brave says 200, 100
and 40 — the error grows with the square of the percentage. It is
identical for `<canvas>`, `<video>`, `<svg>` and `<iframe>`, so it belongs
to the atomic-inline plumbing rather than to any resource, and
`display: block` on the same element gives Brave's answer today.

#### A percentage gap is resolved against a size that does not exist yet

Round thirty-six landed percentage margins and paddings and stopped at
`row-gap`, naming it "a two-pass rule and its own round". This is that
round, and the measurement is the whole of it.

**The rule.** A percentage `row-gap`/`column-gap` resolves against the
container's own **content-box** size in that axis. When that size is
definite, that is the end of it. When it is **not** — an auto height, a
shrink-to-fit width — the size is first computed with the gap treated as
**zero**, the percentage then resolves against that result, and the gap is
applied for positioning only: the container does **not** grow, and the
content overflows.

Measured in Brave 151 on 2026-08-06:

| markup | container | gap | evidence |
|---|---|---|---|
| grid, two 20px rows, `row-gap: 10%` | 40 tall | **4** | 2nd row y=24, `scrollHeight` 44 |
| the same with `row-gap: 4px` | **44** tall | 4 | the px control — the container grows |
| grid, three 20px rows, `row-gap: 10%` | 60 tall | **6** | y 0/26/52, `scrollHeight` 72 |
| grid, rows of 30 and 50, `row-gap: 10%` | 80 tall | **8** | 2nd row y=38 |
| grid, two 20px rows, `row-gap: 200%` | 40 tall | **80** | 2nd row y=100 |

The three-row row is what says it is exactly **one** pass and not a fixed
point: 10% of the gap-free 60 is 6, and a second round against the
resulting 72 would be 7.2.

The inline axis has the same rule wherever the width is indefinite:
`inline-grid` with two 60px columns and `column-gap: 10%` is **120** wide
with a **12px** gap that overflows it, and `inline-flex` with two 60px
items is 120 wide with a 12px gap the items **shrink** to fit (54 each,
because a flex item's `flex-shrink` is 1 and a grid track's size is not
negotiable). For a block-level container the width is definite from the
start: `width: 300px` with `column-gap: 10%` is 30, and the basis is the
**content** box in both `box-sizing` modes — `padding: 0 50px` gives 30
under `content-box` (the content width is 300) and **20** under
`border-box` (it is 200). It is the container's own size and not its
tracks': two 60px columns in a **100px** grid get a 10px gap and overflow.

**And flex is not grid, which was the surprise.** Blink gives a flex
container's **block axis** no second pass at all:

| container | Brave's gap |
|---|---|
| grid, auto height, `row-gap: 10%` / `200%` | 4 / 80 |
| flex column, auto height, `row-gap: 10%` / `50%` / `200%` | **0** / **0** / **0** |
| flex column, `height: 200px`, `row-gap: 10%` | 20 |
| flex column, `min-height: 100px`, `row-gap: 10%` | **0** |
| grid, `min-height: 100px`, `row-gap: 10%` | 10 |
| flex column, `max-height: 30px`, `row-gap: 10%` | **0** |
| grid, `max-height: 30px`, `row-gap: 10%` | 3 |

Only a definite `height` resolves it on a flex container, and a min/max
clamp does not count — where on a grid the clamp is part of the **basis**
rather than something applied after it. That pair of rows is the sharpest
measurement of the round: the same two declarations give 0 and 10, and 0
and 3. A flex container's **inline** axis behaves like a grid's
throughout.

**Where it lands.** `node-style` now carries `:row-gap/raw` and
`:column-gap/raw` beside the coerced pair, for the same reason
`:margin/raw` sits beside `:margin` — `parse-int "10%"` is 10 PIXELS, and
the coercion that makes every other reader safe is exactly what erases a
percentage. Two functions read them: `gap-for-intrinsic-size` (zero for a
percentage, which is what the container's own size is computed with) and
`used-gap` (the percentage resolved against a basis the caller supplies,
and 0 when the caller has none — the state only a flex container reaches).
`layout-grid` binds each axis's used gap the moment that axis's content
size is known, and `layout-flex` hands `used-gap` its `cw` for the inline
axis and its definite content height, or nil, for the block one. Multicol
already resolved percentages correctly (`multicol-gap-px`) and is
untouched.

Two rules this measured and did not implement, with their numbers: a
grid with spare block space **stretches** its auto rows
(`min-height: 100px` over two 20px rows makes them 45 each, so Brave's
second row is at y=55 where this engine says 30 — the 10px gap is right,
the stretch is missing), and `align-content` on a wrapping flex container
already does the equivalent (`height: 200px` with `row-gap: 10%` puts the
second line at y=110 on both sides).

### Round thirty-seven: the box a browser reserves for something it cannot draw

Five tags — `<canvas>`, `<video>`, `<svg>`, `<iframe>`, and `<img>` beside
them — plus `<progress>`, `<meter>` and three `<input>` types had **no
intrinsic size model at all**. Each came out as a block that filled its
container and was **0px tall**, so a page with a `<canvas>` in it was 150px
shorter here than anywhere else and a `<canvas>` in a sentence broke the
sentence in two. Everything below was measured in the same headless Brave
151 the harness drives, on probe pages built to the harness's own page
shell, **before** anything was implemented.

**The 300×150 is an intrinsic size, not a UA `width` rule**, and one
measurement decides it: `<canvas style="width: 50%">` in a 400px block is
**200×100**, not 200×150. A stylesheet `width: 300px; height: 150px` would
leave the height at 150; an intrinsic 300×150 carries a 2:1 ratio the
declared width then solves the height from. A second one confirms it from
the other side: `<canvas style="display: block">` inside a **100px** block
is 300 wide and *overflows*. A block-level box with `width: auto` fills its
containing block — a block-level **replaced** box uses its intrinsic width
(CSS 2.1 10.3.4 against 10.3.3), which no stylesheet rule can express. And
it does not scale with the font: 300×150 at `font-size` 8, 14 and 28.

**A `<canvas>` and a `<video>` are 300×150 for different reasons**, which
is the shape of the whole algorithm:

| declaration | `<canvas>` | `<video>` |
|---|---|---|
| (none) | 300×150 | 300×150 |
| `width: 200px` | 200×**100** | 200×**150** |
| `height: 60px` | **120**×60 | **300**×60 |
| `max-width: 100px` | 100×**50** | 100×**150** |

A `<canvas>`'s bitmap *is* its `width`/`height` content attributes,
defaulting to HTML's own 300 and 150 — so it has an intrinsic size and
therefore a **ratio**. A bare `<video>`/`<svg>`/`<iframe>` has neither, and
CSS's default object size supplies each axis **independently**. The
`max-width` row is where the clamp goes: the ratio solves the height from
the width *after* min/max has had its say.

**The attributes are hints on four of the five and an intrinsic size on the
fifth.** With `width="80" height="40"` and a CSS `width: 200px`, Brave says
**200×40** for `<img>`, `<video>`, `<iframe>` and `<svg>` — the CSS width
replaces the width hint, the height hint stands, and the ratio has nothing
to solve — and **200×100** for `<canvas>`. `presentational-size` is now
honoured for exactly the tags that get a replaced box, and `<canvas>` is
excluded from it and read by `replaced-intrinsic-size` instead.

**Atomic inline-ness is a separate finding from size**, and it is the half
the old scope note got backwards. `inline-atomic-tags` excluded these four
because "this engine has no rendering for any of them, so giving them an
inline box would place an empty rectangle in the middle of a sentence
rather than fix anything". A browser cannot render them either and reserves
a box for every one of them anyway: `before <canvas width=20 height=10>
after` is **one 20px line** with the canvas at x=49 y=4 on the baseline,
where this engine made two lines with a 400px-wide block between them. The
objection was answered by the box being the *right* empty rectangle.

**An `<iframe>`'s 304×154 is one UA declaration.** `border: 2px inset`, and
`border: 0` on the same iframe gives 300×150 exactly — which also proves
the default object size is a **content** size, since `box-sizing:
border-box` still reports 304×154.

**`<progress>` and `<meter>` turned out to be `em`, not constants.** The UA
sheet's own note listed `meter`/`progress` → `inline-block` as deliberately
absent, "a layout decision needing its own measurement". This is that
measurement: at `font-size` 8 / 14 / 28 a `<progress>` is 80×8 / 140×14 /
280×28 and a `<meter>` 40×8 / 70×14 / 140×28, i.e. `10em × 1em` and
`5em × 1em` exactly. The 2.797px they sit *below* the baseline is
`vertical-align: -0.2em` (5.594 at 28px, and unchanged at `line-height: 10px`
and `40px`, which is what rules out a leading-derived explanation). All four
declarations are stylesheet rules now; the length form of `vertical-align`
is new and closed `:inline/vertical-align-length` for free.

**Three `<input>` types are widgets, and one of them is a locale.**
`range` (129×16, `margin: 2px`, no padding or border), `color` (50×27,
border-box, 1px border) and `file` (…×27) all came out of the plain `input`
rule at a text field's 153×21. None of these numbers moves with the font
(measured at 8, 14, 28 and 40px). Their **baselines** are three different
rules, separated by overriding the height: range's is its bottom *border*
edge with its 2px bottom margin hanging below (measured with
`margin-bottom: 20px`, which does not move the box), color's is 6px up from
its bottom edge and moves with the height, and file's is 18px down from its
*top* and does **not**.

**What was cut, with the numbers a fix needs.** Two things, both stated in
code at the function that owns them:

- **An `<img>`'s intrinsic ratio.** **CLOSED by round thirty-eight**,
  through the `:image-size` host hook this paragraph correctly predicted —
  see that round for the hook, its measurements, and how the harness
  supplies it. The rest of the diagnosis stood up: the ratio machinery
  existed and did exactly this for a `<canvas>`, what was missing was only
  the resource's own size, and the control case (with `width`/`height`
  **attributes** both sides already agreed at 200×20) is what made it a
  resource finding rather than a box-model one. `cssom.layout` still emits
  no image draw-op and `dom-gpu` still has no `drawImage` path; what the
  hook buys is the box, not the pixels.

  One claim here did **not** stand up, and round thirty-eight corrects it:
  a bare `<img>` is 0×0 in Brave, but an `<img>` whose src 404s is a
  **16×16 broken-image icon**, and it stops behaving like a replaced box
  at all — a CSS `width: 200px` alone does not even apply to it. That is
  still a scope cut, now with its own measured table.
- **`input[type=file]`'s width.** Brave says 253. The shadow `<button>`
  holding the browser's own "Choose File" is 87.141 wide and "No file
  chosen" in the UA control face is 84.484 — 171.625, **81 short** — so the
  control also reserves a fixed filename column, and both strings are
  en-US. A 253 written into the engine would be a measurement of this
  machine's UI language. The height *is* a rule (27 = the engine's own 21px
  `<button>` with 3px above and below, which is also where the 18px
  baseline comes from) and is implemented, so that case's `<div>` agrees
  and only the input's width does not.

Also deliberately not implemented, each measured: `<object>` (bare it *is*
300×150, but `<object>fallback text</object>` renders the fallback and
shrink-wraps to it — it is only replaced when it has a resource);
`<embed>` with no `src` (**no box at all**, not a 300×150 one); `<audio>`
(`display: none` without `controls`, 300×**54** with); and an `<svg>` with
a `viewBox` (an intrinsic *ratio* with no intrinsic size, which Blink
resolves by filling the container — `viewBox="0 0 40 20"` in a 400px block
is **400×200**).

**Before → after**, both measured on the corpus of 576 at this round's
merge base (`2b1d95b`, i.e. with the stacking and logical-properties
rounds already in — these three rounds ran concurrently and only these
numbers are this round's):

| axis | before | after |
|---|---|---|
| line structure | 540/551 | **541/551** |
| geometry (boxes) | 1870/1959 | **1892/1959** |
| geometry (clean cases) | 524/576 | **535/576** |
| paint order (points) | 14207/14389 | **14285/14389** |
| paint order (clean cases) | 542/576 | **550/576** |
| computed style (values) | 27525/27544 | **27539/27544** |
| computed style (clean cases) | 570/576 | **573/576** |

Twelve cases changed and **none regressed** (`--dump-ops`, corpus-wide,
before and after, on that same merge base): the six `:replaced/`
default-size cases, `:form/progress`, `:form/meter`, `:form/input-range`,
`:form/input-color`, `:form/input-file` (its `<div>` only), and
`:inline/vertical-align-length`. The 14 computed-style values are: the
four `padding` longhands each on the range and file inputs (8, all
`cascade`-attributed), the range's `margin-right`/`margin-bottom`, and
`display: inline-block` on `<progress>` and `<meter>`. What is left in
this group's `ua-default` bucket is one value and it is deliberate — a
range input's `color`, which Brave reports as `rgb(16, 16, 16)` and which
the UA sheet declines to write for the reason already recorded there (the
real UA value is the system colour `fieldtext`, and this sheet has no
system-colour model).

### Round thirty-six: logical properties, and the percentage that is always of the width

Two gaps, fifteen cases between them, and the interesting part of both is
*where* the fix belongs rather than what the numbers are.

**Before → after**, both measured on the corpus of 576 at this round's
merge base (`dac2240`, i.e. with the stacking round already in — the two
rounds ran concurrently, and the paint column moved under this one):

| axis | before | after |
|---|---|---|
| line structure | 540/551 | 540/551 |
| geometry (boxes) | 1851/1959 | **1870/1959** |
| geometry (clean cases) | 510/576 | **524/576** |
| paint order (points) | 14181/14389 | **14207/14389** |
| paint order (clean cases) | 538/576 | **542/576** |
| computed style (values) | 27514/27544 | **27525/27544** |
| computed style (clean cases) | 563/576 | **570/576** |
| computed style (no cascade-attributed mismatch) | 565/576 | **572/576** |

`--dump-ops` diffed corpus-wide names **14 changed cases and no others** —
the eleven `:logical/` cases that now agree and three of the four
percentage ones. Nothing moved in either direction anywhere else.

#### Where a logical property becomes a physical one

`margin-inline-start` is not an alias for `margin-left`: which side it
lands on depends on the element's `direction`, so it cannot be rewritten
at parse time. Three measurements in Brave 151 decided where it *can* be:

- `<div style="max-inline-size: 80px">` reports **`maxWidth: 80px`** from
  `getComputedStyle`, and `margin-inline: 20px 60px` reports
  `marginLeft 20px / marginRight 60px`. The physical longhand genuinely
  holds the value by the time `getComputedStyle` can be asked — which is
  the definition of computed-value time. A layout-time mapping would
  leave the cascade, `cssom.core/computed-style`, and a live page's
  `getComputedStyle` all reporting nothing, the same architectural
  mistake ADR-2800003100 corrected for the UA sheet.
- The direction it reads is the element's **own**, not its containing
  block's: `<div style="direction: rtl; margin-inline: 20px 60px">` puts
  the box at x=60, exactly as declaring `direction: rtl` on the *parent*
  does. Both were measured side by side, because they are
  indistinguishable in every case where only the parent declares it.
- And the sharpest one — what happens when both spellings are declared:

  | declaration block | Brave's `marginLeft` |
  |---|---|
  | `margin-left: 5px; margin-inline-start: 40px` | 40px |
  | `margin-inline-start: 40px; margin-left: 5px` | 5px |
  | `margin: 1px; margin-inline-start: 40px` | 40px |
  | `margin-inline-start: 40px; margin: 1px` | 1px |
  | `#a { margin-left: 5px }` then `.a { margin-inline-start: 40px }` | **5px** |

  Source order decides at equal specificity, and specificity still
  outranks source order. Under `direction: rtl` the first pair gives
  `marginLeft 5px / marginRight 40px` in **both** orders — because there
  the two declarations no longer collide. So the collision is decided
  *after* the rename, not before.

That last row is the whole implementation. `resolve-style-for` already
sorts every declaration by importance/origin/inline/layer/specificity/
order and then takes the last of each property group; the rename is one
`map` over that sorted list, below the sort and above the group-by. Every
row of the table above falls out with no ordering code of its own.

The element's flow (`{:writing-mode :direction}`) is threaded down
`run-cascade-walk` exactly like `parent-font-size` and `parent-display`
already were, because both properties inherit. Because the rename happens
*inside* the cascade rather than after it, `margin-inline-start: 2em` and
`margin-inline: var(--gap) 5px` need no new entries anywhere: they arrive
at `resolve-relative-lengths` and `resolve-style-map` already wearing
their physical names.

#### The percentage rule is one rule, and it is the surprising one

A percentage margin or padding resolves against the containing block's
**inline size on all four sides**. Measured:

| containing block | declaration | computed |
|---|---|---|
| 300x40 | `padding-top: 10%` | 30px |
| 300 wide, no height | `padding-bottom: 50%` | 150px (a 300x150 box) |
| 300 wide | `margin-left: 10%` | 30px |
| **200 wide, 400 tall** | `padding-top: 10%` | **20px** |
| **200 wide, 400 tall** | `margin-top: 10%` | **20px** |
| 300 wide, `padding: 50px` | `padding-top: 10%` | 30px (the *content* width) |
| 300 wide | `margin-left: -10%` | -30px |

The 200x400 rows settle it: a perfectly definite containing-block height
is available and the block-axis percentage still resolves against the
width. It is also why `padding-bottom: 50%` is the aspect-ratio idiom.

`node-style` now carries the raw value beside the coerced one — the same
thing it already did for `margin`'s `auto`, and for the same reason: the
coercion that makes every other reader safe is exactly what erases a
percentage. `resolve-box-percentages` rewrites the map once, at the sites
that know the containing block's inline size, so all ~56 call sites of
`margin-side`/`inset-side` are fixed without one of them being touched.
The sites that genuinely do not know it keep the documented `parse-int`
approximation, which is the same split `explicit-length` vs
`length-or-percentage` already draws in that file.

#### One fix did not cover the gaps, and the reason is a rule difference

The percentage machinery (`percentage-of`) was already there; what each
site needs is its own **basis**, and there are three:

- **margin/padding** → the containing block's inline size, all four sides.
- **`top`/`left`/`right`/`bottom`** → the containing block's size in the
  value's *own* axis. Measured: `left: 50%` of a 200x60 block is 100 and
  `top: 50%` is 30. These already agreed
  (`:position/absolute-percentage-offsets`,
  `:position/relative-percentage-offset`) and are untouched.
- **`row-gap`** → the container's own content *block* size, which for an
  auto-height container is cyclic. Measured in Brave, a 10% row gap on a
  40px-tall auto grid is 4px **and the container stays 40 tall** — the gap
  is resolved against a height computed without it and the content then
  overflows. That is a two-pass rule and its own round. **That round is
  thirty-eight**, and both `:gap/` percentage cases agree now; it also
  found that the inline axis is cyclic in the same way whenever the width
  is indefinite, and that a *flex* container's block axis follows a
  different rule from a grid's.

#### What is still out, with the numbers a fix will need

- **`writing-mode`.** Under `vertical-rl` the whole mapping rotates:
  `inline-size: 70px; block-size: 20px` is a box **20 wide and 70 tall**
  (this engine: 300x20), `margin-inline-start: 40px` is a **margin-top**,
  `padding-block-start: 12px` is a **padding-right**, and `padding-top:
  10%` of a 200px-tall parent is **20px** — i.e. the percentage basis is
  the inline size, which is the *height* there. Adding the four rotated
  rows to `logical-flow-sides` is two minutes' work and would make
  `getComputedStyle` right while every box stayed laid out horizontally, a
  mapping neither layout axis of this corpus could check. So the rename is
  **gated** on `horizontal-tb` instead and a logical property stays
  unmapped under a vertical mode, exactly where it was before.
- **Per-side borders.** *(Fixed in round thirty-nine; all three cases named
  here now agree.)* This is the *only* reason the remaining two cases
  of the fifteen still diverge, and it is one gap rather than two:
  `:logical/border-inline-start` cascades to `border-left-width: 5px`
  correctly and cssom.layout reads one uniform `:border-width`, so the
  physical `border-left: 5px solid #000` renders identically wrong
  (`:box/border-left-width-only` records it from that side). And
  `:box/margin-top-percentage-is-of-the-width` now resolves its 10% to
  30px and then collapses it straight out through a parent whose 1px
  `border-top` — the thing that is there to stop exactly that — this
  engine cannot see. Swap the border for `padding-top: 1px` and both sides
  put the child at y=31, which is what `layout_test` asserts.
- **An absolutely positioned box's margins**, which are not applied at
  all: measured through this engine, `position:absolute; left:0;
  margin-left: 20px` is at x=0 for a plain px margin as much as for a
  percentage. Brave says 20 — and 34 for `margin-left: 10%`, i.e. 10% of
  the containing block's 340px **padding** box, the one place the basis is
  not a content width. Resolving a percentage there would have produced a
  correct number nothing reads, so it was left out and the basis to pass
  is recorded in `percentage-box-basis`.

### Round thirty-five: stacking contexts, and the difference between painting above and confining

The single largest measured divergence in the corpus was one subject:
`210` of the `418` remaining paint-order points, across nine cases, all of
them with **every geometry box already exact**. Everything in this file
above this round paints in document order — CSS 2.1 Appendix E's step 3 —
which is right for most of a page and leaves out exactly the properties
authors reach for on purpose.

Result on the corpus, measured on `a49f29b` before and after: paint order
**13971 → 14181 / 14389** (clean cases **529 → 538 / 576**), and line
structure, geometry and computed style all **unchanged to the value**
(540/551, 1851/1959 with 510 clean, 27514/27544 with 563 clean). Nine cases
went red to green and **none went the other way**. Diffing `--dump-ops`
corpus-wide names 25 cases whose op ORDER changed and exactly one whose op
CONTENT changed (`:stacking/content-visibility-hidden-is-not-painted`,
which gains `hit=[]` on its inner box); no case's set of boxes moved,
which is what says this was a paint change and not a layout one.

#### What was measured, and where Brave departs from a spec reading

Every rule below was read out of a real headless Brave 151 over CDP before
any of it was implemented, on two probe shapes, each in its own
`overflow: hidden` wrapper and sampled with `document.elementFromPoint`:

- **lift** — does this trigger on the EARLIER of two boxes pulled onto each
  other by `margin-top: -60px` put it on top? 25 interior points.
- **confine** — does this trigger on a WRAPPER stop a `z-index: 5` box
  inside it from beating a `z-index: 2` sibling of the wrapper? 20 points.

The two questions have different answers for exactly one input, and that
one difference is the whole of the rule: **a positioned box with
`z-index: auto` lifts but does not confine.** The engine confined in both
shapes, so it was wrong on the first half of the pair and right by accident
on the second.

Creates a stacking context (both probes): `position: fixed | sticky` (with
or without offsets); `position: relative | absolute` **with an integer
`z-index`**; a flex/grid **item** with an integer `z-index`;
`opacity < 1` (`0.999999` does, `1` does not); `transform` / `rotate` /
`scale` / `translate`; `filter` (even `opacity(1)`); `backdrop-filter`;
`clip-path`; `perspective`; `transform-style: preserve-3d`;
`isolation: isolate`; `mix-blend-mode` other than `normal`;
`contain: paint | layout | strict | content`;
`content-visibility: auto | hidden`; `view-transition-name`;
`will-change` naming one of those properties.

Does not, each probed because a spec reading suggests it might:
`overflow: hidden`; `contain: size`; `contain: style`;
`will-change: z-index`; `will-change: top`; `z-index` on a `position:
static` box.

Two departures worth naming rather than arguing with:

- **`container-type` creates no stacking context in Brave.** css-contain
  gives a size container `layout` containment, and `contain: layout` DOES
  create one here — yet `container-type: inline-size` lifted nothing on
  the first probe and confined nothing on the second. Followed the
  browser.
- **`will-change: z-index` creates none either**, although a non-initial
  `z-index` plainly creates one on a positioned box, which is the rule
  css-will-change states. `will-change: position` does.

#### The mechanism, and why it is not the obvious one

A box that paints in the positioned band does not paint in its parent's op
run — it paints in its nearest ancestor stacking CONTEXT's, which may be
many levels up. So the ops cannot be reordered where they are produced;
they have to travel. They travel as a marked span in the op vector itself
(`:stack` push/pop, the same shape as the `:clip` pair already there),
carrying no `:x`/`:y` so that `translate-ops` and `transform-ops` leave
them alone, and the first ancestor that is a stacking context extracts
every span it can see, sorts by level, and splices the negatives after its
own `:node` op and the rest at the end.

Riding in the op vector rather than in a new return key is what kept this
out of `layout-flex`, `layout-grid`, `layout-table`, `layout-multicol` and
`layout-inline-run` entirely: each of them already concatenates its
children's `:draw`, so each already carries the spans correctly without
knowing they exist.

The extraction FLATTENS — a span found inside another span becomes its
sibling — and that is the rule, not a convenience: a `z-index: auto`
positioned box is not a context, so its own positioned descendants belong
to whatever context IT belongs to. Measured through two nested wrappers.

`layout-absolute-children` stopped sorting. It used to return
`{:below :above}` split by the sign of `:z`, which was this file's whole
stacking model; a local sort there cannot be right, because the containing
block is not the stacking context and two boxes anchored to different
containing blocks have to meet in a common ancestor to be compared at all.

#### The splice point, measured on one declaration

Appendix E's steps 1 and 2 put a negative-`z` child above its context's own
background and below everything else in it. In this engine the element's
own `:node` op is the proxy for its own box — it is what both real
hit-testers and this harness read — so `after the node op` is what `above
its own background` means here. The pair: a `z-index: -1` child of a
`position: relative; z-index: 0` parent is answered as the CHILD at all 20
points; drop the `z-index: 0` and the same child is answered as the
PARENT, because it has sunk past a parent that is no longer a context and
the parent's background is ordinary step-3 content painted over it. One
declaration apart, opposite answers, and the splice point is the only
thing that produces both. One unit test asserting the old, single-shape
behaviour was wrong and now asserts the measurement, with its pair beside
it.

#### `content-visibility: hidden`

The last case in the group, and not an ordering question: the element
paints its own background and its contents paint nothing and answer
nothing. Measured, Brave answers the `<section>` at all 25 points while
the inner `<article>` still reports a real 800x60 box a `Range` reads
`inner` out of — so this is not `display: none` and not a box-tree change.
Expressed on the ops the subtree already produced, in the two channels
that already exist for it: `:opacity 0` (what `visibility: hidden` uses)
and `:hit []` (`not a hit-test candidate at all`).

**Scope cut, stated with its cost:** real `content-visibility: hidden`
skips the subtree's LAYOUT too — its size comes from
`contain-intrinsic-size`, not from its contents. This engine lays the
contents out and then declines to paint them: the right picture for the
wrong reason, and the right numbers on all four axes here only because
Brave reports the real inner box for this shape anyway.

#### What this round does NOT implement

- **Appendix E's steps 3, 4 and 5 are still one band.** A block child's
  background and its text travel together, so in-flow INLINE content does
  not paint above a float the way step 5 says. That was already true (see
  round twenty-two's float comment) and is unchanged; nothing in the
  corpus discriminates it.
- **Positioned INLINE-level boxes are not hoisted.** The spans are created
  in `layout-node`, and an inline box inside an inline formatting context
  is laid out by `inline-fragments`, which does not go through it. An
  inline-block does (it is an atomic inline and gets a real `layout-node`
  call), and so does every block, flex item, grid item, table cell and
  out-of-flow box.
- **A hoisted box escapes an `overflow: hidden` ancestor's CLIP.** The
  clip is a `clip-push`/`clip-pop` pair in the parent's own op run and the
  span is spliced past it. Real CSS clips such a descendant when the
  scroll container is between it and its containing block. Nothing in the
  corpus measures a clip edge (the geometry axis reads boxes, not clips),
  so this is a paint change scored by nothing — recorded rather than
  fitted.
- **`z-index` is read as an integer only.** No `calc()`, and no
  `revert`/`unset` handling beyond what the cascade already does.

#### Two harness defects this round exposed, both inert on the old engine

Reordering the op stream broke two places where the harness read the op
vector by POSITION, and both were fixed by reading identity instead. The
proof that neither is a thumb on the scale: the whole harness change, run
against the **unmodified** engine at `a49f29b`, reproduces the baseline
scoreboard to the value on all four axes and produces a **byte-identical**
`--dump-ops` dump.

- `engine-boxes` took the first `:div` node op as the `#root` wrapper and
  subtracted its origin from every box in the case, and
  `engine-topmost-at` took the first two node ops as the two wrappers.
  A `z-index: -1` box whose nearest context is the root is now painted
  before every other box in the document, so it became the first `:div`
  op — and `:stacking/negative-z-index`, whose geometry is exact on both
  sides, came out with all four boxes shifted by −120px. Both now read
  `wrapper-op-ids`, which finds them on the document tree by identity.
- `cluster-lines` sorted a line's words by `:left` and let equal keys fall
  through to arrival order, which is DOCUMENT order on the browser side
  and PAINT order on the engine side. Six corpus cases put two words at
  exactly x=0 on the same line on purpose, and the newly-correct paint
  order read as `want ["a b"] got ["b a"]` on an axis that is not about
  paint order at all. Coincident words now sort by their own text — the
  same rule on both sides, and it can only reorder words whose positions
  are identical, which carry no order to preserve.

### Round thirty-four: the table cluster — `caption-side`, and a cell's own declared width

Four of the corpus's five table-group residuals were one cluster, and all
four are closed. Everything below was measured in the same headless Brave
151 the harness drives, on probe pages built to the harness's own page
shell, **before** anything was implemented.

**`caption-side: bottom` did nothing.** `layout-table`'s docstring said so
("a caption is laid out as an ordinary block row above the rows, never
below"), and the property is not rare — it cost 12 boxes across two cases
and 4 paint-order points. Measured: the caption is in the TABLE WRAPPER
box, which is what a `<table>` element's own box is on both sides. It
spans the table's whole BORDER-box width and sits outside its border and
padding, at whichever end `caption-side` names, and the table's HEIGHT is
the same either way — a `width:200px; border:6px; padding:9px` table with
a `Cap` caption is 200x76 in both, with the caption at y=0 or y=56 and the
rows at y=37 or y=17. So a following block does not move; what moves is
which end each part sits at. `caption-side` also INHERITS: declared on a
wrapping `<div>`, it moves the caption of a `<table>` that declares
nothing (measured), so it is carried down `inherited` like any other
inherited property rather than read off the table alone.

**A cell's declared `width` sized nothing.** The engine read it only as a
max-content DEMAND and then grew every column in proportion to its demand,
so `<table style="width:300px"><tr><td style="width:25%">a</td><td>b</td>`
came out 68 and 31 with the second cell starting at x=267, against Brave's
73.5 and 220.5 at x=2 and x=77.5. Two rules, and neither is guessable from
the other:

- **A length sizes the CELL; a percentage sizes the COLUMN.** `width:
  100px` on a `<td>` gives a 102px column — the declared 100 plus the UA's
  1px padding each side, ordinary `content-box` arithmetic, and `padding:
  8px` gives 116 and `border: 3px` gives 108. `width: 25%` gives 73.5,
  which is 25% of **294** exactly — the content width minus all three 2px
  border-spacings — and not 25% of anything plus padding. Moving the
  spacing moves the basis with it (`border-spacing: 10px` → 67.5 = 25% of
  270; `border-collapse: collapse` → 75 = 25% of the whole 300), which is
  how the basis was identified as "what is left for the columns" rather
  than the table's content width.
- **The declared width is floored at the COLUMN's min-content width, not
  the declaring cell's.** `width: 10px` on a cell holding `averylongword`
  is 93; a `width: 50px` cell in row 1 whose column holds
  `averylongcellword` in row 2 is 121 in both rows.

A declared column then HOLDS while the others absorb the surplus — the
`locked` set `distribute-excess` already had for `<col>` widths, now fed
from cells as well. Where both a `<col>` and a cell declare, the larger
wins (measured both directions: `<col>` 80 against a `<td>` 200 gives 202,
and the mirror gives 200).

And a third thing the first two exposed: **a cell FILLS its column**. Its
own declared width has already been spent on sizing the column, and
resolving it a second time against that column applied it twice — the 25%
cell reported a 21px box inside its own 73px column. Brave reports the
column (73.5), and reports 185 for a `width: 500px` cell in a 200px table.
The declaration is DROPPED rather than overwritten with the column width:
a column width is routinely fractional (50.5625 for `go <b>now</b>`) and
writing one back as a declared length goes through an integer parse that
truncated the cell to 50 and wrapped its content onto a second line. That
spelling cost 5 boxes in `:table/cell-with-inline-content` to fix 2
elsewhere, and the per-case op diff below is what caught it.

**`empty-cells` is not implemented, and is measured to be unscorable
here.** The same table with `hide` and with `show` gives identical boxes
to three decimals in Brave (128.625 / 59.375 with cell borders, 153.813 /
34.188 with backgrounds), and `elementFromPoint` answers `td` over the
empty cell either way. The property changes which pixels are FILLED, and
no axis here compares a fill. Its one-point paint-order residual is a
different thing entirely, and not a table thing: **Brave hit-tests every
element from one pixel above and left of its box.** Swept at 0.05px, a
`td` at y=4..26 answers `table` at y=3.00 and `td` from y=3.05, and stops
at y=26.00 exactly; the same 1px slop appears on a `<p>` in a padded
`<div>` and on a bare `<span>`, in x as well as y. This engine's own
half-open `[x, x+w)` test is the honest answer to the question the axis
asks, so nothing was changed for it — it is recorded beside the case.

**The fifth was not a cssom bug and was fixed where it lived.** `htmldom`
did not synthesise the `<colgroup>` a real parser inserts around a bare
`<col>`, so the corpus reported one box Brave has and this side had not,
plus 14 computed-style values it could not zip against anything. Measured
in Brave and fixed in `htmldom.core/maybe-insert-implied-table-structure`:
consecutive bare `<col>`s share ONE synthesised group, and one that
arrives after a row group gets a group of its own BESIDE it. That repo's
own tree-shape corpus went 137/137 → **139/139** with two new cases, and
its attribute axis 404/405 → **421/422** — the new case was the first with
an inline style on an otherwise bare element, and exposed that the axis
was reporting a phantom `width` attribute for every `:style/width` key,
because `name` erases the namespace that identifies one.

| axis | before | after |
|---|---|---|
| line structure | 540/553 | **542/553** |
| geometry (boxes) | 1823/1959 | **1843/1959** |
| geometry (clean cases) | 502/576 | **505/576** |
| paint order (points) | 13936/14389 | **13956/14389** |
| paint order (clean cases) | 524/576 | **527/576** |
| computed style (values) | 27483/27528 | 27483/27528 |
| computed style (clean cases) | 556/576 | 556/576 |

799 tests / 1834 assertions, 0 failures (789/1817 before, +10 for this
change); 0 lint errors and the same 25 pre-existing warnings, all in
`test/`. Downstream, against this branch: browser 754 / 0, dom-gpu 130 / 0,
htmldom 178 / 0.

Not one table entry is left in either layout residual. The htmldom fix does
not show in this table because it landed first and its pin has not moved
yet; measured on the 501-case corpus either side of it, it took geometry
1722/1766 → 1723/1766 (472 → 473 clean) and turned the 14 EXCLUDED
`element-count-mismatch` computed-style values into 14 comparable ones that
all agree.

#### `--dump-ops`, and the exchange it caught

The scoreboard cannot answer *did this change break anything*: it is four
sums over 501 cases, and a sum hides an exchange. So this round added
`--dump-ops <file>`, which writes every case's `:node` ops in EMITTED
order to a plain text file made to be `diff`ed between two commits, and
the two dumps either side of this change name **exactly three** cases of
576: `:table/caption-side-bottom`, `:table/cell-percentage-width` and
`:page/data-table-with-caption-and-foot`, all three moving onto Brave's
numbers, and **nothing else in the corpus moved at all** — no op added, no
op removed, no coordinate changed. The htmldom fix adds exactly one line to
exactly one more case (`colgroup 2 2 296 22`, which is Brave's box for it
to the pixel).

That is also how the write-back spelling of the cell-fills-its-column fix
was caught: the net geometry score went UP while
`:table/cell-with-inline-content` silently went 6/6 → 1/6.

#### Scope cuts, each with the number a fix will need

- **A `<table>`'s declared width is its BORDER box in Blink**, whatever
  `box-sizing` says, and `resolve-width` gives it the ordinary content-box
  treatment. `width:200px; border:6px solid; padding:9px` is 200 wide in
  Brave with 166 of rows inside it; this engine makes it 230 with the same
  166 of rows — every y is right, and only the outer width (and therefore
  a caption's) is 2x(border+padding) too big. Left alone because it is a
  different rule from anything this round is about, it moves every
  bordered table at once, and no corpus case has a table with both a
  declared width and a border.
- **A percentage cell width on an AUTO-width table is left to the
  max-content path.** It is circular, and Brave does something this engine
  does not model: `<table><tr><td style="width:25%">a</td><td>b</td>` is
  42px wide overall with columns 9 and 27, and 25% of anything in sight is
  none of those numbers.
- **A declared width is not capped by what the other columns need.**
  `width: 500px` in a 200px table gives 185 in Brave — the other column
  keeps its 9px min-content and the declared one takes the rest — where
  this engine leaves 502 and lets the proportional scale-down handle the
  overflow, which is what it did before.
- **A `colspan` cell contributes no declared column width**, exactly as it
  contributes no max-content one. `<td colspan="2" style="width:50%">` over
  a 300px table gives its two columns 73 and 73 (146 = 50% of 292, split
  evenly).
- **A percentage beats a length in the same column**, whichever is larger:
  `width: 20%` in row 1 against `width: 200px` in row 2 gives 58.797 = 20%
  of 294, not 202. Here the two are simply maxed.
- **`distribute-excess` hands out whole pixels**, so the column Brave
  leaves at 220.5 comes out 220 at x=78 against 77.5. Inside the geometry
  axis's 2px tolerance, and the one place these shapes are not exact.

### Round thirty-three: the corpus grows 501 → 576, and the paint axis was asking the wrong question

Seventy-five cases, in seven areas the corpus had never entered, chosen by
inventorying every case-id prefix and then asking of each candidate *can
one of the five axes actually see this*. Every number below was read out of
a real headless Brave 151.1.93.129 over CDP **before** the case was
written, on a page built with the harness's own wrapper.

| axis | 501 cases | 576 cases |
|---|---|---|
| line structure | 473/482 = **98%** | 540/553 = **98%** |
| geometry (boxes) | 1702/1766 = **96%** | 1823/1959 = **93%** |
| geometry (clean cases) | 469/501 | **502/576** |
| paint order (points) | 12421/12514 = **99%** | 13936/14389 = **97%** |
| paint order (clean cases) | 479/501 | **524/576** |
| computed style (values) | 24797/24816 = **100%** | 27483/27528 = **100%** |
| computed style (clean cases) | 492/501 | **556/576** |
| cascade-attributed residual | **11** | **30** |

The right column is *after* the two fixes below. 789 tests / 1817
assertions, 0 failures (783/1804 before, +6 tests for the `inset` fix); 0
lint errors and the same 25 pre-existing warnings, all in `test/`.

Of the 75, **21 agree with Brave on first contact** and are in the corpus
as controls rather than as findings — several of the pairs below exist
for no other reason, because a divergence next to an agreement is a
measurement of a RULE and a divergence on its own is a number.

#### The harness defect, which is worth more than any of the cases

**`engine-topmost-at` was not reading `:pointer-events` or `:visibility`,
and both of the engine's real hit-testers do.** `style-passthrough` puts
both keys on every `:node` draw-op for exactly this purpose — its own
docstring says so — and `browser.session/node-at` (session.cljc) and
dom-gpu's `retained` host each drop an op whose `:pointer-events` is
`none` or whose `:visibility` is `hidden`/`collapse` before taking the
topmost. This harness did not, so the question it was asking was one no
consumer of this engine asks, and it charged the engine for two behaviours
the engine has *right*: 40 sample points across
`:stacking/pointer-events-none-falls-through` and
`:stacking/visibility-hidden-is-not-hit`, where Brave answers the box
UNDERNEATH the transparent one and this engine's own hosts would too.

Reading the two keys is not re-deriving stacking in the harness — it is
reading two more fields of the answer the engine already emitted, exactly
like `:hit`. Measured per case over the whole corpus: **two cases changed,
both to zero disagreements, and nothing else moved at all.**

**And a second, structural one: the axis compared TAG NAMES.** Two
overlapping `<div>`s were indistinguishable to it however they were
stacked, which is most of what stacking is about on a real page — so a
case built out of two divs would have passed while measuring nothing. The
oracle now reports the author's `class` beside the tag and
`engine-topmost-at` returns `[tag class]`, because `:class (attr node
:class)` is already on every `:node` op and is the one identity both sides
can read off the same markup. Corpus-wide effect on landing: **zero** —
no existing case changed by a single point — and
`:stacking/same-tag-opacity-lifts-the-earlier-box` (Brave `div.lower`,
this engine `div.upper`) is the case that could not have existed before
it, with `:stacking/same-tag-later-sibling-covers-earlier` as its control.

#### The one engine fix: the `inset` shorthand

`inset: 10px 20px` was stored verbatim under an `:inset` key nothing
reads, so an absolutely positioned box declaring it fell back to its
static position and shrink-to-fit width. Measured in Brave: **x=20 y=10
w=260 h=40** in a 300x60 relative parent, against **0,0,7x20** here.
Expanded now by the same 1-to-4 rule `margin`/`padding` use, into the
four BARE side names `layout-absolute-children` already reads — which is
the only reason it needed a function of its own rather than
`expand-box-side-shorthand`. `auto` is admitted (it is the property's own
initial value); a percentage is declined, exactly as margin/padding
decline one. Per-case box diff over all 576 cases: **one case changed,
0/2 boxes → 2/2, and no paint-order point moved.**

#### The new divergences, ranked by size

**Logical properties — 12 cases, every one diverging, one cause.**
`margin-inline-*`, `padding-inline-*`, `padding-block-*`, `inline-size`,
`block-size`, `border-inline-*` and `inset-inline-*` match NOTHING in
`src/` (a repo-wide grep for each is zero in both namespaces). The two
that matter most are the ones that FLIP: `margin-inline: 20px 60px` is
x=20 w=220 in an ltr block and **x=60 w=220** in an rtl one, and
`padding-inline-start: 50px` under rtl puts the padding on the right
(outer box 350 wide, inner `<p>` still at x=0). Those two are the only
cases in the corpus that can tell a logical property from an alias for a
physical one.

**Replaced elements with no box — 8 cases.** `inline-atomic-tags` is
`#{:img :input :button :select :textarea}` and its docstring names
`svg`/`canvas`/`video`/`audio`/`iframe` as a deliberate cut, on the
grounds that a box for them "would place an empty rectangle in the middle
of a sentence rather than fix anything". Measured, the cost is not an
empty rectangle: Brave reserves **300x150** for a bare `<canvas>`,
`<video>` and `<svg>`, and **304x154** for an `<iframe>` (the 300x150
default plus Chrome's UA `border: 2px inset`), where this engine lays each
one out as a BLOCK that fills its container and is 0px tall. So a page
with a `<canvas>` in it is 150px shorter here than anywhere else, and
`:replaced/canvas-in-a-sentence` shows the line-axis half: Brave keeps
`before <canvas> after` on one line with the canvas an atomic inline at
x=49 y=4 w=20 h=10, and this engine puts the text on two lines around a
400px block. The `<img>` half is an intrinsic **ratio**: a 40x20 SVG data
URI at `width: 200px` is **200x100** in Brave and 200x**0** here, and its
mirror at `height: 60px` is **120x60** against 0x60. Its control agrees —
`width`/`height` ATTRIBUTES are presentational hints, so a CSS `width`
replaces the width hint and the height hint stands alone: **200x20** on
both sides, which is what says the gap is the resource's ratio and not the
attributes.

**Stacking contexts — 10 diverging cases out of 18, and every geometry box
in all eighteen agrees exactly.** That is the paint-order axis's entire
reason to exist. Four separate triggers put a box above a later in-flow
sibling that overlaps it, and all four are missed:
`opacity: 0.99`, `transform: translateY(0px)`, `filter: blur(0px)` and
plain `position: relative` — Brave answers the EARLIER box at all 25
points in each, this engine the later one. Round twenty-seven already
named the transform half ("a transformed element also establishes a
stacking context in real CSS and this engine does not model that"); this
is that sentence with a number, plus three more triggers it did not name.
The other half is confinement, and it is a discriminating pair:
`position: relative` with `z-index: auto` is NOT a stacking context so a
`z-index: 5` descendant escapes it (Brave `section`, engine `article`),
while the same markup with `z-index: 0` confines it (Brave `article`, and
this engine **agrees**) — because this engine confines a descendant's
z-index in *both* shapes, which is what makes it right by accident in one
and wrong in the other. `isolation: isolate` is the same accident.
`z-index` on a **flex item** is missed too (it applies without
positioning), and so is the Appendix E step-1/step-2 order: a `z-index:
-1` child stays ABOVE its own stacking context's background (Brave
`article`) and sinks past a parent that is not one (Brave `section`) —
this engine sinks it in both.

**Percentage margins and padding in the block axis — 4 cases.** CSS 2.1
§8.3/§8.4 resolves a percentage margin or padding against the containing
block's INLINE size on all four sides. Measured: `padding-top: 10%` of a
300px container is **30px** (inner box 50 tall), `padding-bottom: 50%`
alone makes a **300x150** box with no height anywhere, `margin-top: 10%`
puts the child at **y=31**. This engine reads the number and drops the
unit — 10px, 50px, 10px — which is the same defect round thirty-two
recorded for percentage GAPS ("`node-style` runs `parse-int` on the
string, and it has no available size to resolve a percentage against").
The inline-axis control fails identically (`margin-left: 10%` is x=30
against x=10), so it is not a block-axis problem: the unit is dropped on
every side, and a fix belongs where round thirty-two said it did.

**`vertical-align` on an atomic inline — 6 of 7 cases.** The machinery
exists: `vertical-align-shift` knows `super`/`sub`, `line-edge-aligned`
knows `top`/`bottom`, and `middle` is resolved in `inline-fragments`. But
only `middle` reaches an inline-BLOCK — and it reaches it exactly, both
sides reporting **y=31.828125**, which is what makes the other six a
finding rather than "the property does nothing here". Against a 40px
inline-block setting a 46px line box, Brave puts a 10px one at y=**0**
(`top`), **36** (`bottom`), **28** (`text-top`), **33** (`text-bottom`),
**18** (`12px`) and **20** (`50%`); this engine leaves it on the baseline
at 30 in all six.

**Per-side border shorthands — 2 cases.** *(Fixed in round thirty-nine,
which measured twenty-seven declarations rather than these two and found
the two rules that constrain any fix: an omitted width is `medium` = 3px,
an omitted style is `none`.)* Round twenty-six named
"per-side border widths" as not implemented, on the grounds that this
engine has one uniform `:border-width`. Measured, it is sharper than that:
a per-side SHORTHAND is not read *at all*. `border-top: 10px solid` gives
Brave a 30-tall box with its `<p>` at y=10 and the full w=300 (a top
border costs height and nothing else) and gives this engine 20 tall with
the `<p>` at y=0 — not ten pixels on four sides, zero on all of them. Its
control agrees and constrains the fix: `border-width: 10px;
border-style: none` computes to a border width of ZERO on both sides, so
a fix must not simply start adding declared widths up.

**`visibility: collapse` on a table row — 1 case, with two controls.**
Brave gives the collapsed `<tr>` and its `<td>` **0px** of height, moves
the third row up to y=22 and makes the table **44** tall rather than 66.
This engine renders it as `hidden` — which the two controls say is right
everywhere else: on a plain block and on a flex item, `collapse` is
exactly `hidden` and both sides agree.

**Form controls with a UA box of their own — 5 cases.** `<progress>` is
**140x14** and `<meter>` **70x14** in Brave, and neither tag exists in
`src/` at all (both come out as 400x0 blocks). Three `<input>` types all
come out of this engine's text-field rule at 153x21 where Brave says
**129x16 at x=2 y=2** (`range`, which carries `margin: 2px` and no
padding — those four padding values are the only cascade-attributed
computed-style residual these cases add), **50x27** (`color`) and
**253x27** (`file`, which is the button plus its label text, i.e. a
different KIND of number that a per-type constant table would not
produce).

**Generated content where the oracle can see it — 2 of 4.** A
`display: block` ::before is a block box, so Brave's `<p>` is **40** tall
with `tail` at y=22 and this engine flows the generated text into the
paragraph's own line and reports 20. `list-style-position: inside` — the
value round twenty-nine implemented the default of, measured alongside,
and never gave a case — puts the `<a>` at **x=59** against this engine's
53.70625; that 5.29 is exactly the number that round recorded in
`list-style-inside?` rather than modelling (Brave's disc advance is a
function of the font size, 19px at 14px, not the 13.70625 the `"• "`
string measures). Both controls agree: an `::after` string widens the
`<b>`'s box to 37.03 on both sides, and `counter-reset: k 7` starts the
counter at 7 on both.

**Three singles.** `display: inline-table` is an inline 28x20 box at x=49
in Brave and three stacked 400px blocks here. `writing-mode: vertical-rl`
matches nothing in `src/`: Brave lays the text down the page in a
**20x70** box and this engine gives it a horizontal 300x20 — a deep gap,
recorded rather than chased, because a vertical writing mode is a second
axis convention through every function in `layout.cljc` and not a property
to read. And `border-radius: 50%` shrinks a box's HIT region without
changing the box: Brave answers the wrapper at the four corner sample
points of an 800x200 rounded box and the box itself at the other 21 — the
third measured case of a reported box and a hit region being different
rectangles, and the first where the region is not a union of rectangles at
all.

#### Two things measured and deliberately NOT added

**`shape-outside`.** `circle(30px)` on a 60px left float in a 200px box
moves the first line's text from x=60 to **x=58.281** and leaves the
second line identical — a 1.7px difference, inside the geometry axis's 2px
tolerance, on a coordinate (a word's x) that no axis compares, and with
the same words on the same lines either way. There is nothing here for the
five axes to disagree about at this size, and a shape large enough to move
a wrap point would be measuring the float band rather than the shape.

**`overflow: clip`.** Its boxes and its hit region are identical to
`overflow: hidden`'s in Brave (inner box reports its full 700x60, hit only
inside the 200px clip), and the corpus already has the `hidden` case. What
differs — that `clip` does not create a scroll container — is not
observable on any axis here.

### Round thirty-two: the corpus grows 370 → 431, into layout it had never entered

All four axes were at or rounding to **100%** on the 370-case corpus —
line structure 356/356, geometry 1335/1335 boxes across 370/370 cases,
paint order 9227/9234, computed style 18687/18763. **A corpus that scores
100% can no longer find defects.** Growing it is the only thing left that
teaches anything, and the numbers are *expected* to fall: a fall that
comes from coverage is a better measurement, not a regression.

61 cases, every one of them measured in Brave 151 over CDP *before* it was
added to the corpus. The territory was chosen by inventorying the case-id
prefixes and then targeting what had no case at all.

| axis | 370 cases | 431 cases |
|---|---|---|
| line structure | 356/356 = **100%** | 397/414 = **96%** |
| geometry (boxes) | 1335/1335 = **100%** | 1507/1584 = **95%** |
| geometry (clean cases) | 370/370 | 400/431 |
| paint order (points) | 9227/9234 | 10703/10764 |
| paint order (clean cases) | 364/370 | 414/431 |
| computed style (values) | 18687/18763 | 22183/22273 |
| computed style (clean cases) | 332/370 | 389/431 |
| computed style (clean of a CASCADE mismatch) | 369/370 | 429/431 |

The right column is *after* the four fixes below; without them it would be
lower still. 736 unit tests / 1702 assertions, 0 failures either side; 0
lint errors, the same 25 pre-existing warnings, all in `test/`.

#### What the new cases cover

**multi-column, 12 cases.** `column-count` appears nowhere in `src/`, and
the only `column-gap` there is the grid/flex longhand — so these measure
the size of the gap rather than assert one exists. `column-count`,
`column-width` deriving the count, `column-gap: normal` (1em on a multicol
box, unlike the 0 it means on a grid), `column-rule` taking no space,
`break-inside: avoid` against a control that lets the block split,
`column-span: all`, `column-fill: auto`, a definite height overflowing
sideways, padding outside the columns, and text flowing at the *column's*
inline size.

**`position: sticky`, 4 cases.** The corpus had one, and it covered the
unscrolled default — which `layout.cljc` is explicitly, correctly scoped
out of. But a sticky box **is stuck with no scrolling at all** when it is
anchored to the far edge of a scrollport it starts below, and that is what
these use. No `:oracle/isolated` needed: the harness scrolls the *window*,
and these anchor inside an inner scroll container, so the measurement does
not depend on where the case sits on the page.

**interactive elements, 9 cases.** `<details>` closed, open, and with no
`<summary>`; `<dialog>` with and without `open`; `<template>`; the
`hidden` attribute and an author `display` beating it.

**tables, 8 cases.** Nested tables, `caption-side: bottom`, `<colgroup
span>`, `table-layout: fixed` with overflowing content, `empty-cells`,
`<tfoot>` written before `<tbody>`, a bare `<col>`, a percentage cell
width.

**intrinsic sizes and clamps, 10 cases.** `min-width`/`max-width` on flex
and grid items, `min-content`/`max-content`/`fit-content` as `width`
values, the automatic minimum size of a flex item and what `overflow:
hidden` does to it.

**`gap`, 5 cases**, across the three box types that take one: percentage
gaps on both axes, `row-gap` between flex lines, `gap` on a multicol box,
the two-value shorthand.

**scroll containers, 7 cases**, and **5 real-page composites** (labelled
`:composite`): a sidebar, a sticky header over scrolling content, a card
grid, a two-column article, a data table with a caption and a foot.

#### Four fixes the new cases found

**1. A flex container read the single `:gap` for both axes.** `row-gap`,
`column-gap`, and the second half of `gap: <row> <column>` all did nothing
on a flex box, while a grid two lines away in the same `node-style` map
honoured all three. Measured: `flex-wrap: wrap; row-gap: 12px;
column-gap: 8px` over two 120px items in a 200px box is **52px** tall with
the second line at **y=32** in Brave; this engine had 40 and y=20. And
`gap: 6px 18px` on a flex row put the second item at **x=106** where Brave
says 118 — the shorthand's row half used for the column axis, because
`parse-int "6px 18px"` is 6. `layout-flex` now takes its main-axis gap
from `column-gap`/`row-gap` by direction, and `layout-flex-wrap-row` takes
its cross-axis gap from `row-gap`.

**2. `distribute-excess` grew a column a `<col>` had DECLARED.** A table's
surplus width is handed to its columns in proportion to their demand,
which is right for automatic columns and wrong for declared ones.
Measured: `<table style="width:300px"><col style="width:200px"><col>
<tr><td>a</td><td>b</td></tr></table>` is **200 + 94** in Brave; this
engine had **281 + 13**. Declared columns are now locked and the automatic
ones absorb the surplus. When *every* column is declared the proportional
hand-out still applies — `table-fixed-column-widths` relies on exactly
that, and its own case is unchanged.

**3. Row groups were laid out in SOURCE order.** `<tfoot>` before
`<tbody>` is idiomatic HTML — it exists so a UA can paint the footer
before it has streamed the body — and it renders **last**. Measured, Brave
puts `tfoot` at y=26 and `tbody` at y=2; this engine had them the other
way round. `table-rows` now partitions header/body/footer, stably, so
order *within* a group is still document order.

**4. Two UA rules the sheet was missing.** `template { display: none }`
and `dialog:not([open]) { display: none }`. A closed `<dialog>` rendered
its own text straight into the page — the text of a dialog nobody has
opened, which is as visible a bug as this corpus has found in a while.

#### The new divergences, grouped by cause

**No multi-column implementation at all** — 11 cases, ~90 box mismatches,
and the single largest cluster in the corpus. Columns are laid out as one
stacked block column: `column-count: 2` over four 30px blocks is
(0,0) (0,30) (160,0) (160,30) in Brave and (0,0) (0,30) (0,60) (0,90)
here, and text wraps at the container's 300px rather than the column's
140px. `column-span: all` is the one case that passes the line axis, by
coincidence — the spanner is full-width either way.

**No scroll-position-dependent sticky offset** — 2 cases. A `bottom: 0`
sticky box whose flow position is below its scrollport is pulled **up** to
sit on it (y=100 → **40**), and clamped by its containing block when that
is what stops it (100 → **80**, not the 40 the inset asks for). The two
unscrolled cases still agree, so the same round both confirms the existing
scope-cut is correct *and* bounds it.

**`width: min-content | max-content | fit-content` is treated as `auto`** —
3 cases. `min-content` over "alpha beta" is **35px** in Brave and 300
here; `max-content` and `fit-content` are **70** and 300. The intrinsic
measurement itself already exists in `layout.cljc` — tables and flex items
both use it — it is simply not wired to the `width` property. This is the
cheapest-looking of the remaining gaps.

**Flex min/max clamping does not redistribute** — 2 cases. `min-width:
150px` on one of two `flex: 1` items in a 200px row leaves the other at
its unclamped **100** instead of the **50** that is left, and `max-width:
60px` in a 300px row leaves it at 150 instead of 240. The clamp is
applied; the freeze-and-re-run loop that gives the freed space to the
other items is not there.

**Percentage gaps are read as pixels** — 2 cases. `column-gap: 10%` of a
300px grid is **30** in Brave and 10 here. The block axis is the cyclic
one: Brave resolves a 10% row gap against the grid's *own* 40px content
height and gets **4**. Both are the same defect — `node-style` runs
`parse-int` on the string, and it has no available size to resolve a
percentage against, which is where a fix belongs.

**Inline-blocks wrap inside a `white-space: nowrap` scroll container** —
2 cases, and this one was *re-attributed* by a control. The sticky
horizontal-scroller case looked like a sticky failure; the identical
markup without the sticky wraps the second inline-block onto a second line
too (container 40px tall, not 20), so the wrap is the cause and the sticky
pull (x=300 → 160 in Brave) is a second, smaller one on top of it.

**`caption-side: bottom`** — 2 cases. Already a documented scope-cut in
`layout-table`'s docstring; now it has a number: the caption is 26px down
in Brave and at 0 here, and everything below it shifts by its height.

**The `<dialog open>` UA box** — 1 case. `position: absolute; margin:
auto; width: fit-content; height: fit-content; border: solid; padding:
1em` gives **48x54 at x=126**; this engine lays out an ordinary 300x20
block. Left alone deliberately: it cannot be right until `fit-content`
(above) is, and adding the padding alone would move the numbers without
converging on them.

**A `<details>` with no `<summary>`** — 1 case. *(Fixed in round
thirty-nine: the band is reserved, the label is not drawn, and the case is
paint-clean. Its geometry still cannot be — see there.)* Brave synthesises one and
the element is 20px tall; this engine renders it as empty.
`with-details-visibility`'s docstring already says a summary-less
`<details>` is out of scope, so this is that scope-cut, measured.

**Not a `cssom` finding, recorded where it was seen:** `htmldom` does not
synthesise the implicit `<colgroup>` a real HTML parser inserts around a
bare `<col>`, so Brave reports one box this side has not got. The declared
width now resolves correctly either way (fix 2); only the box count
differs.

#### Two cases are `:oracle/blind`, for the reason the corpus already has

`:interactive/details-closed-shows-only-the-summary`. Chromium hides a
closed `<details>`'s content with `content-visibility: hidden`, **not**
`display: none`: measured, the `<p>` reports a real 300x20 box at y=34 and
a `Range` reads "Body" out of it — and it is never painted. An engine that
emits draw-ops cannot report a box it does not paint. This is the
`text-overflow: ellipsis` situation exactly: comparing the two on text
compares a DOM to a rendering. Geometry and paint order still score.

`:page/sidebar-with-a-nav-list`, for list markers, exactly like
`:page/nested-lists-in-nav`.

#### One thing the harness cannot see, so no case was added

`object-fit` / `object-position` change what is painted **inside** a
replaced element's box. They change neither the box, nor hit testing, nor
any of the 14 properties the computed-style axis compares — there is
nothing here for either side to disagree about, at any value. A case that
can never be scored does not belong in the corpus, and saying so is more
useful than a case that passes for a reason unrelated to the feature.

#### One case was written expecting a divergence and found none

`:overflow/auto-reserves-no-gutter-in-this-oracle` (and the two beside
it). A classic scrollbar takes its width out of a scroll container's
*content* box, and this engine reserves nothing — so this looked like a
guaranteed 15px divergence. Brave 151 headless on macOS uses **overlay
scrollbars** and reserves nothing either. The three cases stay in, named
for what they actually measure: on a classic-scrollbar oracle they would
all diverge by the gutter width, and this corpus should notice when the
oracle changes underneath it.

### Round thirty-one: an element's box and its hit region are two different things

The paint-order axis was at **9202/9234, 356/370 clean**, and its whole
residual sat on one question the axis had never asked out loud: a `:node`
draw-op's `:x`/`:y`/`:w`/`:h` had to be both the box a browser *reports*
and the region a browser *clicks*, and those are not the same rectangle.
Three measurements say so, all taken in Brave 151 over CDP before anything
was changed.

**A wrapped inline box is hit only inside its fragments.** `<p style=
"width:200px">alpha beta gamma <b>delta epsilon</b> zeta eta</p>` gives the
`<b>` client rects `[119,1,33.7,18]` and `[0,22,46.8,18]`, a bounding rect
of `[0,1,152.7,39]`, and answers `elementFromPoint(80, 4)` — inside that
union, inside neither fragment — with **`p`**. `inline-owner-ops` emitted
the union and documented it as "an honest, documented approximation of real
CSS's per-fragment box list"; the geometry axis wanted exactly that union
(`getBoundingClientRect` *is* the union) and the paint-order axis was
charging all five of `:wrap/inline-element-straddles-break`'s sample points
to it, plus two of `:wrap/link-wraps-across-two-lines`' and one of
`:page/login-form`'s.

**Overflowing inline content is hit outside the box, per line.**
`<p style="width:80px">short aaaaaaaaaaaaaaaaaaaa tail</p>` reports an
80×60 box and is hit out to **x=140 on its middle line** — the long word,
which does not fit — and stops at x=80 on the two lines that do. So it is
not `scrollWidth` and it is not a rectangle around the element: it is the
lines themselves. Eleven points (`:text/nowrap-in-narrow-box`,
`:text/white-space-pre-in-a-narrow-box`, `:wrap/single-word-longer-than-
line`) were the engine reporting **nothing** where the browser reports the
paragraph.

**A table row and row group are never hit at all.** Not "they have no
background": measured with `background` set on the `<tbody>` *and* on both
`<tr>`s and `border-spacing: 6px` opening real gaps between the rows,
`elementsFromPoint` over every point of that table returns `td, table`
inside a cell and `table` alone everywhere else. Neither `tr` nor `tbody`
appears at any point. A row's painted background *is* hit — as the table.

**The fix is a second key, not a wider box.** A `:node` op now carries an
optional `:hit`: a vector of rects that replaces `:x`/`:y`/`:w`/`:h` for
hit testing, `[]` meaning "not a hit-test candidate". Absent — the
overwhelmingly common case — means the border box, so nothing that reads
`:node` ops today changes shape. Widening the box instead would have made
every `getBoundingClientRect` comparison wrong to fix the hit test, and
this corpus scores both: **geometry did not move at all** (1335/1335, 370
clean, byte-identical residual).

A fourth cause was ordinary paint order rather than a hit region.
**A float was painted under its own siblings.** CSS 2.1 Appendix E paints
in-flow block-level boxes (step 3) *before* non-positioned floats (step 4),
and this engine emitted a float's ops at the point in the child list where
it was written — so a following `<p>`'s background covered it whole, which
is every ordinary use of a float, because a float narrows a sibling's line
boxes and not its border box. Measured with real backgrounds on both: the
float's colour is what is visible over its own width and what
`elementFromPoint` answers there. `layout-children-block` now accumulates
float draws in their own band and concatenates them after the in-flow ones.
Appendix E puts in-flow *inline* content (step 5) above floats again, which
this still does not model — the whole of a block child's op run goes in one
band — and that is inert here because `float-band` is what narrows the line
boxes in the first place, so in-flow text does not overlap a float it can
see. Five points, all of `:float/float-right-block-with-width`.

**Result**, same corpus, same commit either side:

| axis | before | after |
|---|---|---|
| line structure | 356/356 | 356/356 |
| geometry (boxes) | 1335/1335 | 1335/1335 |
| geometry (clean cases) | 370/370 | 370/370 |
| paint order | 9202/9234 | **9227/9234** |
| paint order (clean cases) | 356/370 | **364/370** |
| computed style | 18687/18763 | 18687/18763 |

`--debug-paint` was added alongside `--debug-geometry`/`--debug-style`, and
prints for every disagreeing case the engine's `:node` ops **in emitted
order** with each sampled point. Without the order a paint-order residual
is unreadable, because the boxes it is made of usually all agree — which is
the axis's entire point.

#### The seven that are left, and why they are not converged

All seven are boundary points where the two sides are within about one
pixel of each other, from two causes, and **neither is a paint-order
error**. They are listed here rather than fixed because fixing either one
would mean breaking something that is currently right.

Four are **this engine flooring a fractional layout position**, inside the
geometry axis's own 2px tolerance and therefore invisible to it:
`:page/article-paragraphs` puts its first `<p>` at y=38 where Brave says
38.75 (an `<h1>`'s `0.67em` bottom margin on a 28px font is 18.76px), and
the sample point is at y=80.3 — inside the browser's box, one third of a
pixel outside the engine's. `:page/table-of-contents` (40 vs 40.609) and
`:page/login-form` (40 vs 40.422) are the same shape;
`:form/textarea-with-rows` is the mirror, an engine box 0.86px *taller*
than the browser's, from the fractional font metrics the harness's own
`:font-metrics` hook already documents. Rounding these is a layout change
that moves every UA margin in the corpus, which is the geometry axis's
subject and not this one's.

Three are **the oracle's own leading-edge slop**, and this one is worth
writing down because it is not in any spec. Scanned at 1/64px, Brave's
`elementFromPoint` answers a box's **top** edge exactly one CSS pixel
early and its **bottom** edge exactly: two stacked 30px divs switch at
**29.0156**, two stacked 30.5px divs at **29.5156**, and a 40px inline
whose box is `y=9..51` is hit from **8.0156** to **51.0000**. It is a
constant one pixel — not font-relative, not box-type-relative, not
affected by fractional position — and the left/right edges have no slop at
all. `:inline/em-strong-code` (point 0.9px above the `<code>`),
`:form/input-inside-a-table-cell` (0.3px above the `<input>`) and
`:page/login-form` are inside it. Modelling it would mean shifting every
element's hit region one pixel up, so `browser.session/node-at` would
deliver every real click one pixel above the box it belongs to — a
regression in the actual product to win three points against one browser's
implementation detail. It stays measured and unmodelled.

`:page/login-form`'s single point changed *kind* rather than count: it was
`form -> label`, the union box over-claiming a 36px-tall rectangle, and is
now `label -> form`, a 0.42px rounding at a fragment's bottom edge.

### Round thirty-two: the corpus grows 370 → 441, into text, typography and selectors

**Every number on this page fell, and that is the point.** All four axes
were at 100% of what the 370-case corpus could ask — line 356/356, geometry
1335/1335 boxes across 370/370 clean cases, paint order 9227/9234, computed
style 18687/18763 — and **a corpus that scores 100% can no longer find
defects**. Seventy-one cases were added in two areas the corpus had barely
entered: text and typography (28 of them), and selectors, specificity and
the cascade (43). The drop below is added coverage, not a regression:
`src/` was **not touched** by this round, and 736 tests / 1702 assertions and
the linter are green and unchanged either side (0 failures, 0 errors; 0 lint
errors, 25 pre-existing warnings, all in `test/`). Both columns were measured
on the SAME commit, after merging the hit-region round that landed alongside
this one, so nothing in the table is another round's doing.

| axis | 370 cases | 441 cases |
|---|---|---|
| line structure | 356/356 = **100%** | 411/425 = **97%** |
| geometry (boxes) | 1335/1335 = **100%** | 1484/1521 = **98%** |
| geometry (clean cases) | 370/370 | **416/441** |
| paint order | 9227/9234 | **10952/11014** |
| paint order (clean cases) | 364/370 | **422/441** |
| computed style (values) | 18687/18763 | **21278/21362** |
| computed style (cases with no cascade-attributed mismatch) | 369/370 | **434/441** |
| cascade-attributed residual | **1** | **9** |

Every case was measured in a real headless Brave 151 over CDP *before* it
was added, and the first draft had to be thrown away for a reason worth
recording: **five of the text cases passed while measuring nothing.** A
`letter-spacing: 4px` on `alpha beta` inside a 120px box is 110px against a
bare 70px, and *both* fit — so the case agreed with the browser about a
property neither side had applied. Every width in the text group below is
now a number at which the two answers must differ (100px for that one), and
they were found by driving the shapes through the browser and reading the
line boxes back, not by arithmetic.

#### What the text group found — nine gaps, five causes

- **`letter-spacing` and `word-spacing` never reach a text run's advance.**
  Both are already in `cssom.layout`'s inherited set, so they arrive and are
  then unused. Measured four ways: a wrap point (`alpha beta` at 100px is
  two lines in Brave, one here), its mirror (a *negative* letter-spacing
  makes 70px of text fit 60px — Brave one line, this engine two), an inline
  box's own width (`<b letter-spacing:3px>wide</b>` is **42.69** against
  **30.68**; `<b word-spacing:10px>one two</b>` is **64.14** against
  **54.14**), and a shrink-to-fit box (**44** against **28**). Six cases.

- **`text-indent` is not implemented at all** — the property does not appear
  in `cssom.layout`. Four cases, and the shapes are chosen so the indent
  changes what wraps rather than only where the first line starts, because
  neither layout axis compares a text run's x. `160px`/`40px` is two lines
  in Brave and one here; `text-indent: 50%` resolves against the *containing
  block*; the property **inherits**, so a 60px indent declared on a wrapper
  reaches the `<p>` inside it; and `hanging` inverts it — the same text is
  **three** lines in Brave and two here. `each-line` re-applies after a
  forced break, which the geometry axis reads directly as the `<br>` at
  **x=65** against **x=35**.

- **A tab is not one space, and `tab-size` is not read.** In a shrink-to-fit
  `white-space: pre` box, `a<tab>b` is **63px** in Brave — nine columns, the
  next multiple of the initial `tab-size: 8` — and **35px** at `tab-size: 4`.
  This engine reports **21px** for both, i.e. three characters. The pair is
  deliberate: one case alone cannot separate *the tab stop is wrong* from
  *`tab-size` is ignored*. `white-space: pre` also drops leading spaces from
  the measured width (**77** against **63**).

- **Three break-opportunity mechanisms are missing, and one is applied too
  eagerly.** A soft hyphen (U+00AD) is a break point under the initial
  `hyphens: manual` — Brave breaks the word and the box is 40px tall against
  20 here. `hyphens: auto` with `lang="en"` breaks `hyphenation` and gives 60
  against 40. `text-wrap: balance` gives `alpha beta gamma` / `delta epsilon`
  where a greedy breaker gives `alpha beta gamma delta` / `epsilon`.
  `white-space: break-spaces` is one of the four *preserving* values, so its
  newline survives — two lines in Brave, one here. And in the other
  direction, `white-space: nowrap` on an **inline child** makes this engine
  break either side of it: `alpha` / `beta gamma` / `delta` against Brave's
  `alpha beta gamma` / `delta`.

- **The three break keywords are treated as one, and one of them differs.**
  `cssom.layout`'s `break?` is `#{"break-word" "anywhere" "break-all"}`, but
  they part company exactly where a box is being **sized**: `anywhere` and
  `break-all` let a long word break while its min-content width is computed,
  so an inline-block takes the 60px on offer; `break-word` does **not**, so
  the same box is **105px** and overflows. Brave: `60×20` with a `105×20`
  span. This engine: `60×40` and `60×40`. The three cases are in the corpus
  together because two of them agreeing is what makes the third one a
  finding rather than a guess.

- **`font-size`'s absolute keywords cost more than the font size.**
  `resolve-font-size` returns nil for `large`/`x-large`/... on purpose (the
  table is keyed on the default font of the *family*, which the cascade
  cannot know — `large` is 16px in this page's monospace and 18 in a
  proportional one). Measured, that unresolved value propagates: the UA
  `p { margin: 1em 0 }` then resolves against 14px instead of 16, so the
  margins are wrong too. Two of the nine cascade-attributed values. Its
  contrast partner `font-size: larger` is a pure ratio off the parent, needs
  no family table, and agrees exactly.

- **`<q>` gets no quotation marks.** The oracle's per-word Ranges cannot see
  generated content, so the *line* axis is blind here — but the `<q>`'s own
  box is two characters wider each side and the geometry axis reads it
  directly: **63** against **35**, and a nested `<q>` **91/35** at x **14/42**
  against **35/7** at x **14/28**.

#### And one margin rule, found sideways

`:selector/empty-pseudo-class` was written to check that `p:empty` matches.
It does — and the case failed anyway, on geometry and on 15 paint-order
points. An empty block with no border or padding is **self-collapsing**: its
own top and bottom margins collapse into one, that one then collapses with
the next sibling's top margin, and with nothing to stop the set at the
parent's top edge the whole of it escapes. Brave puts both children at
**y=0** and the parent is **20px** tall; this engine leaves 14px inside and
reports **34**. `:block/an-empty-block-collapses-through-itself` isolates it
away from the selector.

#### The selector and cascade axis: 43 cases, 5 divergences

This is the axis with the most to lose from a corpus that cannot see it —
the computed-style residual was **1 value** across 370 cases, and there were
six selector cases in the whole corpus. Forty-three more went in:
`:nth-child()` with a negative coefficient / `An+B` / `odd`/`even` / `of
<selector>`, `:nth-of-type`, `:nth-last-child`, `:first-`/`:last-`/`:only-
child`, `:first-of-type`, `:empty`, `:not()` with a selector list and with a
nested pseudo-class, `:has()` in its descendant, direct-child and sibling
forms, `+` and `~`, all six attribute operators plus the case-insensitive
`i` flag, four specificity shapes, three importance-versus-inline-style
shapes, and eight `var()`/shorthand/CSS-wide-keyword shapes.

**Thirty-eight of the forty-three agree with Brave exactly**, which is a
measurement and not a formality: it is the first evidence that the selector
engine's An+B matching, its `:is()`-versus-`:where()` specificity split, its
`:not()` argument specificity, its six attribute operators and its
inline-versus-`!important` ordering are right, rather than merely present.
Two of them also correct this file's own prose: `:is(.wrap section) p` and
`p:not(:first-child)` are both named as out of scope in `cssom.core`'s
docstring and both **work** (a control, `:is(.nomatch xyz) p`, correctly
matches nothing) — the docstring is stale, not the engine incomplete.

The five that diverge:

| case | Brave | this engine |
|---|---|---|
| `:selector/nth-child-of-a-selector` | `2n+1 of .m` counts among the `.m` siblings only, so the first `.m` is bold | the `of` clause is not parsed; nothing matches |
| `:selector/has-a-following-sibling` | `h2:has(~ p)` matches | the sibling-relative form is named as out of scope, and is |
| `:cascade/inherit-on-a-non-inherited-property` | `padding-left: inherit` takes the parent's 40px | `inherit-keyword?` *removes* the declaration, which is right for an inherited property and gives 0 here |
| `:cascade/initial-keyword-resets-to-the-css-initial-value` | `text-align: initial` is `start` | the literal string `initial` is stored |
| `:cascade/revert-drops-to-the-user-agent-value` | `margin: revert` rolls the author origin back, so the UA `1em 0` returns | the literal string `revert` is stored and the author `margin: 0` stands |

The last three are `cssom.core`'s own documented cut — `initial`/`unset`/
`revert` are "deliberately NOT handled" — and the point of writing them into
the corpus is that a documented cut and a measured one are different things.
`revert` in particular needed an author rule to measure at all: with no
author declaration to roll back, *ignoring* `revert` and *obeying* it both
leave the UA margin standing, and the first draft of that case passed for
exactly that reason.

Two more are visible but not scorable, and the harness says so rather than
scoring them: `color: var(--missing)` after a `color: #0000ff` leaves this
engine's cascade holding the **empty string** (real CSS makes the whole
declaration invalid at computed-value time and the property inherits), and
`color: unset` is stored as the literal `unset`. They land in the excluded
buckets as `absent` and `unparseable-color`, printed with their case ids.

#### Not added, and why

- **`text-decoration` and its `-thickness`/`-offset`/`-line` longhands.**
  No axis reads them: decoration does not change a box, a line, or a hit
  region, and the computed-style axis compares fourteen properties none of
  which is a decoration. A case would be scored on everything except the
  thing it was written for.
- **`::first-line` and `::first-letter`.** Neither produces an element box,
  so neither the geometry axis (which walks elements) nor the oracle's
  element probe can see one.
- **`font-variant: small-caps`.** It *is* scorable — Brave renders
  `caps here` at 47px against a plain 63 — but the number comes from a
  synthesized small-caps face whose advances the harness's per-character
  probe does not measure, so the expected value would not reproduce on a
  machine with a different `monospace`. Recorded here instead of pinned.

### Round thirty: `direction: rtl` inside a line, and the coincidence that was not one

Round twenty-six left `direction: rtl` implemented at block level only, and
wrote down why it stopped there: right-aligning `text/rtl-with-inline-
elements` would land its `<b>` within 2px of Brave "purely because the text
either side of it is the same width, while the words on the line were still
in the wrong order."

Measuring it first says the second half of that is not true. Driven through
`cdp_dump.cljs` on twenty-two rtl shapes that were not in the corpus:

| shape (300px block) | ltr | rtl |
|---|---|---|
| `alpha <b>beta</b> gamma` | 0 / 42 / 79.52 | 185.48 / 227.48 / 265 |
| `aa <b>bbbb</b> cccccc <i>d</i> ee` | 0 / 21 / 62.13 / 111.13 / 126.55 | 159.45 / 180.45 / 221.58 / 270.58 / 286 |

The **same order** both times, every word shifted by the same amount, and
that amount is the line's own leftover in the content width (300 − 114.52 =
185.48; 300 − 140.55 = 159.45). Brave does not reorder either line, and it
is not being lenient: UAX #9 resolves a line whose every word is strong
left-to-right into a single left-to-right run, placed at the line's
inline-end. The shift was never the coincidence — believing the words had to
move was the error. The asymmetric second row is in the corpus now
(`text/rtl-two-inline-elements`) precisely because nothing about it is
symmetric, so no coincidence can produce it.

What genuinely reverses is strong-rtl script, and that was measured too:

| shape (300px rtl block) | Brave, left to right |
|---|---|
| `שלום עולם אבג` | `אבג` 193.58, `עולם` 225.78, `שלום` 266.38 — reversed |
| `שלום one two אבג` | `אבג` 178.17, `one` 210.39, `two` 238.39, `שלום` 266.39 — the Latin run keeps ITS order |
| `alpha שלום עולם beta` in an **ltr** block | alpha 0, `עולם` 42, `שלום` 82.59, beta 123.22 — only the pair swapped |
| `שלום 123 אבג` | `אבג` 206.17, `123` 238.39, `שלום` 266.39 — the number reads forward |

So both halves landed, and only together: **line placement** (which edge a
line packs against, including `text-align`'s direction-relative
`start`/`end` — all eight {ltr,rtl}×{start,end,left,right} combinations
measured) and **run reordering** (UAX #9 rule L2, applied per line after
breaking, at the granularity of whole words).

**What is not implemented, and what it costs.** A word is the smallest
thing that carries a direction: no per-character bidi classes, no W-rules
for numbers, no explicit embedding/override/isolate controls, no
`unicode-bidi`. Measured, that costs exactly one shape — a single word
holding strong characters of both directions (`שלוםabc`) is split by Brave
into two runs inside the word and kept whole here.
`text/rtl-mixed-direction-word-is-not-split` records it, and records that
it **passes**: a multi-rect word is re-grouped per character by top on the
oracle side (a facility that exists for words broken across LINES), so both
of its rects fold back into one entry and the line axis cannot see the
split at all. A passing case is not evidence of agreement here; the
boundary is real and this harness has no axis for it.

**A bug the fix exposed.** `layout-text`'s box shrink-wraps its widest line,
so a bare text child looked like a narrow block to
`layout-children-block`'s own rtl rule and got pushed to the right edge by
it — the right answer reached by the wrong mechanism, invisible while it
was the only mechanism. With line placement in force as well,
`<p style="direction: rtl">alpha beta</p>` was shifted right **twice** and
its text left the paragraph. Real CSS wraps such a child in an anonymous
block box that fills its containing block, so that rule has nothing to
place; it now skips text and generated-text children, and the line rule
owns them. Nothing on any axis moved when it was fixed — with the
harness's `padding: 0` the two mechanisms had coincided to the pixel — 
which is exactly why a draw-op diff of all 357 pre-existing cases was taken
rather than trusting the scoreboard.

**Result**, on a corpus grown 357 → 370 by the thirteen cases above:

| axis | before | after |
|---|---|---|
| line structure | 342/344 | 355/357 |
| geometry (boxes) | 1304/1313 | 1327/1335 |
| geometry (clean cases) | 349/357 | 363/370 |
| paint order | 8866/8909 | 9196/9234 |
| computed style | 16138/18453 | 16400/18761 |

Every one of the thirteen new cases passes on all three layout axes;
`text/rtl-with-inline-elements` moves from a −185.48 `b x` and a
`b -> p` paint-order miss on five sample points to clean; and a draw-op
diff of the whole pre-existing corpus shows exactly one case changed.

### Round twenty-nine: the marker that is not in the item, and the line-height that inherits a ratio

Two residuals the geometry axis had localised to the pixel, both measured in
Brave before anything was written.

**`list-style-position`.** Its default is `outside`: the marker is a box of
its own beside the item, not the first thing in the item's content. This
engine synthesised the marker as the `<li>`'s own `::before` and let it flow
inline, so it advanced the item's line and widened anything that
shrink-wrapped the list. Round twenty-eight had already named this as the
whole remaining cause of `:table/cell-with-a-list`, and named the property
as the honest fix rather than a wider cell.

| markup (14px monospace) | Brave | engine |
|---|---|---|
| `<ul><li><a>First section</a>` — `a` x | 40 | 53.70625 |
| `<td><ul><li>one</li><li>two</li></ul>` — `td` w | 63 | 76.70625 |
| the same, `ul` w / `li` w | 61 / 21 | 74.70625 / 34.70625 |

13.70625 is exactly one `"• "` advance in every row. The marker now travels
through the inline pipeline as a fragment of its own KIND: never merged into
the item's text run, never collapsing whitespace against it, never moving
the pen, contributing nothing to the run's max-content width, and painted at
the negative x that puts it immediately before the content edge.
`list-style-position: inside` keeps the old inline behaviour, which makes it
a real property rather than an accident — Brave puts the same `<a>` at x=59
and the same cell at 82px there, so the two values are 19px apart in the
oracle and were 0 apart here.

**What this axis cannot check, said out loud.** A `::marker` is not an
element, so `getBoundingClientRect` has nothing to return for it and the
oracle reports no box for it in either direction. Where the marker itself
paints is therefore unverifiable by this harness, and no assertion here
claims otherwise. What IS verifiable — and what all three failing cases
measured — is the position and width of the item's CONTENT. The closest the
harness can get to the marker's own size is the `inside` value, whose marker
does take inline space: measured there, Brave's `<ol>` advance IS the width
of the marker string (21px for `1. `, 28 for `10. `, 35 for `100. `), which
is what this engine uses, while its `<ul>` disc box is a function of the
font-size alone (19px at 14px, 14 at 10px, 37 at 28px — identical for Arial
and monospace and for `list-style-type: square`, i.e. not the 6.7px bullet
glyph). That 5.3px is recorded in `list-style-inside?` rather than modelled
from three points.

**Unitless `line-height` inherits the FACTOR.** `line-height: 1.5` inherits
as the NUMBER, so a child with a different `font-size` re-multiplies it;
`1.5em` resolves once and inherits as that length. `inherited` only ever
carried resolved pixels, so both reached a 24px child as 21px. The corpus
holds both halves on purpose (`:text/unitless-line-height-inherits-the-factor`
and `:text/em-line-height-inherits-the-computed-value`) and only the unitless
one failed, which is what localised it: Brave reports 36/36 for the first
and 21/21 for the second.

On the way, the multiplier forms are parsed explicitly instead of through
`parse-dbl`, which does not answer the same question on both platforms —
`Double/parseDouble` rejects a trailing unit and `js/parseFloat` ignores
one. `line-height: 1.5em` was 21px under nbb (right, by accident) and the
theme default on the JVM, and `150%` was **150x** the font-size rather than
1.5x. `rem` and the viewport units now fall through to `normal` rather than
being multiplied by a length this file cannot resolve.

**Result**, at the same 341 cases: geometry 1244/1283 → **1256/1283**
(321 → **324** clean), paint order 8429/8509 → **8444/8509** (319 → **321**
clean), line structure and computed style unchanged at 326/328 and
15678/17949 — this is a layout change and the cascade axis should not move.
Four cases' boxes changed. `:page/table-of-contents`,
`:table/cell-with-a-list` and `:text/unitless-line-height-inherits-the-factor`
all went to **every box exact**; `:table/cell-with-a-list` had been 0/8 since
the corpus gained tables.

The fourth is a 1px cost, stated rather than hidden: `:selector/nth-child`
bolds its second `<li>`, and that item now reaches the inline path (it has
two children — marker and text — where the merged marker made it one) where
it used to reach `layout-text`. The two paths round a bold line box
differently, so it reports 21 where the browser and `layout-text` say 20. It
stays within the 2px tolerance and the case stays clean, but it is a real
pre-existing disagreement between two height models that this change
exposed on more elements rather than one it introduced.

**Still not fixed, and not the same cause.** `:page/two-column-text` and
`:overflow/x-hidden-y-scroll` were in the same residual and were checked
against these two causes before being left: both are margin questions. A
flex ITEM's margins do not collapse (Brave puts each `<p>` at y=14 and the
container at 68; this engine drops them), and an `overflow` container
establishes a block formatting context so the margin inside it cannot
collapse through (Brave y=14, this engine 0). Neither has anything to do
with markers or line-height, and improving them from here would have meant
guessing.

An `<li>` whose content is a BLOCK (`<li><div>x</div></li>`) still gives its
outside marker a row of its own where Brave puts it beside the block's first
line — the item comes out one line too tall. Unchanged by this round (the
marker had its own row before too), no corpus case covers it, and it is
named in the namespace docstring.

### Round twenty-eight: the border every content box was standing on

`inset-side` — the whole engine's answer to *where does this box's content
start* — counted the border only under `box-sizing: border-box`. Named as
still-open by rounds twenty-five, twenty-six and twenty-seven, each time
with the same reason for not doing it: it is one change to the box model
rather than one UA reading, and it moves every bordered box on every page.

**The rule, measured before anything was written.** `box-sizing` does not
move the content edge. It decides what a *declared* `width`/`height`
measures — the content box under `content-box`, the border box under
`border-box` — and that question belongs to `resolve-width` /
`used-block-height`, which already answered it correctly through
`declared-inset-side`. Where the content *starts* is border + padding in
from the border edge either way. Ten shapes in Brave 151 over CDP
(2026-08-05), reading `getBoundingClientRect` and `clientLeft`/`clientWidth`
side by side, all say the same thing:

| shape | child lands at | `clientLeft` |
|---|---|---|
| `div{border:2px;padding:10px}` | x=12, w=376 of 400 | 2 |
| `div{box-sizing:border-box;width:200px;border:2px;padding:10px}` | x=12, w=176 | 2 |
| `div{width:200px;border:5px;padding:4px 8px 12px 16px}` | x=21, y=23, w=200 | 5 |
| `div{display:flex;width:200px;border:3px;padding:7px}` | items at x=10, y=10 | 3 |
| `div{display:grid;...;border:3px;padding:7px}` | items at x=10, y=10 | 3 |
| `td{border:4px;padding:6px}` | child at x=10, y=24 | 4 |
| `fieldset` (UA 2px border) | `<p>` at x=12.5 of the fieldset | 2 |

Two neighbours it is **not**, both re-measured so the change would not
swallow them:

- **An absolutely positioned descendant's containing block is the PADDING
  box** — border alone, padding *outside* it. `div{position:relative;
  border:7px;padding:9px}` puts a `top:0;left:0` child at **x=7**, not
  x=16. `layout-block` computes that separately (`pad-x`/`pad-y`) and it
  stays separate.
- **An `overflow` clip lands on the padding box too**, and this engine
  clips at the border box: `div{width:100px;height:40px;overflow:hidden;
  border:6px;padding:5px}` is a 122x62 border box reporting a 110x50
  scrollport. Left alone and written up as a scope cut at the clip site —
  it is a *paint* change where this is a *layout* change, and nothing in
  the corpus scores a clip edge.

**One place had to give the border back.** Under `border-collapse:
collapse` a cell keeps only *half* of each grid line it sits between, and
the column widths were built by ADDING the inner half to a natural width
that was "content + padding, never border". With the border now in the
natural width that double-counted, and `:table/border-collapse` went 5/5 →
**0/5** — cells 15px wide where Brave says 11. Subtracting the *outer* half
instead is the same rule against the corrected input, and restored it to
5/5 exactly. It is the one thing in this round that a net score would have
hidden: geometry read 1241 → 1239 with three cases improving.

**Result.** Per-case old-vs-new box diff over all 341 cases, replaying the
harness's own tag+nearest pairing: **four cases changed, three improved,
none regressed**, and every box that moved landed on the oracle.

| case | boxes | what moved |
|---|---|---|
| `:form/fieldset-and-legend` | 2/3 → **3/3** | `<p>` (12.5, 36.9, 775) → (14.5, 38.9, 771); Brave (14.5, 38.891, 771) |
| `:position/absolute-containing-block-is-the-padding-box` | 2/3 → **3/3** | `<p>` (20, 34, 210) → (25, 39, 200); Brave (25, 39, 200) |
| `:page/toolbar-with-auto-margin` | 4/5 → **5/5** | container h 32 → 34 (Brave 35), children +1px in |
| `:page/card-with-absolute-badge` | 4/4 → 4/4 | `<h3>`/`<p>` (12, 28, 242) → (13, 29, 240) = Brave exactly; was already inside the 2px tolerance |

Geometry **1241 → 1244** boxes, **318 → 321** clean cases; paint order
**8424 → 8429** (the `p -> fieldset` cluster of 5 is gone, and nothing
replaced it); line structure 326/328 and computed style 15678/17949
unchanged, with per-case status identical on the line axis.

Four probe shapes run through both engines to check the axes the corpus
does not cover, before and after:

| shape | before | after | Brave |
|---|---|---|---|
| `flex{width:200px;height:60px;border:5px;padding:8px}` | 226x76, item (8,8) | **226x86, item (13,13)** | 226x86, (13,13) |
| same as `block` | 226x86, item (8,8,210) | **226x86, item (13,13,200)** | 226x86, (13,13,200) |
| same as `grid` | h **60**, item (8,8) | h **60**, item **(13,13)** | h 86, (13,13) |
| `overflow:hidden;border:6px;padding:5px` | item (5,5) | **item (11,11)** | (11,11) |

The grid container's height is the one thing that did not move: `layout-grid`
reads `resolve-height` straight into its own `node-h` instead of
`used-block-height`, so a `content-box` grid with a declared height is still
its content height rather than its border box. That was already true before
this round and is untouched by it — named here rather than left to be
rediscovered.

**Tests.** Sixteen assertions across four tests changed answer, every one
rewritten with the reason rather than with a new number, and every one of
them a test that had been pinning the *wrong* value:

- The three `fieldset`/`legend` tests carried Brave's real numbers in their
  own comments — *"(Brave 14.5, one border out)"*, *"(Brave 38.891, again
  one border out)"*, *"(Brave 771)"*, *"(Brave 24.891)"*, *"(Brave 6.891)"*.
  All five now match Brave exactly, and the comments say so.
- `grid-container-border-and-background-match-block-flex-convention`
  asserted the old convention in prose: *"Content is inset by padding only
  … border-width only offsets content when box-sizing: border-box."*
  Re-measured on that exact shape (Brave: 112x22 container, item at (6,6));
  the container is 22 tall here now, not 18, and the item is at (6,6).
- The three input-caret tests moved 2 → 4, which is an `<input>`'s border
  (2) plus its padding (2). The caret, the value text and the placeholder
  were all being painted one border outside the box they belong to.

665 tests / 1455 assertions, 0 failures; lint 0 errors, 23 warnings
(unchanged).

### Round twenty-seven: `transform`, which changes what a box reports without changing where it is

`transform` matched nothing in `src/` but `text-transform`, an unrelated
property. Round twenty-six added six `:transform/*` cases to find out how
big the gap was; all six failed. All six pass now, plus four more added
from the twenty-three further shapes measured in Brave while implementing
it.

**The two properties the cases exist to pin, and what each cost.** A
transform is a **paint-time** operation: the box still occupies its
untransformed space in flow, so a following sibling does not move and the
parent is not resized. That fell out of *where* the code went rather than
from any care taken with it — `apply-element-transform` wraps
`layout-node`'s whole element dispatch and rewrites the `:draw` half of the
result, handing `:box`, the collapsed margins, the escaped floats and the
out-of-flow list back untouched. Wrapping the dispatch rather than each
branch is also why the same nine lines cover a block, a flex or grid
container, a table, a form control and an atomic inline: every one of them
returns the same `{:box :draw}` shape there. The second property — a
**percentage in `translate` resolves against the element's own border
box**, the one place in CSS a percentage looks inward — is the reason
`transform-length` takes the element's own `w`/`h` as its basis where every
other percentage in the file takes the containing block's.

**Where the transform applies: both, or it would be worse than nothing.** A
transform that moved the `:node` box the geometry axis reads while leaving
the background and the text where they were would score six cases and
render worse than no transform at all. `transform-ops` maps the whole
subtree: a rect-shaped op becomes the axis-aligned bounding box of its
transformed corners, a text op is placed at its transformed origin with its
font size scaled by `sqrt(|det|)`. For the `:node` op the bounding box is
not an approximation — `getBoundingClientRect` reports exactly that box,
which is why `rotate(45deg)` on a 100×20 box reports 84.85 square in both
engines. For a background fill under a rotation it is an over-covering
approximation, and for glyphs it is a stated cut: there is no rotated-quad
or rotated-text primitive in this engine or its hosts.

**One shape that had to *not* move.** CSS applies `transform` to
transformable elements, which excludes a non-replaced inline box. Measured:
`<span style="transform: translateX(30px)">` in a sentence *computes*
`matrix(1, 0, 0, 1, 30, 0)` and sits at exactly the x an untransformed span
sits at. `:transform/not-on-a-non-replaced-inline` is the corpus case for
it, and `transformable?` is the predicate — without it, applying the
transform there would have moved a box every browser leaves alone.

**Scope cuts, stated rather than discovered.** `matrix()` is implemented
(six numbers is the canonical form the others reduce to, and Brave reports
the same box for `matrix(2,0,0,2,10,10)` as for `translate(10px,10px)
scale(2)`). The Z-only 3D functions are accepted as their 2D projections,
because without a `perspective` that projection *is* what a browser
reports. `matrix3d`, `perspective`, `rotate3d`, `rotateX`, `rotateY`,
`transform-style` and `backface-visibility` are **not** modelled, and a
list containing any of them — or a length in a unit outside `px`/`%` — is
dropped **whole**: a list is one composed transform, and applying three of
its four functions puts the box confidently in the wrong place, where
reporting the untransformed box says truthfully that it was not modelled.
A transformed element also establishes a **stacking context** in real CSS
and this engine does not model that. It establishes a **containing block**
for absolutely positioned descendants too, and this engine gets that right
— measured, a `left: 5px; top: 5px` child of a static
`transform: translate(20px, 10px)` box lands at (25, 15) in both — but for
an unrelated reason: every block box here anchors its own out-of-flow
children with no positioned-ancestor check at all, so the containing-block
question never reaches a `position` test. The right answer by the wrong
route, named in `apply-element-transform` so that fixing the broader
simplification does not silently take this with it.

Corpus-wide, same harness both sides, on the corpus as it grew 337 → 341:
line structure 322/324 → **326/328**, geometry 1224/1272 → **1241/1283**
(308/337 → **318/341** clean), paint order 8321/8409 → **8424/8509**
(312/337 → **318/341** clean), computed style 15535/17795 →
**15678/17949** (the axis compares no transform property; the delta is the
four new cases' own elements). Ten cases' boxes changed, all ten are the
`:transform/*` group, and **none regressed** — every other case's box list
and line-axis status is byte-identical either side.

| case | before | after |
|---|---|---|
| `:transform/translate-moves-the-box` | 1/2 | **2/2** |
| `:transform/translate-does-not-affect-siblings` | 2/3 | **3/3** |
| `:transform/scale-changes-the-reported-box` | 1/2 | **2/2** |
| `:transform/percentage-translate-is-of-the-box` | 1/2 | **2/2** |
| `:transform/rotate-grows-the-reported-box` | 1/2 | **2/2** |
| `:transform/on-an-inline-block` | 1/2 | **2/2** |
| `:transform/not-on-a-non-replaced-inline` | new | **2/2** |
| `:transform/functions-compose-in-order` | new | **3/3** |
| `:transform/origin-moves-the-fixed-point` | new | **2/2** |
| `:transform/on-a-flex-item` | new | **4/4** |

No existing test changed answer, because nothing in this file had an answer
for `transform` before. Eleven new tests, 654 → 665 tests / 1407 → 1455
assertions, 0 failures; lint unchanged at 0 errors.

### Round twenty-six: the legend that is not in the flow, the button that wrapped its own label

Five things, each measured in a real headless Brave 151 over CDP **before**
the code that produces it was written, and each probed for its *rule*
rather than for the corpus case's numbers.

**`<fieldset>`/`<legend>` — the largest remaining geometry cluster.** The
box constants were already written down in `ua-control-box` by an earlier
round, which deliberately left the case failing rather than half-fixed
because the legend's placement is not a constant. It is now implemented.
A fieldset carries `margin-inline: 2px`, a 2px groove border and
`0.35em 0.75em 0.625em` of padding — **em**, which the cascade resolves
against the element's own font size (14 → 4.9/10.5/8.75, 20 → 7/15/12.5)
instead of pinning one row of numbers — and its content box establishes an
independent formatting context (measured on `border:0;padding:0;margin:0`,
where the inner `<p>`'s margins stay **inside**: 68px tall with the `<p>`
at y=34, both of which collapse out of an ordinary div).

The legend is lifted out of flow into the block-start border band:

```
band     = max(border-block-start-width, legend height + its margin-BOTTOM)
legend y = (band - that margin box) / 2, from the fieldset's border-box top
content  = band + padding-top
```

Three of those clauses are readings, not derivations. The legend's
margin-**top** is ignored outright: `margin-top: 10px` and `margin-top:
40px` both leave the fieldset **83.641** tall, while `margin-bottom: 10px`
makes it **93.641**. The legend is *centred* in the band, which only shows
up when the border is thicker than it (`border-top-width: 40px` puts a 20px
legend at **y=10**). And its margin-*inline* is honoured normally
(`margin: 10px` moves it from x=14.5 to **24.5**).

Which legend gets lifted was probed the same way, and three of the four
answers are surprising:

| shape | Brave |
|---|---|
| `<legend>` after two `<p>`s | still lifted; the `<p>`s start below the band |
| a **second** `<legend>` | ordinary full-width block in the content, (14.5, 24.891, 771, 20) |
| `<div><legend>` | not a legend at all — no band, 85.641 tall |
| `display:none` / `position:absolute` | no band; fieldset is 65.641, as with no legend |
| `float:left` | an ordinary float *inside* the content, with the `<p>`'s text at x=53.5 |

**A `<button>`'s label counts its markup.** `<button>save <b>now</b>
</button>` was measured through `real-text-child`, which sees a control's
*direct* text children only, so the label came out `save ` — 36px of
content where Brave reports 58.5. The consequence was not a 22px box error:
the button **wrapped its own label**, grew to 34px, and painted the first
line above its own border box. `atomic-intrinsic-width`'s form-control
branch had been shadowing the `:else` branch that already knew how to
measure mixed inline content.

**`box-sizing: border-box` on `<button>`, `<select>` and checkbox/radio.**
Read off `getComputedStyle`, not inferred: those three report `border-box`
and `<input>`/`<textarea>`/`<fieldset>`/`<legend>` report `content-box`
(confirmed on `width: 200px`: button **200**, select **200**, input **208**,
textarea **206**; this engine said 216 for the button). It matters twice.
`inset-side` only counted the border for a border-box box *at the time of
this round* (round twenty-eight removed that gate — it counts the border in
both modes now), so a button's own label was painted at its **border** edge
instead of one border plus one
padding in — and the harness attributes a text op to the atomic inline
whose box *contains* it, so a label sitting 3px above its own box leaked
onto the surrounding line. That is the whole of
`:form/button-with-nested-inline` wanting `["tail"]` and getting
`["save now tail"]`.

**A float narrows a DESCENDANT block's line boxes.** Round twenty-two left
this as a named scope cut — "`layout-node` does not carry a float context
down into a child" — on the grounds that only a wrap point was at stake.
It was worse than that. `:page/media-object` reported **one** line for a
three-line page: every line the engine left at x=0 is geometrically inside
the float's own box, so the harness attributed all of them to the float
rather than to the paragraph they belong to. `layout-node` now takes the
band as an optional trailing argument; it is seeded into the child's own
float list and tagged `:intruding?` so the child neither grows to contain
it nor re-escapes it to its parent. Verified against Brave on five shapes
(text in the same block, in a `<p>`, across two `<p>`s, a right float, and
a doubly nested block) — line content and x-offset agree exactly on all
five.

One consequence is worth naming: a float breaks `layout-node`'s
translation-invariance, which every other placement in this file relies on.
The band a child must avoid depends on where the child really ends up, and
that is not known until the child has been laid out once (its collapsed top
margin takes part in the gap). So a block child that has a band **and** a
non-zero shift is laid out twice — once to learn the gap, once with the
band moved to match. Bounded by construction, and it does not compound.

**A line box after a block keeps the pending bottom margin.** CSS wraps
inline content in an *anonymous* block, and the previous sibling's bottom
margin separates it exactly as it separates a real block. This branch
dropped it. It hid because a **lone** inline child never becomes a run
(`inline-runs` needs two), so `<div><p>para</p>bare text</div>` took the
block path and was right at 54px while `<div><p>para</p><span>a</span>
<b>b</b></div>` came here and was 41 against Brave's 55. It was the whole
of `:page/login-form`'s `label y −18.4` / `input y −17.4`: an `<h2>`'s
17.43px bottom margin vanishing before the first `<label><input>` line.

**One floating-point bug, fixed at its source rather than tolerated.** An
intrinsic width is `inset + content`; it is handed back as the box's
*available* width, and `layout-block` then re-derives the content width by
subtracting the **same** inset. In binary floating point that does not
return `content` — measured, `save now` is 57.89096472741182 and the round
trip returns 57.8909647274118, one ulp short — and one ulp short is enough
for the line breaker to decide the label does not fit the box that was
sized for it. The content is now rounded **up** to a whole pixel before the
inset is added, which makes the subtraction exact instead of lucky, and is
the direction a box may only err in: wider than its content, never
narrower.

Corpus-wide, on the 337-case corpus, same harness both sides: line
structure 320/324 → **322/324**, geometry 1215/1272 → **1224/1272**
(307/337 → **308/337** clean), paint order 8308/8409 → **8321/8409**,
computed style 15535/17795 unchanged. Nine cases' boxes changed and **none
regressed**; the six that changed without changing score are all button
widths landing closer to Brave (43.46 → 44 against 44.17, 29.73 → 30
against 30.09, and so on).

| case | before | after |
|---|---|---|
| `:page/login-form` | 1/7 | **7/7** |
| `:form/fieldset-and-legend` | 0/3 | **2/3** |
| `:form/button-with-nested-inline` | 0/3 | **1/3** |

Two closed tests changed answer, both rewritten with the reason rather than
with a new number: the float scope-cut test now asserts the browser's
`x=80` instead of its own `x=0`, and the flex-child test asserts a button's
**200px** border box instead of 216.

Still open, and named rather than left to be rediscovered:

- **`inset-side` omits the border for a content-box element**, in both axes
  — already named by round twenty-five for
  `position/absolute-containing-block-is-the-padding-box`, and it is now
  also the *entire* remaining residual of `:form/fieldset-and-legend`: its
  inner `<p>` is 4px wide of Brave and 2px left of it, and nothing else
  about that case disagrees. It is one change to the box model rather than
  one UA reading, and it moves every bordered box on every page, so it
  belongs with whoever owns width/height resolution — not folded into a
  fieldset constant, which would fit this case and mislead the next.
  **Closed by round twenty-eight**, exactly as described: both cases went
  clean and nothing regressed.
- **`:page/table-of-contents`' `a x +13.70625`** and
  `:table/cell-with-a-list`'s `li w +13.70625` are the same number and the
  same cause round twenty-four already named: this engine paints an
  `<li>`'s marker *inside* the item's line, as `list-style-position:
  inside`, where the browser's `outside` default puts it in the list's own
  40px padding and leaves it out of the item's content entirely. Brave puts
  the `<a>` at x=**40**, the `<li>`'s content edge, and this engine at
  53.70625 — exactly one marker advance in. The fix is that property. It is
  not attempted here partly because a `::marker` produces **no element box
  in the oracle**, so the marker's own placement cannot be verified by this
  harness at all — only the content's can.
- **A `display: flex|grid|table` fieldset gets no band.** The lift lives in
  `layout-block`, and Brave lifts the legend before the fieldset picks a
  formatting context at all (measured: `display: flex` leaves the fieldset
  83.641 tall with the legend still at y=0, and 20 here). Doing it properly
  means moving the lift above `layout-node`'s display-driven branch.
- **Per-side border widths.** `border-top-width: 40px` is not read at all —
  this engine has one uniform `:border-width` — so the band's centring
  clause, which is correct, can only be reached by a uniform border taller
  than the legend.

### Round twenty-five: where the leftover inline space goes, and a height that is a content height

Six gaps, and every number below was read out of a real headless Brave 151
first. Three of them turned out to be the same defect wearing three faces:
**a value that is not a plain px length reached arithmetic that only knows
plain px lengths**, and the arithmetic won.

**`margin: 0 auto` did not centre a block, in either layer.** The cascade
declined to expand the shorthand at all (`auto` is not a length, and
`expand-box-side-shorthand` only expanded lengths), so `margin-left` read
0 where the browser reports 150px — 4 of the 16 values the computed-style
axis still charged to the cascade. Then layout had nothing to read even if
it had been expanded, because node-style's `parse-int` turns `auto` into
the same nil a missing margin gives. Both halves are fixed: `margin`
(and only `margin` — `padding: auto` is not CSS) expands with `auto`
tokens, node-style carries the raw inline margins alongside the coerced
ones, and `layout-children-block` distributes the leftover space by CSS
2.1 §10.3.3's own rule.

Which is not "an auto margin centres the box", and the corpus now says so
in four cases measured before any of it was written:

| case | Brave | this engine, before |
|---|---|---|
| `box/margin-auto-centers-a-block` (100 in 400) | x=150 | x=0 |
| `box/margin-left-auto-pushes-a-block-right` | x=300 | x=0 |
| `box/margin-right-auto-leaves-a-block-left` | x=0 | x=0 (agreed already) |
| `box/margin-auto-with-no-room-does-not-centre` (300 in 200) | x=0, w=300 | agreed already |
| `box/margin-auto-with-a-vertical-length` (`margin: 10px auto`) | x=150 | x=10 |

The last two are the ones worth keeping. The over-constrained case says
Brave does **not** centre a box wider than its container at x=−50 — an
auto margin with nothing to absorb is 0 — and the `10px auto` case caught a
bug the fix introduced on its way in: `margin-side` falls back to the
uniform `:margin` when a per-side longhand is absent, so the *vertical*
10px leaked into the `auto` inline sides and indented the box instead of
centring it.

**`direction: rtl`, exactly as far as it can be verified.** In an rtl
containing block the over-constrained equation resolves `margin-left`
instead of `margin-right`, so a 60px block in a 200px container sits at
**x=140** where this engine had it at 0 (`text/rtl-block-alignment`).
That is block-level alignment, and in this round it was all that was
implemented: no embedding levels, no neutral resolution, no run reversal,
so `text/rtl-with-inline-elements` still failed. `text-align`'s
direction-relative `start`/`end` was left alone deliberately, on the
reasoning that right-aligning that case's line would land its `<b>` within
2px of Brave's x purely because the text either side of it is the same
width, while the words on the line were still in the wrong order.

**Round thirty measured that and found the second half of it wrong** —
Brave does not reorder that line, because every word on it is strong
left-to-right — and implemented both line placement and UAX #9 run
reordering. See round thirty for the measurements and for what is still
not resolved below a word. The block-level rule described here survives
unchanged except that it no longer applies to a bare TEXT child, which was
being shifted right twice once line placement existed.

**A negative margin never wins a `max`.** The cascade had the `-8` all
along; `layout-children-block` collapsed adjacent margins with `max`, and
`(max 0 -8)` is 0. Real CSS collapses to *the largest positive plus the
most negative*, which reduces to `max` when everything is positive.
Measured in Brave, both directions:
`box/negative-margin-pulls-up` is a 32px-tall parent with its second block
at y=12 (engine: 40 and 20), and the new
`box/negative-margin-bottom-pulls-the-next-sibling-up` is the same numbers
from the other side. The control that says the rule is not "negatives are
special" is `box/negative-margin-left-widens-an-auto-width-block`:
`margin-left: -20px` on an auto-width block makes it x=−20, w=220 in
Brave, which this engine already got right.

**A percentage height against an auto-height parent is `auto`.**
`resolve-height` read `"50%"` through `explicit-length`'s leading-digit-run
as 50 **px**, whatever the parent was. `percentage-of` — which already
returns nil for an indefinite basis, exactly the "size me from content" nil
every caller spells — was right there and unused on this path. The basis
now travels down as `:block/containing-height`, set by `layout-block` and
**dropped** by `layout-flex`/`layout-grid`/`layout-table`, whose items'
containing block is not the block that set it and whose own definite
content height this round does not compute; an honest `auto` beats the
grandparent's height.

`box/percentage-height-of-a-fixed-parent` had been passing throughout
because 50% of a 100px parent is 50 either way. Adding
`box/percentage-height-of-a-padded-parent` — asking WHICH height, the
content box or the border box — found a second bug immediately, and it was
not in the percentage:

**A declared `height` is the CONTENT height, and was being used as the
border box.** `resolve-width` had been corrected for this in the inline
axis and the block axis had not. Measured in Brave,
`div{height:100px;padding:10px}` is **120** tall and lays its children out
in **100**; this engine said 100 and 80. Fixing it also moved a case
nobody had connected to it: `table/cell-vertical-align`'s
`<td style="height:60px">` cells are 62 tall in Brave (their UA 1px
padding), and were 60 here.

That fix needed one thing to be kept apart from it, and the corpus caught
it on the same run. Two places in this engine SOLVE a height and inject it
back onto the node to be re-read through the ordinary path — a stretched
flex item's line cross size (`force-cross-size`), and an absolute box's
`top`+`bottom` (`layout-absolute-children`). Those numbers are already
border boxes, and box-sizing must not be applied to them twice; routed
through `style/height` they were, and `page/form-row`'s `<button>` went
from 20 to 24 against Brave's 21. They now travel as a distinct
`:kotoba/used-height`, which is what `force-main-width` had already
concluded for itself in the inline axis (it pins `box-sizing: border-box`
on its own injection for exactly this reason).

**`calc()` with a percentage in it, and a percentage width resolved
twice.** `cssom.core` collapses a *constant* `calc()` during the cascade,
so anything still wearing the `calc(` text in layout contains something
the cascade could not resolve — which in practice means a percentage.
`calc(100% - 40px)` in a 300px block is **260** in Brave and was 300 here
(the value failed to parse outright and the avail-width fallback won);
`calc(50% + 10px)` is **160**. The `%` is resolved at the calc tokenizer's
leaf against the containing block, which leaves `eval-calc-node`'s
same-unit rule for `+`/`-` exactly as it was, and degrades to nil — not to
zero — when there is no definite basis.

`position/absolute-percentage-width` was a different bug with the same
symptom: `measure-child` resolved `width: 50%` against the containing
block (correctly, 100) and handed the result down as the child's
*available width*, where the child's own `resolve-width` resolved the same
percentage a second time and got 50. The used width is now written back
onto the child as a plain length, so the second resolution is a no-op.

Corpus-wide, this round added 10 cases (four of them controls that already
agreed). Measured on the 337-case corpus as it stands after merging round
twenty-six's transform cases, same harness both sides: geometry
1201/1272 → **1215/1272** (296/337 → **307/337** clean), computed style
15534/17801 → **15535/17795** with the cascade-attributed residual 16 →
**9**, paint order 8307/8409 → **8308/8409** (311 → **312** clean cases),
line structure **320/324** unchanged. Twelve cases' boxes changed and
**none regressed**; every one of the twelve went to exact agreement on
every box.

The computed-style axis's compared-value count falls by 6 because
`margin-left`/`margin-right` now hold the string `auto` on the cases that
declare it, which that axis excludes as a non-absolute-length rather than
scoring — the same treatment a directly-declared `margin-left: auto`
already got. The browser reports a *used* value there (150px, or −100px on
the over-constrained case); this engine's cascade holds the *specified*
one. Neither is wrong and they are not comparable, which is what the
exclusion says.

Still open, and named rather than left to be rediscovered: no bidi
reordering (above -- **closed by round thirty**, at word granularity);
`flex/auto-margin-pushes-item-right` still fails,
because a flex line distributes its free space through
`place-main-axis-auto-margins` and not through this round's block-flow
path; `inset-side` still omits the border for a content-box element, in
both axes, which is what `position/absolute-containing-block-is-the-
padding-box` measures (**closed by round twenty-eight**); and a percentage
height inside a flex or grid item resolves to `auto` rather than against
the container.

### Round twenty-one: the corpus grows 200 → 292

The engine went 47% → 89% on geometry while the corpus stayed at 200 cases.
A corpus that stops growing stops finding things, so this round inventoried
what the 200 actually covered — by keyword namespace, case by case — and
added 92 cases only where the answer was "nothing" or "one case".

Nothing here was chosen to pass. **59 of the 92 diverge**, and the
aggregate percentages fell accordingly (table above). That is the honest
number, not a regression: the same `src/` scores 89% on the old 200 and 82%
on the new 292, because the new 92 ask about things the old 200 never did.

Two corpus bugs were found and fixed before any of it counted, both worth
recording because they are hazards of a shared-document harness:

- **An unbalanced case leaks into every case after it.** `<div>` × 16 with
  15 `</div>`s in one new case put the harness's own `<script>` *inside*
  that case's root, and its element counts went off by one. There is now a
  tag-balance check over the whole corpus; it is clean.
- **A float that escapes its container intrudes on the NEXT case.** Three
  new cases deliberately leave a float uncontained. Measured on the shared
  page, one pushed the following case's BFC box 50px right, one moved the
  following case's float from x=10 to x=130, and one turned a one-line
  paragraph into two. Each is now wrapped in an `overflow: hidden` box that
  is *not* the subject, with a comment saying so. Every new case was then
  re-run in isolation and its oracle geometry diffed against its geometry
  on the full page, to prove no case's numbers depend on its neighbours.

#### What the 92 found, by cause

**Percentage lengths are consumed as bare pixels.** `cssom.layout`'s
`parse-int`/`parse-dbl` run `js/parseInt`/`js/parseFloat` over the cascaded
string, so `"50%"` becomes `50` **px** and `calc(…)` fails to parse and
takes the fallback. One cause, nine cases, four subsystems:

| case | browser | engine |
|---|---|---|
| `box/percentage-width` (50% of 400) | 200 | 50 |
| `box/max-width-percentage` (50% of 300) | 150 | 50 |
| `box/percentage-height-of-an-auto-parent` | 20 (auto) | 50 |
| `position/absolute-percentage-offsets` (50%/50% of 200×60) | x=100 y=30 | x=50 y=50 |
| `position/absolute-percentage-width` (50% of 200) | 100 | 50 |
| `position/relative-percentage-offset` (25% of 200) | x=50 | x=25 |
| `table/width-percentage` (50% of 400) | 200 | 50 |
| `box/calc-width` (`calc(100% - 40px)` of 300) | 260 | 300 |

`box/percentage-height-of-a-fixed-parent` **passes**, and is in the corpus
as the control that says why: 50% of a 100px parent is 50, which is exactly
what reading `"50%"` as `50` produces. The pass is a coincidence, and
without the other eight it would read as coverage.

**`auto` and negative values in the box model.**

- `box/margin-auto-centers-a-block` — a 100px block with `margin: 0 auto`
  in 400px sits at x=150 in the browser, x=0 here. This one shows on the
  CASCADE axis too, and is a genuinely new cascade finding: `margin: 0 auto`
  is stored as the raw string `"0 auto"` and never expanded into longhands
  (the expander declines because `auto` is not a length), so a
  `getComputedStyle` consumer reads `margin-left: 0` where the browser
  reports `150px`. 2 of the 11 cascade-attributed values.
- `flex/auto-margin-pushes-item-right` — `margin-left: auto` on a flex item:
  x=265 in the browser, x=28 here.
- `box/negative-margin-pulls-up` — `margin-top: -8px` is stored correctly by
  the cascade (`-8`) and dropped by layout: the browser puts the second
  block at y=12 in a 32px parent, the engine at y=20 in a 40px one.

**Floats: `clear`, containment, and the float's own margins.** The float
round named three unimplemented things and left them without cases. All
three now have one, plus two more. (All five were fixed in round
twenty-two, above; the measurements are kept here because they are what
that round was written against.)

- `float/clear-left`, `float/clear-both` — `clear` is unimplemented.
  `below` lands at y=40 (container 60) in the browser and y=20 (container
  40) here; `after` at y=50 (container 70) against y=0 (container 50).
- `float/parent-does-not-contain-its-float` — a float does not contribute to
  its parent's height. The browser reports the wrapper **200×0**; the
  engine **200×60**. The companion `float/overflow-hidden-contains-its-float`
  agrees with the browser, so the BFC half of the rule is already right and
  only the non-BFC half is missing.
- `float/float-with-margin` — a float's own margins are dropped: the browser
  places it at (10,10) in a 50px-tall container, the engine at (0,0) in a
  30px one.
- `float/floats-that-do-not-fit-stack` — two 120px floats in 200px: the
  browser drops the second to y=20, the engine leaves it beside at x=120.
- `float/float-after-text-in-its-container` — the documented v1 boundary,
  now measured: y=34 in the browser, y=0 here.

**Flexbox past the defaults.** Ten cases, ten separate properties, none of
them implemented:

| case | browser | engine |
|---|---|---|
| `flex/align-self-overrides-align-items` | items at y=40, y=20 | both y=0 |
| `flex/order-reorders-items` | `second` first (x=0) | DOM order |
| `flex/row-reverse` | x = 279, 286, 293 | x = 0, 7, 14 |
| `flex/column-reverse` | three 800×20 rows, bottom-up | three 7×90 boxes side by side (laid out as a ROW) |
| `flex/wrap-reverse` | second line at y=0 | y=0 for line 1, item 2 at x=100 |
| `flex/align-content-space-between` | line 2 at y=100 | y=20 |
| `flex/flex-shorthand-one` (`flex: 1`) | 150 / 150 | 70 / 7 (basis not zeroed) |
| `flex/column-align-items-center` | items centred at x=96.5, x=86 | stretched to 200 at x=0 (cross axis taken as vertical) |
| `flex/align-items-baseline` | line 24 tall, item 2 at y=4 | 20 tall, y=0 |
| `flex/min-content-floor-on-an-item` | 147 / 7 | 113 / 6 (shrinks past min-content) |

`flex/inline-flex-in-a-sentence` is a different shape of the same gap:
`display: inline-flex` is not inline-level, so the paragraph around it goes
from one 20px line to three.

**Grid: one crash, and flow/gap/alignment.**

- **`grid-row: span 2` throws.** `:grid/row-span-two` is the only case in
  292 that makes `cssom.layout` raise rather than answer:
  `nth not supported on this type`. Narrowed by probe: `grid-column:
  span 2` and `grid-row: 1 / 3` both lay out fine, so the defect is
  specifically the `span` form on the ROW axis.
- `grid/explicit-row-placement` — `grid-row: 2` places the item but does not
  leave the column cursor where a browser leaves it: the browser puts the
  next auto item at (0,0), the engine at (70,30).
- `grid/auto-rows` — `grid-auto-rows: 40px` ignored (rows 20px, container 40
  against the browser's 80).
- `grid/auto-flow-column` — `grid-auto-flow: column` ignored; items stack
  vertically at the full container width.
- `grid/separate-row-and-column-gap` — the `row-gap`/`column-gap` LONGHANDS
  are ignored where the `gap` shorthand works: an 8px column gap and a 24px
  row gap are both applied as 0 (container 40 against 64).
- `grid/justify-items-center`, `grid/align-items-center-in-a-tall-row` —
  neither is implemented; items sit at the track origin and stretch.
- `grid/auto-columns-size-to-content` — `grid-template-columns: auto auto`
  produces **zero-width** tracks (browser 154.5 / 245.5), and the container
  goes 80 tall instead of 20.
- `grid/inline-grid-in-a-sentence` — same as inline-flex.

**Absolute positioning: the containing-block rules themselves.** Every
pre-existing `absolute` case gave the box a `position: relative` PARENT, so
none of this was measured:

- `position/absolute-left-and-right-set-width` — `left` and `right` together
  do not resolve a width: 260 in the browser, 63 here.
- `position/absolute-top-and-bottom-set-height` — same on the block axis:
  80 against 20.
- `position/absolute-containing-block-is-the-padding-box` — the containing
  block is taken as the ancestor's CONTENT box. `left: 0; top: 0` lands at
  (5,5) in the browser (just inside the 5px border) and at (20,20) here —
  off by exactly the ancestor's 20px padding.
- `position/absolute-static-position-no-offsets` and
  `position/absolute-with-no-positioned-ancestor` — when the offsets are
  `auto` the box should keep its STATIC position; the engine puts it at
  y=0 (browser y=48 and y=34 respectively).
- `position/absolute-child-of-a-relative-inline` — a relatively positioned
  INLINE is a containing block; here the paragraph goes from one line to
  three.

**Display types with no implementation.**

- `display/table-cells-from-divs`, `display/table-with-anonymous-rows` — the
  CSS table display types on `<div>`s produce **one** draw-op, tagged
  `table`, sized 300×2, and no boxes for the divs at all. Two divergences in
  one: the display types are not laid out, and an element laid out as a
  table reports the wrong tag to the geometry axis.
- `display/contents-is-transparent` — the engine gives the box a real
  300×40 rect and lays its children out as blocks; the browser generates no
  box for it and promotes the children to flex items (7×20 each). One of
  this case's four boxes is not comparable by construction and is noted in
  the case itself.
- `display/flow-root-establishes-a-context` — `flow-root` does not establish
  a formatting context, so the first child's margin collapses through: the
  `<p>` is at y=14 in the browser and y=0 here.

**Table sizing algorithms.**

- `table/layout-fixed` — `table-layout: fixed` ignored: the browser gives
  147/147 columns in a 46px-tall table, the engine 163/9 in a 26px one.
- `table/colgroup-widths` — `<colgroup>`/`<col>` widths are ignored AND
  neither element gets a box: browser 186px table with 120/60 columns,
  engine 24px with 9/9.
- `table/th-is-centered-and-bold` — an explicit `width` on a table reaches
  the table, tbody and tr boxes (all 196) but is not distributed to the
  CELLS, which shrink-wrap to 49.3.
- `table/border-collapse` — not implemented; border-spacing is still
  applied, so the table is 30px tall against the browser's 26 (the widths
  happen to agree at 24).

**`direction: rtl` is parsed and not applied.**
`text/rtl-with-inline-elements` puts the `<b>` at x=227.5 in the browser and
x=42 here; `text/rtl-block-alignment` puts a 60px block at x=140 in the
browser and x=0 here.

**Inherited `line-height`: unitless is not a length.**
`text/unitless-line-height-inherits-the-factor` — `line-height: 1.5` on a
parent with a `font-size: 24px` child gives 36px lines in the browser and 21
here. Its deliberate pair `text/em-line-height-inherits-the-computed-value`
(`1.5em`, same markup otherwise) **passes at 21**, which localises the bug
precisely: the engine resolves the unitless factor against the DECLARING
element's font size and inherits the result, instead of inheriting the
factor.

**BFC detection reads `overflow` but not `overflow-x`/`overflow-y`.**
`overflow/x-hidden-y-scroll` — the round-ten rule that a scroll container
does not collapse margins with its children fires on the shorthand and not
on the longhands: the `<p>` is at y=14 in the browser and y=0 here. The
three shorthand overflow cases all pass.

#### Two things measured rather than assumed

- **`overflow/scroll-container-reserves-a-scrollbar` passes**, which is a
  fact about the ORACLE, not about the engine: this headless Brave uses
  overlay scrollbars, so a 200px `overflow-y: scroll` box has a 200px-wide
  child and there is no gutter to disagree about. The case stays in as a
  control; if the oracle configuration ever changes it will start failing
  and the reason will be recorded here.
- **Documents at scale are fine.** Six of the seven `doc/` cases — 24
  sibling blocks, 12 margin-collapsing paragraphs, 16 levels of nesting, 16
  levels of nesting each with 4px of padding, a 16-item list, 20 wrapping
  inline siblings, a 12-row table — agree with the browser on **every** box.
  Nothing accumulates. The seventh is unscorable for the list-marker reason
  below. This was worth measuring precisely because it was assumed.

#### The composites, and why they are not evidence

Seven cases are deliberately NOT isolating: a dashboard stat row, a login
form, a media object, a card with an absolute badge, a sticky header over a
list, a three-column grid page, a toolbar with an auto margin. They are page
shapes real sites are made of, and each one fails for reasons the isolating
cases above already name — `page/card-with-absolute-badge` is the padding-box
containing block (x off by 11 = padding 12 − border 1),
`page/toolbar-with-auto-margin` is `margin-left: auto` on a flex item (x=99
against 440.6), `page/login-form` is control metrics plus label layout.
A composite failing tells you the page is wrong; it does not tell you which
rule. Read them as regression cover, not as attribution.

### Round twenty: two more from the biggest cluster

`div h −20` (13 boxes) held two unrelated causes:

- **A grid item stretches to its track.** `align-items: stretch` is the
  default, so an item in a `grid-template-rows: 40px` track is 40px tall
  whatever its content needs; this engine left every item at its content
  height. That case went from 1/5 boxes to exact.
- **`overflow-wrap: break-word` was unimplemented.** A long unbroken string
  — a URL, a hash, a compound word — overflowed its column instead of being
  split to fit: a 90px column reported 40px of height where the browser
  needs 60. Now exact on the geometry axis.

The break-word case does, however, now FAIL the line axis, and that is
recorded rather than papered over: the browser measures one Range per WORD,
so a word broken across two lines still reports a single union rect and
clusters as one line, while this engine emits one text op per piece. The
line axis structurally cannot represent an intra-word break. Making the
engine stop breaking the word would "fix" the number and unfix the layout.

### Round nineteen: grid span, and relative on a flex/grid item

Both named by the round-17 corpus expansion, both small once measured.

`grid-column: span 2` declares only a WIDTH — the item stays auto-placed
and occupies N tracks, and the shared cursor resumes after it. It was
previously parsed as a placement request and would have been treated as an
explicit one.

`position: relative` on a FLEX or GRID item was never applied: the shift
existed only in block flow, a scope-cut documented since relative
positioning landed. Both cases now agree with the browser on every box.

### Round eighteen: flex-grow and flex-shrink

Real flexbox distributes a line's FREE SPACE across its items — positive by
`flex-grow`, negative by `flex-shrink` weighted by each item's base size.
This engine froze every item at its base size, so `flex-grow: 1` (the most
common flex idiom on the real web) did nothing at all and over-wide items
overflowed instead of shrinking.

The distribution was the easy half. The bug that made it *look*
unimplemented after it was written: the `align-items: stretch` pass
re-measures each item at the CONTAINER width, which silently undid the main
-axis sizing. The re-measure at the final main size now runs after it.
`flex/grow-fills-the-row` went from 1/3 boxes to exact.

Two unit tests that pinned the old no-shrink behaviour are updated: three
90px items plus two 20px gaps want 310px of a 292px content area, and with
`flex-shrink: 1` — the default — they shrink to fit rather than overflow.

### Round seventeen: an inline box is its OWN font's height

A `<span>` wrapping a `<b>` is 15px tall in the browser — its own 14px face —
while the bold run inside it is 18. This engine sized every nesting parent
by its tallest child, because the box rect was accumulated from each
fragment's metrics rather than the owner's. One rule, +22 boxes: geometry
89% → 90% on the 150-case corpus, cases fully clean 122 → 127.

### Round seventeen (b): the corpus grows again, 150 → 200

98% line / 90% geometry was saturation for the third time. 50 more cases in
territory still unmeasured: flex sizing beyond the defaults (`flex-grow`,
shrink, `align-items: flex-end`, `space-around`, wrap with gap), grid flow
and spans (`span 2`, explicit rows, `minmax`, nested grids), sticky with an
offset, overflow with explicit heights, min/max-height, margin collapsing
through a border, deeper inline nesting, mixed row/col spans in one table,
table inside flex, label wrapping a control, and ten larger page shapes
(sidebar + main, card grid with images, article with a figure, data table,
inline form in a paragraph, two-column text, header/nav/main, blockquote
with attribution).

Scores on contact: line 98% → 96%, geometry 90% → 83%. What the new cases
name, all now measured rather than assumed:

- `grid-column: span 2` is not implemented.
- `position: relative` is still not applied to a FLEX item (a scope-cut
  documented since the relative-positioning round).
- an `inline-block` wrapping a block box took the container width — the
  empty/single-element natural-width rules added last round lived only in
  the flex path, not the atomic one. Fixed here.

### Round sixteen: one baseline rule for every atomic inline

The `p h +6` cluster was one rule again. An atomic inline's baseline is its
own LAST LINE's baseline — top inset, half-leading, ascent — for everything
except a replaced box, which alone sits on the baseline. That single rule
covers an `inline-block` (a browser reports a line holding a 20px one as
20px, where the bottom-edge reading stacks the strut's descent underneath
and gives 26), a form control (21px, not 27), and a `<textarea>`, whose
last line is `rows − 1` lines further down.

`<textarea>` also gained its own height: `rows` lines (HTML's default is 2),
where every other control is one — 34px against a 21px input, and a 40px
line box around it.

And the harness stopped measuring only ASCII. `©`, `·`, `›`, `—` and friends
were falling back to a guessed advance, which put the first link of a footer
1.4px off and the second 6.4px — small, but a mismatch the engine was blamed
for and never made. The advance table now covers ASCII, Latin-1 and the
typographic codepoints real page furniture uses.

### Round fifteen: a cell with nothing measurable in it

Two clusters with enormous deltas (`td w +727`, `tbody w +759`, `tr w +759`)
turned out to be one missing rule with two faces: a box whose content has no
measurable natural width fell back to the CONTAINER width.

- An **empty** `<td>` took 782px where the browser gives it 2 (its padding),
  so a single empty cell made its table fill the page.
- A `<td>` holding a **nested table** did the same, for want of a rule for
  "a single element child": measure it.

And measuring it exposed the follow-on: a TABLE must be laid out rather than
recursed into, because it already shrink-wraps itself and recursing finds
its rows while losing its border-spacing (37px against the browser's 41).

The nested-table case now agrees with the browser on **all nine boxes**, the
empty-cells case on all six, and the geometry axis went 86% → 89%.

### Round fourteen: vertical-align, on that foundation

The first rule the metrics model made implementable. Measured rather than
looked up: Chrome raises a 14px `super` run by 5.66px and lowers a `sub`
one by 3.79px — 0.404em and 0.271em, the font's own superscript/subscript
offsets, which a browser reads from the OS/2 table and this engine takes as
measured platform values.

`sub { vertical-align: sub }` and `sup { vertical-align: super }` are UA
rules too — an author writes the tag, never the declaration — so without
them a subscript and a superscript sat on the same baseline as the text
around them, which is the entire visual point of both tags. A shifted box
carries its whole vertical span with it, so it grows the line box in that
direction; the corpus case went from a 21px line box against the browser's
29.45 to 28, with `sup` at 4.13 against 4 and `sub` at 11.55 against 13.45.

`top`, `bottom` and `middle` are deliberately absent: each aligns against
the FINAL line box, which is not known until every other box on the line
has been placed, so they need a second pass this file does not have. They
keep the baseline default — which is what every value did before.

### Round thirteen: the font-metrics model

Round eleven stopped at a named prerequisite rather than fitting constants:
a browser positions each inline box by the font's REAL ascent and descent
and takes their union, and this engine modelled neither. That prerequisite
now exists.

Measured first, as the stopping note asked for. Chrome on this machine:

| face | ascent | descent | content area |
|---|---|---|---|
| 14px monospace | 12 | 3 | 15 (not the 16.8 a 1.2em guess assumes) |
| bold 14px monospace | 14 | 4 | 18 |
| 24px monospace | 21 | 5 | 26 |
| 13.33px Arial (controls) | 12 | 3 | 15 |

Working the CSS line-box rule by hand with those numbers reproduces the
browser exactly: for `small <span style="font-size:24px">big</span>` in a
`line-height: 20px` container, the strut contributes
`[baseline−14.5, baseline+5.5]` and the 24px run `[baseline−18,
baseline+2]` (its half-leading is NEGATIVE, which is why it overflows
rather than growing the line), union 23.5 ≈ the browser's 24.

So the engine gained a `:font-metrics` theme hook — the vertical
counterpart of `:measure-text`, with the same bargain: a host that HAS real
metrics supplies them, a host that does not keeps this file's documented
1.2em approximation BYTE FOR BYTE. The harness supplies them (canvas
`TextMetrics`), and its own text boxes are converted from the engine's
em-box convention to the content-area one the oracle reports, so the two
sides describe the same box in the same coordinates.

It also forced a rule that only becomes visible once the vertical model is
real: **an atomic inline's baseline is not always its bottom edge.** A
replaced box sits ON the baseline, but a form control's baseline is its own
internal text's — which is why a browser reports a line holding an
`<input>` as exactly 21px, where treating the bottom edge as the baseline
adds the strut's descent underneath and gives 27.

Cases that are now exact where they never were: `<b>` inline boxes
(63,1,47.63,18 against the browser's 63,1,47.64,18), the mixed-font-size
line box (24, previously 20), the input line (21).

And the honest part: the aggregate went 87% → 86%. The remaining vertical
rules — `vertical-align` for `<sub>`/`<sup>`, and a `<textarea>`'s own
baseline — are still missing, and with a REAL vertical model they now show
up as mismatches instead of being averaged away by an approximation that
was wrong in a compensating direction. The model is the foundation those
rules need; the point of this axis is to measure the engine, not to protect
a number.

### Round twelve: form controls do not inherit the page font

`input w +7` had sat in the residual for six rounds with a plausible story
attached to it. Measured directly instead: an `<input>` inside a
`font-family: monospace; font-size: 14px` container computes to
**`Arial 13.3333px`** in Chrome — controls do not inherit the page font at
all — with `padding: 2px; border: 2px` of their own (a `<button>` gets
`6px` horizontal and `1px` vertical padding; a checkbox is a bare 13×13
square with `margin: 3px 3px 3px 4px` and no padding or border).

So the answer to "which side is wrong" was: the ENGINE, and not in the way
the number suggested — it was not 7px of arithmetic error but a missing UA
rule. The engine now carries that font and box as UA defaults, names the
family so a host can measure it (the harness measures a fourth face for
it), and sizes a control's content box by its font-size rather than by a
line box. Two general box-model bugs fell out of the same work: neither
block nor control height added the border, which `box-sizing: content-box`
puts outside the content box in both axes.

input 0/9 → 5/9 boxes, geometry 84% → 85%, cases fully clean 115 → 118.

Both follow-ups from that round are now closed. A `<button>`'s label is
measured in the CONTROL font and its width counts the UA *horizontal*
padding (6px a side) rather than the uniform value — charging the uniform
padding left it 10px narrow even after the font was right. And an atomic
inline carries its own margins: a checkbox's UA `margin: 3px 3px 3px 4px`
now places it at x=4 y=3, exactly where the browser puts it, where before
the margins were counted in the line's advance but never applied to the box
itself (the line breaker rebuilt the piece and dropped them).

Geometry 85% → 87%, cases fully clean 118 → 123.

### Round eleven: rowspan, and the rule behind it

`rowspan` is implemented: cells are assigned their [row col colspan
rowspan] by an occupancy walk, the rows below skip the columns a spanning
cell still holds, a spanning cell grows the last row it covers when the
rows cannot hold it, and its own box spans every row it covers.

The browser's expectation for the corpus case named the rule that made it
work: **a table cell's UA default is `vertical-align: middle`**, so its
content is centred in the cell box — which is exactly what makes a rowspan
cell sit BETWEEN the rows it covers rather than at the top of the first
one. The browser renders `tall` (rowspan 2) on its own line between `a` and
`b`; this engine had it beside `a`.

### Round ten: what the widened corpus was hiding

Four real rules, each found by attributing a delta cluster to its cases:

- **A box that establishes a formatting context does not collapse margins
  with its children.** `overflow: hidden` is the obvious one — it is *why*
  authors reach for it — and a flex or grid ITEM is the same, decided by
  the parent rather than by a declaration. This one cluster was `p y −14`
  and `div h −30.75` across a dozen boxes.
- **A caption participates in its table's width.** The table grows to fit
  the caption's MIN-content (its longest word) and the caption then wraps
  inside that width. Measured: `Caption text` gave a 24px table here where
  the browser reports 49, with the caption overflowing it.
- **Whitespace-only text runs are the space between inline elements.** The
  parser dropped them entirely, so `<a>one</a>\n  <a>two</a>` rendered as
  `onetwo` — with no way for layout to recover the gap. kotoba-lang/htmldom
  now keeps them; layout drops the ones that would form a stray row between
  blocks, because that decision needs the box tree the tokenizer cannot
  see. Geometry 81% → 84% on this alone.

### Round nine: widening the corpus again

The line axis had reached 99% and geometry 88% on 105 cases — which is
exactly when a corpus stops earning its keep. 45 cases were added in
territory the harness had never touched: selectors and the cascade
(specificity, `!important`, `:nth-child`, `:not`, attribute presence,
custom properties), overflow and scroll containers, `z-index` stacking,
`position: sticky`, `direction: rtl`, letter/word spacing, `text-indent`,
nested tables, `rowspan`, richer forms, and six larger page shapes
(pricing grid, comment thread, breadcrumb, table of contents, hero with a
floated image, form row).

Both scores fell, which is the point: line 99% → 94%, geometry 88% → 78%.
Fixing what the new cases exposed brought them back to 98% and 79% on the
larger corpus. What they exposed:

- **`<mark>`, `<del>`, `<ins>`, `<meter>`, `<output>`, `<progress>`, ruby
  tags were not inline-level**, so any of them broke the sentence around it
  into stacked rows.
- **An atomic inline with MIXED content had no max-content width.**
  `<button>save <b>now</b></button>` fell back to the container width, so a
  button with any markup in its label swallowed the whole line and pushed
  the text after it onto the next one.
- **`&rsaquo;` and friends painted as literal source text** — a breadcrumb
  (`Home &rsaquo; Docs`) showed the entity. Another 25 page-furniture
  entities landed in kotoba-lang/htmldom.
- Harness: **an `inline-block`'s contents are their own formatting
  context**, exactly like a form control's, and must be excluded from the
  line comparison on both sides. The engine had that case geometrically
  right (2/2 boxes) while the line metric scored it wrong.

### Round eight: block-in-inline

An inline box containing a BLOCK box is now split around it, as real CSS
does: `<p>text <span>a <div>b</div> c</span> end</p>` renders as `text a` /
`b` / `c end`, three lines, with both fragments still styled by the same
`<span>`. This engine used to refuse to flow the whole span once it saw the
block child, so the paragraph fell apart into five stacked rows. The split
is expressed as data — the element is replaced by a clone per run of inline
children, with the block children hoisted between them — so nothing
downstream needed a new concept. Bounded v1: the block must be a DIRECT
child of the inline element.

### The remaining line-structure failures

`page/hero-with-floated-image` was written up here as the float band's
documented v1 boundary. Round twenty-two measured it and it was neither:
the engine's three lines were correct and `engine-lines` was discarding
them, because its inside-a-replaced-box test counted the right edge as
inside. Fixed there.

The one below is deliberate:

`position/fixed-leaves-flow` stays red and is NOT chased. `position: fixed`
takes the box out of flow and OVERLAPS the content beside it, so "which line
is this word on" has no single right answer — the browser's own word rects
for the fixed box and for the flow text occupy the same band. The GEOMETRY
axis, which asks the well-defined question (where is the box, how big is
it), agrees with the browser on every box in that case. Contorting the
engine to satisfy an ill-defined comparison would make the number better
and the engine worse.

### Still open on the geometry axis

`input` w is now within ~7px rather than ~650: the remainder is that a
browser does NOT inherit the page font into form controls (Chrome UA gives
them 13.33px Arial), so their intrinsic width comes from a font this
harness never measures.

### Known divergence the LINE axis does not see

A control's INNER text (a `<button>`'s label, an `<input>`'s value) is
excluded from the line comparison on both sides, because it belongs to that
control's own formatting context rather than to the line being measured.
That exclusion hides a real divergence found on the way here: this engine
paints a button's label at the top inset of its box, while a browser
centers it vertically. Measuring that needs a different axis — comparing
the control's own box and its content position — and is a candidate for the
next corpus dimension rather than something to pretend the current one
covers.

### Bugs found

The harness has already paid for itself twice. It found that a
`display: none` element in the middle of a sentence split the surrounding
text into two one-child inline runs, stacking `keep`/`this` on separate
lines where every real browser puts them on one. That bug was invisible to
497 passing unit tests. Fixed in the same change, with regression tests.

It also caught, via the downstream `kotoba-lang/browser` suite, an arity
error in the new `<select>` intrinsic-width path that this repo's own 502
tests never reached — a reminder that cssom's consumers exercise shapes its
own corpus does not.

## Some cases are unscorable on the LINE axis, on purpose

Generated content (`::before`/`::after`, list markers) is not DOM text — a
real browser paints it from the box tree and no `Range` can reach it, while
this engine synthesizes it as real text. Those cases are marked
`:oracle/blind true`, excluded from the LINE score, and printed, rather than
silently counted as failures. Their geometry and computed style are still
scored — only the text-per-line comparison is blind. Their line-level
correctness is covered by unit tests.

12 of the 292 carry the marker as of round twenty-one; the two added that
round are `display/list-item-on-a-div` (a `<div>` made a list item generates
a marker) and `doc/long-list-of-items` (16 `<li>`s). 22 of the 501 carry it
now.

The two most recent are worth naming, because they show the marker being
earned rather than granted: `inline/q-adds-quotation-marks` and
`inline/nested-q-uses-the-second-quote-level` scored on the line axis for
the whole of their life and stopped the day the engine learned to generate
the quotes a `<q>` gets from the UA sheet. Both sides used to read
`he said hello loudly`, for the same wrong reason — neither produced a
quotation mark at all. Now the engine reads `he said “hello” loudly` and
the oracle still cannot: no `Range` reaches a `::before`. Their geometry
went 0/3 boxes to 3/3 in the same change.

## How the oracle is driven (measured, not assumed)

Brave is the intended oracle, and as of 2026-08-04 it is again the one that
actually runs — over **CDP**, not `--dump-dom`.

`--dump-dom` is a *headless-shell* facility, and on **Brave 151.1.93.129**
it is simply dead: zero bytes and no stderr on a 200-case page, on
`<p>hello</p>`, in `--headless=old`, `--headless=new` and plain
`--headless`; `--screenshot` writes no file either. Chrome 150 on the same
machine dumps fine. For a while the harness therefore fell through to
Chrome on every run — the same engine, so the numbers were sound, but the
named comparison target had quietly stopped being measured.

What Brave does still answer is the DevTools protocol. `conformance/
cdp_dump.cljs` launches it with `--headless=new --remote-debugging-port=0`,
reads the port back out of `DevToolsActivePort` (so parallel runs cannot
collide), navigates, polls `Runtime.evaluate` for the measurement block and
kills the browser. `run.cljs` tries CDP first and `--dump-dom` second, and
prints which transport produced the numbers — `oracle: … (cdp)` — because
"the oracle was Brave" and "the oracle was Brave over CDP because its
`--dump-dom` is dead" are different facts about a measurement.

Two things fell out of this that were worth the change on their own:

- **It is ~6x faster** (12s vs 79s for the full corpus), because the
  `--dump-dom` path depends on a headless Chromium exiting, which it never
  does — every run burned its whole SIGKILL timeout.
- **Brave and Chrome were verified byte-identical over CDP** on all 202
  measured blocks, which is the concrete version of "same engine, shields
  do not change layout" that was previously only asserted.

Getting 124 KB out of the child process needed a file, not a pipe: `println`
loses the tail (Node buffers pipe writes; `process.exit` drops the rest), a
single `writeSync` to a non-blocking pipe writes 65536 bytes and reports it,
and looping on that count throws `EAGAIN`. The `--dump-dom` path already
wrote to a file for an unrelated reason (Chromium's children hold stdout
open, so a pipe never reaches EOF); both paths now do.

## The paint-order axis (added 2026-08-04)

The three original axes all measure SIZE and POSITION. None of them can see
**stacking**: which element is on top where two overlap. `z-index`, negative
`z-index`, later-sibling overlap and `pointer-events` were invisible to the
whole harness, so a paint-order regression could not fail anything.

The axis samples a 5x5 grid of interior points per case and asks each side
which element is at that point: `document.elementFromPoint` in the browser,
and in the engine the LAST `:node` draw-op whose HIT REGION contains the
point — its `:hit` rects when it has them, its box otherwise. That
distinction is round thirty-one's; before it the box was the only answer a
`:node` op could give, and three quarters of this axis's residual was the
places where a browser's reported box and its hit region are different
rectangles.
Reading the emitted op vector back is deliberate — that vector *is* the
engine's paint order, so the question asked is "given what this engine told
a host to paint, what would a user click?". Re-deriving stacking inside the
harness would test the harness author's model of the engine instead.

First measurement: **6978/7285 points = 96%**, 238/292 cases fully agreeing.

Two things it found immediately:

- `:stacking/negative-z-index` agrees on **every box** (geometry 12/12) and
  still disagrees at 5 points. That is the whole reason for the axis: an
  engine can get every rectangle right and still paint them in the wrong
  order.
- The rest of the residue lands on cases already failing on geometry —
  `:page/two-column-text`, `:position/absolute-inside-table-cell`,
  `:form/fieldset-and-legend` — where a box in the wrong place naturally
  puts the wrong element under a point. Those are not new bugs and are not
  counted as such.

Both sides wrap each case (the page in `.kotoba-case`, `cascaded-document`
in `<div id="root">`), and neither wrapper is an answer. Scoring one against
the other made every point landing on a case's own top-level text read as a
disagreement — text nodes are not elements, so the browser returns the
containing element, which there is the wrapper. That single asymmetry was
2246 of 2523 disagreements on the first run, i.e. the axis's first number
was 65% and meaningless. Points outside the viewport, or on page chrome, are
counted as skipped rather than scored.

## An axis that measured nothing says so

If any axis compares zero values, the run prints `UNMEASURED:` with the
oracle and transport, appends nothing to the ledger, and exits 3. Measured
2026-08-04: two runs of the same checkout minutes apart printed
`COMPUTED STYLE 0/0 (0%)` and `8501/9982 (85%)` — the oracle had returned no
styles once, and only the implausibility of the number gave it away. A
silent zero is worse than a crash: it enters the ledger as a data point and
reads as a regression forever after.
