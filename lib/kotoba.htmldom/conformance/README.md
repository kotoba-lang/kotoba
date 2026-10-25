# Parser conformance: htmldom.core vs a real Blink browser

Differential testing against a real browser, because unit tests can only
check what someone thought to assert. This parses the same markup through
`htmldom.core/parse-into-document` → `kotoba.wasm.dom/tree` and through a
real headless Chrome, and compares the **tree shape** the two built: element
tag names and nesting depth in document order, plus text nodes normalised
for whitespace, plus comments.

```bash
kbb --backend sci --classpath "src:../dom-gpu/src:../cssom/src" conformance/run.cljk \
  [--browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"] \
  [--only table/] [--verbose] [--ledger path/to/ledger.edn]
```

`--verbose` prints the tree fragment either side of each first divergence,
which is usually enough to attribute a failure without opening a REPL.

This exists because the repo's README says *"WHATWG HTML compatibility: not
a goal (trusted subset only)"* and nothing ever measured how far from a
browser that actually is. The sibling `kotoba-lang/cssom` repo measures its
**layout** the same way and that harness has repeatedly found real bugs;
this is the parser's own equivalent, and the first run found two.

## Result

**Tree shape: 115/122 = 94%.** The first run, on 2026-08-04 against the
unmodified parser, was 82/100 = 82%; the corpus has grown since, so the two
numbers are not directly comparable — the map underneath them is the point.
The two most recent changes, each measured on the corpus as it stood before
it: the reconstruction fix 102/113 → 104/113 (+5 cases), then scope markers
109/118 → 111/118 (+4 cases). Per group:

| group | | | |
|---|---|---|---|
| attribute | 12/12 | 100% | |
| eof | 8/8 | 100% | after the tag-open fix; was 3/8 |
| form | 4/4 | 100% | |
| list | 6/6 | 100% | |
| omission | 11/11 | 100% | after the reconstruction fix; was 5/8 |
| paragraph | 7/7 | 100% | |
| rawtext | 9/9 | 100% | |
| table | 25/25 | 100% | after foster parenting then markers; was 12/16 |
| whitespace | 5/5 | 100% | |
| formatting | 12/13 | 92% | |
| entity | 7/8 | 88% | after the nbsp fix; was 6/8 |
| misc | 4/5 | 80% | |
| selfclose | 4/5 | 80% | |
| **comment** | **1/4** | **25%** | structurally impossible today |

**Attributes** (a secondary axis, see below): 366/367 comparable elements
carry exactly the browser's attribute map.

82% on the first run was already higher than the repo's own framing would
predict, and that was a real finding: optional end tags, implied `<tbody>`,
misnested formatting, raw text, entity decoding and attribute tokenization
were in far better shape than "trusted subset only" suggests — the parser
had quietly grown most of an in-body insertion mode. The remaining failures
are not scattered; they are two causes.

### 2026-08-06: the parser collapses no whitespace at all

This parser used to collapse runs of spaces and tabs into one space as it
built text nodes, on the reasoning that space collapsing is HTML-structural
while newline handling is CSS. An earlier round had already split that
belief in half — it stopped destroying newlines, because
`white-space: pre-line`/`pre-wrap` need them — and kept the other half.

The other half is also wrong, and one probe run says so.
`conformance/ws_probe.cljk` reads text nodes back **codepoint by
codepoint**, with no normalisation, next to the same markup's rendered box.
Brave 151, 2026-08-06:

| markup | text node |
|---|---|
| `<div>   a   b   </div>` | `SP SP SP a SP SP SP b SP SP SP` |
| `<div>a⇥b</div>` | `a TAB b` |
| `<p>a&nbsp;&nbsp;b</p>` | `a NBSP NBSP b` |
| `<div>\n  <p>a</p>\n</div>` | `LF SP SP` between the two blocks |

Nothing is collapsed. A browser reaches the rendered result by collapsing at
**layout** time, from `white-space`, which is CSS — and a parser cannot see
CSS. The whitespace this parser genuinely drops is one rule, not a class:

- **the single leading U+000A after a `<pre>`/`<textarea>` start tag.**
  Measured to be exactly one and exactly first: `<pre>\nx` is `x`, but
  `<pre>\n\nx` is `LF x` and `<pre> \nx` is `SP LF x`.

and one rule it REWRITES rather than drops, which is now implemented where
it belongs:

- **CR and CRLF become LF** (WHATWG 13.2.3.5, input stream preprocessing).
  `<div>a\r\nb</div>`, `<pre>a\r\nb</pre>` and `<pre>a\rb</pre>` all give
  `a LF b`, and the `<pre>` shapes render 40px tall — a real line break.
  Before this, a CR outside a `<pre>` became a SPACE (it was in the
  collapsing class) and a CR inside one survived as a literal U+000D. It
  runs on the source before tokenizing, which is the only place that can
  reach `<pre>` and raw-text content.

Everything else survives, including where the tree builder is actively
moving nodes around: `<table>\n<tr>` keeps its newlines *inside* the table,
and `<table> x <tr>` fosters the whole run out because it is not
whitespace-only — which is exactly what `foster-parented-text?` already
encoded.

**This axis does not move: 139/139 before and after.** That is the correct
result rather than a disappointing one — this harness normalises whitespace
inside text on both sides and compares only that whitespace-only *nodes*
land in the same places, and nothing about where a node lands changed. The
axis that can see it is the sibling **cssom** corpus, where three cases had
been sitting red since 2026-08-05 with a note naming this parser as the
blocker: a `<span style="white-space: pre">   indented</span>` reached
layout as `" indented"` and a tab reached it as a space, so the characters
were gone before CSS could be applied to them. Those three now report
77/63/35 px — the browser's numbers exactly — and **nothing else in that
597-case corpus moved**.

Two tests here changed, and both changed because the browser was asked
rather than because a convention was revised:
`ordinary-elements-collapse-space-runs-but-keep-newlines` became
`ordinary-elements-keep-every-whitespace-character` (the assertion is now
the source string itself), and the half of `nbsp-survives-whitespace-
collapsing` that asserted *"ordinary spaces and tabs still collapse"* now
asserts that they arrive verbatim. `preserve-whitespace-context?` is gone:
it existed to answer "is this a context where text stays verbatim", and
every context now is.

### 2026-08-05: the implied `<colgroup>`, found by a DOWNSTREAM corpus

A bare `<col>` — one with no `<colgroup>` written around it — was left as a
direct child of the `<table>`. Real HTML5's "in table" insertion mode
inserts a `colgroup` with no attributes and reprocesses, and this parser
had the `<tbody>` half of that scaffolding but not the column half.

It was not found here. It was found by **cssom's** conformance corpus,
whose geometry axis reported one `colgroup` box Brave has and that side had
not, and whose computed-style axis had to EXCLUDE 14 values because the two
sides disagreed on how many `colgroup` elements existed. Measured in Brave
151 before implementing anything, by assigning each shape to `innerHTML`
and walking the result:

| markup | Brave |
|---|---|
| `<table><col><col><tr><td>a` | one `colgroup` holding BOTH cols |
| `<table><col><col><col><tr><td>a` | still one, holding three |
| `<table><colgroup><col></colgroup>…` | untouched — nothing synthesised |
| `<table><colgroup></colgroup><col>…` | TWO colgroups |
| `<table><tr><td>a</td></tr><col>` | `tbody`, then a SIBLING `colgroup` |
| `<table><thead>…</thead><col><tbody>…` | thead, colgroup, tbody |
| `<table><caption>c</caption><col>…` | caption, colgroup, tbody |

All seven fall out of two lines: a `:col` entry in `table-clear-targets`
stopping at `:colgroup` **and** `:table` (so consecutive cols share a
group, and one arriving later pops back to table level), and a branch in
`maybe-insert-implied-table-structure` that opens a `colgroup` when the
stack top is the table itself. Tree shape 137/137 → **139/139** with two
new cases; downstream, cssom's geometry went 1722/1766 → 1723/1766 and its
14 excluded computed-style values became 14 comparable ones that agree.

## The two causes, in order of size

**1. Comments have no node type (3 cases).** `kotoba.wasm.dom` knows only
`:element` and `:text`; `tokenize` therefore discards comments entirely.
Every case with a comment in it diverges, and the divergence cascades —
which is why the harness special-cases the category (see
`divergence-category`) instead of reporting the shifted text that follows.
Fixing this needs a change in `kotoba-lang/dom-gpu`, not here.

**2. Individually rare spec behaviours (4 cases).** `</br>` is treated as
`<br>`; `<a>` inside `<a>` closes the outer one (the `a`/`nobr` special
case, listed as deferred in the namespace commentary); `<body>` in flow
content is ignored (there is no html/head/body model at all — an L3
architectural change); `&notit;` expands to `¬it;` because a browser matches
the longest named reference even without a semicolon.

## What the parser fixes were, and why they were fixes

Each was found by this harness, each has its evidence recorded in a code
comment at the change site, and each left the test suite at 0 failures.

**Bare `<` in prose was fabricating elements and deleting text.**
`<p>1 < 2 and 3 > 4</p>` tokenized to a start tag named `2` with an
attribute `and`, and `2 and 3 >` disappeared from the document: the scan
took the `<` before ` 2` as a tag open and found the `>` after `3` as its
terminator. HTML5's tag-open state only enters markup for ASCII alpha, `/` +
alpha, `!` or `?`; anything else emits the `<` as an ordinary character.
`markup-start?` now implements exactly that, and `tokenize` keeps a literal
`<` inside the surrounding text run so it produces one text node rather than
splitting it. The same change made an unterminated tag at EOF drop the
partial tag (HTML5's `eof-in-tag`) instead of leaking `div class="x` into
the document as visible text. Four cases, `eof` 3/8 → 8/8.

**`&nbsp;` was being decoded and then destroyed.** Text collapsing used
`[^\S\n]` — "everything `\s` matches except newline" — and `\s` also matches
U+00A0. So `&nbsp;`, correctly decoded to U+00A0 a moment earlier, was
rewritten straight back to a collapsible U+0020: the browser reported
codepoints 97/160/98 for `<p>a&nbsp;b</p>` and this parser 97/32/98. That
destroys the only thing `&nbsp;` exists to do, and CSS is explicit that
U+00A0 is not collapsible white space. The class is now spelled out as
HTML's own ASCII whitespace set minus the newline this parser deliberately
keeps.

**Tables did not foster-parent, and a bare `<td>` got no row.** Content that
is not allowed in a table — text, a `<div>`, a formatting element — must be
inserted *before* the table in the table's own parent (WHATWG 13.2.6.1,
"the rules for inserting a node into a foster parent"); it was staying
nested inside the table instead. `htmldom.core` now reads the spec's
foster-parenting condition off the stack of open elements rather than off
insertion modes it does not have: the insertion point is table structure
exactly when the current node is `table`/`tbody`/`thead`/`tfoot`/`tr`, which
is the set §13.2.6.1 itself tests. Every tag's allowed/fostered status was
measured one shape at a time in Brave rather than read off the prose,
including the two the prose makes easy to miss — a whitespace-only run stays
*inside* the table (but `&nbsp;` does not, since U+00A0 is not ASCII
whitespace), and `<input type=hidden>` stays while every other input goes
out. Three companion rules came with it, each measured: a table-structure
start tag clears the stack back to its own context (without which a
foster-parented element left open swallows the rows), a bare `<td>` gets an
implied `<tr>` as well as the implied `<tbody>`, and a `<table>` inside
table context closes the open table rather than nesting. `table` 12/16 →
20/21, with the one residual being cause 3 above.

**"Reconstruct the active formatting elements" ran for every start tag.**
WHATWG takes that step for character tokens and for the "any other start
tag" rule, but a large minority of start tags carry their own "in body"
rule and those rules do not list it. `parse-into-document` took it
unconditionally, so `<p>lead <em>emph <ul>` reopened the `<em>` and nested
the `<ul>` inside it, where a browser makes the `<ul>` a sibling at depth 0.
The whole `omission` residual was this, and the table insertion modes
already carried the equivalent exemption (`inserted-by-table-mode?`), so the
shape of the fix was known.

What was *not* known was the rule. The obvious reading — "the block-level
tags that close an open `<p>`" — is wrong in both directions, and the
difference was measured rather than argued: 93 tags were probed one at a
time in Brave with `<div><em>x</div><TAG>`, a shape where the `<em>` is in
the active formatting list but off the stack, so a reconstructing tag lands
*inside* a reopened `<em>` and a non-reconstructing one stays a sibling. 58
came back as siblings, 25 nested, and 10 produced an empty tree because the
browser drops the token outright (`html`, `head`, `body`, `frameset`,
`frame` and the stray table-structure tags — which is why those are *not* in
the set: an ignored token measures nothing about reconstruction). The set is
**wider** than the p-closing tags —
`li`/`dd`/`dt` reach a `<p>` through their own rules rather than
`auto-close-tags`' `:p` entry, and `textarea`, `iframe`, `noembed`,
`plaintext`, `param`/`source`/`track`, `rb`/`rt`/`rp`/`rtc` and the head-ish
elements do not close a `<p>` at all yet none of them reconstructs — and
**narrower**, because `xmp` closes a `<p>` exactly like the `pre`/`listing`
rule beside it and *does* reconstruct, as does `button` for the button it
closes. Both counterexamples are now corpus cases
(`:fmt/xmp-still-reconstructs`, `:fmt/button-still-reconstructs`) precisely
so that widening the set later fails loudly.

The other half of the rule is that a character token still reconstructs, so
the formatting reappears *inside* the block, around its text, and again
after it — `<div><em>x</div><ul><li>y</li></ul>z` is
`<ul><li><em>y</em></li></ul><em>z</em>` in both. That is what makes
over-suppressing invisible at the block and visible at the text, which is
why it is its own case. `omission` 5/8 → 10/11 (three failures fixed, five
cases added), overall 102/113 → 104/113 before the additions.
`:omission/table-closes-p-through-inline` was one of the three and now fails
on cause 2 instead; the deliberate table exemption and the adoption agency's
own tests were unaffected, which is what
`:fmt/xmp-still-reconstructs` and the seven new unit tests exist to keep true.

**The list of active formatting elements had no scope markers.** The spec
pushes a marker when it opens a `td`/`th`/`caption`, and reconstruction
never walks back past one; closing the element clears the list back to it.
Without markers, formatting still open when a table started was recreated
inside the first cell (`<table><b>bold<tr><td>x` gave `<b>x</b>` where a
browser gives a bare `#text "x"`), and formatting opened *inside* a cell
leaked into the next cell and out past the table.

Both halves were measured, and the second is the one that constrains the
implementation: `<b>a<table><tr><td><i>b</td><td>c</table>d` puts `<i>b</i>`
in the first cell, a bare `#text "c"` in the second, and `#text "d"` inside
the `<b>` but *not* inside an `<i>`. So clearing is neither "empty the list"
nor "keep everything" — it cuts at the marker, dropping what was pushed
after it and keeping what was pushed before. That case is in the corpus
(`:table/clearing-keeps-formatting-from-before-the-marker`) precisely
because a marker that gets the forward half right can still fail it.

The awkward part was never the algorithm, it was that a cell can be popped
from four places (`auto-close-stack` on a sibling cell,
`clear-to-table-context`, `close-open-table-for-nested-table`, and the
`:end` case) and none of them sees the afe list — the earlier SCOPE CUT
comment sized this as "threading markers through" all of it. It is not
threaded: a marker carries the id of the element that pushed it and stays
live exactly as long as that id is on the stack of open elements, so
"clear up to the last marker" falls out of a prune the next read performs.
That is the same move the foster-parenting work made, reading the answer
off the stack of open elements instead of off insertion modes this parser
does not have.

The spec's `applet`/`marquee`/`object`/`template` markers are **not**
implemented, and that is a measurement statement rather than a shortcut:
all four reconstruct *before* inserting themselves, which puts the
formatting element back on the stack, after which every reconstruction
inside them is a no-op with or without a marker — no probe distinguishes
them. `table` 20/21 → 25/25, `omission` 10/11 → 11/11, overall 109/118 →
111/118 before the four cases added with it. One unit test moved: it had
asserted `[:td [:b "x"]]` while its own comment said Brave gives a bare
`#text "x"`, so it now asserts the measurement it named.

Deliberately **not** fixed: everything in the two causes above, plus the
one attribute divergence — `@click="f"` becomes `click="f"`, because
`attrs`' name pattern requires an ASCII-alpha/`_`/`:` first character while
the spec forbids only whitespace, `/`, `>` and `=` in an attribute name.
Real in the wild (Vue, Alpine, htmx) but the fix means widening the single
most load-bearing regex in the file, and this axis is secondary; it is
recorded here rather than changed on the way past.

## How the browser is read

The same way the cssom harness reads layout, for the same reason: no CDP
client, no Playwright, no driver.

One page, one browser launch, `--headless=old --dump-dom` written to a
**file**. Both of those are measured constraints, not preferences.
`--headless=new --dump-dom` prints nothing at all and bare `--headless`
never returns; and Chromium's child processes inherit stdout and hold it
open after the parent dies, so a **pipe never reaches EOF** and the reader
hangs forever — `spawnSync`'s own `:timeout` does not save you, because it
kills the parent and then still waits on the pipe. `timeout -s KILL` bounds
the run, because headless Chromium writes its dump and then ignores SIGTERM.
The page script base64s its result into a `<pre>` so no case's markup can
break the block being read back.

The one structural difference from the cssom harness is that each case is
injected with **`innerHTML` on a detached `<div>`** rather than written into
the page source. That is not cosmetic:

- `innerHTML` on a `<div>` *is* the HTML fragment parsing algorithm with a
  `<div>` context element — the same insertion modes, the same foster
  parenting, the same adoption agency — which is precisely what
  `parse-into-document` does (it parses into a `:document` root; there is no
  html/head/body synthesis on either side, so depth 0 means the same thing).
- It **isolates** the cases. Written into page source, an unterminated
  `<table>` keeps the "in table" insertion mode across everything after it
  and swallows the rest of the corpus, measurement script included. Half
  this corpus is deliberately malformed, so isolation is a correctness
  requirement.
- Scripts inserted via `innerHTML` never execute, so the raw-text cases
  cannot run anything.

The corpus goes into the page base64-encoded for the same reason the result
comes back that way: a case containing `</script>` would otherwise end the
element carrying it.

## Normalisation — and one harness bug it caught

Both sides are reduced by the *same* function. Two steps are worth naming
because getting them wrong scores the harness instead of the parser.

**Adjacent text nodes are merged first, on both sides.** A browser appends
characters to the text node already at the insertion point, so a token it
drops in between leaves one text node; htmldom emits one per `:text` token
and never merges. Before this step `<p>a</b>b</p>` was scored as a
divergence — `#text "a"`, `#text "b"` against `#text "ab"` — when the two
trees are `Node.normalize()`-identical and no consumer can tell them apart.
That was a harness bug, not a parser bug, and fixing it moved the first run
83% → 84% *before* any parser change. Merging happens on the raw text,
before whitespace normalisation, so the real content divergence it was
hiding stays visible: `<p>a < b</p>` still failed afterwards, correctly.

**Whitespace is collapsed but not trimmed.** Whitespace-only text nodes stay
in the comparison as their own `#ws` item, because where such a run lands is
genuine parser behaviour — this parser only started keeping them at all on
2026-08-03 (`fix(core): keep whitespace-only text runs`), and `<a>one</a>\n
<a>two</a>` renders as `one two` precisely because the run survives. The
collapsing class is ASCII whitespace only, deliberately **not** the regex
`\s` class, which would also match U+00A0 and erase the entity cases the
harness is there to measure. (It very nearly did: the parser bug above was
only visible because this class was written narrowly first.)

## What is excluded from comparison, and why

- **`style` attributes.** `apply-attrs` folds them into `:style-inline` /
  `:style-inline-important` plus a parsed map for the cascade — the reason
  this repo contains a `calc()` evaluator. Comparing a parsed map against a
  browser's raw string would score the cascade bridge, not the parser. The
  `:style/<prop>` keys written beside them are dropped by NAMESPACE while
  the tree is walked, not by name later: `name` erases the namespace, so
  `(name :style/width)` is plain `width` and an element carrying an inline
  style was reporting a phantom `width` attribute the browser cannot have.
  Found by `:table/bare-col-gets-an-implied-colgroup` on 2026-08-05, the
  first case here to put an inline style on an element with no other
  attributes — one more instance of the harness bug the normalisation
  section above describes.
- **`default-value` / `default-checked` / `default-selected`, and `value` on
  `<select>`/`<textarea>`, `selected` on `<option>`.** Synthesised by
  `initialize-form-defaults`. In a browser these are DOM *properties*, never
  content attributes, so the oracle cannot have them and their absence is
  not a divergence.
- **Exact whitespace inside text.** `<pre>` and `<textarea>` preserve runs
  verbatim on both sides, but the comparison collapses them, so a
  divergence in how many spaces survive is invisible here. That difference
  is a *layout* question — `white-space` is a CSS property — and the cssom
  harness is where it becomes measurable. What this harness does check is
  that the whitespace-only *nodes* exist in the same places.
- **Element identity beyond tag name.** Namespaces (SVG/MathML) are not in
  the corpus at all; this parser has no namespace concept.

## Adding cases

Append to `cases.edn`. Keep the markup exact — incidental indentation inside
a case's `:html` becomes real whitespace text nodes on both sides, so
whitespace should only appear where a case is deliberately testing it. A
failing case is a **measurement, not a bug report**: several groups here are
known scope cuts and are in the corpus precisely so the number tells the
truth about them.
