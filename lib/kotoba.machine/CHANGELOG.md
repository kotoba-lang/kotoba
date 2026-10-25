# Changelog

## 0.3.0 — 2026-08-03

`:bandwidth` section and `bandwidth-at-stride`.

Bandwidth is a property of the machine AND the access pattern. The same part
measured here gives 24 GB/s to a line-strided walk, 34 at a 1 KiB stride and
11.5 at the 16 KiB page size where the TLB gives out — a 3x spread.

Documenting "pass the constant that matches your stride" did not stop the wrong
end being used **twice** in one afternoon, once making a model predict a 1.00x
speedup where measurement gave 2.69x. So the curve now lives in the descriptor
and a planner reads it by stride instead of being handed a number.

Same contract as every other fact here: the curve carries a `:source`, an
empty one is refused, and a machine without a measured curve answers `nil` so
the caller has to ask out loud rather than default. Between measured points it
takes the nearer-lower stride and it does not extrapolate past the last one.

A curve is specific to the RUNTIME that measured it, not only to the machine:
a C loop and a JVM loop on the same part disagree by 4x at a 128-byte stride
and by under 10% at 16 KiB, differing in shape as well as scale. `:runtime` is
required for that reason.

25 tests, 81 assertions.


## 0.2.0 — 2026-08-03

First contact with a real device (an Apple M1 Max, via the new
`kotoba-lang/machine-probe`) broke two assumptions this contract shipped with
that morning.

- **`:ways` is now optional.** macOS exposes cache sizes, line width, page
  size and cluster topology through `sysctl` and does not expose associativity
  at all. A contract demanding a fact the platform will not give leaves a probe
  choosing between fabricating a plausible 8 and refusing to describe the
  machine. Both are worse than recording that it is unknown. A declared but
  nonsensical `:ways` is still an error, and the geometry check still runs when
  it is present.
- **Heterogeneous CPUs are modelled.** `:cpu :clusters` carries per-cluster
  cores and caches, because P+E is the normal case now (Apple silicon, Intel
  hybrid, ARM DynamIQ) and one flat `:cache` cannot describe an 8-core cluster
  with a 12 MiB L2 shared by four alongside a 2-core cluster with 4 MiB shared
  by two.
  - Capacity questions (`cache-at`, `private-cache-bytes`) **throw** on a
    heterogeneous machine rather than silently answering for one half.
    `for-cluster` returns an ordinary flat descriptor every existing planner
    takes unchanged — naming the cluster is the whole cost.
  - `line-bytes` still answers, because a maximum does have a single answer.
  - Declaring both a flat `:cache` and `:clusters` is refused: a planner would
    read the flat one and mis-plan for the other half.

21 tests, 67 assertions.


## 0.1.0 — 2026-08-03

Initial extraction. T5 (mechanism) had no contract: the numbers that describe
hardware — cache line width, page size, private cache capacity, NUMA distance,
SIMD width, GPU subgroup, device queue depth — lived nowhere, so every planner
that needed them would have hardcoded its own.

- `machine.core` — closed, validated descriptor (`:kotoba.machine/v1`).
- Provenance (`:measured` / `:vendor-declared` / `:assumed`) is part of the
  descriptor, and `measured` refuses an empty source.
- Absent facts answer `nil`; `require-fact` throws with the path it wanted.
- Geometry checks that catch transcription errors, not just type errors
  (cache capacity must equal ways × line × sets and must increase by level;
  NUMA self-distance must be minimal; huge pages must exceed the base page).
- `fingerprint`: deterministic 31-bit, JVM/JS-exact, explicitly not
  cryptographic — it exists for staleness detection in `perfgate`.
- Profiles: `portable-64` (conservative floor, `:assumed`) and `unknown`
  (valid but factless). No product-specific profile is shipped, because
  hardcoding numbers nobody here measured is the fossil this repo prevents.
