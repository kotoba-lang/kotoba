# kotoba-lang/org-iso-jpeg

Zero-dep portable `.cljc` implementation of JPEG (ISO/IEC 10918-1, jointly
ITU-T T.81) — marker-segment metadata reading and a baseline (SOF0) pixel
decoder. Named `org-iso-jpeg` (ISO/IEC numbering chosen as the canonical
reference across this repo's jointly-ITU/ISO-published codec specs — see
also `org-iso-h264`/`org-iso-aac`/`org-iso-isobmff`/`org-iso-pdf`/
`org-iso-opentype`).

Extracted from `kotoba-lang/kasane` (kasane.jpeg + kasane.jpeg.decode,
ADR-2606280010).

- `jpeg.core` — marker-segment scan (SOI/SOF0-2/SOS/etc.) → dimensions,
  component count, progressive flag. Does not decode pixels.
- `jpeg.decode` — baseline (SOF0) pixel decoder: Huffman entropy decode →
  dequantize → 8×8 IDCT → chroma upsample → YCbCr→RGB. Float IDCT, so output
  is bit-close (not bit-exact) to libjpeg/Pillow — verified mean abs error
  < 3, max < 40 against a real Pillow-encoded fixture. Progressive (SOF2)
  and restart-heavy streams are best-effort/unimplemented.

## Usage

```clojure
(require '[jpeg.core :as jpeg] '[jpeg.decode :as jd])

(jpeg/parse jpeg-bytes)        ; => {:width :height :components :progressive? :markers}
(jd/decode-rgb jpeg-bytes)     ; => {:width :height :rgb [r g b ...]}  (baseline only)
```

## Test

```sh
kbb -M:test
```
