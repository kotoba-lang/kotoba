# sheets

[![CI](https://github.com/kotoba-lang/sheets/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/sheets/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/sheets.

Pages editor: https://kotoba-lang.github.io/sheets/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Compatibility direction

The workbook model keeps spreadsheet semantics needed for Google Sheets and
Excel-style roundtrips: tabs, cell values, formulas, cell style metadata, named
ranges, and chart descriptors. The shared wire format is the Kotoba office
envelope via `sheets.wire/workbook-envelope`, using `application/json` and the
`:sheets/workbook` resource kind.

## Coming back

The envelope is a lossy projection: `:sheets/type` leaves as `"workbook"` and
a cell address `[1 1]` leaves as the string `"[1 1]"`, while tab ids and
named-range ids are strings that must stay strings. Telling those apart needs
the schema, so the reader is here rather than in `transit`:

```clojure
(wire/workbook-of-envelope (:body envelope))   ; read + rehydrate
(wire/rehydrate-workbook projected)            ; if you already read it
(wire/cell-address-string [1 1])               ; "[1 1]", for reaching into a projection
```

## CSV

```clojure
(csv/tab->csv (m/tab-by-id wb "plan"))    ; one tab out, RFC 4180
(csv/import-csv wb "data" text)           ; text in, as a tab of that id
```

A tab and not a workbook: CSV has no idea a workbook has more than one, and
pretending otherwise means inventing a convention nothing on the other end
would agree with.

Everything read is text — CSV does not say what a field is, and guessing is
how a part number becomes a float. An empty field is left out rather than
stored as `""`, because a missing cell and an empty one are different things
to anything counting them. A field beginning with `=` is a formula, and a
formula writes back as `=EXPR` rather than as its value: there is no
evaluator here, so the value is not something this could write.

## Excel

```clojure
(xlsx/xlsx-bytes wb)   ; a .xlsx, JVM
(xlsx/xlsx-files wb)   ; the parts, for a host without a zip
```

On `ooxml`, the same division `slides.pptx` uses — that library supplies the
OPC vocabulary and knows nothing about spreadsheets, and it already
anticipated this one: `package-kind` returns `:xlsx` for an `xl/` prefix and
`part-sort-key` orders `xl/worksheets/sheetN.xml`.

Every cell is written as an inline string, including one whose value looks
like a number. Reading refuses to guess for a stated reason; deciding on the
workbook's behalf that `0042` is forty-two at the moment it leaves for Excel
would be the same guess arriving late. Inline strings also mean no
`sharedStrings.xml` — one part fewer and no string table to keep in step
with the cells indexing it.

A formula writes `<f>` and no cached `<v>`: there is no evaluator here, so
Excel recalculates on open.

```clojure
(xlsx/workbook-from-bytes b)   ; a .xlsx back into a workbook, JVM
(xlsx/workbook-from-files m)   ; from the parts, anywhere
```

Reading meets more shapes than writing chose. A .xlsx from Excel keeps its
strings in a shared table, writes numbers with no `t` at all, and carries
the value it last calculated next to each formula. All of those come in, and
**the formula wins over its cached value** — the formula is what the
document says and the value is what Excel last thought, so keeping the value
would turn a spreadsheet into a printout of one.

Sheets come in the order `<sheets>` declares, resolved through the
workbook's relationships, because a workbook may relate rId1 to
`sheet3.xml`. A package whose relationships are missing still comes in, by
part order — an import that silently produced an empty workbook would look
like a working import of an empty file.

**Styles are not read, so neither are dates.** Excel stores a date as a
serial number whose format is what makes it a date, so one arrives here as
`45000`. Reading styles is what this needs next; an obvious number is better
than a wrong date.

Rehydrate before validating. `sheets.validate` reads namespaced keys, and on
a projected payload it finds none — reporting no problems rather than
reporting that it cannot see any.

## Formulas compute

A workbook could hold `=SUM(B2:B9)` and never compute one. `sheets.xlsx`
writes `<f>` with no cached value on purpose — Excel recalculates on open —
but inside a viewer that is not Excel the cell showed the text for ever.

```clojure
(f/value-at tab 4 2)   ; what that cell comes to now
(f/values tab)         ; every cell, keyed the way the cells are
```

**Nothing is stored.** A computed value written back into `:sheets/value`
would be a second copy of something derived — stale the moment an input
changes and afterwards indistinguishable from a value somebody typed.

**Cells hold text and that is not undone.** Evaluation parses text to a
number where a number is required and says so when it cannot; it does not
decide `0042` was a number all along. Which is Excel's rule: `=A1+1` over
text is `#VALUE!`, while `=SUM(A1:A9)` ignores the text in the range —
arithmetic asks for a number, an aggregate asks for the numbers there are.

**Errors are values.** `#DIV/0!` `#VALUE!` `#NAME?` `#REF!` `#CIRCULAR!`,
and they propagate: a sum over a range containing one is that error, because
a total that silently omitted it would be a number nobody can see is wrong.
A cell that refers to itself, directly or round a loop, is `#CIRCULAR!`
rather than a stack overflow.

**`IF` chooses before it computes.** Everything else takes evaluated
arguments; evaluating both branches of an IF defeats the thing it is most
used for — `IF(A1=0,"ゼロ",100/A1)` guards a division by zero, and computing
the guarded branch anyway makes the whole formula `#DIV/0!`, which is the
error the guard exists to avoid. `AND`/`OR` are *not* lazy, and neither are
Excel's.

Implemented: `+ - * / ^`, comparison, `&`, ranges, `$A$1` accepted and
ignored, and

    SUM AVERAGE COUNT COUNTA MIN MAX ABS ROUND
    COUNTIF SUMIF
    LEN LEFT RIGHT MID UPPER LOWER TRIM CONCATENATE
    IF AND OR NOT

A criterion for `COUNTIF`/`SUMIF` is a value to equal or a comparison
written as text — `">1000"`. The operator being part of the *string* is a
spreadsheet convention rather than a general one, and `SUMIF` takes an
optional third range to total instead of the one it tested, which is how
Excel spells "test one column, total another".

Not implemented: everything else, which is `#NAME?` rather than a crash.

**A formula can read another sheet.** `原価表!A1`, `SUM(原価表!A1:A2)`, and
`'売上 表'!A1` when the name has a space — a single-quoted run in a formula
is a sheet name, and there is no single-quoted string for it to be confused
with. A sheet that is not there is `#REF!`, which is what a spreadsheet says
about an address it cannot resolve, rather than `#NAME?`, which is what it
says about a word it does not know.

The chain of cells being computed is keyed by **sheet and cell**. With one
tab those are the same thing; with two, `売上表!A1` and `原価表!A1` are both
`[1 1]`, so a cell-only key reports an ordinary cross-tab reference as a
cycle — and misses a real one that goes out to another sheet and back. Both
halves are tested.

`values` on a bare tab has no workbook to resolve a sheet name against, so a
qualified reference there is `#REF!` rather than a wrong number. Use
`workbook-values`.

**Named ranges resolve.** `=SUM(売上)` where 売上 is `A1:A3` on this tab.
Use `workbook-values`, not `values`: a name belongs to the workbook and a
tab does not know which workbook it is in. The tab is matched by its
**title** — the same rule `sheets.xlsx` uses to write a `definedName`,
because that is what a `definedName` references and what somebody defining a
range writes. A name whose range is on another
tab is *not* resolved — answering it against the wrong sheet would be a
number computed from the wrong cells, which is worse than `#NAME?`.

A word the tokeniser meets ends at an operator, punctuation or whitespace,
rather than being matched against a list of ASCII letters. A named range
here is as likely to be 売上 as Sales, and an allowlist would make every
non-English name unspellable.

`sheets.xlsx` writes them now, as `<definedNames>` after `</sheets>` — the
schema fixes that order and Excel refuses a file that gets it wrong. Only a
name pointing at a tab the workbook does not have is still dropped, and
`unexpressed` reports exactly those rather than all of them.

## A chart, drawn

`add-chart` was in the model from the start and nothing could draw one or
write one — `sheets.xlsx/unexpressed` reported charts as dropped and that
was the whole of their existence.

```clojure
(chart/svg tab {:sheets/id "c" :sheets/data-range "A1:B3" :sheets/chart-type :bar})
(chart/charts-of workbook "売上")   ; every chart over that tab, with its SVG
```

SVG, and in this library rather than in an application: a string can be
tested without a browser, rendered server-side, and put in a page by
anything that can put a string in a page. An application drawing its own
would be the second implementation of an axis.

**It plots what a formula comes to**, through `sheets.formula`, because a
chart over a column of `=SUM(…)` should plot the totals and reading
`:sheets/value` would plot nothing at all.

**The first column becomes labels when it holds no numbers.** A range
selected by dragging across a table almost always includes the row headings,
and plotting 四半期 as zero is worse than using it to name the bar.

**A range with no numbers draws nothing** — nil, not an empty frame. Axes
around no data read as *there is no data here*, which is the wrong answer
when the range is simply wrong; a caller that gets nil can say which.
`charts-of` still lists such a chart, with a nil `:svg`, because a chart
somebody defined and cannot see is a thing to say rather than to hide.

The axis top is a round number — one, two or five times a power of ten —
because a bar touching the frame reads as clipped and a fixed percentage
produces labels like 1,127.

**And `.xlsx` carries them.** A chart in a spreadsheet is four parts and a
chain of relationships: the sheet points at a drawing, the drawing at a
chart, and the chart back at the cells. A link missing anywhere gives a file
that opens with no chart and no complaint, so all of them are written
together — including a content type for each new part, without which Excel
does not read it at all.

The series names its cells *and* caches what they hold. Both: the reference
is what Excel recalculates from, and the cache is what every other reader
draws — a chart with only the reference is blank in anything that does not
evaluate formulas.

Only a chart naming a tab the workbook does not have is still dropped: there
is no sheet for its drawing to sit on, and one anchored to nothing opens as
an empty frame.

## Cell styles

Weight, slant, underline, horizontal alignment and a number format are
written and read back. They were the largest of the losses `unexpressed`
reported: a file whose header row was bold came back plain, and going out
again lost it for good.

A style is two levels of indirection — cell → `cellXfs` entry → font and
`numFmt` — and that is what made it the largest. A writer that emits a
`<font b="1"/>` and nothing else produces a file Excel opens with no bold in
it, because nothing pointed at the font. `applyFont="1"` matters for the
same reason.

`xl/styles.xml` is written even by a workbook with no styles: a cell with no
`s` attribute means `cellXfs` position 0, and a package missing the part
opens with a repair prompt. Two cells with one style share one entry, so a
header row of twenty bold cells writes one.

The vocabulary is closed on purpose — `:sheets/style` is an open map in the
model. What is left, a colour or a border or a font family, is reported **by
key**: not "the style is dropped" but "`border`、`color` are not written".

## Where a column letter lives

`sheets.model/column-name` and `column-number`. They were in `sheets.xlsx`,
which made addressing look like a fact about a file format; it is not, and
the cost of the copy was that the same host-portability bug got written
twice — `(int ch)` is a code point on the JVM and 0 in ClojureScript, so the
arithmetic version read every column as 1 under cljs. Fixed once in `xlsx`,
then reintroduced verbatim in `formula` before the tests caught it. There is
one of them now.

## Test

```bash
kbb -X:test                                                  # JVM
kbb --backend sci --classpath "src:test:$(kbb -Spath)" scripts/test-cljs.cljk   # ClojureScript
```

Run both. This is a `.cljc` library and the JVM suite passed for as long as
`sheets.xlsx` had two bugs that existed only under ClojureScript: `(int \A)`
is a code point on the JVM and `0` in cljs, so `column-name` wrote control
characters where cell references belong and `column-number` read every
column as column 1. Neither is visible from one host — column A is 1 either
way, and `AA` came out as 27 by coincidence.

## Kotoba bounded profile

`src/sheets/bounded_cells.kotoba` is a capability-free port of a single
tab's cell table, scoped to string-valued cells keyed by a bounded
`{:row :col}` integer coordinate — the shape `sheets.model-test`'s own
`workbook-model` fixture exercises. It uses `kotoba-lang/compiler`'s
canonical bounded typed-map (`[:map [:record :sheets/coord …] :string]`,
up to 31 entries) with a **record key** — the same primitive already
production-qualified by `kotoba-lang/crdt` and by the sibling
`kotoba-lang/states` bounded-model migration. Formulas, styles, named
ranges, charts, the workbook/tab container, `range-values`, the validator,
and the Transit wire envelope stay in the CLJC oracle (`sheets.model` /
`sheets.wire`). See [migration/bounded-cell-table-v1.edn](migration/bounded-cell-table-v1.edn).
