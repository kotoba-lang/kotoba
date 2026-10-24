# kotoba-lang/org-ietf-deflate

Zero-dep portable `.cljc` implementation of **DEFLATE (RFC 1951), zlib
(RFC 1950) and gzip (RFC 1952) — compression *and* decompression.** Huffman +
LZ77 by hand: no `java.util.zip`, no Node `zlib`, no external library, on any
Clojure dialect.

Named `org-ietf-deflate` (RFC-numbered IETF spec, same pattern as
`org-ietf-turn`/`org-ietf-oauth2`/`org-ietf-cbor`).

Extracted from `kotoba-lang/kasane` (ADR-2606272100) as a *decompressor*, where
it was the single codec backing PSD ZIP channels and PDF FlateDecode streams.
Also consumed by `org-w3-png` (IDAT), `org-pkware-zip` (raw deflate),
`org-w3-woff` (per-table compression) and `org-iso-pdf` (FlateDecode) — DEFLATE
is byte-identical across all of those containers, so this is the one shared leaf
dependency in the kotoba-lang media/graphics standards substrate.

The compressor, the gzip container, the checksums and the strict-decode paths
were added in ADR-2607300400. Before that, anything in this workspace that
needed to *compress* had to reach for a host zlib (`java.util.zip.Deflater` on
the JVM, `require('zlib')` on Node) — exactly the runtime dependency the
kotoba-lang runtime priority order exists to remove.

## Usage

```clojure
(require '[deflate.core :as deflate])

;; decompress
(deflate/inflate zlib-bytes)        ; RFC 1950 zlib stream → vector of unsigned bytes
(deflate/inflate-raw raw-bytes)     ; RFC 1951 raw deflate (ZIP members, WOFF tables)
(deflate/gunzip gzip-bytes)         ; RFC 1952, including multi-member files

;; compress
(deflate/deflate     bytes)             ; → zlib stream
(deflate/deflate-raw bytes)             ; → raw deflate stream
(deflate/gzip        bytes)             ; → single-member gzip file
(deflate/deflate     bytes {:level 9})  ; 0 stores, 1 fastest, 9 densest (default 6)
(deflate/gzip        bytes {:filename "log.txt"})

;; checksums (also what org-pkware-zip uses per entry)
(deflate/crc32   bytes)             ; CRC-32/ISO-HDLC, matches java.util.zip.CRC32
(deflate/adler32 bytes)             ; Adler-32
```

Every byte sequence in and out is a sequence of **unsigned** bytes (0–255);
results are vectors.

### Options

| option | applies to | default | meaning |
|---|---|---|---|
| `:level` | compression | 6 | 0 = stored only, 1 = shallow match search, 9 = deepest |
| `:max-output` | decompression | 128 MiB | ceiling on inflated size; `nil` = unbounded |
| `:verify-checksum` | `inflate`, `gunzip` | `true` | check the Adler-32 / CRC-32 / ISIZE trailer |
| `:dictionary` | decompression | — | RFC 1950 preset dictionary (FDICT) |
| `:filename` `:comment` `:mtime` `:os` | `gzip` | mtime 0, os 255 | gzip header fields |

Failures are `ex-info` with a `:reason` — `:truncated`, `:bad-header`,
`:bad-code`, `:bad-block-type`, `:bad-stored-length`, `:bad-distance`,
`:bad-length-symbol`, `:checksum-mismatch`, `:size-mismatch`, `:output-limit`,
`:dictionary-required` — so a container above can tell a corrupt member from a
mis-framed one.

### Beyond the facade

`deflate.core` is the public surface. The implementation is split into
`deflate.bits`, `deflate.huffman`, `deflate.tables`, `deflate.lz77`,
`deflate.inflate`, `deflate.compress`, `deflate.zlib` and `deflate.gzip`; use
those directly for the extra return values a container needs:

```clojure
(inflate/raw* data nil)   ; => {:bytes [...] :end <byte offset past the stream>}
(zlib/unwrap* data nil)   ; => {:bytes [...] :end ... :adler32 ...}
(gzip/members data)       ; => [{:bytes ... :filename ... :mtime ... :crc32 ...} ...]
(checksum/crc32-update state bytes)  ; running checksums for streaming callers
```

## What it does and does not do

**Decoder** — all three block types, dynamic tables, preset dictionaries, strict
header/checksum validation, a default output ceiling so a compression bomb cannot
exhaust the process, and every RFC-level invalidity reported rather than
tolerated (reserved block type, LEN/NLEN mismatch, back-reference before the
start of the stream, code lengths overrunning the declared tables).

**Encoder** — greedy LZ77 with one-step lazy matching over 32 KiB hash chains,
then a per-block choice between stored, fixed-Huffman and dynamic-Huffman, priced
in bits so the cheapest one wins. Output is a conformant DEFLATE stream —
`java.util.zip.Inflater` reads it at every level, which the test suite asserts —
and typically a few percent larger than zlib's at the same level. Not an optimal
parse (no zopfli-style search), and no preset dictionary on the encoding side.

Correctness-first decode: output accumulates in a persistent vector and
back-references read it via `nth`, so there is no ring buffer to get wrong. Large
rasters should be inflated on demand rather than all at once.

`deflate.lz77` is the one namespace using typed arrays behind reader
conditionals; the hash chains are pure scratch state and the tokens it returns
are ordinary Clojure data. Bit cursors are `volatile!` cells. Both mean this
namespace set is not yet `kotoba/pure`-compilable — a `.kotoba` port is future
work, not a claim this repo makes today.

## Test

```sh
kbb -M:test     # JVM: portable suite + conformance against java.util.zip
kbb --backend sci run-tests.cljk  # ClojureScript: the same portable suite, no host zlib
kbb -M:lint
```

The JVM suite uses `java.util.zip` **only as an oracle**, in both directions:
reference → us proves the decoder reads real streams, and us → reference proves
the encoder writes them. A self-round-trip cannot tell the difference between
"conformant" and "consistently wrong", which is why both directions are pinned,
at every compression level, alongside checksum parity and a ratio bound against
zlib level 9.
