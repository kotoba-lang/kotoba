# kotoba-lang/org-xiph-flac

Zero-dependency portable `.cljc` **FLAC** codec (xiph.org's format
specification) — decoding, and encoding with fixed predictors.

```clojure
(require '[flac.core :as flac])

(flac/flac? bytes)       ; signature sniff
(flac/stream-info bytes) ; sample rate, channels, bit depth, total samples, MD5
(flac/metadata bytes)    ; every metadata block, VORBIS_COMMENT tags included
(flac/decode bytes)      ; => {:channels [[…] […]] :sample-rate … :bits … :samples n}
(flac/encode {:channels [[…] […]] :sample-rate 44100 :bits 16})
```

FLAC is lossless, so there is exactly one right answer: `decode` returns the
original integer samples, per channel, exactly. Samples are signed integers at
the stream's own bit depth — not normalised — the same convention as
`org-microsoft-riff`.

## What is implemented

All four subframe types (CONSTANT, VERBATIM, FIXED orders 0-4, LPC orders 1-32),
both Rice residual methods with escaped partitions, wasted-bits subframes, all
three stereo decorrelations (left/side, right/side, mid/side), every block-size
and sample-rate coding including the explicit 8- and 16-bit forms, and
STREAMINFO / VORBIS_COMMENT metadata with the remaining block types reported by
type, offset and length.

## Encoding

`encode` writes FLAC with **fixed predictors, LPC and stereo decorrelation**,
every choice made by counting bits: each block is costed as CONSTANT, as each of
the five fixed predictors, as LPC at every order up to 12, and as VERBATIM, and
the cheapest wins; a stereo pair is costed as independent, left/side, right/side
and mid/side; each residual is costed over every partition order and Rice
parameter. No tuning constants, no heuristics.

`flac -t` accepts the output — which verifies both frame CRCs — and `flac -d`
returns the input samples exactly.

**The ratio is at parity, measured: 0.56x-1.03x of `flac -5`** on the suite's
sources — at or better than the reference on every one, and within 3% of
`flac -8` on the hardest. Getting there took both pieces, in this order of
effect: fixed predictors alone measured 0.56x-2.31x, LPC brought the worst case to
1.95x, and stereo decorrelation brought it to 1.03x. On material whose channels
resemble each other, decorrelation matters more than prediction quality does.

The LPC order is **estimated** from the Levinson-Durbin residual variance rather
than searched, and only that order and its two neighbours are costed properly —
measured 2.6x faster for 0.6% larger output than costing all twelve. Still
missing: the coefficient precision is fixed at 15 bits rather than searched, the
residual partitioning is still exhaustive, and there is no `-e`-style model
search. It remains slow in absolute terms under nbb.

When comparing sizes yourself, pass `--no-padding` to the reference: it writes an
8 KB PADDING block by default, which makes a naive comparison on short inputs
meaningless (it reported our output as 30x *smaller* until I noticed).

## Not implemented

**The STREAMINFO MD5 is recorded on read and written as all zeros** (the format's
value for *unknown*, which `flac -t` reports as unverified rather than as a
failure), because there is no MD5 in this workspace and a codec is the wrong place
to add one. On read it is** — there is no MD5 in this
workspace, and a codec is the wrong place to add one. Frame CRC-8/CRC-16 fields
are read past rather than checked; corruption still surfaces, because a damaged
frame fails structurally (the suite flips a bit and asserts it is caught).

Also absent: Ogg-encapsulated FLAC (`org-xiph-ogg` identifies it, and the
mapping's header would need unwrapping first), seeking, and streaming — whole
buffer in, whole buffer out, bounded by `:max-samples`.

## Traps this format sets

- **The frame number is UTF-8-*like*, extended to 36 bits** — seven bytes, well
  past the four Unicode allows. A decoder written against modern UTF-8 rejects a
  legal frame beyond 2^31 samples.
- **The side channel of a decorrelated pair carries one extra bit**, because a
  difference needs the range. Which channel it is depends on the assignment.
- **Mid/side hides a low bit**: the mid channel is stored shifted, and the side
  channel's parity restores it.
- **The first partition of a residual is shorter by the predictor order**, and
  only the first.
- **LPC prediction needs a floor division**, not a truncation — `quot` rounds
  toward zero and produces wrong samples on negative predictions only, so a
  suite that tests a rising waveform passes.

## Test

```sh
kbb -M:test        # JVM: portable suite + the `flac` binary, sample for sample
kbb -M:local:test  # …against sibling checkouts
kbb --backend sci run-tests.cljk     # ClojureScript: the portable suite, recorded fixtures
kbb -M:lint
```

The portable fixtures carry **the reference decoder's own output**, so
ClojureScript asserts bit-exactness rather than "it decoded something". The JVM
suite adds the breadth a recording cannot: **every compression level 0-8** over
four sources chosen so each subframe type occurs, three bit depths (8/16/24),
mono and stereo, four block sizes, a sample rate outside the frame header's
table, a 3-second file, and an encoder-written VORBIS_COMMENT.

Regenerate the fixtures with:

```sh
kbb --backend sci tools/record_fixtures.cljk
```
