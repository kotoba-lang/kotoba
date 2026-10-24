# AGENTS.md — org-ietf-deflate

DEFLATE (RFC 1951) + zlib (RFC 1950) + gzip (RFC 1952), both directions, in
portable zero-dep `.cljc`. This is a **leaf**: it must never grow a dependency,
and nothing here may depend back on `kasane`, `utsushi` or any consumer.

## Invariants

- **No host codec, ever.** `java.util.zip`, Node `zlib`, `pako`, `CompressionStream`
  are forbidden in `src/`. They appear in `test/deflate/jvm_interop_test.cljk`
  only, as a conformance oracle. The whole point of this repo is that a caller
  on any runtime — JVM, browser, nbb, a future `.kotoba` host — gets the same
  bytes without one.
- **Zero dependencies.** `deps.edn` `:deps` stays empty. Consumers
  (`org-w3-png`, `org-pkware-zip`, `org-w3-woff`, `org-iso-pdf`) pin this repo,
  so a dependency added here lands in all of them.
- **Both directions stay conformance-tested against a reference.** When you
  touch the encoder, the assertion that matters is
  `our output → java.util.zip.Inflater`, not a self-round-trip: a bug that
  changes both halves consistently passes a round-trip and breaks every real
  consumer. Levels 0–9 are all covered; keep it that way.
- **Unsigned bytes in, vectors of unsigned bytes out.** No byte arrays, no
  typed arrays, no strings in the public API.
- **Every failure is an `ex-info` with `:reason`.** Containers dispatch on it.
  Do not throw bare exceptions and do not silently tolerate invalid streams —
  the decoder is a parser for hostile input.
- **ClojureScript numerics.** Bitwise operators return *signed* int32 there, so
  any value that can reach the high bit is normalised through
  `deflate.checksum/u32`. If you write new bit-twiddling, add a case to the
  "unsigned 32-bit domain" test in `portable_test.cljc`.
- **The portable suite must pass under both runtimes.** `kbb -M:test` and
  `kbb --backend sci run-tests.cljk`. Keep sizes in `portable_test.cljc` modest — nbb
  interprets, so a megabyte-scale case belongs in the JVM suite instead.

## Layout

| namespace | role |
|---|---|
| `deflate.core` | public facade; the only namespace consumers should need |
| `deflate.tables` | RFC 1951 constants, shared by both directions so they cannot drift |
| `deflate.bits` | bit reader/writer; LSB-first data vs MSB-first Huffman codes |
| `deflate.huffman` | canonical codes both ways + length-limited Huffman from a histogram |
| `deflate.inflate` | decompressor; `raw*` also reports where the stream ended |
| `deflate.lz77` | match finder (typed-array hash chains) |
| `deflate.compress` | block strategy: price stored/fixed/dynamic, emit the cheapest |
| `deflate.zlib` / `deflate.gzip` | the two wrappers, with header validation and checksums |
| `deflate.checksum` | Adler-32 + CRC-32 (also used by `org-pkware-zip`) |

## Traps

- **Two bit orders.** Data elements are LSB-first; Huffman codes are MSB-first
  (RFC 1951 §3.1.1). Mixing them produces a stream only this decoder can read —
  which is precisely what the interop test exists to catch.
- **A Huffman tree the format cannot express.** Code lengths are capped at 15
  bits (7 for the code-length alphabet). `huffman/lengths-from-freqs` returns
  nil rather than an illegal tree; callers must fall back (the encoder falls
  back to fixed). Never emit an over-long code.
- **A dynamic block still needs a distance tree** even with no matches, and a
  one-symbol tree cannot be expressed with a nonzero length — hence the padding
  to two codes in `lengths-from-freqs`.
- **`inflate` validates and verifies by default.** That was a deliberate
  behaviour change (ADR-2607300400): the old version skipped the zlib header
  blind and ignored Adler-32. If a consumer feeds deliberately truncated
  streams, it passes `:verify-checksum false` — do not weaken the default.
- **Do not "optimise" the decoder's output vector into a mutable buffer**
  without measuring: back-references read the output, so a ring buffer changes
  the correctness argument, and the persistent vector is what makes the decoder
  safe to use from two runtimes and re-entrant.

## Changing pins

Consumers pin this repo by git sha in their own `deps.edn` and each has a
`:local` alias for same-monorepo development. After landing a change here, run
the consumers' suites with `-M:local:test` before advancing their pins, and
advance `manifest/west.yml` in the superproject via a single-entry commit.
