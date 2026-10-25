# kotoba-lang/org-tukaani-xz

Portable `.cljc` **LZMA / LZMA2 decompressor** with the **.xz** container
(Tukaani's `xz-file-format.txt`) and the legacy **.lzma** "alone" format. One
dependency: `org-ietf-deflate`, for the CRC-32 that .xz uses on every structural
field.

Named `org-tukaani-xz` — Tukaani publishes the .xz and .lzma format
specifications, the same `org-<body>-<spec>` pattern as `org-ietf-deflate` and
`org-pkware-zip`.

## Usage

```clojure
(require '[xz.core :as xz])

;; read
(xz/decompress xz-bytes)                    ; .xz → vector of unsigned bytes
(xz/decompress xz-bytes {:max-output (* 64 1024 1024)})
(xz/decompress-alone lzma-bytes)            ; legacy .lzma
(xz/streams xz-bytes)                       ; per-stream check type, blocks, index

;; write (see "What it does not do")
(xz/compress bytes)                         ; → .xz, LZMA2 uncompressed chunks
(xz/compress bytes {:check :crc32})
(xz/lzma2-uncompressed bytes)               ; raw LZMA2, as org-7-zip-7z uses

;; the codec directly, if you have a raw stream
(require '[xz.lzma :as lzma])
(lzma/decompress-lzma2 bytes 0 {:dict-size (* 8 1024 1024)})
(lzma/decompress-lzma1 bytes 0 {:props 0x5d :unpacked-size n})
```

## What it does

**Decoding is complete for what liblzma produces by default**: LZMA1, LZMA2, all
of `xz`'s presets 0–9, every dictionary size, non-default `lc`/`lp`/`pb`,
multi-block streams, multi-stream files with stream padding, the Delta filter,
and all four integrity checks.

Every structural CRC-32 (stream flags, block header, index, footer) and the
per-block check are **verified by default**:

| check type | status |
|---|---|
| None | accepted, nothing to verify |
| CRC-32 | verified (from `org-ietf-deflate`) |
| CRC-64 | verified — the default `xz` uses; implemented here as 32-bit halves because ClojureScript has no 64-bit integer |
| SHA-256 | verified (from `org-nist-sha2`) |

A hash implementation does not belong *inside* a compression library, which is
why SHA-256 is a dependency rather than code in this repo — and why `:sha256`
remains an injection point for a caller that already has one it would rather use:

```clojure
(xz/decompress f {:sha256 (fn [bytes] ...32 bytes...)})
```

Until `org-nist-sha2` existed, a `--check=sha256` stream was **refused by name**:
the alternatives were injecting a host hash or declining the file, and declining
was the honest one. That refusal is gone.

Failures are `ex-info` with a `:reason` — `:not-xz`, `:truncated`,
`:checksum-mismatch`, `:bad-block-header`, `:bad-index`, `:bad-footer`,
`:unsupported-filter`, `:unsupported-check`, `:output-limit`, `:bad-properties`,
`:bad-chunk`, `:bad-distance`, `:size-mismatch`.

## What it does not do

- **No LZMA encoder.** `compress` writes a conformant .xz file whose LZMA2 chunks
  are *uncompressed* — `xz -t` and `xz -d` accept it, which the suite asserts —
  but it does not compress. An LZMA encoder is only worth having with the
  optimal-parse price model, and shipping a bad one would be worse than shipping
  none: reach for `org-ietf-deflate`'s gzip when you want size, and for this when
  you need the .xz container itself (a 7z folder, a tool that only accepts .xz).
- **No BCJ filters.** x86, ARM, ARM64, PowerPC, IA64, SPARC and RISC-V branch
  conversion are recognised and **refused by name** (`:unsupported-filter` with
  `:filter :bcj-x86`). They are not `xz`'s default, and mis-decoding them
  silently would corrupt executables in a way that looks like a compiler bug.
- **No streaming.** Whole-buffer in, whole-buffer out. The decoder holds the
  entire output because LZMA back-references reach up to the dictionary size into
  it; `:max-output` bounds the damage from a hostile file.
- **Values above 2^53** in a variable-length integer are refused rather than
  rounded, since ClojureScript cannot represent them exactly.

## Test

```sh
kbb -M:test          # JVM: portable suite + conformance against liblzma and the xz CLI
kbb -M:local:test    # …against a sibling org-ietf-deflate checkout
kbb --backend sci run-tests.cljk       # ClojureScript: the same portable suite
kbb -M:lint
```

The JVM suite generates every fixture with python3's `lzma` (which *is* liblzma)
and compares byte-for-byte: presets 0/1/6/9 across eight input shapes, all four
check types, dictionaries from 4 KiB to 16 MiB, five `lc`/`lp`/`pb` combinations,
the Delta chain, a BCJ chain (asserting the refusal), multi-block and
multi-stream files, `.lzma` at three presets, and a 1 MB file. Our own output is
then read back by python's `lzma`, by `xz -d`, and by `xz -t`.

That thoroughness is not decoration. LZMA has no byte alignment, no Huffman
tables and no resynchronisation point: a probability index off by one produces
plausible output for a few hundred bytes and then diverges, so only a
byte-for-byte comparison against the reference across many parameter
combinations actually tells you the decoder is right.
