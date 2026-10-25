# AGENTS.md — org-w3-woff

WOFF 1.0 and WOFF 2.0 decoding in portable `.cljc`. Dependencies:
`org-ietf-deflate` (WOFF 1.0's per-table zlib), `org-ietf-brotli` (WOFF2's
compressed block), `org-iso-opentype` (metadata parse).

## Invariants

- **No host codec, no font library.** The `woff2_compress`/`woff2_decompress`
  binaries appear in `test/woff/woff2_oracle_test.cljk` only, as an oracle.
- **`src/woff/woff2_data.cljk` is generated.** Never hand-edit it; regenerate
  with `tools/extract_woff2_tables.cljk`, which refuses to write unless the tag
  list has exactly 63 entries and every triplet row satisfies
  `byteCount = 1 + (xBits + yBits) / 8`.
- **Decoding only.** No WOFF or WOFF2 *encoder* here.
- **Every failure is an `ex-info` with `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **A reconstruction is not the original bytes, and must not be compared as
  such.** §5.1 permits any valid point encoding and forbids rejecting a font
  because the reconstructed `glyf` differs in size from `origLength`. Three
  tables legitimately differ from the input font: `glyf` (re-encoded points),
  `loca` (offsets follow from `glyf`), and `head` — both because
  `checkSumAdjustment` is recomputed *and* because §6 makes a WOFF2 encoder set
  flags bit 11. Tests compare decoded outlines, not bytes.
- **Bounding boxes are usually absent.** A bitmap says which glyphs have one;
  for the rest the decoder computes xMin/yMin/xMax/yMax from the points it just
  decoded — including off-curve points. A composite glyph always has an explicit
  box, an empty glyph never does, and both rules are worth enforcing.
- **`hmtx` reconstruction needs `glyf`'s xMin values**, so `glyf` must be rebuilt
  first. That ordering is why `->sfnt` resolves the tables in two passes rather
  than mapping over the directory once.
- **The transformed `loca` carries `transformLength` = 0** (§5.3) and is rebuilt
  entirely from the `glyf` transform's output; its `indexFormat` comes from the
  transformed `glyf` header, not from `head`.
- **`glyf` transform version 3 is the null transform, not 0** — the opposite of
  every other table, where 0 means "untransformed". Getting this backwards makes
  a decoder try to reconstruct plain glyph data.
- **Every substream is length-prefixed in the transformed `glyf` header, and the
  bbox stream's declared size includes its bitmap.** Off-by-one here shifts every
  glyph after the first.
- **No fixture available here exercises the `hmtx` transform** — `woff2_compress`
  does not apply it to any font on this machine — so it is covered by a direct
  unit test in `woff2_test.cljc`. Keep that test if you touch the code.

## Layout

| namespace | role |
|---|---|
| `woff.core` | WOFF 1.0: per-table zlib, sfnt reassembly |
| `woff.woff2` | WOFF2 header, table directory, brotli, `hmtx` transform, sfnt assembly with recomputed checksums |
| `woff.glyf` | the `glyf`/`loca` transform: seven substreams → glyph records + offsets |
| `woff.woff2-data` | **generated**: known table tags, triplet encoding |
| `tools/extract_woff2_tables.cljk` | regenerates that data from the spec HTML |
| `test/woff/sfnt_compare.cljk` | test-side sfnt/glyf reader for outline comparison |
