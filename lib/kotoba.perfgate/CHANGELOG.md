# Changelog

## 0.2.0 — 2026-08-03

Power analysis: `minimum-detectable-improvement`, `detectable?`,
`samples-needed`.

Everything in 0.1.0 judges a result after it exists, which is one turn too
late for a common and expensive mistake — running an experiment whose effect
is smaller than its own noise, then reading the sign off the means anyway.
Two real cases in one afternoon: a thread-scaling sweep whose three
consecutive runs gave +3%, +31% and -22%, and a matmul tiling sweep whose best
blocking bought 5% against a noise floor above it.

The arithmetic is the separation rule run backwards. Qualifying needs
`mean_b - mean_c > sd_b + sd_c`, so the smallest improvement the gate could
ever pass is `(sd_b + sd_c) / mean_b`. Run a pilot, call `detectable?`, and
learn before committing to the long run.

`samples-needed` says out loud that more sampling is the wrong answer when the
spread comes from a scheduler migrating threads between core types rather than
from ordinary jitter.

21 tests, 66 assertions.


## 0.1.0 — 2026-08-03

Initial implementation.

- `observation` — one measured arm, refusing an empty source or a machine
  descriptor that does not validate.
- `qualify` — seven named refusals, including `:not-separated-from-noise`
  (a 6% improvement whose arms overlap within their own spread) and
  `:provenance-too-weak` (a claim resting on `machine.core/portable-64`).
- `claim` / `verify-claim` — an unqualified result gets no artifact at all;
  a sealed one detects edits to either a sample or the headline number.
- `stale-on?` / `applicable` — a claim records the fingerprint of the machine
  it was proved on, so a system can carry its own list of retired
  optimizations instead of accumulating fossils.
- Statistics are mean / sample stdev / median / p95, and the separation test
  is documented as a heuristic rather than a significance test.

18 tests, 54 assertions.
