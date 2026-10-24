# kotoba-lang/org-ietf-brotli

Zero-dep portable `.cljc` **brotli decompressor** (RFC 7932), including the full
122,784-byte static dictionary and its 121 word transformations.

Named `org-ietf-brotli` — brotli is specified by IETF RFC 7932, the same
`org-ietf-*` pattern as `org-ietf-deflate` and `org-ietf-zstd`.

## Usage

```clojure
(require '[brotli.core :as brotli])

(brotli/decompress br-bytes)                       ; → vector of unsigned bytes
(brotli/decompress br-bytes {:max-output (* 64 1024 1024)})
```

Failures are `ex-info` with a `:reason` — `:truncated`, `:bad-window-size`,
`:bad-metablock`, `:bad-prefix-code`, `:bad-context-map`, `:bad-context-mode`,
`:bad-block-type`, `:bad-distance`, `:bad-dictionary-word`, `:bad-transform`,
`:output-limit`.

## What it decodes

Everything the reference encoder produces at every quality level, which matters
more here than for other codecs: brotli's `-q` does not merely tune a match
finder, it turns *format features* on and off.

| feature | support |
|---|---|
| window sizes 10-24 (`--lgwin`) | yes, including the reserved-code rejection |
| meta-blocks: compressed, uncompressed, empty, metadata | yes |
| three block categories with up to 256 block types each | yes |
| literal context modelling (LSB6, MSB6, UTF8, Signed) | yes |
| context maps with run-length coding + inverse move-to-front | yes |
| simple *and* complex prefix codes, with both repeat mechanisms | yes |
| distances: 16 recent-distance symbols, NPOSTFIX/NDIRECT, ring buffer | yes |
| **static dictionary** with all 121 transformations | yes |

There is **no encoder**, and there is unlikely ever to be one: brotli's whole
design is expensive-encode / cheap-decode, and this workspace's compressing path
is `org-ietf-deflate` (gzip). Also absent: streaming (whole-buffer only,
`:max-output` bounds a hostile input) and custom dictionaries.

## Where the tables come from

The dictionary, the transformations and the three context-ID lookup tables are
**generated from the text of RFC 7932** by `tools/extract_rfc_tables.cljk`, and
every one of them is verified against the check value the RFC publishes for it:

| table | size | CRC-32 |
|---|---|---|
| static dictionary (Appendix A) | 122,784 bytes | `0x5136cb04` |
| word transformations (Appendix B) | 648 bytes | `0x3d965f81` |
| Lut0 / Lut1 / Lut2 (§7.1) | 256 bytes each | `0x8e91efb7` / `0xd01a32f4` / `0x0dd7a0d6` |

```sh
curl -sL https://www.rfc-editor.org/rfc/rfc7932.txt -o /tmp/rfc7932.txt
kbb --backend sci --classpath ../org-ietf-deflate/src tools/extract_rfc_tables.cljk /tmp/rfc7932.txt
```

That is not ceremony. Three bugs in this workspace's zstd decoder were
mis-remembered constants that stayed *plausible* when wrong (ADR-2607300500), and
a fourth showed up here: the generator first emitted the RFC's C string literals
verbatim, so transform 22's suffix was the two characters `\` and `n` instead of
one newline — which corrupted exactly one byte per dictionary reference, on
inputs above ~76 KB, at high qualities only.

`src/brotli/data.cljk` is generated (169 KB, the dictionary as base64) and should
never be hand-edited.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against the brotli CLI
kbb --backend sci run-tests.cljk       # ClojureScript: the same decoder, recorded fixtures
kbb -M:lint
```

The JVM suite drives the reference `brotli` binary across qualities 0/1/2/5/9/11
over ten input shapes, four window sizes, an input that can only compress via the
static dictionary, sizes either side of the meta-block boundaries, and a 2 MB
file, then cross-checks that the reference decoder agrees on the same bytes. The
portable suite carries recorded reference streams so the same decode paths — the
dictionary included — run on a runtime with no shell.
