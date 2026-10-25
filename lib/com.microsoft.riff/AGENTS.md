# AGENTS.md — org-microsoft-riff

RIFF/WAVE, both directions, portable `.cljc`, zero dependencies.

## Invariants

- **No host codec and no host float conversion in `src/`.** No `DataView`, no
  `ByteBuffer`, no `Math.fround`. ffmpeg/ffprobe appear in
  `test/riff/riff_oracle_test.cljk` and `tools/record_fixtures.cljk` only.
- **Samples keep the file's own domain**: signed integers for PCM (8-bit
  de-biased), doubles for float. Do not normalise to [-1,1] — it destroys
  bit-exactness, which is the whole point of a lossless path.
- **Compressed WAVE codecs are refused by name**, never returned as samples.
  The chunk walk still works on them.
- **`test/riff/fixtures.cljk` is generated** — `kbb --backend sci tools/record_fixtures.cljk`.
- **Every failure is an `ex-info` with a `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **8-bit PCM is unsigned (128 bias); everything wider is two's complement.**
- **A chunk's pad byte is outside its size.** One byte of drift per odd chunk.
- **`WAVE_FORMAT_EXTENSIBLE` hides the format in a SubFormat GUID**, and ffmpeg
  writes 24/32-bit PCM that way. Trusting the tag rejects ordinary files.
- **The `data` chunk's size is authoritative, not the file length.**
- **Float encoding, twice bitten:** (1) assembling an f64's eight bytes into one
  integer passes 2^53 and loses mantissa bits — `0.1` became
  `0.10000000000000142`; the layouts are therefore written out explicitly for f32
  and f64 rather than derived by a generic bit-splitter, which is where it went
  wrong. (2) Subtracting the implicit 1.0 before scaling re-normalises into [0,1),
  gains an exponent, and rounding then drops a bit — scale first, subtract after.
- **The denormal exponent sign is easy to invert**: the value is
  `mantissa * 2^(1 - bias - mantissa-bits)`; using `(inc bias)` gave +972 instead
  of −1074 and the smallest denormal decoded as 4e292.
- **`ldexp` must scale in chunks.** A naive `2^-1074` has already underflowed to
  zero, and dividing by it makes the exponent-nudge loop spin forever on the
  smallest denormal.
- **A test that writes 0.49 into a 32-bit float file cannot expect it back.**
  Use float32-exact values (k/256) or the format's own rounding looks like a bug.

## Layout

| namespace | role |
|---|---|
| `riff.core` | chunk walk, `parse`, `samples`, `build`, format tags and the GUID |
| `riff.bytes` | little-endian integers and portable IEEE-754 |
| `tools/record_fixtures.cljk` | regenerates the recorded WAV files |

## Next consumer

`org-xiph-flac` (not built yet): FLAC's oracle is the `flac` binary, which speaks
WAV on both sides, so this repo is how that suite gets its inputs and checks its
outputs.
