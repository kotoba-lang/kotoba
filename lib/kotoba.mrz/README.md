# mrz

ICAO Doc 9303 Machine Readable Zone decode + checksum validation for kotoba-lang.

Decoding and validating MRZ **text** (TD1/TD2/TD3 — the fixed-width lines
printed on passports and many national ID cards, ~190 issuing countries) is a
public, deterministic, fully-specified standard: `mrz.core`/`mrz.checksum`
implement it for real, verified against ICAO's own published worked example.

Going from a **photograph** to that text is a different, much harder problem.
`mrz.glyph`/`mrz.adapters.template-ocr` provide a real, tested
segmentation + correlation-matching algorithm for a pre-cropped,
perspective-corrected zone image — but ship **no bundled OCR-B template
data** and **no accuracy claim**. See `MATURITY.md`.

## Usage

```clojure
(require '[mrz.core :as mrz])

(def parsed
  (mrz/parse-td3
   "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
   "L898902C36UTO7408122F1204159ZE184226B<<<<<10"))

(:doc-number parsed)  ;=> "L898902C3"
(mrz/valid? parsed)   ;=> true
```

`mrz.core/parse` dispatches on line count/width (2×44 → TD3, 2×36 → TD2,
3×30 → TD1) if you don't already know the format.

## Honesty boundary (read before relying on this for anything real)

- `mrz.model` / `mrz.checksum` / `mrz.core`: real, deterministic, no
  external dependency, verified against ICAO's own TD3 test vector.
- `mrz.ports` / `mrz.glyph` / `mrz.adapters.template-ocr`: **R1
  experimental**. A real, tested template-matching *algorithm* — not a
  validated OCR *product*. No document detection, no zone localization, no
  perspective correction, no bundled font template data, no benchmark
  against real photographed documents. Do not represent this as
  production-grade document capture.

See `MATURITY.md` and `90-docs/adr/2607198200-kotoba-lang-mrz.edn` (in the
`com-junkawasaki/root` superproject) for the full rationale.
