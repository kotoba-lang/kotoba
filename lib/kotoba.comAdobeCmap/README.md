# kotoba-lang/com-adobe-cmap

**Adobe's CID-to-Unicode CMaps, parsed.** The five published character
collections — `Adobe-Japan1`, `Adobe-GB1`, `Adobe-CNS1`, `Adobe-KR`,
`Adobe-Korea1` — as `{cid "string"}`.

```clojure
(require '[adobe.cmap.core :as cmap])
(get (cmap/cid->unicode "Adobe-Japan1") 1125)   ;; => "亜"
```

## What this answers

A PDF composite font names a character collection and puts CIDs in the
content stream. `/ToUnicode` is how a producer is supposed to say what those
CIDs mean, and **25 of 576 `/Type0` fonts in a measured corpus do not ship
one** — every one of them a `CIDFontType0C`, which is bare CFF and carries no
`cmap` table to fall back on. For those the collection's own table is the
answer, and Adobe publishes it.

## Vendored, not reimplemented

The files under `resources/adobe/cmap/` are Adobe's, byte for byte, from
[`adobe-type-tools/mapping-resources-pdf`](https://github.com/adobe-type-tools/mapping-resources-pdf),
under the BSD-3-Clause licence reproduced beside them.

Retyping a 23,000-entry mapping would introduce errors nobody could find. The
whole value here is that it is Adobe's table and not somebody's transcription
of it — so the tests spot-check against the *published* collection rather than
against a fixture written here.

`Adobe-Identity` is deliberately absent: it declares that the CIDs mean
whatever the font says they mean, so there is no table to publish, and a font
using it without `/ToUnicode` is not decodable by anyone.

## Predefined encodings, for when the code is not a CID

`Identity-H` — where the code IS the CID — is only the most common
`/Encoding`. `90ms-RKSJ-H` is Shift-JIS: codes are one byte **or** two, the
widths are declared in the file, and a reader that assumed two splits every
ASCII character in half.

```clojure
(get (cmap/code->unicode "90ms-RKSJ-H") 0x82A0)   ;; => "あ"
```

Two published tables composed — code → CID → Unicode — neither guessed at.
`split-codes` does the variable-width splitting from the file's own
`codespacerange`, so it needs to know nothing about Shift-JIS, and `usecmap`
is followed (`90ms-RKSJ-V` is the horizontal one plus vertical substitutions;
read alone it maps almost nothing).

Measured: 2 documents of 160, both Japanese legal PDFs whose **entire text**
was unreadable without this. Only the encodings the corpus showed are
vendored — adding another is dropping a file into
`resources/adobe/cmap/encoding/`.

## Two ways a CMap range is misread, both tested

A `bfrange` destination **increments** — reading it as one string repeated
maps a whole range to a single character, which looks like a font whose
glyphs are all the same. And it is the **last UTF-16 code unit** that
increments: a destination of `<D842DF9F>` is a surrogate pair, and adding one
to it as a number walks the high surrogate instead.

## The parser is not the PDF one

These files use `beginbfchar`/`beginbfrange`, the same syntax a PDF
`/ToUnicode` stream uses, so a reader already exists in `kotoba-lang/hanmen`.
Depending on a PDF renderer to read a font resource would point the dependency
the wrong way, and the parser is thirty lines.

`parse` is pure `.cljc`. `cid->unicode` reads a classpath resource and is
JVM-only; a caller elsewhere reads the bytes itself and calls `parse`.

## Test

```sh
kbb -M:test
kbb -M:lint
```

13 tests / 44 assertions.
