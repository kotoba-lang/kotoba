# Changelog

## 0.6.0 — 2026-08-03

`kbb -M:perarm` — does per-arm bandwidth lookup predict better than one
shared constant?

One configuration, two predictions, one measurement, and a verdict that can say
the change bought nothing. It measures the bandwidth curve on the same run
rather than reusing a pasted one, so a stale constant cannot be blamed either
way.

Result on this machine: ratio error 10% with one constant, 4% per arm, against
a measured 17.56x. The limits are recorded in `layout`'s calibration — chiefly
that the JVM curve is compressed at short strides, so the arms differed by only
1.14x here rather than the 2.5x the change was designed for.


## 0.5.0 — 2026-08-03

`bandwidth-curve` and `kbb -M:curve` — measure the whole curve, not one
point.

`bandwidth-bytes-per-ns` measures a single line-strided figure. That number was
handed to two planners this afternoon that needed a different one, and both
were wrong as a result. `machine.core` 0.3.0 carries a curve; this produces it
in the shape the descriptor takes, validates the result, and prints it ready to
paste.

Measured here (JVM, 256 MiB working set): 6.2 GB/s at a 128-byte stride, 23.8
at 2 KiB, 10.2 at 32 KiB — a 3.9x spread.

Against the same curve measured from C: 24.1 at 128 bytes, 34.3 at 1 KiB, 11.5
at 16 KiB. Four times apart at the short-stride end, under 10% apart at the
page size, and peaking at a different stride. **A curve describes a runtime on
a machine, not a machine**, which is why `:runtime` is now required.


## 0.4.0 — 2026-08-03

`machine.bench/sum-*-unrolled` and `kbb -M:unrolled` — get the loop out of
the memory system's way.

Three experiments had failed because the per-element loop cost dwarfed the
per-element memory cost. The cause was not the machine: a serial summation
loop runs at floating-point add *latency*, because every add waits on the
previous one. Four independent accumulators break the chain.

| | ns/element | AoS/SoA ratio |
|---|---|---|
| serial | 2.87 | 2.12x |
| unrolled x4 | 0.87 | **6.63x** |

At n=8e6 the unrolled ratio reaches 20.2x, above the byte model's 16x, because
a 1 GiB array exhausts TLB reach.

**Still not enough.** SoA remains loop-bound at 0.87 ns/element against a
0.36 ns memory cost, so `both-memory-bound?` is false at the sizes where the
measurement is stable. Reaching it needs roughly one cycle per element, which
means SIMD the JVM will not reliably emit — the next lever is a cheaper
runtime, not a cheaper loop.

Every gate here still refuses on `:too-noisy`: these arrays are 256 MiB to
1 GiB and page-fault variance dominates. The loop speedup is reproducible
across runs; the sealed claim is not yet.


## 0.3.0 — 2026-08-03

`machine.bench/run-tiling` and `kbb -M:tiling` — is `traversal/tile-plan`'s
tile the fast one?

Unanswerable here, and the CLI now says so before spending twenty minutes
finding out. A pilot goes through `perfgate/detectable?` first: on this machine
it reports a **133% minimum detectable improvement**, so a 10% tiling effect
cannot pass whatever the sweep does. The sweep then confirms it — every tile
from 8 to 768 lands within 1.2x of every other, and two runs of the same sweep
named different winners (384, then 48).

The cause is the loop-bound harness again. `traversal` records the finding as
`:model/validation {:status :unvalidated}` — not `:wrong`, because nothing here
shows the capacity rule is wrong; it shows this machine plus this harness
cannot tell.


## 0.2.0 — 2026-08-03

`machine.bench/run-scaling` and `kbb -M:scaling` — does contention widen
the layout gap?

The answer is that this harness cannot say. Three consecutive runs put the
1-thread to 8-thread change at +3%, +31% and -22%, and every point was refused
by `perfgate` as `:too-noisy`. On a heterogeneous CPU the scheduler moves
threads between performance and efficiency cores mid-run, and nothing here
pins them.

**The first version of the CLI printed a SUPPORTED / NOT-SUPPORTED verdict
straight off the means**, which is how two runs of refused data produced
opposite conclusions. That is precisely the failure `perfgate` exists to
prevent, committed by the tool that consumes `perfgate`. The verdict is now
gated on the points: any point that does not qualify makes the trend
INCONCLUSIVE, and the percentage is printed with an explicit instruction not
to read it as a result.

What *was* stable across all three runs, and is worth more than the trend:
SoA peaks near 6 GB/s while AoS reaches 35-42 GB/s. SoA is bound by the
per-element loop, not by memory — which is the observation that produced
`layout/achievable-ratio` in layout 0.3.0.


## 0.1.0 — 2026-08-03

The effect half of the `machine` contract, which declares
`:must-not [:probe-hardware]` precisely so this could exist separately.

- `machine.probe` — Darwin `sysctl` and Linux `/sys/devices/system/cpu`
  parsers. Pure, with the effect injected, so every parser is testable against
  captured output on machines nobody has in the room.
- `machine.bench` — the measurement half: AoS vs SoA as real `double-array`s,
  warmup then raw samples, no verdict of its own.
- `kbb -M:probe --summary` and `kbb -M:bench [n] [width] [warmup] [reps]`.

First run on an Apple M1 Max forced two changes upstream in `machine` (0.2.0):
optional `:ways`, because macOS does not report associativity at all, and
heterogeneous CPU clusters, because one flat `:cache` cannot describe 8
performance cores beside 2 efficiency ones.

10 tests, 35 assertions.
