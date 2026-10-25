# kotoba-lang/yield

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-yield`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Yield & Reliability: Monte Carlo simulation, PVT corner analysis, and
aging/degradation estimation.

| Namespace | Restored from | Purpose |
|---|---|---|
| `yield.monte-carlo` | `monte_carlo` | Monte Carlo simulation engine (Gaussian/Uniform/LogNormal parameter distributions) |
| `yield.corner` | `corner` | PVT (Process-Voltage-Temperature) corner analysis (5 standard corners) |
| `yield.aging` | `aging` | Aging/degradation estimation (NBTI/PBTI/HCI/TDDB/EM, Arrhenius-based models) |

## Status

Restored — all 3 modules ported from the original 420-line Rust source
(`lib.rs` + `monte_carlo.rs` + `corner.rs` + `aging.rs`), with all 6
original Rust unit tests mirrored 1:1 in `test/yield_test.cljk` (+1 smoke
test) — 7 tests / 9 assertions, 0 failures. Pure data + pure functions
throughout; no IO/GPU.

`yield.monte-carlo`'s deterministic LCG PRNG uses u64-wraparound
arithmetic (JVM `unchecked-multiply`/`unchecked-add` on `long` — same
2's-complement bit pattern as Rust's `wrapping_mul`/`wrapping_add`;
unsigned interpretation via `unsigned-bit-shift-right`).

## Develop

```bash
kbb -M:test
```
