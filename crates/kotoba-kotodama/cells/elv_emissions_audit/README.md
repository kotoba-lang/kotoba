# elv_emissions_audit — hodoki cross-cutting (R0 scaffold)

Cross-cutting per-vehicle F-gas leakage + ASR mass/composition + PGM yield audit.
Per ADR-2605261215 §6 cross-cutting. R0 scaffold — `.solve()` raises until R1.

- **Murakumo node**: levi
- **Output**: per-vehicle compliance log (G6 + G13 + G14 verdicts)
- **Constraints**: G6 F-gas ≥95% recovery; G13 ASR <5% of input mass; G14 PGM yield ≥95%
