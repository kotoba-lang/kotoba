# kotoba-lang/org-w3-woff

Portable `.cljc` decoder for **both** web font formats: **WOFF 1.0** and
**WOFF 2.0** (W3C Recommendations). Named `org-w3-woff` — same `org-w3-<spec>`
pattern as `org-w3-svg`/`org-w3-png`.

Extracted from `kotoba-lang/kasane` (kasane.woff, ADR-2606272100) as WOFF 1.0
only; WOFF2 was deferred because it needs brotli. It arrived with
`org-ietf-brotli` (ADR-2607300500) and is now implemented here, transforms
included.

| format | compression | per-table transforms | status |
|---|---|---|---|
| WOFF 1.0 | zlib per table (`org-ietf-deflate`) | none | `woff.core` |
| WOFF 2.0 | brotli over the whole font (`org-ietf-brotli`) | `glyf`/`loca` split into seven substreams, `hmtx` lsb elision | `woff.woff2` |

## Usage

```clojure
(require '[woff.core :as woff] '[woff.woff2 :as woff2])

;; WOFF 1.0
(woff/->sfnt woff-bytes)     ; => reassembled plain SFNT byte vector
(woff/parse woff-bytes)      ; => opentype.core/parse shape, plus {:woff true}

;; WOFF 2.0
(woff2/->sfnt woff2-bytes)   ; => reconstructed SFNT (TTF/OTF)
(woff2/parse woff2-bytes)    ; => opentype.core/parse shape, plus {:woff2 true}
(woff2/header woff2-bytes)   ; => flavor, numTables, totalSfntSize, …
(woff2/tables woff2-bytes)   ; => directory entries with transform versions
```

Failures are `ex-info` with a `:reason` — `:not-woff2`, `:truncated`,
`:bad-header`, `:bad-uint-base128`, `:size-mismatch`, `:unsupported-transform`,
`:bad-glyf-transform`, `:bad-hmtx-transform`, `:bad-loca-transform`,
`:font-collection`.

## What WOFF2 reconstruction involves

WOFF2 is not "WOFF with brotli". Three tables are pre-processed before
compression and have to be rebuilt:

- **`glyf`/`loca`** (§5.1-5.3): the file carries seven parallel substreams —
  contour counts, point counts, point flags, packed coordinate triplets,
  composite data, bounding boxes, instructions — which the decoder walks in
  lockstep, glyph by glyph, rebuilding the glyph records *and* the `loca` offsets.
  Bounding boxes are usually absent and must be computed from the points.
- **`hmtx`** (§5.4): the left-side-bearing arrays may be dropped entirely and
  recovered from the glyph bounding boxes.
- **the sfnt itself** (§6): records sorted by tag, data 4-byte aligned, every
  `checkSum` recomputed, and `head.checkSumAdjustment` recomputed over the
  finished font.

**The reconstruction is not byte-identical to the original font, by design.** A
glyph's points have several valid encodings and §5.1 forbids rejecting a font
over a size mismatch, so this emits the simple always-valid form (one flag byte
per point, 16-bit deltas). Conformance is therefore checked on decoded
*outlines*. A WOFF2 encoder also sets `head` flags bit 11 (§6), so that bit
differs from the original too.

Not supported: font collections (`ttcf`, refused by name), extended metadata and
private data blocks (present in the header, not extracted), and writing WOFF2.

## Where the WOFF2 tables come from

The 63 known table tags (§4.1) and the 128-row triplet encoding (§5.2) are
**generated from the specification** by `tools/extract_woff2_tables.cljk`:

```sh
curl -sL https://www.w3.org/TR/WOFF2/ -o /tmp/woff2.html
kbb --backend sci tools/extract_woff2_tables.cljk /tmp/woff2.html
```

The spec publishes no checksums, so the generator verifies structurally instead:
exactly 63 tags, and every triplet row satisfying
`byteCount = 1 + (xBits + yBits) / 8`. That invariant is what catches a mis-parse
of the spec's rowspan-heavy HTML, where most rows inherit their byte count from
the row above. `src/woff/woff2_data.cljk` is generated — do not hand-edit.

## Test

```sh
kbb -M:test          # JVM: portable suites + conformance against the woff2 tools
kbb -M:local:test    # …against sibling checkouts
kbb --backend sci run-tests.cljk       # ClojureScript: the same WOFF2 decode, recorded fixture
kbb -M:lint
```

The portable suite decodes a recorded WOFF2 file and compares it against the
*original* font it was compressed from: original TTF → reference
`woff2_compress` → this decoder → identical outlines, and byte-identical tables
everywhere the format allows. The JVM suite adds a sweep with
`woff2_compress`/`woff2_decompress` over whatever real fonts the machine has —
including a large one with composite glyphs and a CFF-flavoured font with no
`glyf` at all — and checks that the results parse as OpenType.
