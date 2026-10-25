# kotoba-lang/org-compuserve-gif

Zero-dep portable `.cljc` GIF89a decoder. Named `org-compuserve-gif` —
CompuServe published the GIF89a specification (still the canonical
reference, mirrored at w3.org/Graphics/GIF/spec-gif89a.txt), same
`org-<vendor>-<spec>` pattern as `org-adobe-tiff`/`org-pkware-zip` (a
published spec exists even though the original publisher is a defunct
vendor rather than a standing standards body).

Extracted from `kotoba-lang/kasane` (kasane.gif, ADR-2606272100).
Header/Logical-Screen-Descriptor via a self-contained EDN-grammar engine
(`gif.decode`, duplicated from kasane.decode); first-frame LZW pixel decode
(LSB-first, non-early code-width change — GIF's own variant, distinct from
TIFF/PDF's MSB early-change variant) verified bit-exact against real
Pillow-encoded fixtures, including a 96×40 interlaced image exercising the
4-pass de-ordering.

## Usage

```clojure
(require '[clojure.edn :as edn] '[clojure.java.io :as io] '[gif.core :as gif])

(def grammar (edn/read-string (slurp (io/resource "gif/grammar.edn"))))
(gif/parse grammar gif-bytes)                ; => {:width :height :frames :version :global-color-table?}
(gif/first-frame-indices gif-bytes)          ; => vector of palette indices, row-major
```

## Test

```sh
kbb -M:test
```
