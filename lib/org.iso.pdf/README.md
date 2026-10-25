# kotoba-lang/org-iso-pdf

Zero-dep-beyond-`org-ietf-deflate` portable `.cljc` PDF COS object model
reader (ISO 32000). Named `org-iso-pdf` — PDF was formally standardized as
ISO 32000-1/2 (same reasoning `org-ieee-verilog` applies to a
vendor-originated-then-standardized spec: use the numbered ISO/IEC
designation as the canonical reference once one exists).

Extracted from `kotoba-lang/kasane` (kasane.cos, ADR-2606272100). PDF is not
a linear struct grammar (COS object graph + xref + trailer), so this is a
hand-written recursive-descent reader (dict/array/string/name/number/ref/
stream). R0 collects top-level objects by scan (robust to classic or
rebuilt xref), resolves the page tree, decodes FlateDecode content streams
via `org-ietf-deflate`, and extracts BT/ET shown text. Image XObjects:
FlateDecode → raw samples; DCTDecode → opaque JPEG bytes (feed to
`org-iso-jpeg`'s `decode-rgb`, kept decoupled); other filters → opaque.

**Objects packed inside `/Type /ObjStm` compressed object streams (ISO
32000 §7.5.7)** are expanded and merged into `:objects` (2026-07-08) —
`expand-objstm` decodes each ObjStm's header table (N pairs of `objnum
offset`) and parses each packed object's bytes individually, all at
generation 0 per spec. This matters in practice: **many real-world PDFs
from recent Acrobat and other modern tools pack most of their objects into
object streams**, so without this a lot of real PDFs would fail to resolve
their object graph at all, not just lose some coverage. Cross-reference
*streams* (the xref-table equivalent that usually accompanies ObjStm-using
files) are still not parsed — this repo's object discovery stays scan-based
(`"N G obj"` text search), which doesn't need the xref table at all, so
files relying on ObjStm still resolve correctly through this path even
though the xref stream itself is ignored.

## Usage

```clojure
(require '[pdf.core :as pdf])

(def parsed (pdf/parse pdf-bytes))       ; => {:objects :trailer :root}
(def pages  (pdf/pages parsed))          ; leaf page dicts, MediaBox/Resources inherited
(pdf/page-text (:objects parsed) (first pages))     ; => vector of shown text strings
(pdf/page-images (:objects parsed) (first pages))   ; => image XObjects
```

## Test

```sh
kbb -M:test
```
