(ns yield
  "KAMI Yield & Reliability — Monte Carlo simulation, PVT corner analysis,
  and aging/degradation estimation. Restored from the legacy kami-engine/
  kami-yield Rust crate (deleted in kotoba-lang/kami-engine PR #82
  'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  One namespace per original Rust module:
    yield.monte-carlo — Monte Carlo simulation engine (Gaussian/Uniform/
                        LogNormal parameter distributions)
    yield.corner      — PVT (Process-Voltage-Temperature) corner analysis
    yield.aging       — aging/degradation estimation (NBTI/PBTI/HCI/TDDB/EM)

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.
  `yield.monte-carlo`'s deterministic LCG PRNG uses u64-wraparound
  arithmetic (JVM `unchecked-*` ops on `long`, same bit pattern as Rust's
  `wrapping_mul`/`wrapping_add`).")
