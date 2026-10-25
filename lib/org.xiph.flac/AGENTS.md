# AGENTS.md — org-xiph-flac

FLAC in portable `.cljc`, both directions, zero runtime dependencies.

## Invariants

- **No host codec in `src/`.** The `flac` and `ffmpeg` binaries appear in
  `test/flac/flac_oracle_test.cljk` and `tools/record_fixtures.cljk` only.
  `org-microsoft-riff` is a *test* dependency: the reference decoder emits WAV.
- **Bit-exactness is the assertion.** FLAC is lossless; "decoded without
  throwing" proves nothing. Every fixture carries the reference's own samples.
- **`test/flac/fixtures.cljk` is generated** — `kbb --backend sci tools/record_fixtures.cljk`.
- **The encoder has fixed predictors, LPC and stereo decorrelation**, and is at
  parity: 0.56x-1.03x of `flac -5` measured. The suite's bound is 1.15x, tight
  enough to catch a regression — do not loosen it without a measurement.
- **The reference must accept what we write.** `flac -t` verifies both frame
  CRCs, and `flac -d` must return the input samples exactly. A self round-trip
  proves nothing on its own.
- **Every failure is an `ex-info` with a `:reason`.**
- **Both runtimes are gated** (`kbb -M:test`, `kbb --backend sci run-tests.cljk`).

## Traps

- **`Math/pow` returns a double on the JVM.** A double where an integer is
  expected fails loudly there (`Argument must be an integer: 246.0`) and passes
  silently under ClojureScript, where every number is a double. Every power of
  two goes through `bits/pow2`, which is exact on both. This broke seven JVM
  tests while nbb was green.
- **Side-effecting reads inside a map literal are not sequenced.** A map with
  more than eight entries becomes a hash-map, and under SCI its value forms are
  *not* evaluated in written order — a bit reader threaded through them returns
  shuffled fields. STREAMINFO came back with sample rate 315 (the min frame size)
  until every read moved into a `let`. Never put a reader call in a map literal.
- **LPC needs floor division** (`bits/floor-div`), not `quot`. Truncation toward
  zero is wrong only for negative predictions, so a rising test waveform hides it.
- **The frame number is UTF-8 extended to 36 bits** — seven bytes.
- **The side channel of a decorrelated pair has one extra bit**, and which
  channel that is depends on the assignment (8/9/10).
- **Mid/side stores the mid channel shifted**, with the side channel's parity
  carrying the dropped low bit.
- **Only the first residual partition is shortened by the predictor order.**

## Layout

| namespace | role |
|---|---|
| `flac.core` | metadata blocks, frames, subframes, residuals, stereo decorrelation, `decode` |
| `flac.bits` | MSB-first reader, unary/Rice helpers, the UTF-8-like frame number, `pow2`/`floor-div` |
| `flac.encode` | bit writer, subframe choice by cost, Rice partitioning, frames, STREAMINFO |
| `flac.crc` | CRC-8 (frame header) and CRC-16 (whole frame) |
| `tools/record_fixtures.cljk` | regenerates the fixtures, reference samples included |

## Encoder notes

- **Everything is decided by counting bits**, never by a heuristic: each channel
  block is costed as CONSTANT, then the five fixed predictors, then VERBATIM, and
  the cheapest wins; each residual is costed over every partition order and every
  Rice parameter. There are no tuning constants to get wrong.
- **The CRCs must be right or the reference rejects the file with no other
  symptom.** CRC-8 covers the header up to its own byte; CRC-16 covers the whole
  frame including that header.
- **The STREAMINFO MD5 is written as all zeros**, which the format defines as
  unknown. `flac -t` then reports it unverified and still exits 0.
- **Rice coding costs at least one bit per sample.** An all-zero residual (a
  straight ramp under the order-2 predictor) still costs ~512 bytes per 4096
  samples — there is no all-zero-partition shortcut in the format, so a test
  expecting near-zero is wrong, not the encoder.
- **The LPC residual must be computed with the *quantised* coefficients through
  the same floor division the decoder uses.** An encoder that predicts in floating
  point and lets the decoder predict in integers produces a file only it can read,
  and the failure is silent until a reference decoder sees it.
- **Coefficient quantisation needs error feedback** — carry each rounding error
  into the next coefficient, as libFLAC does, or a 15-bit quantisation drifts the
  prediction.
- **Autocorrelation needs a window.** Without one the estimate implies a periodic
  signal and the coefficients predict the block wrap-around badly at the edges.
- **The side channel of a decorrelated pair needs one extra bit**, and which
  channel that is depends on the assignment (8/9/10). The decoder is unforgiving.
- **Stereo decorrelation beat LPC on the test material**: fixed-only measured up
  to 2.31x of the reference, LPC brought it to 1.95x, decorrelation to 1.03x.
  When the ratio is off, check the channel layout before the predictor.
- **The LPC order is estimated, not searched.** The Levinson-Durbin recursion
  already produces the residual variance at each order, so the order is chosen
  from `n/2 * log2(err) + order * (precision + bps)` and only that order and its
  two neighbours are costed properly. Measured A/B on the same input, stereo
  active in both: **102.7 s to 38.8 s (2.6x) for 0.6% larger output**. Costing all
  twelve buys almost nothing.
- **When timing a change, hold the other variables still.** The first measurement
  of this pruning looked like a *slowdown* (19 s to 39 s) because stereo
  decorrelation had been added in between and quadrupled the subframe work. The
  A/B above was taken with `git stash` on one file and the same input both times.
