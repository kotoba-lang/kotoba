# AGENTS.md — org-xiph-ogg

The Ogg container, both directions, portable `.cljc`, zero dependencies.

## Invariants

- **This repo decodes no codec.** Ogg carries packets; Opus/Vorbis/FLAC live
  elsewhere. `identify` sniffs a first packet and stops there.
- **ffmpeg appears in tests only** (`test/ogg/ogg_oracle_test.cljk`,
  `tools/record_fixtures.cljk`), never in `src/`.
- **Both directions are checked against ffmpeg**, including a file we muxed being
  decoded by it. A container writer that only satisfies its own reader proves
  nothing.
- **`test/ogg/fixtures.cljk` is generated** — `kbb --backend sci tools/record_fixtures.cljk`,
  which confirms ffmpeg decodes each file before recording it.
- **Every failure is an `ex-info` with a `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **Ogg's CRC-32 is neither gzip's nor bzip2's**: same polynomial, init 0, no
  final complement. `(crc32 [])` is 0, which is a quick way to tell it apart.
- **The CRC covers the page including its own zeroed field.** `build-raw` patches
  the four bytes in afterwards for that reason; do not "optimise" it into a
  prefix computation.
- **Granule `:none` is the reserved -1** and means no packet ends on this page.
  It is a keyword, not a number, so it cannot silently become 18446744073709551615.
  Any page the muxer emits that finishes no packet must carry it.
- **A packet length that is a multiple of 255 needs a terminating zero segment.**
  `lacing` handles it; a hand-rolled segment table usually does not.
- **A page holds at most 255 lacing values = 65,025 bytes.** Larger packets are
  split across pages by `stream/build`; the split page must end on a 255 segment
  with no terminator, which is why `page/build-raw` (explicit segments) exists
  alongside `page/build` (segments derived from packets).
- **Opus requires its headers on their own pages** (RFC 7845 §3). `:flush-after`
  exists because of that; without it ffmpeg rejects our output. The test suite
  passes `#{0 1}` for exactly this reason — if you remove it, the oracle fails.
- **`(int "a")` is 0 in ClojureScript.** Test helpers use `.charCodeAt`.

## Layout

| namespace | role |
|---|---|
| `ogg.core` | facade: `ogg?`, `logical-streams`, `packets`, `identify`, `build` |
| `ogg.crc` | the init-0/no-xorout CRC-32 variant |
| `ogg.page` | page parse, `build` (from packets) and `build-raw` (explicit segments), `lacing` |
| `ogg.stream` | packet reassembly across pages, muxing with splitting and `:flush-after` |
| `tools/record_fixtures.cljk` | regenerates the recorded reference containers |
