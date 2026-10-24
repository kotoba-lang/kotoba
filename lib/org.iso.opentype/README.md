# kotoba-lang/org-iso-opentype

Zero-dep portable `.cljc` implementation of TrueType/OpenType (SFNT) —
ISO/IEC 14496-22 Open Font Format. Named `org-iso-opentype` (ISO/IEC-numbered
spec, consistent with `org-iso-jpeg`/`org-iso-isobmff`/`org-iso-pdf` in the
same batch).

Extracted from `kotoba-lang/kasane` (kasane.ttf, ADR-2606272100). Offset-based
hand parser over the table directory + head/maxp/name tables. R0 extracts the
table set, head metrics (units-per-em, the fixed magicNumber for validation),
glyph count, and family name — CFF/glyf outline parsing is a follow-up.
Consumed by `org-w3-woff`, which reassembles a WOFF-wrapped SFNT and
delegates here for the same metadata.

## Usage

```clojure
(require '[opentype.core :as opentype])

(opentype/parse sfnt-bytes)
;; => {:sfnt-version :num-tables :tables :magic :magic-ok?
;;     :units-per-em :num-glyphs :family}
```

## Test

```sh
kbb -M:test
```

## `cmap`, and the reverse direction (`opentype.cmap`)

Forwards is what a layout engine wants. Backwards is what anybody holding
glyph ids and no characters wants — and that is a real position: a PDF
composite font with `Identity-H` puts GLYPH IDS in the content stream, so the
text of the page is unreadable without the font that drew it. `/ToUnicode` is
how a producer is supposed to say what those ids mean, and plenty do not ship
one (measured at 3 of 30 real documents, 550 runs in one LaTeX-CJK paper).

For an embedded subset font the answer is in the file:

```clojure
(let [uni (cmap/unicode->gid font-bytes cmap-offset)]
  (cmap/gid->unicode uni))      ;; => {glyph-id code-point}
```

Not a heuristic — the font's own table read the other way. Format 12 is
preferred over format 4 so anything outside the BMP survives; a (3,0) symbol
subtable is read and **marked**, because its code points are private-use and
mean nothing on their own. The lowest code point wins a collision, which is
what keeps `A` from coming back as U+F041.

`parse` now also returns `:table-offsets`, so a caller that got a yes from
`:tables` can find out where.
