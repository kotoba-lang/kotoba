# kotoba-lang/org-microsoft-riff

Zero-dependency portable `.cljc` **RIFF** container and **WAVE** audio
(Microsoft/IBM), both directions.

```clojure
(require '[riff.core :as riff])

(riff/chunks bytes)   ; every chunk: id, offset, size — works on any RIFF form
(riff/parse bytes)    ; => {:format :pcm :channels 2 :sample-rate 44100 :bits 16 …}
(riff/samples bytes)  ; => [[ch0 …] [ch1 …]] deinterleaved
(riff/build {:channels [[…] […]] :sample-rate 44100 :bits 16})
```

Bytes in and out are vectors of unsigned 0-255 integers. Samples are **signed
integers for PCM and doubles for float** — what the file actually holds. A
library that silently normalised everything to [-1,1] would make a bit-exact
round trip impossible.

## Scope

RIFF is a chunk container, not an audio format — `WAVE` is one form of it,
`AVI` and `WEBP` are others — so `chunks` is useful on its own and works on any
of them. What this repo decodes is **uncompressed PCM (8/16/24/32-bit) and IEEE
float (32/64-bit)**, in a plain `fmt ` chunk or `WAVE_FORMAT_EXTENSIBLE`.

Every compressed WAVE codec is **refused by name**: MS-ADPCM, IMA-ADPCM,
A-law, mu-law, GSM 6.10, MP3-in-WAV. Handing their bytes back as samples would be
silent garbage. The chunk walk still works on such a file, which is what a
container reader owes you.

## Why this repo exists

It is the interchange format for audio work. `org-xiph-flac` needs it to be
testable against the `flac` binary at all, and the same is true of anything else
that produces samples. It is also the smallest of the audio formats, so it is
where the sample conventions get pinned down once.

## Traps this format sets

- **8-bit PCM is unsigned with a 128 bias**; 16/24/32-bit are two's complement.
  Sample sign flips with width, and only in WAVE.
- **A chunk's pad byte is not counted in its size.** Odd-sized chunks are padded
  to even; a walker that forgets it drifts one byte per odd chunk and then reads a
  garbage id.
- **`WAVE_FORMAT_EXTENSIBLE` (0xFFFE) hides the real format in a SubFormat
  GUID.** ffmpeg writes 24- and 32-bit PCM that way, so a reader that trusts the
  tag alone rejects perfectly ordinary files.
- **The `data` chunk's declared size is authoritative**, not the file length —
  trailing chunks after `data` are legal and common (`LIST`/`INFO`).
- **RIFF is little-endian**, unlike almost every other container here.

## Floats without a host

`f32`/`f64` are decoded and encoded **arithmetically** — no `DataView`, no
`ByteBuffer` — so they work identically on the JVM and under nbb. Two bugs worth
knowing about, both fixed and both pinned by tests:

- Assembling all eight bytes of an f64 into one integer exceeds 2^53 and loses the
  low mantissa bits: `0.1` came back as `0.10000000000000142`. Nothing in the
  final version forms a value above 2^53.
- Subtracting the implicit 1.0 *before* scaling re-normalises into [0,1), which
  gains an exponent and therefore a bit; the product then lands on a half-integer
  and rounding drops it.

The suite asserts f64 round-trips every double exactly, denormals and the
smallest-normal boundary included, and that f32 round-trips every value that is a
float32 (and lands on the nearest one when it is not).

## Test

```sh
kbb -M:test      # JVM: portable suite + ffmpeg in both directions
kbb --backend sci run-tests.cljk   # ClojureScript: the portable suite, recorded files
kbb -M:lint
```

The oracle's strongest assertion is not "ffprobe accepts our file" but **ffmpeg's
decode of our file is byte-identical to its decode of the original** — both
converted to the same raw format first. A header field at the wrong offset
survives our own reader and fails everywhere else.

Regenerate the recorded files with:

```sh
kbb --backend sci tools/record_fixtures.cljk
```

## Not implemented

No compressed WAVE codecs (see above). No RF64/BW64 (the >4 GiB extension), no
`AVI` or `WEBP` parsing beyond the chunk walk, no cue/playlist/sampler chunk
interpretation, and no streaming — whole buffer in, whole buffer out.
