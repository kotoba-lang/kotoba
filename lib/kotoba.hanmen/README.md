# hanmen（版面）

**A page, as placed marks.** 版面 is the composed area of a printed page — the
type and rules as they sit on the paper, not the text that went into them. This
library is that value: a size, a rotation and a vector of marks with
coordinates, plus one producer (PDF) and one drawer (SVG).

Portable `.cljc`, one dependency (`org-iso-pdf`), no host effects. Reading a
file is the caller's capability to spend; nothing here opens anything.

```clojure
(require '[hanmen.pdf :as hpdf] '[hanmen.svg :as svg])

(def page (hpdf/page-at (pdf.core/parse bytes) 0))
(svg/->svg page {:fit-to [900 1200]})   ;; => "<svg …>" — inert, themeable
```

## Why this exists

`org-iso-pdf` answers what is *in* a document. `pdf.core/extract-text` returns
the strings shown between `BT` and `ET` — enough to search, and nothing to look
at, because it has no text matrix. A viewer is entirely a question of *where*.

`kotoba-lang/app-preview` had the other half: a catalog of pages with sizes,
rotations and text counts. Between "what a page weighs" and "what a page says"
there was no value describing what a page *looks like*, so there was nothing to
draw.

## Three decisions

**The coordinate space is the reader's.** PDF puts the origin at the bottom
left with y up; SVG, Canvas and every raster buffer put it at the top left with
y down. The flip happens once, here, because a viewer that flips is a viewer
that can flip twice — and an upside-down page is a bug only a human eye catches.
Rotation is applied for the same reason: `:page/width` is the width **as seen**.

**A run's start is exact and its width is optional.** Where text begins comes
out of the matrices and is arithmetic. How wide it is depends on the font's
`/Widths`, which a document only sometimes ships. When they are there the run
carries its measured width and a drawer can make its own font occupy exactly
that space; when they are not, the width is **absent rather than estimated** —
an estimate would be indistinguishable from a measurement downstream and wrong
by a different amount on every document.

**A form XObject is run, not outlined.** A form is a content stream with its
own `/Matrix` and `/Resources` — a figure, a stamp, a letterhead — and a viewer
that draws its bounding box instead produces a page of empty rectangles.
Measured: across 30 real PDFs this turned 1,957 dashed boxes into marks, and
one 24 MB document went from *"scanned, no text"* to 2,932 text runs. Recursion
is depth-bounded and cycle-guarded, and where it stops it says so.

**What still cannot be drawn is placed and marked, never skipped.** A shading, a
`/Type0` run with no `/ToUnicode`: each becomes a `:frame` with a label and a
reason — and the label names the CMap that would decode it (`Adobe-Japan1`), so
the answer is something a reader can act on. A page that quietly omits a mark
looks exactly like a page that is complete, and `hanmen.svg/emit-item` throws on
an unknown kind rather than dropping it, so a fifth item kind cannot be added on
one side only.

## The SVG is safe inside `default-src 'none'`

Hosts that serve uploaded bytes keep SVG out of their inline allowlist on
purpose — an SVG is XML, it may carry `<script>`, and a browser runs it when it
is a document. This emitter is the other thing wearing that extension: markup
generated from a closed vocabulary of three item kinds, where document content
only ever becomes an escaped text node or an escaped attribute *value*. There
is no path from a file to an element name.

`serialize` enforces that a second time — an element outside `allowed-elements`
or an attribute outside `allowed-attributes` throws instead of being written.
No element here takes a URL, so the fragment loads nothing and the host's CSP
does not have to be widened to show a page. Deciding what a page may load is a
decision on its own, not a side effect of adding a viewer.

## Paths, not only rectangles

`re … f` was the only path this understood, so a chart, a logo and a
signature were all equally invisible. Every construction operator is run now
— `m` `l` `c` `v` `y` `h` `re` — and every painting one decides what the
accumulated path becomes. Across 47 real documents that is **28,966 paths
that previously produced nothing at all**.

A path made only of rectangles still becomes `:rule`s, one per rectangle,
because `re … f` is most of what documents draw and a box is worth more to a
consumer laying marks out than a closed four-segment path. Mix a rectangle
with a curve and it is one `:path`.

`d` is SVG path data, already transformed into reader space — every drawer
this could target accepts it, the grammar is tiny and closed, and a segment
vocabulary would be a second spelling every consumer has to translate back.
The bounding box is the control hull, so it can be larger than the ink and
never smaller: the safe direction for a value whose job is deciding what to
throw away.

Fill and stroke carry separate ink, because lower-case colour operators set
one and upper-case the other — treating them as one is how a hairline table
border ends up the colour of the cell behind it.

## Constant alpha reaches the ink

`gs` was ignored entirely, and after the drawing operators it is the most
common thing in the corpus: **1,100 calls across 86 documents, 217 setting a
stroke alpha below 1**. A 30%-alpha hairline drawn at full ink is a black
line where the document has a grey one — and every one of them came out the
same shade. Measured: distinct ink levels **319 → 485**.

`/ca` and `/CA` multiply into ink rather than becoming a separate channel.
That is exact for a single layer on paper — 50% of black ink IS grey — and
an approximation the moment marks overlap, which is what a real compositor
is for and what this is not.

Two things this needed that were wrong on their own:

- The initial colour is now **black, per the spec**, not nil. Starting at nil
  made *no colour operator yet* and *a colour this cannot read* the same
  value, and lost every alpha set before the first colour — which is most of
  them, because `gs` usually comes first.
- A form XObject looks up **its own** `/ExtGState` and `/Pattern`, not the
  page's. A form that names `/G1` means its own, and reading the page's is
  how a stamp ends up drawn at the alpha of whatever the page called `G1`.

A fill whose colour is a **pattern** now says so (`:item/pattern`). Before,
`scn` with a name left the previous colour, so the shape was filled in
whatever happened to be set last — an arbitrary colour presented as the
document's.

## The clip is honoured, as a box

`W n` marks the current path as the clip and ends it without painting. A
reader that ignored it draws what the document hides — a caption from under
a cropped figure, a row from a table that was scrolled. Measured across 47
documents: **112 text runs the document does not show**.

The **path** is carried, not only its box. `:page/clips` holds the regions
and each mark names the one it is under; `hanmen.svg` emits them as
`<clipPath>` and wraps each run of marks in a `<g clip-path>`. Measured
across 86 documents: **379 clip regions over 4,399 of 11,549 marks**.

Nested clips point at each other rather than sharing an element, because two
paths inside one `clipPath` are **unioned** — the opposite of what a document
that clipped twice meant. Nesting is how SVG intersects.

The grouping is per *run* of marks, not per clip: a clip turns on and off
between marks, and gathering all of one clip's together would reorder the
page. Painting order is the one thing a page cannot lose.

The **box** is still tracked and still used to drop marks the clip cannot
show, because a consumer that lays marks out itself needs an extent and
cannot intersect a cubic. That test stays wholly-outside-only, and the
direction of its error is chosen: showing slightly too much is a mark drawn
where the document drew nothing; showing too little is a mark **missing**,
and a reader cannot tell a missing mark from a document that never had one.

The clip is part of the graphics state, so `q`/`Q` save and restore it —
including restoring it to *absent*, which `merge` alone cannot do and which
would otherwise leave a narrowed clip swallowing the rest of the page.

## Ink, and text that is knocked out of it

Every fill-colour operator records ink — `g`, `rg`, `k`, and the
space-dependent `sc`/`scn`, chosen by operand arity because that is what
actually distinguishes them. Tracking only the first two left a CMYK fill
recording nothing and drawing at full strength, which is the PDF default and
therefore not obviously wrong until you look at a poster.

Text carries ink too. It was the one mark that did not, which is invisible on
the documents everybody has — black on white — and wrong on a heading
reversed out of a dark panel, where it drew the text in the same ink as the
panel beneath it. Low-ink text paints in `var(--hanmen-paper, canvas)`: a
threshold rather than an opacity, because text at 0.3 of the ink is not faint
text, it is unreadable text.

## It picks no colour and no font

Everything paints in `currentColor` under a class. The host's tokens decide
what the ink looks like, which is the only way one rendering is right in both
light and dark — a document's black is not the reader's black on a dark page.
Ink *density* survives (a 60% grey rule stays lighter than a black one, through
`fill-opacity`), because that difference is the document's meaning and the
absolute colour is not. Add `hanmen.svg/stylesheet` to the host's stylesheet.

## Images are the host's decision, and the default is inert

An `:image` item carries **the index of the image on its page, never its
name** — a name is file content and would end up in a URL; an integer cannot
carry anything a document wrote. `hanmen.pdf/page-images` resolves an index
back to bytes **through the same traversal that assigned it**, because the
page's `/XObject` dictionary is in resource order and the two agree only on a
document that never invokes a form.

A `DCTDecode` XObject **is** a JPEG. A host can serve those bytes as one with
no decoder at all — 12 of the 57 images in the sample. The rest are raw samples
and `:media-type` is nil, which says somebody has to encode them rather than
guessing a type that arrives at a browser as a broken image. `:bits`,
`:colorspace` and `:palette` come with them, because a byte count alone
cannot tell 16-bit gray from 8-bit RGB — they are the same bytes per pixel.
Reported, never converted: turning CMYK into RGB is a decision about what a
colour means, and this library does not have the host's answer.

`hanmen.svg` draws an image only when the caller passes `:image-href`, and
refuses anything that is not a same-origin path:

```clojure
(svg/->svg page {:image-href (fn [{:keys [index]}]
                               (str "/api/…/pages/3/images/" index))})
```

Without it the region is outlined like a frame and **the fragment loads
nothing**, so a host that has not decided its CSP is not forced to.

## One `Tj` per glyph is a real thing producers do

An audit-report cover emitted **52 runs for one line**, so `text-of` returned
`["O" "p" "e" "n" …]` — not a search index and not a quotation. Drawn in a
font that is not the document's, each glyph at its own document x, it read as
`Cont r act s`, and a reader blames the renderer.

`coalesce` joins runs that are exactly contiguous — the pen's end position is
known from the advance, so it is an equality test and not a guess. **Nothing
is ever inserted between them.**

That is a reversal. An earlier version put a space back whenever the gap
looked like one, and on a real cover page it produced
`F o r m  a l V e r i f i c a t i o n`: a space between every pair of
letters. The gaps on that page formed one continuous spread with no break
anywhere, so no threshold separated letter-spacing from a word space — every
choice invents characters somewhere.

The root cause was worth more than the heuristic. The advance was scaled by
the CTM but **not by the text matrix**, so a producer that sets `Tf 1` and
sizes with `Tm` — extremely common — got a width a whole font size too
small: 0.61 where the glyph advanced 14.90. Every run looked separated from
the next. With both matrices applied the glyphs are flush and join into
words on their own.

Measured across 45 documents: **6,289 fabricated space characters removed**,
and the pages still read as words (`Formal`, `OpenZeppelin`) rather than
letters. A caller that wants a line joins the runs itself — `reading-text`
does, which is a presentation choice made at the edge rather than a
character smuggled into the model.

## Reading order is a guess, kept apart from the fact

`text-of` is what the document says in the order it said it. `reading-order`
groups into columns and sorts down the page and across the line, rounding
baselines into bands so a superscript does not jump the word it belongs to.
Two columns are inferred only when both halves carry a real share of the text
and almost nothing straddles the gutter; three are never inferred, because
nothing in the measured sample had three and a heuristic that can produce an
unchecked answer will produce it on somebody's invoice.

A caller that needs the fact should not have to opt out of the guess, which is
why these are two functions.

## What it does not do

- **No raster decoding.** `FlateDecode` samples come back raw; encoding them to
  something a browser renders is the host's job (`kotoba-lang/org-w3-png`).
- **No shadings, and no soft masks or blend modes.** Measured at **zero
  occurrences** across 86 documents — `sh` never appears, no `/Shading`
  resource, no `/SMask`, no non-normal `/BM`. Code for a feature nobody can
  test against real files is code nobody should trust.
- **A tiling pattern is marked, not tiled.** Running one means deciding how
  many times, and a 2pt tile over a page is thousands of copies.
- **CID→Unicode without `/ToUnicode` needs a table from the host.** Measured across 160 documents and
  576 `/Type0` fonts: 549 ship one and are read; 25 do not and are
  `CIDFontType0C`; 2 have no embedded font; **zero** are the SFNT case an
  embedded-`cmap` fallback would have fixed. Bare CFF has no `cmap` table, so
  decoding those needs its charset plus a registry CMap resource
  (Adobe-Japan1-UCS2 and siblings), and neither exists here yet. The frame
  names both the ordering and the font kind so the next person does not
  repeat that dead end. `opentype.cmap` was written for the fallback and is
  deliberately NOT wired in — a dependency for a path that fires on zero of
  576 fonts is not a dependency.
- **No zoom or pan.** `fit` answers the one number a server-side render needs.
  Viewport gestures are `kotoba-lang/canvaskit`'s subject.
- **No writing.** A viewer that can rewrite what it is showing is a different
  program.

## Test

```sh
kbb -M:local:test   # sibling checkouts
kbb -M:test         # pinned git deps
kbb -M:lint
```

73 tests / 253 assertions. Every placement assertion is a coordinate against a
PDF the test wrote, not a rendering somebody looked at.

Measured out of sample against 30 real PDFs: 12,584 text runs, 2,083 rules, 57
images, **0 XObject regions left undrawn**.
