# AGENTS.md — org-sourceware-bzip2

bzip2, both directions, portable `.cljc`, zero dependencies.

## Invariants

- **No host codec in `src/`.** No `java.util.zip`, no node stream, no shelling
  out. The `bzip2`/`bunzip2` binaries appear in `test/bzip2/bzip2_oracle_test.cljk`
  and `tools/record_fixtures.cljk` only.
- **Both directions are conformance-tested against the reference**, and the
  encoder is checked by `bunzip2 -t` as well as by `bunzip2 -c`. An encoder that
  only agrees with its own decoder passes nothing.
- **`test/bzip2/fixtures.cljk` is generated.** Regenerate with
  `kbb --backend sci tools/record_fixtures.cljk`, which round-trips every stream through
  `bunzip2` before writing and refuses otherwise.
- **Unsigned byte vectors in the API**, on both runtimes.
- **Every failure is an `ex-info` with a `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **MSB-first bit order**, unlike DEFLATE. If you copy a bit cursor from
  `org-ietf-deflate`, you will get a stream only this decoder can read.
- **The CRC-32 is the unreflected variant** (`bzip2.crc`), pinned to the CRC
  catalogue's check value. Do not reach for `deflate.checksum/crc32`.
- **The rank packing in `bwt/forward` requires every rank below `n`.** Seeding it
  with raw byte values silently mis-sorts any block shorter than 256 bytes whose
  values are spread out; the block then fails its own CRC on the way back. That
  bug was real — `test/bzip2/bzip2_test.cljk` keeps the case
  (`short-with-spread-values`) that caught it.
- **Rotations, not suffixes.** For a block whose end repeats its beginning the
  orders differ and only the rotation order round-trips.
- **RLE1 groups are indivisible** (four equal bytes plus a count byte). The block
  splitter packs whole groups for that reason.
- **`(int "a")` is `0` in ClojureScript** — `int` is `(bit-or x 0)` and a string
  coerces to 0. A sweep written with `(mapv int "text")` compresses a vector of
  zeros and proves nothing; it looked like a 46-byte miracle before the oracle
  caught it. The suite uses `.charCodeAt` under `:cljs`.
- **The encoder's four-iteration table assignment is what makes the output the
  expected size.** Reduce it to one table and everything still round-trips,
  which is why the ratio bound against `bzip2 -9` is part of the suite.

## Layout

| namespace | role |
|---|---|
| `bzip2.core` | facade: `compress`, `decompress`, `bzip2?` |
| `bzip2.bits` | MSB-first bit reader/writer, 32- and 48-bit fields in halves |
| `bzip2.crc` | the unreflected CRC-32 and the rotate-then-XOR stream fold |
| `bzip2.huffman` | decode tables (`limit`/`base`/`perm`), length generation with the weight-scaling cap, the delta-walk table encoding |
| `bzip2.bwt` | inverse (O(n)) and forward (prefix doubling) transform |
| `bzip2.decode` | symbol map, selectors, RLE2, RLE1, blocks, concatenated streams |
| `bzip2.encode` | RLE1 grouping and block splitting, MTF/RLE2, table assignment, emission |
| `tools/record_fixtures.cljk` | regenerates the recorded reference streams |
