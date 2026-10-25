# kotoba-lang/org-xiph-ogg

Zero-dependency portable `.cljc` **Ogg** container (RFC 3533), both directions.

```clojure
(require '[ogg.core :as ogg])

(ogg/logical-streams bytes)   ; every stream in the file, packets reassembled
(ogg/packets bytes)           ; the first stream's packets
(ogg/identify (first (ogg/logical-streams bytes)))  ; :opus / :vorbis / :flac / ...
(ogg/build {:serial 1 :packets [...] :granules [...] :flush-after #{0 1}})
```

Bytes in and out are vectors of unsigned 0-255 integers.

## Why this repo exists

`org-ietf-opus` decodes Opus packets — CELT range decoder, PVQ, MDCT, 925 lines
of it — and **could not open a `.opus` file**, because a `.opus` file is Ogg and
nothing here spoke Ogg. Same for Vorbis and FLAC-in-Ogg. This is the framing
layer those decoders were missing, and it deliberately knows nothing about any of
them: Ogg carries *packets*, not samples.

## What it does

- **Pages** — the 27-byte header, the segment table, CRC verification, and the
  `:tail` of a packet that continues onto the next page.
- **Logical streams** — grouping by serial number, so an interleaved file (audio
  plus video, or chained streams) reassembles per stream rather than per file.
- **Packet reassembly** across page boundaries, including the case where a page
  finishes no packet at all.
- **Muxing** — packets into pages, **splitting a packet across pages** when it
  exceeds one page's 65,025-byte capacity, with the continued flag and the
  reserved granule `-1` set as the format requires.
- **Codec identification** from the first packet: Opus, Vorbis, FLAC, Speex,
  Theora, Skeleton.

## Traps this format sets

- **The CRC-32 is a third variant of the same polynomial.** Ogg uses poly
  0x04C11DB7 unreflected with **initial value 0 and no final complement**;
  bzip2 uses the same polynomial with all-ones init *and* final XOR; gzip/ZIP/PNG
  use the reflected form. Three CRC-32s, one polynomial, no interoperability.
- **The checksum covers the page including its own field**, which must be zeroed
  while computing. Get the region wrong and every page you write is rejected.
- **Fields are little-endian**, unlike most containers. The granule position is
  64-bit, so it is handled as two 32-bit halves — a 64-bit shift does not exist
  on ClojureScript.
- **Granule `0xFFFFFFFFFFFFFFFF` means "no packet ends on this page"**, not
  "position zero". It is returned as `:none` so it cannot be arithmetic'd by
  accident, and the muxer sets it on any page that finishes no packet.
- **A packet whose length is a multiple of 255 needs a terminating zero
  segment.** Omit it and the packet reads as continuing onto the next page —
  either losing the last packet of a stream or fusing two.
- **Codec mappings decide where pages break, not the container.** Opus (RFC 7845
  §3) requires its ID header alone on the first page and its comment header on
  its own page; a greedy muxer produces a file ffmpeg refuses. `build` exposes
  `:flush-after` rather than guessing.

## Test

```sh
kbb -M:test      # JVM: portable suite + ffmpeg in both directions
kbb --backend sci run-tests.cljk   # ClojureScript: the portable suite, recorded containers
kbb -M:lint
```

The portable suite carries real Ogg files produced by ffmpeg (Opus, Vorbis and
FLAC), so ClojureScript asserts conformance rather than self-consistency. The JVM
suite adds the direction a recording cannot cover: **a file we muxed, decoded by
ffmpeg**, plus a page-for-page byte-identical rebuild of the reference's own
pages — the check that would catch a wrong checksummed region.

Regenerate the fixtures with:

```sh
kbb --backend sci tools/record_fixtures.cljk   # confirms ffmpeg decodes each one before writing
```

## Not supported

No seeking (no bisection search on granule position). No chained-stream
concatenation helper — `logical-streams` returns each serial separately and the
caller decides what a chain means. No codec decoding of any kind: that is what
`org-ietf-opus` and the FLAC repo are for.
