# kotoba-lang/org-ansi-iges

IGES 5.3 (ANSI/USPRO/IPO-100-1996) — read and write. Portable `.cljc`.

IGES is the exchange format CAD systems that predate STEP still emit, and the
one a shop's twenty-year-old fixture library is in. This reads and writes the
card format directly; there is no external converter in the path.

```clojure
(iges/write [{:iges/type 110 :line/start [0 0 0] :line/end [10 0 0]}] {:units "MM"})
(iges/parse text)  ;=> {:iges/entities [...] :iges/counts {...} :iges/unsupported {...}}
```

## What it decodes

100 circular arc · 106 copious data · 110 line · 116 point · 124 transformation
matrix. **Surfaces (128), trimmed surfaces (144) and everything built on them
are not decoded** — `parse` reports every type it does not know by number and
count in `:iges/unsupported`, because a reader that drops what it does not
recognise turns someone else's model into a subset of itself and says nothing.
`write` throws on a type it cannot write rather than emitting a card another
system will reject.

## Two things this format punishes

**The delimiters are declared in the file.** The first two Global fields are
Hollerith strings giving the parameter and record delimiters. They are usually
`,` and `;`, and a reader that assumes so mis-splits every field of a file from
a system that chose otherwise — with no error, because the fields still split,
just in the wrong places. The test suite parses a fixture using `|` and `#`
that nothing here emits.

**Every card is exactly 80 columns.** The section letter is column 73 and the
sequence number columns 74-80, both by position, so a line one character short
is not slightly wrong: its section is a digit and its sequence number is
garbage. Our own reader would accept such a file, which is why the width is
asserted directly rather than through a round-trip.

## Test

```sh
kbb -M:test
```
