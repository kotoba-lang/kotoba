# docs

[![CI](https://github.com/kotoba-lang/docs/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/docs/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/docs.

Pages editor: https://kotoba-lang.github.io/docs/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Compatibility direction

The document model keeps document semantics needed for Google Docs and
Word-style roundtrips: ordered blocks, headings, paragraphs, lists, tables,
inline text style runs, comments, suggestions, and refs to sheets/files/decks.
The shared wire format is the Kotoba office envelope via
`docs.wire/document-envelope`, using `application/json` and the
`:docs/document` resource kind.

## Coming back

The envelope is a lossy projection: `:docs/type`, a block's `:docs/kind` and a
suggestion's `:docs/op` all leave as bare strings, and a text run's style is a
map whose keys belong to whoever wrote it. Telling those apart needs the
schema, so the reader is here rather than in `transit`:

```clojure
(wire/document-of-envelope (:body envelope))   ; read + rehydrate
(wire/rehydrate-document projected)            ; if you already read it
```

Rehydrate before validating. `docs.validate` reads namespaced keys, and on a
projected payload it finds none — reporting no problems rather than reporting
that it cannot see any.

## Markdown

A document could only leave as EDN, which is the same as not leaving. `docs.markdown`
writes one as Markdown and reads one back:

```clojure
(md/write doc)        ; => "# 月次報告\n\n..."
(md/read text "id")   ; => a document docs.validate will accept
(md/unexpressed doc)  ; => what write will drop, before it drops it
```

`unexpressed` is the part worth knowing about. Markdown cannot carry block ids,
comments, suggestions, a style it has no syntax for, a table cell that is not
text, or a Drive reference — so a document can be asked what it will lose
before someone exports it rather than after. Entries are shaped like
`docs.validate/problems`, all `:info`: losing something on the way to Markdown
is a property of Markdown, not a fault in the document.

Reading accepts more than writing produces, because whatever was pasted in was
not written here, and it never throws — malformed input becomes the nearest
block and the validator is what reports it.

## HTML, for printing

`docs.html/body` renders a document's blocks as HTML.

Written for printing, and that is the point: a PDF writer would have to
embed a CJK font — the reason there is no PDF export here — and a browser
already has one. The honest way to get a PDF of a Japanese document out is a
page the browser can print, and this is that page's body.

Semantic, not styled: `<h2>`, `<blockquote>`, `<ol>`, `<table>` with a
`<thead>`. The block kinds are already the distinctions HTML has names for,
and a document rendered as styled `<div>`s prints the same and reads as
nothing to a screen reader.

Runs are emitted in **one pass**, each span escaped as it is written.
Splicing tags into the raw string and escaping afterwards eats the tags;
escaping first moves every offset, because `&lt;` is four characters where
`<` was one. The one pass is the only order that is right, which is worth
saying because the other two look right.

## Word

`docs.docx` writes a document as a .docx and reads one back, on top of
`ooxml` — the same arrangement `slides.pptx` and `sheets.xlsx` use, and
`ooxml/package-kind` already returned `:docx` for a `word/` prefix.

```clojure
(docx/docx-files doc)               ; path -> text, inspectable without a zip
(docx/docx-bytes doc)               ; JVM
(docx/read files "id")              ; back again
(docx/document-from-bytes b "id")   ; JVM
```

**Structure rather than appearance.** A heading is a paragraph carrying
`w:pStyle Heading1`, not bold 18pt text; a list is `w:numPr`, not a line
beginning with `-`; a table is `w:tbl`, not aligned spaces. Word renders
both the same way and only one of them can be read back as a heading,
collapsed into an outline, or restyled by whoever receives it. That means
shipping `styles.xml` and `numbering.xml`, because a style id referring to
nothing is a paragraph with no style and a `numId` with no entry is a list
with no marker.

Two things the reader has to do that the writer does not. Word splits a
paragraph into runs for reasons that have nothing to do with its content —
a spell-check marker, a language change, a bookmark — so every `w:t` under
a paragraph is concatenated. And tags are matched on their **local name**:
WordprocessingML puts `w:` on everything, so `xml.parse` returns `:w/p`
where SpreadsheetML gives a bare `:c`, and an attribute written `w:val` is
not found by asking for `val`. Getting either wrong returns an empty
document, which looks exactly like a document with nothing in it.

Block ids do not survive — .docx has nowhere to put them, the same as
Markdown — so `read` regenerates them.

## Test

```bash
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "src:test:$(kbb -Spath)" scripts/test-cljs.cljk   # ClojureScript
```

Run both. `docs.markdown` is regular expressions and string surgery, which is
where two hosts differ most quietly.
