# Changelog

## 0.5.1 — 2026-08-03

Measured whether 0.5.0's per-arm bandwidth lookup actually predicts better. It
does, modestly: on 2e6 elements of 128 doubles reading one field, the ratio
error goes from 10% (one constant) to 4% (per arm) against a measured 17.56x.

Recorded with three reasons not to treat it as strong. The arms' bandwidths
differed by only 1.14x here because the JVM curve is compressed at short
strides, so this did not exercise the 2.5x gaps the change was designed for.
The absolute times are 15-20% out under both schemes, and per-arm is slightly
**worse** on the AoS arm alone while better on the ratio. And it is one
configuration on one machine under one runtime.


## 0.5.0 — 2026-08-03

`achievable-ratio` reads the machine's bandwidth curve **per arm**.

The two arms of a layout comparison do not walk the same stride. Reading one
field of a 128-byte AoS element skips 128 bytes a step; the same field in a SoA
skips 8. At a 4 KiB element they are 4096 and 8 — opposite ends of the curve,
15.3 GB/s against 6.2 on the machine this was calibrated against.

Handing both arms one bandwidth figure is the error that made two models wrong
in a single afternoon. `touch-stride-bytes` computes each arm's stride and the
curve is read at it. An explicit `:bandwidth-bytes-per-ns` still wins, because
a caller who measured this exact pass knows better than a curve; with neither a
figure nor a curve it throws rather than defaulting, naming both remedies.

Each arm reports the `:stride-bytes` and `:bandwidth-bytes-per-ns` it used, so
the choice is visible rather than implied.

23 tests, 99 assertions.


## 0.4.0 — 2026-08-03

**Bug fix.** `cost` charged `ceil(element-bytes / line)` lines per AoS element
unconditionally — "AoS pulls the whole struct". That holds while the struct
fits a line or two, because the line holding one field also holds the
neighbours the pass is about to touch. Past that it is false: reading one f64
out of a 4 KiB element pulls **one** line, not thirty-two.

The model over-counted a 4 KiB element by 32x and reported a 512x AoS/SoA ratio
where 16x is the truth. Every fixture used elements of a line or less, so it
never showed. Wide elements are now charged the lines their touched fields
actually sit on; the narrow case keeps the span formula unchanged; and reading
all fields of a wide element still gives `ceil(element/line)`, so the fix
degrades correctly. All three are pinned by tests.

**Documented.** `achievable-ratio`'s bandwidth input must match the stride
being modelled. Measured here, one f64 touched every S bytes over 256 MiB:

    stride  128 B  256 B  512 B  1 KiB  4 KiB  16 KiB  64 KiB
    GB/s     24.1   29.7   27.6   34.3   14.5    11.5    14.2

A 3x spread with the floor at the 16 KiB page size, where the TLB gives out.
Handing the 34 GB/s figure to a plan about a page-strided walk is the error
that made `traversal/tiling-benefit` v1 predict 1.00x against a measured 2.69x.

19 tests, 86 assertions.


## 0.3.2 — 2026-08-03

`achievable-ratio` now has a real test behind it. Constants measured
independently — loop floor on an L1-resident array, bandwidth on a line-strided
scan of a differently-sized one — predicted a configuration neither touched, to
within 19% (erring pessimistic). Recorded in `:model/calibration` as
`:held-out-test`.

The first attempt missed by 65%, and the fault was the calibration rather than
the model: bandwidth measured with a contiguous f64 sum reports the loop floor
in different units, because 8 bytes per iteration at 0.77 ns caps at 10.4 GB/s.


## 0.4.0 — 2026-08-03 (second entry)

The held-out test `achievable-ratio` was owed.

`loop-floor-ns` measures the loop on a 16 KiB L1-resident array, where memory
is free. `bandwidth-bytes-per-ns` measures a **line-strided** scan of a 45 MiB
array, where the loop is amortised over a whole cache line per touch. Neither
shares a size, stride or element width with the configuration then predicted.

Result: predicted AoS 8.501 ms / SoA 3.084 ms for 4e6 elements of 8 doubles;
measured 6.848 / 2.804. Within 19%, erring toward pessimism.

**It failed first, at 65%, and the fault was the calibration.** Bandwidth had
been measured with a contiguous f64 sum — 8 bytes per iteration at 0.77 ns caps
at 10.4 GB/s, so what came back was the loop floor in different units, and the
model duly over-predicted the AoS arm by 2.9x. Measure bandwidth where the loop
is not the bottleneck.


## 0.3.1 — 2026-08-03

**Correction.** The agreements between `achievable-ratio` and measurement
reported in 0.3.0 are not validations. Both inputs were derived from the two
arms being explained — the loop floor from the candidate, the bandwidth from
the baseline — so the formula returns their ratio by construction wherever
neither term clamps. The model may be right; nothing so far has tested it.
`achievable-ratio`'s docstring now says so, and says what an honest test would
need: an L1-resident loop-floor measurement and a separate streaming-bandwidth
measurement, used to predict a configuration nobody measured.

New calibration point, and this one is a real measurement. The serial
summation loop ran at floating-point add *latency* — 2.87 ns/element for one
load and one add, about ten cycles — because every add waited on the previous
one. Four independent accumulators took it to 0.87 ns and moved the measured
AoS/SoA ratio from 2.12x to 6.63x. **The layout was never what was being
measured; the dependency chain was.** At n=8e6 the same change reached 20.2x,
*above* the byte model's 16x, because a 1 GiB array exhausts TLB reach — the
other direction, and also on the not-modelled list.


## 0.3.0 — 2026-08-03

`achievable-ratio` — the missing step from bytes to time.

`cost` counts bytes and always did so correctly. The 16x-predicted /
2.02x-measured gap recorded in 0.2.0 was never a modelling error; it was a
category error in the reading. A bytes ratio becomes a time ratio only when
BOTH arms are memory-bound, and the moment one arm's per-element loop cost
exceeds its memory cost that arm stops getting faster and the ratio caps.

    per-arm time = max(loop-ns-per-element * n, bytes-fetched / bandwidth)

Fed the two numbers measured on an Apple M1 Max — a 3.03 ns/element loop floor
and 18.5 GB/s observed by one thread — this reproduces the measurement:
predicted 13.8 ms / 6.0 ms against a measured 13.844 ms / 6.066 ms, and an
achievable ratio of 2.30x against a measured 2.28x.

`:both-memory-bound?` is the field that matters: when it is false the bytes
ratio is unreachable no matter how good the layout is, and a plan promising it
is promising something the loop will not allow.

16 tests, 81 assertions.


## 0.1.0 — 2026-08-03

Initial implementation. AoS / SoA / AoSoA planning against a `machine`
descriptor, with a printed cost model.

- `aos` (declaration order, optional `:reorder?` and `:pad-to-line?`), `soa`,
  `aosoa` with a block width chosen so each sub-array is a whole number of
  lines.
- `cost` / `recommend` — compulsory-line model, returns the losers and the
  model itself. `:cost/streams` breaks ties on the thing a line count cannot
  price.
- `lines-for-strided-run` — the two stride regimes, which is where a layout
  decision actually flips.
- `abi-canonical?` / `abi-guard!` — a reordered or padded layout may not cross
  a Canonical ABI boundary.
- `false-sharing-risk` judged on write stride, so SoA is correctly flagged
  where AoS is not.

14 tests, 72 assertions.
