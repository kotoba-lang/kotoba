# kotoba-lang/org-ietf-zstd

Zero-dep portable `.cljc` **Zstandard decompressor** (RFC 8878), with a
raw-block writer. Named `org-ietf-zstd` — zstd is specified by IETF RFC 8878,
the same `org-ietf-*` pattern as `org-ietf-deflate`.

## Usage

```clojure
(require '[zstd.core :as zstd])

;; read
(zstd/decompress zst-bytes)                    ; → vector of unsigned bytes
(zstd/decompress zst-bytes {:max-output (* 64 1024 1024) :verify-checksum true})
(zstd/frames zst-bytes)                         ; per-frame window, content size, checksum flag

;; write (raw blocks — see below)
(zstd/compress bytes)
(zstd/compress bytes {:checksum false})
```

## What it decodes

Everything the reference `zstd` produces without a dictionary:

| part | support |
|---|---|
| frame header | all content-size widths, single-segment, window descriptor, skippable frames, multi-frame files |
| block types | raw, RLE, compressed |
| literals | raw, RLE, Huffman, **treeless** (reusing the previous block's table), 1 or 4 bitstreams |
| Huffman table | direct 4-bit weights *and* FSE-compressed weights |
| sequences | predefined / RLE / FSE / **repeat** modes for each of the three code types |
| offsets | the three repeat offsets, including the literal-length-zero rule |
| checksum | XXH64 (implemented here, in 32-bit halves) verified by default |

Failures are `ex-info` with a `:reason` — `:not-zstd`, `:truncated`,
`:checksum-mismatch`, `:bad-frame-header`, `:bad-block`, `:bad-literals`,
`:bad-sequences`, `:bad-huffman-table`, `:bad-fse-table`, `:bad-bitstream`,
`:bad-offset`, `:size-mismatch`, `:output-limit`, `:dictionary-required`.

**Dictionaries are refused by name** (`:dictionary-required` with
`:dictionary-id`), not silently mis-decoded.

## What it does not do

There is **no zstd encoder**. `compress` writes a conformant frame of *raw*
blocks — `zstd -t` and `zstd -d` accept it, which the suite asserts — but it does
not compress. A real encoder needs FSE and Huffman table construction, a match
finder, and the block-strategy decisions that make zstd worth using; a naive one
would be larger and slower than `org-ietf-deflate`'s gzip while adding a class of
"only our decoder reads it" bugs. Use gzip when you want size, and this when you
need to *read* `.zst`.

Also absent: streaming (whole-buffer only; `:max-output` bounds a hostile file)
and long-distance matching beyond what fits in the output buffer.

## Layout

| namespace | role |
|---|---|
| `zstd.core` | frames, blocks, literals section, sequences section, execution, writer |
| `zstd.fse` | FSE table description, table build, decoder, RFC predefined distributions |
| `zstd.huff` | Huffman weights (direct and FSE-coded) → decode table |
| `zstd.bits` | the two bit readers: forward LSB-first, backward MSB-first |
| `zstd.xxhash` | XXH64 as `[hi lo]` 32-bit halves |

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against the zstd CLI
kbb --backend sci run-tests.cljk       # ClojureScript: the same portable suite
kbb -M:lint
```

The JVM suite generates every fixture with the reference `zstd` and compares
byte-for-byte: levels −1/−3/−9/−19 across nine input shapes, with and without a
checksum, three window configurations, a >1 MB multi-block file, concatenated
frames, skippable frames, a dictionary frame (asserting the refusal), and our own
output read back by `zstd -d` and `zstd -t`. Our XXH64 is checked against the
checksum the reference writes into its own frames.

That breadth is the point. zstd has more independent paths per block than any
other codec here, and a decoder can be wrong in one while looking healthy in the
others — three real bugs found this way, all recorded in AGENTS.md.
